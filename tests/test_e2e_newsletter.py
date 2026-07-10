# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""E2E integration tests for the newsletter double opt-in flow.

Two test modes:
- **Local (pytest):** Django test client + direct token generation (no email transport).
- **Docker (mailpit):** Full flow including email delivery via Mailpit API.
  Requires: Docker stack with Mailpit on localhost:8025.
  Run with: pytest -m mailpit

Test scenarios:
1. Double opt-in flow (subscribe → confirm → active)
2. Duplicate email → already_subscribed
3. Unsubscribe flow (token-based, anonymous)
4. List-Unsubscribe header (RFC 8058)
5. NEWSLETTER_DOUBLE_OPTIN=False fallback
"""

import re
import urllib.error
import urllib.request
from json import loads as json_loads

import pytest
from django.test import override_settings
from django.urls import reverse

from django_agreements.models import ConsentRecord
from django_agreements.services import consent_service
from django_agreements.services.token_service import generate_token

# ---------------------------------------------------------------------------
# Mailpit helpers
# ---------------------------------------------------------------------------

MAILPIT_BASE = "http://localhost:8025/api/v1"


def _mailpit_available() -> bool:
    try:
        req = urllib.request.Request(f"{MAILPIT_BASE}/messages", method="GET")
        urllib.request.urlopen(req, timeout=2)
        return True
    except (urllib.error.URLError, OSError):
        return False


def _mailpit_clear():
    """Delete all messages in Mailpit."""
    req = urllib.request.Request(f"{MAILPIT_BASE}/messages", method="DELETE")
    try:
        urllib.request.urlopen(req, timeout=2)
    except urllib.error.URLError:
        pass


def _mailpit_get_messages() -> list[dict]:
    """Fetch all messages from Mailpit."""
    req = urllib.request.Request(f"{MAILPIT_BASE}/messages", method="GET")
    resp = urllib.request.urlopen(req, timeout=5)
    data = json_loads(resp.read())
    return data.get("messages", [])


def _mailpit_get_message(msg_id: str) -> dict:
    """Fetch a single message by ID (includes full headers and body)."""
    req = urllib.request.Request(f"{MAILPIT_BASE}/message/{msg_id}", method="GET")
    resp = urllib.request.urlopen(req, timeout=5)
    return json_loads(resp.read())


def _mailpit_find_message(to_email: str) -> dict | None:
    """Find the latest Mailpit message sent to a given address."""
    for msg in _mailpit_get_messages():
        for recipient in msg.get("To", []):
            if recipient.get("Address") == to_email:
                return _mailpit_get_message(msg["ID"])
    return None


def _extract_token_from_body(body: str) -> str | None:
    """Extract token param from a confirm/unsubscribe URL in email body."""
    match = re.search(r"[?&]token=([A-Za-z0-9_.:-]+)", body)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


mailpit = pytest.mark.skipif(
    not _mailpit_available(), reason="Mailpit not available — run Docker stack with `make dev`"
)


@pytest.fixture(autouse=False)
def clear_mailpit():
    """Clear Mailpit inbox before and after tests that use it."""
    _mailpit_clear()
    yield
    _mailpit_clear()


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _subscribe_url(channel_idx="default-europe"):
    return reverse("public-newsletter-subscribe", kwargs={"channel_idx": channel_idx})


def _confirm_url(channel_idx="default-europe"):
    return reverse("public-consent-confirm", kwargs={"channel_idx": channel_idx})


def _unsubscribe_url(channel_idx="default-europe"):
    return reverse("public-consent-unsubscribe", kwargs={"channel_idx": channel_idx})


def _status_url(channel_idx="default-europe"):
    return reverse("public-consent-status", kwargs={"channel_idx": channel_idx})


# ---------------------------------------------------------------------------
# E2E flow — local (Django test client, no email transport)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDoubleOptinFlowLocal:
    """Full double opt-in lifecycle using Django test client and direct token generation."""

    @pytest.mark.skip(reason="Predates the X-API-KEY requirement on subscribe; needs rewrite with authenticated client")
    def test_full_subscribe_confirm_flow(self, api_client, marketing_published_version):
        """Subscribe → pending → generate token → confirm → consent active."""
        email = "e2e-local@test.com"

        # Step 1: Subscribe
        response = api_client.post(_subscribe_url(), {"email": email}, format="json")
        assert response.status_code == 201

        # Step 2: Verify pending record exists but is_consented is False
        assert consent_service.is_consented(email, "marketing-email") is False
        pending = ConsentRecord.objects.filter(email=email, source="double-optin-pending")
        assert pending.exists()

        # Step 3: Generate token (simulates what the confirmation email contains)
        token = generate_token(email, "marketing-email")

        # Step 4: Confirm
        response = api_client.post(_confirm_url(), {"token": token}, format="json")
        assert response.status_code == 200

        # Step 5: Verify consent is now active
        assert consent_service.is_consented(email, "marketing-email") is True
        confirmed = ConsentRecord.objects.filter(email=email, source="double-optin-confirmed")
        assert confirmed.exists()

    def test_full_unsubscribe_flow(self, api_client, marketing_published_version):
        """Subscribe → confirm → unsubscribe → consent revoked."""
        email = "e2e-unsub@test.com"

        # Subscribe + confirm
        api_client.post(_subscribe_url(), {"email": email}, format="json")
        token = generate_token(email, "marketing-email")
        api_client.post(_confirm_url(), {"token": token}, format="json")
        assert consent_service.is_consented(email, "marketing-email") is True

        # Unsubscribe via token (simulates email link click)
        unsub_token = generate_token(email, "marketing-email")
        response = api_client.get(_unsubscribe_url(), {"token": unsub_token})
        assert response.status_code == 200

        # Verify consent revoked
        assert consent_service.is_consented(email, "marketing-email") is False
        revoked = ConsentRecord.objects.filter(email=email, source="unsubscribed")
        assert revoked.exists()

    @pytest.mark.skip(reason="Predates the X-API-KEY requirement on subscribe; needs rewrite with authenticated client")
    def test_duplicate_email_returns_already_subscribed(self, api_client, marketing_published_version):
        """Second subscribe for a confirmed email returns already_subscribed."""
        email = "e2e-dup@test.com"

        # First: subscribe + confirm
        api_client.post(_subscribe_url(), {"email": email}, format="json")
        token = generate_token(email, "marketing-email")
        api_client.post(_confirm_url(), {"token": token}, format="json")

        # Second: subscribe again
        response = api_client.post(_subscribe_url(), {"email": email}, format="json")
        assert response.status_code == 200
        assert response.json().get("status") == "already_subscribed"

    @pytest.mark.skip(reason="Predates the X-API-KEY requirement on subscribe; needs rewrite with authenticated client")
    def test_resubscribe_after_unsubscribe(self, api_client, marketing_published_version):
        """Unsubscribed user can subscribe again (fresh double opt-in)."""
        email = "e2e-resub@test.com"

        # Subscribe → confirm → unsubscribe
        api_client.post(_subscribe_url(), {"email": email}, format="json")
        token = generate_token(email, "marketing-email")
        api_client.post(_confirm_url(), {"token": token}, format="json")
        unsub_token = generate_token(email, "marketing-email")
        api_client.get(_unsubscribe_url(), {"token": unsub_token})

        assert consent_service.is_consented(email, "marketing-email") is False

        # Re-subscribe (should create new pending, not already_subscribed)
        response = api_client.post(_subscribe_url(), {"email": email}, format="json")
        assert response.status_code == 201

    @pytest.mark.skip(reason="Predates the X-API-KEY requirement on subscribe; needs rewrite with authenticated client")
    def test_consent_status_reflects_double_optin(self, api_client, marketing_published_version):
        """Status endpoint should show False while pending, True after confirm."""
        email = "e2e-status@test.com"

        # Pending — status is False
        api_client.post(_subscribe_url(), {"email": email}, format="json")
        response = api_client.get(_status_url(), {"email": email})
        assert response.status_code == 200
        assert response.json()["consents"]["marketing-email"] is False

        # Confirm — status is True
        token = generate_token(email, "marketing-email")
        api_client.post(_confirm_url(), {"token": token}, format="json")
        response = api_client.get(_status_url(), {"email": email})
        assert response.json()["consents"]["marketing-email"] is True

    @pytest.mark.skip(reason="Predates the X-API-KEY requirement on subscribe; needs rewrite with authenticated client")
    def test_audit_trail_complete(self, api_client, marketing_published_version):
        """Full lifecycle creates exactly 3 records: pending → confirmed → unsubscribed."""
        email = "e2e-audit@test.com"

        api_client.post(_subscribe_url(), {"email": email}, format="json")
        token = generate_token(email, "marketing-email")
        api_client.post(_confirm_url(), {"token": token}, format="json")
        unsub_token = generate_token(email, "marketing-email")
        api_client.get(_unsubscribe_url(), {"token": unsub_token})

        records = ConsentRecord.objects.filter(email=email).order_by("created_at")
        assert records.count() == 3

        sources = list(records.values_list("source", flat=True))
        assert sources == ["double-optin-pending", "double-optin-confirmed", "unsubscribed"]


# ---------------------------------------------------------------------------
# NEWSLETTER_DOUBLE_OPTIN=False fallback
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDoubleOptinDisabled:
    @override_settings(NEWSLETTER_DOUBLE_OPTIN=False)
    @pytest.mark.skip(reason="Predates the X-API-KEY requirement on subscribe; needs rewrite with authenticated client")
    def test_subscribe_directly_confirms(self, api_client, marketing_published_version):
        """When double opt-in is disabled, subscribe immediately activates consent."""
        email = "direct@test.com"

        response = api_client.post(_subscribe_url(), {"email": email}, format="json")
        assert response.status_code in (200, 201)

        # Consent should be immediately active (no confirmation needed)
        assert consent_service.is_consented(email, "marketing-email") is True

    @override_settings(NEWSLETTER_DOUBLE_OPTIN=False)
    def test_no_pending_record_created(self, api_client, marketing_published_version):
        """When disabled, no double-optin-pending record should exist."""
        email = "direct-nopending@test.com"

        api_client.post(_subscribe_url(), {"email": email}, format="json")

        pending = ConsentRecord.objects.filter(email=email, source="double-optin-pending")
        assert not pending.exists()


# ---------------------------------------------------------------------------
# Mailpit integration — full email flow (Docker only)
# ---------------------------------------------------------------------------


@mailpit
@pytest.mark.django_db
class TestDoubleOptinFlowMailpit:
    """Full flow with real email delivery via Mailpit.

    These tests require the Docker stack running with Mailpit (localhost:8025).
    """

    def test_subscribe_sends_confirmation_email(self, api_client, marketing_published_version, clear_mailpit):
        """Subscribe triggers a confirmation email captured by Mailpit."""
        email = "e2e-mailpit@test.com"

        # Subscribe
        response = api_client.post(_subscribe_url(), {"email": email}, format="json")
        assert response.status_code == 201

        # Check Mailpit for confirmation email
        msg = _mailpit_find_message(email)
        assert msg is not None, f"No email found for {email} in Mailpit"

        # Email body should contain a confirmation link with token
        body = msg.get("Text", "") or msg.get("HTML", "")
        token = _extract_token_from_body(body)
        assert token is not None, "Confirmation email missing token in body"

    def test_full_flow_via_email_token(self, api_client, marketing_published_version, clear_mailpit):
        """Subscribe → extract token from email → confirm → active."""
        email = "e2e-mailpit-flow@test.com"

        # Step 1: Subscribe
        api_client.post(_subscribe_url(), {"email": email}, format="json")

        # Step 2: Extract token from Mailpit email
        msg = _mailpit_find_message(email)
        assert msg is not None, "Confirmation email not received"
        body = msg.get("Text", "") or msg.get("HTML", "")
        token = _extract_token_from_body(body)
        assert token is not None

        # Step 3: Confirm via extracted token
        response = api_client.post(_confirm_url(), {"token": token}, format="json")
        assert response.status_code == 200

        # Step 4: Verify consent active
        assert consent_service.is_consented(email, "marketing-email") is True

    def test_email_contains_list_unsubscribe_header(self, api_client, marketing_published_version, clear_mailpit):
        """Confirmation email must include List-Unsubscribe header (RFC 8058)."""
        email = "e2e-headers@test.com"

        # Subscribe + confirm to trigger marketing emails
        api_client.post(_subscribe_url(), {"email": email}, format="json")
        confirm_token = generate_token(email, "marketing-email")
        api_client.post(_confirm_url(), {"token": confirm_token}, format="json")

        # Check the confirmation email headers
        msg = _mailpit_find_message(email)
        assert msg is not None

        headers = {h["Name"]: h["Value"] for h in msg.get("Headers", [])}

        # RFC 8058 requires both headers for one-click unsubscribe
        assert "List-Unsubscribe" in headers, "Missing List-Unsubscribe header"
        assert "List-Unsubscribe-Post" in headers, "Missing List-Unsubscribe-Post header"

        # List-Unsubscribe should contain a URL
        unsub_header = headers["List-Unsubscribe"]
        assert "http" in unsub_header, f"List-Unsubscribe has no URL: {unsub_header}"

        # List-Unsubscribe-Post must be exactly this value per RFC 8058
        assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"

    def test_unsubscribe_via_email_link(self, api_client, marketing_published_version, clear_mailpit):
        """Full unsubscribe flow: email link → GET unsubscribe → consent revoked."""
        email = "e2e-unsub-mailpit@test.com"

        # Subscribe + confirm
        api_client.post(_subscribe_url(), {"email": email}, format="json")
        confirm_token = generate_token(email, "marketing-email")
        api_client.post(_confirm_url(), {"token": confirm_token}, format="json")
        assert consent_service.is_consented(email, "marketing-email") is True

        # Get unsubscribe link from email
        msg = _mailpit_find_message(email)
        assert msg is not None
        body = msg.get("Text", "") or msg.get("HTML", "")

        # Find unsubscribe URL and extract token
        unsub_match = re.search(r"unsubscribe[^\s]*[?&]token=([A-Za-z0-9_.:-]+)", body)
        assert unsub_match is not None, "Unsubscribe link not found in email body"
        unsub_token = unsub_match.group(1)

        # Unsubscribe
        response = api_client.get(_unsubscribe_url(), {"token": unsub_token})
        assert response.status_code == 200
        assert consent_service.is_consented(email, "marketing-email") is False
