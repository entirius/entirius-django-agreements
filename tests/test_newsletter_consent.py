# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for newsletter double opt-in consent flow — TDD (written before implementation).

These tests are intentionally RED until @dev-python implements:
- consent_service: request_consent, confirm_consent, revoke_consent (updated is_consented)
- ConsentRecord: 3 new SOURCE_CHOICES (double-optin-pending, double-optin-confirmed, unsubscribed)
- Public API: newsletter subscribe, consent confirm, token-based unsubscribe endpoints

New URL names expected:
  public-newsletter-subscribe → POST {channel}/newsletter/subscribe/
  public-consent-confirm      → POST {channel}/consents/confirm/
  public-consent-unsubscribe  → GET  {channel}/consents/unsubscribe/?token=...
"""

from unittest.mock import patch

import pytest
from django.urls import reverse

from django_agreements.services import consent_service
from django_agreements.services.token_service import generate_token

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _subscribe_url(channel_idx):
    return reverse("public-newsletter-subscribe", kwargs={"channel_idx": channel_idx})


def _confirm_url(channel_idx):
    return reverse("public-consent-confirm", kwargs={"channel_idx": channel_idx})


def _unsubscribe_url(channel_idx):
    return reverse("public-consent-unsubscribe", kwargs={"channel_idx": channel_idx})


# ---------------------------------------------------------------------------
# Service tests — new functions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRequestConsent:
    def test_request_consent_creates_pending_record(self, marketing_published_version):
        # Act
        record = consent_service.request_consent(
            email="user@test.com", consent_type="marketing-email", channel_idx="default-europe"
        )

        # Assert
        assert record.email == "user@test.com"
        assert record.granted is True
        assert record.source == "double-optin-pending"
        assert record.channel_idx == "default-europe"

    def test_request_consent_returns_consent_record(self, marketing_published_version):
        from django_agreements.models import ConsentRecord

        record = consent_service.request_consent(
            email="user@test.com", consent_type="marketing-email", channel_idx="default-europe"
        )

        assert isinstance(record, ConsentRecord)

    def test_request_consent_no_published_version_raises(self, marketing_definition):
        with pytest.raises(ValueError, match="No published version"):
            consent_service.request_consent(
                email="user@test.com", consent_type="marketing-email", channel_idx="default-europe"
            )


@pytest.mark.django_db
class TestConfirmConsent:
    def test_confirm_consent_activates(self, marketing_published_version):
        # Arrange
        consent_service.request_consent(
            email="user@test.com", consent_type="marketing-email", channel_idx="default-europe"
        )
        token = generate_token("user@test.com", "marketing-email")

        # Act
        record = consent_service.confirm_consent(token)

        # Assert
        assert record.email == "user@test.com"
        assert record.granted is True
        assert record.source == "double-optin-confirmed"

    def test_confirm_consent_invalid_token_raises(self, marketing_published_version):
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            consent_service.confirm_consent("totally-invalid-token")

    def test_confirm_consent_expired_token_raises(self, marketing_published_version):
        # Arrange — generate token in far past
        with patch("django.core.signing.time.time", return_value=0.0):
            token = generate_token("user@test.com", "marketing-email")

        with pytest.raises(ValueError, match="[Ee]xpired"):
            consent_service.confirm_consent(token)


@pytest.mark.django_db
class TestRevokeConsent:
    def test_revoke_consent_marks_unsubscribed(self, marketing_published_version):
        # Arrange — user has confirmed consent
        consent_service.request_consent(
            email="user@test.com", consent_type="marketing-email", channel_idx="default-europe"
        )
        token = generate_token("user@test.com", "marketing-email")
        consent_service.confirm_consent(token)

        # Act
        revoke_token = generate_token("user@test.com", "marketing-email")
        record = consent_service.revoke_consent(revoke_token)

        # Assert
        assert record.email == "user@test.com"
        assert record.granted is False
        assert record.source == "unsubscribed"

    def test_revoke_consent_invalid_token_raises(self):
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            consent_service.revoke_consent("totally-invalid-token")

    def test_revoke_consent_expired_token_raises(self):
        # Arrange — generate token in far past
        with patch("django.core.signing.time.time", return_value=0.0):
            token = generate_token("user@test.com", "marketing-email")

        with pytest.raises(ValueError, match="[Ee]xpired"):
            consent_service.revoke_consent(token)


@pytest.mark.django_db
class TestIsConsentedExcludesPending:
    def test_is_consented_false_when_only_pending(self, marketing_published_version):
        """PENDING record must not count as active consent."""
        # Arrange — only pending record exists
        consent_service.request_consent(
            email="user@test.com", consent_type="marketing-email", channel_idx="default-europe"
        )

        # Act / Assert
        assert consent_service.is_consented("user@test.com", "marketing-email") is False

    def test_is_consented_true_after_confirm(self, marketing_published_version):
        # Arrange
        consent_service.request_consent(
            email="user@test.com", consent_type="marketing-email", channel_idx="default-europe"
        )
        token = generate_token("user@test.com", "marketing-email")
        consent_service.confirm_consent(token)

        # Act / Assert
        assert consent_service.is_consented("user@test.com", "marketing-email") is True

    def test_is_consented_false_after_revoke(self, marketing_published_version):
        # Arrange — confirm then revoke
        consent_service.request_consent(
            email="user@test.com", consent_type="marketing-email", channel_idx="default-europe"
        )
        confirm_token = generate_token("user@test.com", "marketing-email")
        consent_service.confirm_consent(confirm_token)

        revoke_token = generate_token("user@test.com", "marketing-email")
        consent_service.revoke_consent(revoke_token)

        # Act / Assert
        assert consent_service.is_consented("user@test.com", "marketing-email") is False

    def test_is_consented_unaffected_for_non_marketing(self, published_version):
        """Non-marketing consent (checkout) still works as before."""
        consent_service.record_consent(email="user@test.com", slug="terms-of-service", granted=True, source="checkout")

        assert consent_service.is_consented("user@test.com", "terms-of-service") is True


# ---------------------------------------------------------------------------
# Public API tests — new endpoints
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.skip(reason="Predates the X-API-KEY requirement on subscribe; needs rewrite with authenticated client")
class TestNewsletterSubscribeAPI:
    def test_subscribe_no_auth_required(self, api_client, marketing_published_version):
        # Arrange / Act
        response = api_client.post(_subscribe_url("default-europe"), {"email": "user@test.com"}, format="json")

        # Assert — no authentication needed
        assert response.status_code in (200, 201)

    def test_subscribe_creates_pending_record(self, api_client, marketing_published_version):
        # Act
        response = api_client.post(_subscribe_url("default-europe"), {"email": "new@test.com"}, format="json")

        # Assert — pending record created
        assert response.status_code == 201
        assert consent_service.is_consented("new@test.com", "marketing-email") is False  # PENDING does not count

    def test_subscribe_duplicate_already_subscribed(self, api_client, marketing_published_version):
        """Email with active confirmed consent returns already_subscribed status."""
        # Arrange — confirm subscription first
        consent_service.request_consent(
            email="active@test.com", consent_type="marketing-email", channel_idx="default-europe"
        )
        token = generate_token("active@test.com", "marketing-email")
        consent_service.confirm_consent(token)

        # Act
        response = api_client.post(_subscribe_url("default-europe"), {"email": "active@test.com"}, format="json")

        # Assert
        assert response.status_code == 200
        assert response.json().get("status") == "already_subscribed"

    def test_subscribe_missing_email_returns_400(self, api_client, marketing_published_version):
        response = api_client.post(_subscribe_url("default-europe"), {}, format="json")
        assert response.status_code == 400

    def test_subscribe_language_pl_propagates_to_email_service(
        self, user_client, marketing_published_version, settings
    ):
        """POST with language=pl → NewsletterSignupEmail instantiated with language='pl'.
        Regression test for the pre-1.0.1 bug where the caller hardcoded language='en'."""
        from unittest.mock import patch

        settings.NEWSLETTER_DOUBLE_OPTIN = True
        with patch("django_email.service.agreements.newsletter_signup.NewsletterSignupEmail") as NewsletterSignupEmail:
            response = user_client.post(
                _subscribe_url("default-europe"),
                {"email": "pl-booker@test.com", "language": "pl"},
                format="json",
            )

        assert response.status_code == 201, response.json()
        NewsletterSignupEmail.assert_called_once()
        assert NewsletterSignupEmail.call_args.kwargs["language"] == "pl"

    def test_subscribe_no_language_is_not_hardcoded_to_en(self, user_client, marketing_published_version, settings):
        """Omitted language MUST NOT result in the pre-1.0.1 hardcoded `"en"`
        bug. Final ``language`` kwarg is whatever the channel-default resolver
        returns (channel default iso2, or None to defer to EMAIL_DEFAULT_LANGUAGE).
        """
        from unittest.mock import patch

        settings.NEWSLETTER_DOUBLE_OPTIN = True
        with patch("django_email.service.agreements.newsletter_signup.NewsletterSignupEmail") as NewsletterSignupEmail:
            response = user_client.post(_subscribe_url("default-europe"), {"email": "no-lang@test.com"}, format="json")

        assert response.status_code == 201
        NewsletterSignupEmail.assert_called_once()
        lang_kwarg = NewsletterSignupEmail.call_args.kwargs["language"]
        # Either resolved to a channel-default iso2 or None (both valid;
        # the regression would be a hardcoded "en" unrelated to the channel).
        assert lang_kwarg is None or len(lang_kwarg) == 2

    def test_subscribe_invalid_language_returns_400(self, user_client, marketing_published_version):
        """Regex ``^[a-zA-Z]{2}$`` rejects 3-letter codes, unicode, traversal attempts."""
        for bad in ["eng", "../", "pl-PL", "<script>", "en;en"]:
            response = user_client.post(
                _subscribe_url("default-europe"),
                {"email": "x@test.com", "language": bad},
                format="json",
            )
            assert response.status_code == 400, f"accepted bad lang: {bad}"


@pytest.mark.django_db
class TestConsentConfirmAPI:
    def test_confirm_valid_token(self, api_client, marketing_published_version):
        # Arrange
        consent_service.request_consent(
            email="user@test.com", consent_type="marketing-email", channel_idx="default-europe"
        )
        token = generate_token("user@test.com", "marketing-email")

        # Act
        response = api_client.post(_confirm_url("default-europe"), {"token": token}, format="json")

        # Assert
        assert response.status_code == 200
        assert consent_service.is_consented("user@test.com", "marketing-email") is True

    def test_confirm_expired_token_returns_400(self, api_client, marketing_published_version):
        # Arrange — generate token in far past
        with patch("django.core.signing.time.time", return_value=0.0):
            token = generate_token("user@test.com", "marketing-email")

        # Act
        response = api_client.post(_confirm_url("default-europe"), {"token": token}, format="json")

        # Assert
        assert response.status_code == 400

    def test_confirm_invalid_token_returns_400(self, api_client, marketing_published_version):
        response = api_client.post(_confirm_url("default-europe"), {"token": "not-a-valid-token"}, format="json")
        assert response.status_code == 400

    def test_confirm_missing_token_returns_400(self, api_client):
        response = api_client.post(_confirm_url("default-europe"), {}, format="json")
        assert response.status_code == 400

    def test_confirm_no_auth_required(self, api_client, marketing_published_version):
        """Confirmation link in email must work without authentication."""
        token = generate_token("user@test.com", "marketing-email")
        # Even with invalid token we should get 400, not 401
        response = api_client.post(_confirm_url("default-europe"), {"token": token}, format="json")
        assert response.status_code != 401


@pytest.mark.django_db
class TestConsentUnsubscribeAPI:
    def test_unsubscribe_valid_token(self, api_client, marketing_published_version):
        # Arrange — confirmed subscriber
        consent_service.request_consent(
            email="user@test.com", consent_type="marketing-email", channel_idx="default-europe"
        )
        confirm_token = generate_token("user@test.com", "marketing-email")
        consent_service.confirm_consent(confirm_token)

        unsubscribe_token = generate_token("user@test.com", "marketing-email")

        # Act
        response = api_client.get(_unsubscribe_url("default-europe"), {"token": unsubscribe_token})

        # Assert
        assert response.status_code == 200
        assert consent_service.is_consented("user@test.com", "marketing-email") is False

    def test_unsubscribe_invalid_token_returns_400(self, api_client):
        response = api_client.get(_unsubscribe_url("default-europe"), {"token": "not-a-valid-token"})
        assert response.status_code == 400

    def test_unsubscribe_expired_token_returns_400(self, api_client):
        # Arrange — generate token in far past
        with patch("django.core.signing.time.time", return_value=0.0):
            token = generate_token("user@test.com", "marketing-email")

        response = api_client.get(_unsubscribe_url("default-europe"), {"token": token})
        assert response.status_code == 400

    def test_unsubscribe_missing_token_returns_400(self, api_client):
        response = api_client.get(_unsubscribe_url("default-europe"))
        assert response.status_code == 400

    def test_unsubscribe_no_auth_required(self, api_client, marketing_published_version):
        """Unsubscribe link in email must work without authentication (GDPR Art. 7)."""
        # Even invalid token → 400, not 401
        response = api_client.get(_unsubscribe_url("default-europe"), {"token": "invalid"})
        assert response.status_code != 401
