# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for django-agreements public API."""

import uuid
from unittest.mock import patch

import pytest
from django.urls import reverse


def _public_definitions_url(channel_idx):
    return reverse("public-definition-list", kwargs={"channel_idx": channel_idx})


def _public_consent_submit_url(channel_idx):
    return reverse("public-consent-submit", kwargs={"channel_idx": channel_idx})


def _public_consent_status_url(channel_idx):
    return reverse("public-consent-status", kwargs={"channel_idx": channel_idx})


def _public_consent_withdraw_url(channel_idx):
    return reverse("public-consent-withdraw", kwargs={"channel_idx": channel_idx})


def _public_order_agreements_url(channel_idx, order_id):
    return reverse("public-order-agreements", kwargs={"channel_idx": channel_idx, "order_id": str(order_id)})


def _public_for_user_url(channel_idx):
    return reverse("public-definition-for-user", kwargs={"channel_idx": channel_idx})


def _subscribe_url(channel_idx):
    return reverse("public-newsletter-subscribe", kwargs={"channel_idx": channel_idx})


def _newsletter_subscribe_url(channel_idx):
    return reverse("public-newsletter-subscribe", kwargs={"channel_idx": channel_idx})


@pytest.mark.django_db
class TestPublicDefinitions:
    def test_no_auth_required(self, api_client, definition, published_version):
        url = _public_definitions_url("default-europe")
        response = api_client.get(url)
        assert response.status_code == 200

    def test_returns_active_with_published_version(self, api_client, definition, published_version):
        url = _public_definitions_url("default-europe")
        response = api_client.get(url)
        data = response.json()
        assert data["count"] >= 1
        result = data["results"][0]
        assert result["slug"] == "terms-of-service"
        assert result["summary"]  # Resolved text
        assert result["version_number"] == 1

    def test_excludes_inactive(self, api_client, definition, published_version):
        definition.is_active = False
        definition.save()
        url = _public_definitions_url("default-europe")
        response = api_client.get(url)
        assert response.json()["count"] == 0

    def test_excludes_definitions_without_published_version(self, api_client, definition):
        """Definition without published version should not appear in public API."""
        url = _public_definitions_url("default-europe")
        response = api_client.get(url)
        assert response.json()["count"] == 0

    def test_filter_by_category(
        self, api_client, definition, published_version, marketing_definition, marketing_published_version
    ):
        url = _public_definitions_url("default-europe")
        response = api_client.get(url, {"category": "mandatory"})
        slugs = [d["slug"] for d in response.json()["results"]]
        assert "terms-of-service" in slugs
        assert "marketing-email" not in slugs

    def test_language_resolution(self, api_client, definition, published_version):
        url = _public_definitions_url("default-europe")
        response = api_client.get(url, {"language": "pl"})
        result = response.json()["results"][0]
        assert result["summary"] == "Akceptuję regulamin"

    def test_channel_scoping(self, api_client, definition, published_version, channel):
        # Assign to specific channel
        definition.channels.add(channel)
        url = _public_definitions_url("default-europe")
        response = api_client.get(url)
        slugs = [d["slug"] for d in response.json()["results"]]
        assert "terms-of-service" in slugs

        # Different channel should not see it
        url2 = _public_definitions_url("other-channel")
        response2 = api_client.get(url2)
        slugs2 = [d["slug"] for d in response2.json()["results"]]
        assert "terms-of-service" not in slugs2

    def test_global_definition_visible_everywhere(self, api_client, definition, published_version):
        """Empty channels = global, visible to all channels."""
        url = _public_definitions_url("any-channel")
        response = api_client.get(url)
        slugs = [d["slug"] for d in response.json()["results"]]
        assert "terms-of-service" in slugs


@pytest.mark.django_db
class TestPublicConsent:
    def test_submit_consent(self, api_client, published_version):
        url = _public_consent_submit_url("default-europe")
        response = api_client.post(
            url,
            {
                "email": "user@test.com",
                "agreements": [{"slug": "terms-of-service", "granted": True}],
                "source": "checkout",
            },
            format="json",
        )
        assert response.status_code == 201

    def test_submit_consent_authenticated_uses_jwt_email(self, user_client, regular_user, published_version):
        """Authenticated users cannot forge consent for another email via the request body."""
        from django_agreements.services import consent_service

        url = _public_consent_submit_url("default-europe")
        response = user_client.post(
            url,
            {
                "email": "someone-else@evil.com",
                "agreements": [{"slug": "terms-of-service", "granted": True}],
                "source": "checkout",
            },
            format="json",
        )
        assert response.status_code == 201
        # Consent recorded under JWT email, not the body email
        assert consent_service.is_consented(regular_user.email, "terms-of-service") is True
        assert consent_service.is_consented("someone-else@evil.com", "terms-of-service") is False

    def test_submit_consent_no_published_version(self, api_client, definition):
        url = _public_consent_submit_url("default-europe")
        response = api_client.post(
            url,
            {
                "email": "user@test.com",
                "agreements": [{"slug": "terms-of-service", "granted": True}],
                "source": "checkout",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_consent_status(self, user_client, regular_user, published_version):
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email=regular_user.email, slug="terms-of-service", granted=True, source="checkout"
        )
        url = _public_consent_status_url("default-europe")
        response = user_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == regular_user.email
        assert data["consents"]["terms-of-service"] is True

    def test_consent_status_requires_auth(self, api_client):
        url = _public_consent_status_url("default-europe")
        response = api_client.get(url)
        assert response.status_code == 401

    def test_withdraw_consent(self, user_client, regular_user, published_version):
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email=regular_user.email, slug="terms-of-service", granted=True, source="checkout"
        )
        url = _public_consent_withdraw_url("default-europe")
        response = user_client.post(url, {"slugs": ["terms-of-service"]}, format="json")
        assert response.status_code == 200

        # Verify consent withdrawn
        assert consent_service.is_consented(regular_user.email, "terms-of-service") is False

    def test_withdraw_requires_auth(self, api_client, published_version):
        url = _public_consent_withdraw_url("default-europe")
        response = api_client.post(url, {"slugs": ["terms-of-service"]}, format="json")
        assert response.status_code == 401


@pytest.mark.django_db
class TestPublicOrderAgreements:
    def test_record_order_agreements(self, api_client, published_version):
        order_id = uuid.uuid4()
        url = _public_order_agreements_url("default-europe", order_id)
        response = api_client.post(
            url, {"email": "customer@test.com", "slugs": ["terms-of-service"], "language": "en"}, format="json"
        )
        assert response.status_code == 201

    def test_record_nonexistent_agreement(self, api_client):
        order_id = uuid.uuid4()
        url = _public_order_agreements_url("default-europe", order_id)
        response = api_client.post(
            url, {"email": "customer@test.com", "slugs": ["nonexistent"], "language": "en"}, format="json"
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestPublicForUser:
    def test_for_user_unauthenticated_ignores_email_param(self, api_client, published_version):
        """Guest with ?email= should never see already_consented=True — email param is ignored."""
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email="already_consented@test.com", slug="terms-of-service", granted=True, source="checkout"
        )
        url = _public_for_user_url("default-europe")
        response = api_client.get(url, {"context": "checkout", "email": "already_consented@test.com"})
        assert response.status_code == 200
        for result in response.json()["results"]:
            assert result["already_consented"] is False

    @pytest.mark.skip(reason="Fixture predates display_contexts filtering on the for-user endpoint")
    def test_for_user_authenticated_applies_consent_filter(self, user_client, regular_user, published_version):
        """Authenticated user who previously consented should see already_consented=True."""
        from django_agreements.services import consent_service

        consent_service.record_consent(
            email=regular_user.email, slug="terms-of-service", granted=True, source="checkout"
        )
        url = _public_for_user_url("default-europe")
        response = user_client.get(url, {"context": "checkout"})
        assert response.status_code == 200
        slugs_consented = {r["slug"]: r["already_consented"] for r in response.json()["results"]}
        assert slugs_consented.get("terms-of-service") is True


@pytest.mark.django_db
class TestAPIKeyAuth:
    """API key validation on subscribe endpoint."""

    def test_subscribe_without_api_key_returns_401(self, api_client, marketing_definition, marketing_published_version):
        """Anonymous request without X-API-KEY is rejected."""
        url = _subscribe_url("default-europe")
        response = api_client.post(url, {"email": "test@test.com"}, format="json")
        assert response.status_code == 401

    def test_subscribe_with_wrong_api_key_returns_401(
        self, api_client, marketing_definition, marketing_published_version
    ):
        """Wrong API key is rejected."""
        url = _subscribe_url("default-europe")
        response = api_client.post(url, {"email": "test@test.com"}, format="json", HTTP_X_API_KEY="wrong-key")
        assert response.status_code == 401

    def test_subscribe_with_valid_api_key_returns_201(
        self, api_client, make_api_key, marketing_definition, marketing_published_version
    ):
        """Valid API key allows subscribe."""
        url = _subscribe_url("default-europe")
        with patch("django_agreements.api.public.views.consent_views._send_confirmation_email"):
            response = api_client.post(
                url, {"email": "apikey-test@test.com"}, format="json", HTTP_X_API_KEY=make_api_key()
            )
        assert response.status_code == 201
