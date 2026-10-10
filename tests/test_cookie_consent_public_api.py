# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Public cookie banner and cookie consent endpoints."""

import uuid

import pytest
from django.urls import reverse

from django_agreements import settings as agreements_settings
from django_agreements.api.public.throttling import CookieConsentThrottle
from django_agreements.api.public.views.cookie_consent_views import PublicCookieConsentViewSet
from django_agreements.models import AgreementDefinition, CookieConsent
from django_agreements.services import version_service


def _banner_url(channel_idx):
    return reverse("public-cookie-banner", kwargs={"channel_idx": channel_idx})


def _consent_url(channel_idx):
    return reverse("public-cookie-consent-submit", kwargs={"channel_idx": channel_idx})


def _payload(version, **overrides):
    payload = {
        "consent_id": str(uuid.uuid4()),
        "revision": version.pk,
        "language": "pl",
        "action": "custom",
        "categories": {"necessary": True, "analytics": False},
    }
    return {**payload, **overrides}


def _assert_envelope(response, status, error):
    assert response.status_code == status
    data = response.json()
    assert (data["error"], set(data)) == (error, {"error", "message", "debug_id", "details"})
    return data


@pytest.fixture
def site_channel(channel, lang_pl, lang_en):
    """Channel with languages pl + en, default en."""
    channel.default_language = lang_en
    channel.save()
    channel.languages.add(lang_pl)
    return channel


@pytest.fixture
def banner(cookie_definition, make_cookie_version):
    return make_cookie_version(cookie_definition, languages=("pl", "en", "de"))


@pytest.mark.django_db
class TestCookieBanner:
    def test_shape(self, api_client, site_channel, banner):
        response = api_client.get(_banner_url(site_channel.idx), {"language": "pl"})
        assert response.status_code == 200
        data = response.json()
        assert data["revision"] == banner.pk
        assert (data["version_number"], data["definition_slug"], data["language"]) == (1, "cookie-banner", "pl")
        assert data["max_age_days"] == agreements_settings.COOKIE_CONSENT_MAX_AGE_DAYS == 365
        assert data["text"] == "We use cookies pl"
        assert data["buttons"] == {
            "accept_all": "Accept all",
            "reject_all": "Reject all",
            "customize": "Settings",
            "save": "Save",
        }
        assert (data["preferences_title"], data["close_label"]) == ("Settings pl", "Close")
        assert response["Cache-Control"] == "public, max-age=300"
        assert data["categories"][1] == {
            "key": "analytics",
            "required": False,
            "consent_mode": ["analytics_storage"],
            "label": "Analytics pl",
            "description": "Site usage pl",
        }

    @pytest.mark.parametrize(("requested", "expected"), [("pl", "pl"), ("en", "en"), ("de", "en")])
    def test_language(self, api_client, site_channel, banner, requested, expected):
        data = api_client.get(_banner_url(site_channel.idx), {"language": requested}).json()
        assert (data["language"], data["text"], data["categories"][0]["label"]) == (
            expected,
            f"We use cookies {expected}",
            f"Necessary {expected}",
        )

    def test_unknown_channel_404(self, api_client, banner):
        response = api_client.get(_banner_url("nope"))
        _assert_envelope(response, 404, "NOT_FOUND")
        assert "Cache-Control" not in response

    def test_banner_without_texts_returns_null(self, api_client, site_channel, banner):
        banner.cookie_banner.pop("texts_t9n")
        banner.save(update_fields=["cookie_banner"])
        data = api_client.get(_banner_url(site_channel.idx), {"language": "pl"}).json()
        assert (data["preferences_title"], data["close_label"]) == (None, None)

    def test_no_published_banner_404(self, api_client, channel, cookie_definition, make_cookie_version):
        make_cookie_version(cookie_definition, published=False)
        assert api_client.get(_banner_url(channel.idx)).status_code == 404

    def test_channel_isolation(self, api_client, channel, channel_2, make_cookie_version):
        scoped = AgreementDefinition.objects.create(slug="cookie-a", name="A", category="cookies")
        scoped.channels.add(channel)
        version = make_cookie_version(scoped)
        assert api_client.get(_banner_url(channel.idx)).json()["revision"] == version.pk
        assert api_client.get(_banner_url(channel_2.idx)).status_code == 404


@pytest.mark.django_db
class TestCookieConsentSubmit:
    def test_created(self, api_client, site_channel, banner):
        payload = _payload(banner, language="PL")
        response = api_client.post(_consent_url(site_channel.idx), payload, format="json")
        assert response.status_code == 201
        data = response.json()
        assert (data["consent_id"], data["revision"], data["language"], data["action"]) == (
            payload["consent_id"],
            banner.pk,
            "pl",
            "custom",
        )
        consent = CookieConsent.objects.get()
        assert (consent.channel_idx, consent.agreement_version, consent.language) == (site_channel.idx, banner, "pl")
        assert consent.categories == {"necessary": True, "analytics": False}

    @pytest.mark.parametrize(
        ("overrides", "error"),
        [
            ({"consent_id": "not-a-uuid"}, "VALIDATION_ERROR"),
            ({"action": "maybe"}, "VALIDATION_ERROR"),
            ({"categories": {}}, "VALIDATION_ERROR"),
            ({"categories": {"necessary": True}}, "INVALID_REQUEST"),
            ({"categories": {"necessary": True, "analytics": False, "marketing": False}}, "INVALID_REQUEST"),
            ({"categories": {"necessary": False, "analytics": False}}, "INVALID_REQUEST"),
            ({"action": "accept_all"}, "INVALID_REQUEST"),
            ({"action": "reject_all", "categories": {"necessary": True, "analytics": True}}, "INVALID_REQUEST"),
            ({"language": "pol"}, "VALIDATION_ERROR"),
            ({"language": "fr"}, "INVALID_REQUEST"),
            ({"language": "de"}, "INVALID_REQUEST"),
        ],
    )
    def test_validation_400(self, api_client, site_channel, banner, overrides, error):
        response = api_client.post(_consent_url(site_channel.idx), _payload(banner, **overrides), format="json")
        _assert_envelope(response, 400, error)
        assert not CookieConsent.objects.exists()

    def test_validation_details(self, api_client, site_channel, banner):
        payload = _payload(banner, consent_id="not-a-uuid")
        response = api_client.post(_consent_url(site_channel.idx), payload, format="json")
        data = _assert_envelope(response, 400, "VALIDATION_ERROR")
        assert [detail["field"] for detail in data["details"]] == ["consent_id"]
        assert data["details"][0]["location"] == "body"

    def test_malformed_json_400(self, api_client, site_channel, banner):
        response = api_client.post(_consent_url(site_channel.idx), "{", content_type="application/json")
        _assert_envelope(response, 400, "VALIDATION_ERROR")

    def test_unknown_channel_404(self, api_client, banner):
        response = api_client.post(_consent_url("nope"), _payload(banner), format="json")
        _assert_envelope(response, 404, "NOT_FOUND")

    def test_stale_revision_409(self, api_client, site_channel, cookie_definition, banner, make_cookie_version):
        draft = make_cookie_version(cookie_definition, published=False, languages=("pl", "en", "de"))
        version_service.publish_version(pk=draft.pk)
        response = api_client.post(_consent_url(site_channel.idx), _payload(banner), format="json")
        _assert_envelope(response, 409, "STALE_REVISION")
        assert not CookieConsent.objects.exists()

    def test_ignores_jwt(self, user_client, site_channel, banner):
        assert user_client.post(_consent_url(site_channel.idx), _payload(banner), format="json").status_code == 201

    def test_ignores_invalid_jwt(self, api_client, site_channel, banner):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
        assert api_client.post(_consent_url(site_channel.idx), _payload(banner), format="json").status_code == 201

    def test_throttled_429(self, api_client, site_channel, banner, monkeypatch):
        monkeypatch.setattr(CookieConsentThrottle, "THROTTLE_RATES", {"agreements_cookie_consent": "2/min"})
        responses = [api_client.post(_consent_url(site_channel.idx), _payload(banner), format="json") for _ in range(3)]
        assert [response.status_code for response in responses] == [201, 201, 429]
        _assert_envelope(responses[2], 429, "RATE_LIMITED")
        assert "Retry-After" in responses[2]


class TestCookieConsentThrottle:
    def test_wired_on_consent_view(self):
        assert CookieConsentThrottle in PublicCookieConsentViewSet.throttle_classes

    def test_fallback_without_config(self, monkeypatch):
        monkeypatch.setattr(CookieConsentThrottle, "THROTTLE_RATES", {})
        assert CookieConsentThrottle().get_rate() == "30/min"

    def test_fallback_with_malformed_rate(self, monkeypatch):
        monkeypatch.setattr(CookieConsentThrottle, "THROTTLE_RATES", {"agreements_cookie_consent": "lots"})
        assert CookieConsentThrottle().get_rate() == "30/min"

    def test_configured_rate_wins(self, monkeypatch):
        monkeypatch.setattr(CookieConsentThrottle, "THROTTLE_RATES", {"agreements_cookie_consent": "5/hour"})
        assert CookieConsentThrottle().rate == "5/hour"
