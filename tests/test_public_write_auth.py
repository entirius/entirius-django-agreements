# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Public writes need a valid X-API-KEY or a JWT; token links and GETs stay open. Throttles key on the client IP
header and the subscribe mail is capped per address."""

import secrets
import uuid
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse

from django_agreements.api.public.throttling import SubscribeAddressThrottle, SubscribeThrottle

pytestmark = pytest.mark.django_db

CHANNEL = "default-europe"
EMAIL = "someone@example.com"


def _url(name: str, **extra) -> str:
    return reverse(name, kwargs={"channel_idx": CHANNEL, **extra})


# name, url kwargs, body: each write endpoint with a body that passes validation when the caller is allowed in.
WRITES = [
    ("public-consent-submit", {}, {"email": EMAIL, "agreements": [], "source": "checkout"}),
    ("public-consent-withdraw", {}, {"slugs": ["terms-of-service"]}),
    ("public-newsletter-subscribe", {}, {"email": EMAIL}),
    ("public-order-agreements", {"order_id": str(uuid.uuid4())}, {"email": EMAIL, "slugs": [], "language": "en"}),
]


@pytest.fixture(autouse=True)
def _setup(channel, marketing_published_version):
    with patch("django_agreements.api.public.views.consent_views._send_confirmation_email"):
        yield


@pytest.mark.parametrize(("name", "extra", "body"), WRITES)
def test_write_without_key_or_jwt_is_401(api_client, name, extra, body):
    response = api_client.post(_url(name, **extra), body, format="json")
    assert response.status_code == 401


@pytest.mark.parametrize(("name", "extra", "body"), WRITES)
def test_write_with_wrong_key_is_401(api_client, make_api_key, name, extra, body):
    make_api_key()
    response = api_client.post(_url(name, **extra), body, format="json", HTTP_X_API_KEY=secrets.token_hex(32))
    assert response.status_code == 401


@pytest.mark.parametrize(("name", "extra", "body"), WRITES)
def test_valid_key_passes_the_gate(keyed_client, name, extra, body):
    response = keyed_client.post(_url(name, **extra), body, format="json")
    # withdraw takes its e-mail from a JWT: a key alone is refused there, by design
    if name == "public-consent-withdraw":
        assert response.status_code == 401
    else:
        assert response.status_code in {201, 400, 404}


@pytest.mark.parametrize(("name", "extra", "body"), WRITES)
def test_jwt_passes_the_gate(user_client, name, extra, body):
    assert user_client.post(_url(name, **extra), body, format="json").status_code in {200, 201, 400, 404}


def test_cookie_consent_post_stays_anonymous(api_client):
    # no banner published: 404 from the service, not 401 from the gate
    response = api_client.post(_url("public-cookie-consent-submit"), {}, format="json")
    assert response.status_code == 400


def test_stored_ip_follows_client_ip_header(keyed_client, settings, published_version):
    from django_agreements.models import ConsentRecord

    settings.CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
    body = {"email": EMAIL, "agreements": [{"slug": "terms-of-service", "granted": True}], "source": "checkout"}
    keyed_client.post(
        _url("public-consent-submit"), body, format="json", REMOTE_ADDR="10.0.0.1", HTTP_CF_CONNECTING_IP="198.51.100.7"
    )
    assert ConsentRecord.objects.get(email=EMAIL).ip_address == "198.51.100.7"


def test_token_links_and_gets_need_no_key(api_client):
    assert api_client.post(_url("public-consent-confirm"), {}, format="json").status_code == 400
    assert api_client.get(_url("public-consent-unsubscribe")).status_code == 400
    assert api_client.get(_url("public-definition-list")).status_code == 200
    assert api_client.get(_url("public-cookie-banner")).status_code == 404


def test_subscribe_confirmation_is_limited_per_address(keyed_client):
    url = _url("public-newsletter-subscribe")
    # the per-client throttle is raised so only the per-address one can answer 429
    with patch.object(SubscribeThrottle, "fallback_rate", "100/min"):
        statuses = [keyed_client.post(url, {"email": EMAIL}, format="json").status_code for _ in range(4)]
        other = keyed_client.post(url, {"email": "other@example.com"}, format="json").status_code
    assert statuses == [201, 201, 201, 429]
    assert other == 201


def test_subscribe_address_limit_ignores_case_and_spaces(keyed_client):
    url = _url("public-newsletter-subscribe")
    with patch.object(SubscribeThrottle, "fallback_rate", "100/min"):
        for variant in (EMAIL, EMAIL.upper(), f" {EMAIL} "):
            keyed_client.post(url, {"email": variant}, format="json")
        assert keyed_client.post(url, {"email": EMAIL}, format="json").status_code == 429


def test_subscribe_address_key_is_a_hash():
    class _Request:
        data = {"email": EMAIL}

    key = SubscribeAddressThrottle().get_cache_key(_Request(), None)
    assert key.startswith("throttle_agreements_subscribe_address_")
    assert "someone" not in key and "example" not in key


@pytest.mark.parametrize(
    ("rates", "expected"),
    [
        ({}, "3/hour"),
        ({"agreements_subscribe_address": None}, "3/hour"),
        ({"agreements_subscribe_address": "x"}, "3/hour"),
    ],
)
def test_subscribe_address_rate_never_none(rates, expected):
    with patch.object(SubscribeAddressThrottle, "THROTTLE_RATES", rates):
        assert SubscribeAddressThrottle().rate == expected


def test_throttle_keys_on_client_ip_header_when_set(keyed_client, settings):
    settings.CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
    url = _url("public-consent-confirm")
    # the same REMOTE_ADDR (a proxy) but different client addresses: separate buckets
    for _ in range(10):
        keyed_client.post(url, {}, format="json", REMOTE_ADDR="10.0.0.1", HTTP_CF_CONNECTING_IP="198.51.100.1")
    blocked = keyed_client.post(url, {}, format="json", REMOTE_ADDR="10.0.0.1", HTTP_CF_CONNECTING_IP="198.51.100.1")
    other = keyed_client.post(url, {}, format="json", REMOTE_ADDR="10.0.0.1", HTTP_CF_CONNECTING_IP="198.51.100.2")
    assert blocked.status_code == 429
    assert other.status_code != 429


def test_throttle_ignores_the_header_when_unset(api_client, settings):
    if hasattr(settings, "CLIENT_IP_HEADER"):
        del settings.CLIENT_IP_HEADER
    cache.clear()
    url = _url("public-consent-confirm")
    for n in range(10):
        api_client.post(url, {}, format="json", REMOTE_ADDR="10.0.0.1", HTTP_CF_CONNECTING_IP=f"198.51.100.{n}")
    assert api_client.post(url, {}, format="json", REMOTE_ADDR="10.0.0.1").status_code == 429


def _consent(client, slug: str, granted: bool, email: str = EMAIL):
    body = {"email": email, "agreements": [{"slug": slug, "granted": granted}], "source": "checkout"}
    return client.post(_url("public-consent-submit"), body, format="json")


@pytest.mark.parametrize("granted", [True, False])
def test_key_alone_cannot_record_marketing_consent(keyed_client, granted):
    from django_agreements.models import ConsentRecord

    response = _consent(keyed_client, "marketing-email", granted)
    assert response.status_code == 400
    assert "newsletter" in str(response.json()).lower()
    assert not ConsentRecord.objects.exists()


def test_key_alone_records_a_non_marketing_consent(keyed_client, published_version):
    assert _consent(keyed_client, "terms-of-service", True).status_code == 201


def test_jwt_records_marketing_consent(user_client):
    assert _consent(user_client, "marketing-email", True).status_code == 201


def test_service_default_keeps_internal_callers_working(marketing_published_version):
    from django_agreements.services import consent_service

    agreements = [{"slug": "marketing-email", "granted": True}]
    assert consent_service.record_multiple_consents(email=EMAIL, agreements=agreements, source="crm")
    with pytest.raises(ValueError, match="verified"):
        consent_service.record_multiple_consents(email=EMAIL, agreements=agreements, source="crm", email_verified=False)
