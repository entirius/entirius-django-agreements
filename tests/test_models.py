# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for django-agreements models."""

import uuid

import pytest
from django.db import IntegrityError

from django_agreements.models import (
    AgreementDefinition,
    AgreementVersion,
    Channel,
    ConsentRecord,
    OrderAgreementSnapshot,
)


@pytest.mark.django_db
class TestChannel:
    def test_create_channel(self):
        ch = Channel.objects.create(idx="test-channel", name="Test")
        assert ch.idx == "test-channel"
        assert ch.name == "Test"
        assert ch.default_language is None

    def test_idx_unique(self):
        Channel.objects.create(idx="unique-ch")
        with pytest.raises(IntegrityError):
            Channel.objects.create(idx="unique-ch")

    def test_str(self):
        ch = Channel.objects.create(idx="my-channel")
        assert str(ch) == "my-channel"


@pytest.mark.django_db
class TestAgreementDefinition:
    def test_create_definition(self):
        defn = AgreementDefinition.objects.create(
            slug="terms", name="Terms of Service", category="mandatory", consent_channel="general"
        )
        assert defn.slug == "terms"
        assert defn.category == "mandatory"
        assert defn.is_active is True
        assert defn.sort_order == 0

    def test_slug_unique(self):
        AgreementDefinition.objects.create(slug="unique-slug", name="Test", category="mandatory")
        with pytest.raises(IntegrityError):
            AgreementDefinition.objects.create(slug="unique-slug", name="Test 2", category="marketing")

    def test_channels_m2m(self, channel, channel_2):
        defn = AgreementDefinition.objects.create(slug="test-m2m", name="Test", category="mandatory")
        defn.channels.set([channel, channel_2])
        assert defn.channels.count() == 2

    def test_empty_channels_means_global(self):
        defn = AgreementDefinition.objects.create(slug="global", name="Global", category="mandatory")
        assert defn.channels.count() == 0

    def test_str(self, definition):
        assert "Terms of Service" in str(definition)
        assert "terms-of-service" in str(definition)


@pytest.mark.django_db
class TestAgreementVersion:
    def test_create_version(self, definition):
        v = AgreementVersion.objects.create(definition=definition, version_number=1, summary_t9n={"en": "Accept terms"})
        assert v.version_number == 1
        assert v.published_at is None
        assert v.is_current is False

    def test_unique_version_number(self, definition):
        AgreementVersion.objects.create(definition=definition, version_number=1, summary_t9n={})
        with pytest.raises(IntegrityError):
            AgreementVersion.objects.create(definition=definition, version_number=1, summary_t9n={})

    def test_str_draft(self, definition):
        v = AgreementVersion.objects.create(definition=definition, version_number=1, summary_t9n={})
        assert "draft" in str(v)

    def test_str_published(self, published_version):
        assert "published" in str(published_version)


@pytest.mark.django_db
class TestConsentRecord:
    def test_create_record(self, published_version):
        record = ConsentRecord.objects.create(
            email="user@test.com", agreement_version=published_version, granted=True, source="checkout"
        )
        assert record.email == "user@test.com"
        assert record.granted is True
        assert record.created_at is not None

    def test_append_only_pattern(self, published_version):
        """Multiple records for same email — audit trail."""
        ConsentRecord.objects.create(
            email="user@test.com", agreement_version=published_version, granted=True, source="checkout"
        )
        ConsentRecord.objects.create(
            email="user@test.com", agreement_version=published_version, granted=False, source="consent-page"
        )
        records = ConsentRecord.objects.filter(email="user@test.com")
        assert records.count() == 2

    def test_str(self, published_version):
        record = ConsentRecord.objects.create(
            email="user@test.com", agreement_version=published_version, granted=True, source="checkout"
        )
        assert "granted" in str(record)


@pytest.mark.django_db
class TestOrderAgreementSnapshot:
    def test_create_snapshot(self, published_version):
        order_id = uuid.uuid4()
        snapshot = OrderAgreementSnapshot.objects.create(
            order_id=order_id,
            email="customer@test.com",
            agreement_version=published_version,
            body_snapshot="Full legal text here",
            language="en",
        )
        assert snapshot.order_id == order_id
        assert snapshot.body_snapshot == "Full legal text here"

    def test_unique_order_version(self, published_version):
        order_id = uuid.uuid4()
        OrderAgreementSnapshot.objects.create(
            order_id=order_id,
            email="customer@test.com",
            agreement_version=published_version,
            body_snapshot="Text",
            language="en",
        )
        with pytest.raises(IntegrityError):
            OrderAgreementSnapshot.objects.create(
                order_id=order_id,
                email="customer@test.com",
                agreement_version=published_version,
                body_snapshot="Text",
                language="en",
            )
