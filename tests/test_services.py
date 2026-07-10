# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for django-agreements services."""

import uuid

import pytest

from django_agreements.models import AgreementDefinition, ConsentRecord
from django_agreements.services import consent_service, definition_service, order_agreement_service, version_service


@pytest.mark.django_db
class TestDefinitionService:
    def test_list_definitions(self, definition):
        result = definition_service.list_definitions(include_inactive=True)
        assert result.count() >= 1

    def test_list_active_only(self, definition):
        AgreementDefinition.objects.create(slug="inactive", name="Inactive", category="marketing", is_active=False)
        result = definition_service.list_definitions(include_inactive=False)
        slugs = list(result.values_list("slug", flat=True))
        assert "inactive" not in slugs

    def test_filter_by_category(self, definition, marketing_definition):
        result = definition_service.list_definitions(include_inactive=True, category="marketing")
        slugs = list(result.values_list("slug", flat=True))
        assert "marketing-email" in slugs
        assert "terms-of-service" not in slugs

    def test_filter_by_channel(self, definition, channel):
        definition.channels.add(channel)
        AgreementDefinition.objects.create(slug="global-def", name="Global", category="mandatory")
        result = definition_service.list_definitions(include_inactive=True, channel_idx="default-europe")
        slugs = list(result.values_list("slug", flat=True))
        assert "terms-of-service" in slugs
        assert "global-def" in slugs  # empty channels = global

    def test_search(self, definition):
        result = definition_service.list_definitions(include_inactive=True, search="terms")
        assert result.count() == 1

    def test_create_definition(self):
        defn = definition_service.create_definition(
            slug="new-agreement", name="New Agreement", category="informational"
        )
        assert defn.slug == "new-agreement"
        assert defn.category == "informational"

    def test_create_with_channels(self, channel):
        defn = definition_service.create_definition(
            slug="channel-def", name="Channel Def", category="mandatory", channel_ids=[channel.pk]
        )
        assert defn.channels.count() == 1

    def test_update_definition(self, definition):
        defn = definition_service.update_definition(slug="terms-of-service", name="Updated Terms")
        assert defn.name == "Updated Terms"

    def test_update_channels(self, definition, channel):
        definition_service.update_definition(slug="terms-of-service", channel_ids=[channel.pk])
        definition.refresh_from_db()
        assert definition.channels.count() == 1

        # Clear channels
        definition_service.update_definition(slug="terms-of-service", channel_ids=[])
        definition.refresh_from_db()
        assert definition.channels.count() == 0

    def test_delete_definition_soft(self, definition):
        definition_service.delete_definition(slug="terms-of-service")
        definition.refresh_from_db()
        assert definition.is_active is False

    def test_get_definition(self, definition):
        result = definition_service.get_definition(slug="terms-of-service")
        assert result.pk == definition.pk


@pytest.mark.django_db
class TestVersionService:
    def test_create_version_auto_increment(self, definition):
        v1 = version_service.create_version(definition_slug="terms-of-service", summary_t9n={"en": "V1 text"})
        assert v1.version_number == 1

        v2 = version_service.create_version(definition_slug="terms-of-service", summary_t9n={"en": "V2 text"})
        assert v2.version_number == 2

    def test_publish_version(self, definition):
        v = version_service.create_version(definition_slug="terms-of-service", summary_t9n={"en": "Text"})
        published = version_service.publish_version(pk=v.pk)
        assert published.published_at is not None
        assert published.is_current is True

    def test_publish_replaces_current(self, definition):
        v1 = version_service.create_version(definition_slug="terms-of-service", summary_t9n={"en": "V1"})
        version_service.publish_version(pk=v1.pk)

        v2 = version_service.create_version(definition_slug="terms-of-service", summary_t9n={"en": "V2"})
        version_service.publish_version(pk=v2.pk)

        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.is_current is False
        assert v2.is_current is True

    def test_publish_already_published_raises(self, published_version):
        with pytest.raises(ValueError, match="already published"):
            version_service.publish_version(pk=published_version.pk)

    def test_list_versions(self, definition, published_version, draft_version):
        result = version_service.list_versions(definition_slug="terms-of-service")
        assert result.count() == 2

    def test_get_current_version(self, definition, published_version):
        result = version_service.get_current_version(definition=definition)
        assert result.pk == published_version.pk

    def test_resolve_summary_exact_language(self, published_version):
        text = version_service.resolve_summary(published_version, "en")
        assert text == "I accept the Terms of Service"

    def test_resolve_summary_fallback(self, published_version):
        text = version_service.resolve_summary(published_version, "de", "en")
        assert text == "I accept the Terms of Service"

    def test_resolve_summary_first_available(self, published_version):
        text = version_service.resolve_summary(published_version, "de", "fr")
        assert text == "I accept the Terms of Service"


@pytest.mark.django_db
class TestConsentService:
    def test_record_consent(self, published_version):
        record = consent_service.record_consent(
            email="user@test.com",
            slug="terms-of-service",
            granted=True,
            source="checkout",
            channel_idx="default-europe",
        )
        assert record.email == "user@test.com"
        assert record.granted is True
        assert record.channel_idx == "default-europe"

    def test_record_consent_no_published_version_raises(self, definition):
        with pytest.raises(ValueError, match="No published version"):
            consent_service.record_consent(
                email="user@test.com", slug="terms-of-service", granted=True, source="checkout"
            )

    def test_record_multiple_consents(self, published_version, marketing_published_version):
        records = consent_service.record_multiple_consents(
            email="user@test.com",
            agreements=[{"slug": "terms-of-service", "granted": True}, {"slug": "marketing-email", "granted": False}],
            source="checkout",
        )
        assert len(records) == 2

    def test_is_consented(self, published_version):
        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")
        assert consent_service.is_consented("user@test.com", "terms-of-service") is True

    def test_is_consented_latest_wins(self, published_version):
        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")
        consent_service.record_consent(
            email="user@test.com", slug="terms-of-service", granted=False, source="consent-page"
        )
        assert consent_service.is_consented("user@test.com", "terms-of-service") is False

    def test_get_consent_status(self, published_version, marketing_published_version):
        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")
        status = consent_service.get_consent_status("user@test.com")
        assert status["terms-of-service"] is True
        assert status["marketing-email"] is False

    def test_list_consent_records_filter_email(self, published_version):
        consent_service.record_consent(email="alice@test.com", slug="terms-of-service", granted=True, source="checkout")
        consent_service.record_consent(email="bob@test.com", slug="terms-of-service", granted=True, source="checkout")
        result = consent_service.list_consent_records(email="alice@test.com")
        assert result.count() == 1

    def test_get_consent_history(self, published_version):
        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")
        consent_service.record_consent(
            email="user@test.com", slug="terms-of-service", granted=False, source="consent-page"
        )
        history = consent_service.get_consent_history("user@test.com")
        assert history.count() == 2


@pytest.mark.django_db
class TestGetPersonDetail:
    def test_returns_status_with_category_and_name(self, published_version):
        # Arrange
        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")

        # Act
        detail = consent_service.get_person_detail("user@test.com")

        # Assert
        status_item = detail["current_status"]["terms-of-service"]
        assert "status" in status_item
        assert "category" in status_item
        assert "name" in status_item
        assert status_item["status"] == "granted"
        assert status_item["category"] == "mandatory"
        assert status_item["name"] == "Terms of Service"

    def test_pending_status_for_double_optin(self, published_version):
        # Arrange — only a pending record exists (no confirmed record)
        consent_service.record_consent(
            email="user@test.com", slug="terms-of-service", granted=True, source="double-optin-pending"
        )

        # Act
        detail = consent_service.get_person_detail("user@test.com")

        # Assert — is_consented excludes pending, so granted=False; pending_slugs has it
        assert detail["current_status"]["terms-of-service"]["status"] == "pending"

    def test_history_includes_category_via_consent_record(self, published_version):
        # Arrange
        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")

        # Act
        detail = consent_service.get_person_detail("user@test.com")

        # Assert — history is a QuerySet of ConsentRecord with definition accessible
        first = detail["history"].first()
        assert first.agreement_version.definition.category == "mandatory"

    def test_withdrawn_status_after_withdrawal(self, published_version):
        # Arrange
        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")
        consent_service.record_consent(
            email="user@test.com", slug="terms-of-service", granted=False, source="consent-page"
        )

        # Act
        detail = consent_service.get_person_detail("user@test.com")

        # Assert
        assert detail["current_status"]["terms-of-service"]["status"] == "withdrawn"


@pytest.mark.django_db
class TestListActiveMarketingSubscribers:
    def test_returns_granted_marketing_subscribers(self, marketing_published_version):
        # Arrange
        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=True, source="registration"
        )

        # Act
        result = consent_service.list_active_marketing_subscribers()

        # Assert
        emails = list(result.values_list("email", flat=True))
        assert "subscriber@test.com" in emails

    def test_excludes_withdrawn(self, marketing_published_version):
        # Arrange — grant then withdraw
        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=True, source="registration"
        )
        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=False, source="consent-page"
        )

        # Act
        result = consent_service.list_active_marketing_subscribers()

        # Assert
        assert result.count() == 0

    def test_excludes_pending_only(self, marketing_published_version):
        # Arrange — only a double-optin-pending record (not yet confirmed)
        consent_service.record_consent(
            email="pending@test.com", slug="marketing-email", granted=True, source="double-optin-pending"
        )

        # Act
        result = consent_service.list_active_marketing_subscribers()

        # Assert — pending records are excluded
        assert result.count() == 0

    def test_filter_by_slug(self, marketing_published_version, published_version):
        # Arrange — grant marketing-email, filter by a different slug
        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=True, source="registration"
        )

        # Act — filter for terms-of-service (not a marketing definition)
        result = consent_service.list_active_marketing_subscribers(slug="terms-of-service")

        # Assert — terms-of-service is not a marketing category, returns empty
        assert result.count() == 0

    def test_filter_by_marketing_slug_returns_matching(self, marketing_published_version):
        # Arrange
        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=True, source="registration"
        )

        # Act
        result = consent_service.list_active_marketing_subscribers(slug="marketing-email")

        # Assert
        assert result.count() == 1
        assert result.first().email == "subscriber@test.com"


@pytest.mark.django_db
class TestOrderAgreementService:
    def test_record_order_agreements(self, published_version):
        order_id = uuid.uuid4()
        snapshots = order_agreement_service.record_order_agreements(
            order_id=order_id,
            email="customer@test.com",
            slugs=["terms-of-service"],
            language="en",
            channel_idx="default-europe",
        )
        assert len(snapshots) == 1
        assert snapshots[0].body_snapshot  # Has text

        # Also creates ConsentRecord
        records = ConsentRecord.objects.filter(email="customer@test.com", source="checkout")
        assert records.count() == 1

    def test_get_order_agreements(self, published_version):
        order_id = uuid.uuid4()
        order_agreement_service.record_order_agreements(
            order_id=order_id, email="customer@test.com", slugs=["terms-of-service"], language="en"
        )
        result = order_agreement_service.get_order_agreements(order_id=order_id)
        assert result.count() == 1
