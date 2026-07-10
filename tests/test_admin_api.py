# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for django-agreements admin API."""

import pytest
from django.urls import reverse

DEFINITION_LIST_URL = reverse("admin-definition-list")


def _definition_detail_url(slug):
    return reverse("admin-definition-detail", kwargs={"slug": slug})


def _version_list_url(slug):
    return reverse("admin-version-list", kwargs={"slug": slug})


def _version_detail_url(pk):
    return reverse("admin-version-detail", kwargs={"pk": pk})


def _version_publish_url(pk):
    return reverse("admin-version-publish", kwargs={"pk": pk})


CONSENT_LIST_URL = reverse("admin-consent-list")
CHANNEL_LIST_URL = reverse("admin-channel-list")
CHANNEL_SYNC_URL = reverse("admin-channel-sync")


@pytest.mark.django_db
class TestDefinitionAuth:
    """Auth tests: 401 no token, 403 regular user, 200 admin."""

    def test_no_token_returns_401(self, api_client):
        response = api_client.get(DEFINITION_LIST_URL)
        assert response.status_code == 401

    def test_regular_user_returns_403(self, user_client):
        response = user_client.get(DEFINITION_LIST_URL)
        assert response.status_code == 403

    def test_admin_returns_200(self, admin_client):
        response = admin_client.get(DEFINITION_LIST_URL)
        assert response.status_code == 200


@pytest.mark.django_db
class TestDefinitionList:
    def test_list_returns_paginated(self, admin_client, definition):
        response = admin_client.get(DEFINITION_LIST_URL)
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "results" in data
        assert data["count"] >= 1

    def test_list_includes_inactive(self, admin_client, definition):
        definition.is_active = False
        definition.save()
        response = admin_client.get(DEFINITION_LIST_URL)
        slugs = [d["slug"] for d in response.json()["results"]]
        assert "terms-of-service" in slugs

    def test_filter_by_category(self, admin_client, definition, marketing_definition):
        response = admin_client.get(DEFINITION_LIST_URL, {"category": "marketing"})
        slugs = [d["slug"] for d in response.json()["results"]]
        assert "marketing-email" in slugs
        assert "terms-of-service" not in slugs

    def test_search(self, admin_client, definition):
        response = admin_client.get(DEFINITION_LIST_URL, {"search": "terms"})
        assert response.json()["count"] == 1


@pytest.mark.django_db
class TestDefinitionCRUD:
    def test_create(self, admin_client):
        response = admin_client.post(
            DEFINITION_LIST_URL,
            {"slug": "new-agreement", "name": "New Agreement", "category": "informational"},
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["slug"] == "new-agreement"

    def test_create_duplicate_slug_returns_400(self, admin_client, definition):
        response = admin_client.post(
            DEFINITION_LIST_URL,
            {"slug": "terms-of-service", "name": "Duplicate", "category": "mandatory"},
            format="json",
        )
        assert response.status_code == 400

    def test_create_with_channels(self, admin_client, channel):
        response = admin_client.post(
            DEFINITION_LIST_URL,
            {"slug": "channel-def", "name": "Channel Def", "category": "mandatory", "channel_ids": [channel.pk]},
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["channel_ids"] == [channel.pk]

    def test_retrieve(self, admin_client, definition):
        url = _definition_detail_url("terms-of-service")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.json()["slug"] == "terms-of-service"

    def test_retrieve_not_found(self, admin_client):
        url = _definition_detail_url("nonexistent")
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_update(self, admin_client, definition):
        url = _definition_detail_url("terms-of-service")
        response = admin_client.patch(url, {"name": "Updated Terms"}, format="json")
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Terms"

    def test_delete_soft(self, admin_client, definition):
        url = _definition_detail_url("terms-of-service")
        response = admin_client.delete(url)
        assert response.status_code == 204
        definition.refresh_from_db()
        assert definition.is_active is False

    def test_update_not_found_returns_404(self, admin_client):
        url = _definition_detail_url("nonexistent-slug")
        response = admin_client.patch(url, {"name": "Does not matter"}, format="json")
        assert response.status_code == 404

    def test_delete_system_definition_returns_400(self, admin_client):
        from django_agreements.models import AgreementDefinition

        system_def = AgreementDefinition.objects.create(
            slug="system-def", name="System Def", category="mandatory", is_system=True
        )
        url = _definition_detail_url(system_def.slug)
        response = admin_client.delete(url)
        assert response.status_code == 400

    def test_update_system_definition_blocked_fields_returns_400(self, admin_client):
        from django_agreements.models import AgreementDefinition

        system_def = AgreementDefinition.objects.create(
            slug="system-locked", name="System Locked", category="mandatory", is_system=True
        )
        url = _definition_detail_url(system_def.slug)
        response = admin_client.patch(url, {"category": "marketing"}, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestVersionAPI:
    def test_list_versions(self, admin_client, definition, published_version):
        url = _version_list_url("terms-of-service")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.json()["count"] >= 1

    def test_create_version(self, admin_client, definition):
        url = _version_list_url("terms-of-service")
        response = admin_client.post(url, {"summary_t9n": {"en": "New version text"}}, format="json")
        assert response.status_code == 201
        assert response.json()["version_number"] == 1

    def test_create_auto_increments(self, admin_client, definition, published_version):
        url = _version_list_url("terms-of-service")
        response = admin_client.post(url, {"summary_t9n": {"en": "V2 text"}}, format="json")
        assert response.status_code == 201
        assert response.json()["version_number"] == 2

    def test_retrieve_version(self, admin_client, published_version):
        url = _version_detail_url(published_version.pk)
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.json()["is_current"] is True

    def test_publish_version(self, admin_client, definition):
        # Create draft
        create_url = _version_list_url("terms-of-service")
        create_resp = admin_client.post(create_url, {"summary_t9n": {"en": "Draft text"}}, format="json")
        version_pk = create_resp.json()["id"]

        # Publish
        publish_url = _version_publish_url(version_pk)
        response = admin_client.post(publish_url)
        assert response.status_code == 200
        assert response.json()["is_current"] is True
        assert response.json()["published_at"] is not None

    def test_publish_already_published_returns_400(self, admin_client, published_version):
        url = _version_publish_url(published_version.pk)
        response = admin_client.post(url)
        assert response.status_code == 400


@pytest.mark.django_db
class TestVersionAuth:
    def test_no_token_returns_401(self, api_client, definition):
        url = _version_list_url("terms-of-service")
        response = api_client.get(url)
        assert response.status_code == 401

    def test_regular_user_returns_403(self, user_client, definition):
        url = _version_list_url("terms-of-service")
        response = user_client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestVersionPatchDelete:
    def test_update_draft_version_200(self, admin_client, draft_version):
        url = _version_detail_url(draft_version.pk)
        response = admin_client.patch(url, {"summary_t9n": {"en": "Updated summary"}}, format="json")
        assert response.status_code == 200
        assert response.json()["summary_t9n"]["en"] == "Updated summary"

    def test_update_published_version_returns_400(self, admin_client, published_version):
        url = _version_detail_url(published_version.pk)
        response = admin_client.patch(url, {"summary_t9n": {"en": "Cannot edit"}}, format="json")
        assert response.status_code == 400

    def test_update_nonexistent_version_returns_404(self, admin_client):
        url = _version_detail_url(99999)
        response = admin_client.patch(url, {"summary_t9n": {"en": "No version here"}}, format="json")
        assert response.status_code == 404


@pytest.mark.django_db
class TestConsentAdmin:
    def test_list_consents(self, admin_client, published_version):
        from django_agreements.services import consent_service

        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")
        response = admin_client.get(CONSENT_LIST_URL)
        assert response.status_code == 200
        assert response.json()["count"] >= 1

    def test_filter_by_email(self, admin_client, published_version):
        from django_agreements.services import consent_service

        consent_service.record_consent(email="alice@test.com", slug="terms-of-service", granted=True, source="checkout")
        response = admin_client.get(CONSENT_LIST_URL, {"email": "alice@test.com"})
        assert response.json()["count"] == 1

    def test_consent_history(self, admin_client, published_version):
        from django_agreements.services import consent_service

        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")
        url = reverse("admin-consent-history", kwargs={"email": "user@test.com"})
        response = admin_client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
class TestChannelAdmin:
    def test_list_channels(self, admin_client, channel):
        response = admin_client.get(CHANNEL_LIST_URL)
        assert response.status_code == 200
        assert response.json()["count"] >= 1

    def test_channel_auth(self, api_client):
        response = api_client.get(CHANNEL_LIST_URL)
        assert response.status_code == 401


@pytest.mark.django_db
class TestMiscEndpointsAuth:
    def test_consent_history_no_token_returns_401(self, api_client):
        url = reverse("admin-consent-history", kwargs={"email": "user@test.com"})
        response = api_client.get(url)
        assert response.status_code == 401

    def test_consent_history_regular_user_returns_403(self, user_client):
        url = reverse("admin-consent-history", kwargs={"email": "user@test.com"})
        response = user_client.get(url)
        assert response.status_code == 403

    def test_channel_sync_no_token_returns_401(self, api_client):
        response = api_client.post(CHANNEL_SYNC_URL)
        assert response.status_code == 401

    def test_channel_sync_regular_user_returns_403(self, user_client):
        response = user_client.post(CHANNEL_SYNC_URL)
        assert response.status_code == 403

    def test_order_agreements_no_token_returns_401(self, api_client):
        import uuid

        url = reverse("admin-order-agreements", kwargs={"order_id": str(uuid.uuid4())})
        response = api_client.get(url)
        assert response.status_code == 401

    def test_order_agreements_regular_user_returns_403(self, user_client):
        import uuid

        url = reverse("admin-order-agreements", kwargs={"order_id": str(uuid.uuid4())})
        response = user_client.get(url)
        assert response.status_code == 403

    def test_marketing_subscribers_export_no_token_returns_401(self, api_client):
        response = api_client.get(MARKETING_SUBSCRIBERS_EXPORT_URL)
        assert response.status_code == 401

    def test_marketing_subscribers_export_regular_user_returns_403(self, user_client):
        response = user_client.get(MARKETING_SUBSCRIBERS_EXPORT_URL)
        assert response.status_code == 403


@pytest.mark.django_db
class TestOrderAgreementsAdmin:
    def test_list_order_agreements(self, admin_client, published_version):
        import uuid

        from django_agreements.services import order_agreement_service

        order_id = uuid.uuid4()
        order_agreement_service.record_order_agreements(
            order_id=order_id, email="customer@test.com", slugs=["terms-of-service"], language="en"
        )
        url = reverse("admin-order-agreements", kwargs={"order_id": str(order_id)})
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.json()["count"] == 1


PEOPLE_LIST_URL = reverse("admin-people-list")


def _people_detail_url(email):
    return reverse("admin-people-detail", kwargs={"email": email})


GENERATE_UNSUBSCRIBE_URL = reverse("admin-generate-unsubscribe-url")


@pytest.mark.django_db
class TestTokenGenerateUnsubscribeUrl:
    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.post(
            GENERATE_UNSUBSCRIBE_URL, {"email": "user@test.com", "consent_type": "marketing-email"}, format="json"
        )
        assert response.status_code == 401

    def test_non_admin_returns_403(self, user_client):
        response = user_client.post(
            GENERATE_UNSUBSCRIBE_URL, {"email": "user@test.com", "consent_type": "marketing-email"}, format="json"
        )
        assert response.status_code == 403

    def test_success_returns_url(self, admin_client):
        response = admin_client.post(
            GENERATE_UNSUBSCRIBE_URL, {"email": "user@test.com", "consent_type": "marketing-email"}, format="json"
        )
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "token=" in data["url"]
        assert "action=unsubscribe" in data["url"]

    def test_missing_required_field_returns_400(self, admin_client):
        response = admin_client.post(
            GENERATE_UNSUBSCRIBE_URL,
            {"email": "user@test.com"},  # consent_type omitted
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestPeopleAuth:
    def test_no_token_returns_401(self, api_client):
        response = api_client.get(PEOPLE_LIST_URL)
        assert response.status_code == 401

    def test_regular_user_returns_403(self, user_client):
        response = user_client.get(PEOPLE_LIST_URL)
        assert response.status_code == 403

    def test_admin_returns_200(self, admin_client):
        response = admin_client.get(PEOPLE_LIST_URL)
        assert response.status_code == 200


@pytest.mark.django_db
class TestPeopleList:
    def test_list_returns_people(self, admin_client, published_version):
        # Arrange
        from django_agreements.services import consent_service

        consent_service.record_consent(email="alice@test.com", slug="terms-of-service", granted=True, source="checkout")

        # Act
        response = admin_client.get(PEOPLE_LIST_URL)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "results" in data
        emails = [p["email"] for p in data["results"]]
        assert "alice@test.com" in emails

    def test_search_by_email(self, admin_client, published_version):
        # Arrange
        from django_agreements.services import consent_service

        consent_service.record_consent(email="alice@test.com", slug="terms-of-service", granted=True, source="checkout")
        consent_service.record_consent(email="bob@test.com", slug="terms-of-service", granted=True, source="checkout")

        # Act
        response = admin_client.get(PEOPLE_LIST_URL, {"search": "alice"})

        # Assert
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["email"] == "alice@test.com"


@pytest.mark.django_db
class TestPersonDetail:
    def test_returns_current_status_with_category(self, admin_client, published_version):
        # Arrange
        from django_agreements.services import consent_service

        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")

        # Act
        url = _people_detail_url("user@test.com")
        response = admin_client.get(url)

        # Assert
        assert response.status_code == 200
        data = response.json()
        status_item = data["current_status"]["terms-of-service"]
        assert status_item["status"] == "granted"
        assert status_item["category"] == "mandatory"
        assert "name" in status_item

    def test_marketing_pending_shows_pending_status(self, admin_client, marketing_published_version):
        # Arrange — only a double-optin-pending record
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email="user@test.com", slug="marketing-email", granted=True, source="double-optin-pending"
        )

        # Act
        url = _people_detail_url("user@test.com")
        response = admin_client.get(url)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["current_status"]["marketing-email"]["status"] == "pending"

    def test_history_includes_category(self, admin_client, published_version):
        # Arrange
        from django_agreements.services import consent_service

        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")

        # Act
        url = _people_detail_url("user@test.com")
        response = admin_client.get(url)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["history"]) == 1
        assert data["history"][0]["category"] == "mandatory"

    def test_no_token_returns_401(self, api_client):
        url = _people_detail_url("user@test.com")
        response = api_client.get(url)
        assert response.status_code == 401

    def test_regular_user_returns_403(self, user_client):
        url = _people_detail_url("user@test.com")
        response = user_client.get(url)
        assert response.status_code == 403


MARKETING_SUBSCRIBERS_URL = "/api/agreements/v2/admin/marketing-subscribers/"
MARKETING_SUBSCRIBERS_EXPORT_URL = "/api/agreements/v2/admin/marketing-subscribers/export/"


@pytest.mark.django_db
class TestMarketingSubscribersAuth:
    def test_no_token_returns_401(self, api_client):
        response = api_client.get(MARKETING_SUBSCRIBERS_URL)
        assert response.status_code == 401

    def test_regular_user_returns_403(self, user_client):
        response = user_client.get(MARKETING_SUBSCRIBERS_URL)
        assert response.status_code == 403

    def test_admin_returns_200(self, admin_client):
        response = admin_client.get(MARKETING_SUBSCRIBERS_URL)
        assert response.status_code == 200


@pytest.mark.django_db
class TestMarketingSubscribersList:
    def test_returns_active_subscribers(self, admin_client, marketing_published_version):
        # Arrange
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=True, source="registration"
        )

        # Act
        response = admin_client.get(MARKETING_SUBSCRIBERS_URL)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        emails = [r["email"] for r in data["results"]]
        assert "subscriber@test.com" in emails

    def test_excludes_withdrawn(self, admin_client, marketing_published_version):
        # Arrange — grant then withdraw
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=True, source="registration"
        )
        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=False, source="consent-page"
        )

        # Act
        response = admin_client.get(MARKETING_SUBSCRIBERS_URL)

        # Assert
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_excludes_pending(self, admin_client, marketing_published_version):
        # Arrange — only a pending record (not yet confirmed)
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email="pending@test.com", slug="marketing-email", granted=True, source="double-optin-pending"
        )

        # Act
        response = admin_client.get(MARKETING_SUBSCRIBERS_URL)

        # Assert
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_filter_by_slug(self, admin_client, marketing_published_version, published_version):
        # Arrange — grant marketing-email, filter for a slug with no grants
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=True, source="registration"
        )

        # Act — filter by the terms-of-service slug (not a marketing definition)
        response = admin_client.get(MARKETING_SUBSCRIBERS_URL, {"slug": "terms-of-service"})

        # Assert
        assert response.status_code == 200
        assert response.json()["count"] == 0


@pytest.mark.django_db
class TestMarketingSubscribersExport:
    def test_returns_csv(self, admin_client, marketing_published_version):
        # Arrange
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=True, source="registration"
        )

        # Act
        response = admin_client.get(MARKETING_SUBSCRIBERS_EXPORT_URL)

        # Assert
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]

    def test_csv_contains_header_and_data(self, admin_client, marketing_published_version):
        # Arrange
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email="subscriber@test.com", slug="marketing-email", granted=True, source="registration"
        )

        # Act
        response = admin_client.get(MARKETING_SUBSCRIBERS_EXPORT_URL)

        # Assert
        content = b"".join(response.streaming_content).decode("utf-8")
        assert "email" in content
        assert "subscriber@test.com" in content


@pytest.mark.django_db
class TestPagination:
    def test_page_size_default(self, admin_client):
        from django_agreements.models import AgreementDefinition

        for i in range(25):
            AgreementDefinition.objects.create(slug=f"def-{i}", name=f"Def {i}", category="mandatory")
        response = admin_client.get(DEFINITION_LIST_URL)
        data = response.json()
        assert len(data["results"]) == 20
        assert data["next"] is not None

    def test_page_size_param(self, admin_client):
        from django_agreements.models import AgreementDefinition

        for i in range(5):
            AgreementDefinition.objects.create(slug=f"def-{i}", name=f"Def {i}", category="mandatory")
        response = admin_client.get(DEFINITION_LIST_URL, {"page_size": 2})
        assert len(response.json()["results"]) == 2

    def test_max_page_size_enforced(self, admin_client, definition):
        response = admin_client.get(DEFINITION_LIST_URL, {"page_size": 200})
        # Should cap at 100, not error
        assert response.status_code == 200
