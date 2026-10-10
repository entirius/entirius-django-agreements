# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Cookie banner config: schema validation, admin version API and publish guards."""

import pytest
from django.core.management import call_command
from django.urls import reverse

from django_agreements.models import AgreementDefinition, AgreementVersion, Channel


def _version_list_url(slug):
    return reverse("admin-version-list", kwargs={"slug": slug})


def _version_detail_url(pk):
    return reverse("admin-version-detail", kwargs={"pk": pk})


def _version_publish_url(pk):
    return reverse("admin-version-publish", kwargs={"pk": pk})


def _create(client, banner, summary=None, slug="cookie-banner"):
    payload = {"summary_t9n": summary or {"pl": "Cookies pl", "en": "Cookies en"}, "cookie_banner": banner}
    return client.post(_version_list_url(slug), payload, format="json")


def _language(iso2):
    from django_regional.models import Language

    return Language.objects.create(iso2=iso2, iso3=f"{iso2}x", name_en=iso2, name_pl=iso2)


def _channel(idx, *languages):
    channel = Channel.objects.create(idx=idx, name=idx)
    channel.languages.add(*languages)
    return channel


def _cookie_definition(slug, *channels):
    definition = AgreementDefinition.objects.create(slug=slug, name=slug, category="cookies", consent_channel="web")
    definition.channels.add(*channels)
    return definition


@pytest.mark.django_db
class TestCookieBannerSchema:
    def test_valid_config_round_trips(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        response = _create(admin_client, banner)
        assert response.status_code == 201
        assert response.json()["cookie_banner"] == banner
        assert AgreementVersion.objects.get(pk=response.json()["id"]).cookie_banner == banner

    def test_duplicate_key_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        banner["categories"][1]["key"] = "necessary"
        banner["categories"][1]["consent_mode"] = []
        response = _create(admin_client, banner)
        assert response.status_code == 400
        assert "unique" in str(response.json())

    def test_bad_key_pattern_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        banner["categories"][1]["key"] = "Analytics-1"
        assert _create(admin_client, banner).status_code == 400

    def test_unknown_consent_mode_signal_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        banner["categories"][1]["consent_mode"] = ["functionality_storage"]
        assert _create(admin_client, banner).status_code == 400

    def test_duplicate_consent_mode_signal_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        banner["categories"][1]["consent_mode"] = ["analytics_storage", "analytics_storage"]
        assert _create(admin_client, banner).status_code == 400

    def test_required_category_with_signals_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        banner["categories"][0]["consent_mode"] = ["ad_storage"]
        response = _create(admin_client, banner)
        assert response.status_code == 400
        assert "Required category" in str(response.json())

    def test_category_language_mismatch_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        del banner["categories"][1]["description_t9n"]["en"]
        response = _create(admin_client, banner)
        assert response.status_code == 400
        assert "analytics" in str(response.json())

    def test_buttons_language_mismatch_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        banner["buttons_t9n"]["de"] = dict(banner["buttons_t9n"]["en"])
        assert _create(admin_client, banner).status_code == 400

    def test_missing_button_label_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        del banner["buttons_t9n"]["pl"]["save"]
        response = _create(admin_client, banner)
        assert response.status_code == 400
        assert "save" in str(response.json())

    def test_missing_texts_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        del banner["texts_t9n"]
        response = _create(admin_client, banner)
        assert response.status_code == 400
        assert "texts_t9n" in str(response.json())

    def test_empty_close_label_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        banner["texts_t9n"]["pl"]["close_label"] = ""
        response = _create(admin_client, banner)
        assert response.status_code == 400
        assert "close_label" in str(response.json())

    def test_texts_language_mismatch_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        del banner["texts_t9n"]["en"]
        response = _create(admin_client, banner)
        assert response.status_code == 400
        assert "texts_t9n" in str(response.json())

    def test_invalid_language_key_returns_400(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner(languages=("PL",))
        assert _create(admin_client, banner, summary={"pl": "Cookies"}).status_code == 400

    def test_html_is_sanitised(self, admin_client, cookie_definition, cookie_banner):
        banner = cookie_banner()
        banner["categories"][1]["description_t9n"]["pl"] = (
            '<script>alert(1)</script><a href="/pl/cookies">Polityka</a> <a href="javascript:alert(1)">x</a>'
        )
        banner["buttons_t9n"]["en"]["save"] = "<b>Save</b><script>x</script>"
        response = _create(admin_client, banner)
        assert response.status_code == 201
        stored = response.json()["cookie_banner"]
        assert stored["categories"][1]["description_t9n"]["pl"] == 'alert(1)<a href="/pl/cookies">Polityka</a> <a>x</a>'
        assert stored["buttons_t9n"]["en"]["save"] == "<b>Save</b>x"

    def test_cookie_banner_on_mandatory_definition_returns_400(self, admin_client, definition, cookie_banner):
        response = _create(admin_client, cookie_banner(), slug=definition.slug)
        assert response.status_code == 400
        assert "category=cookies" in response.json()["detail"]

    def test_patch_cookie_banner_on_mandatory_draft_returns_400(self, admin_client, draft_version, cookie_banner):
        response = admin_client.patch(
            _version_detail_url(draft_version.pk), {"cookie_banner": cookie_banner()}, format="json"
        )
        assert response.status_code == 400

    def test_patch_draft_updates_cookie_banner(
        self, admin_client, cookie_definition, make_cookie_version, cookie_banner
    ):
        version = make_cookie_version(cookie_definition, published=False, cookie_banner={})
        banner = cookie_banner()
        response = admin_client.patch(_version_detail_url(version.pk), {"cookie_banner": banner}, format="json")
        assert response.status_code == 200
        assert response.json()["cookie_banner"] == banner

    def test_patch_published_version_returns_400(
        self, admin_client, cookie_definition, make_cookie_version, cookie_banner
    ):
        version = make_cookie_version(cookie_definition)
        response = admin_client.patch(
            _version_detail_url(version.pk), {"cookie_banner": cookie_banner(languages=("en",))}, format="json"
        )
        assert response.status_code == 400
        version.refresh_from_db()
        assert set(version.cookie_banner["buttons_t9n"]) == {"pl", "en"}


@pytest.mark.django_db
class TestCookiePublishGuards:
    def _publish(self, client, version):
        return client.post(_version_publish_url(version.pk))

    def test_happy_publish_sets_is_current(self, admin_client, cookie_definition, make_cookie_version):
        previous = make_cookie_version(cookie_definition)
        draft = make_cookie_version(cookie_definition, published=False)
        response = self._publish(admin_client, draft)
        assert response.status_code == 200
        assert response.json()["is_current"] is True
        previous.refresh_from_db()
        assert previous.is_current is False

    def test_empty_config_returns_400(self, admin_client, cookie_definition, make_cookie_version):
        draft = make_cookie_version(cookie_definition, published=False, cookie_banner={})
        response = self._publish(admin_client, draft)
        assert response.status_code == 400
        assert "Invalid cookie banner config" in response.json()["detail"]
        draft.refresh_from_db()
        assert draft.published_at is None

    def test_summary_language_mismatch_returns_400(self, admin_client, cookie_definition, make_cookie_version):
        draft = make_cookie_version(cookie_definition, published=False, summary_t9n={"pl": "Cookies"})
        response = self._publish(admin_client, draft)
        assert response.status_code == 400
        assert "summary_t9n" in response.json()["detail"]

    def test_global_scope_language_not_covered_returns_400(
        self, admin_client, cookie_definition, make_cookie_version, lang_pl
    ):
        _channel("de-store", _language("DE"), lang_pl)
        draft = make_cookie_version(cookie_definition, published=False)
        response = self._publish(admin_client, draft)
        assert response.status_code == 400
        assert "['de']" in response.json()["detail"]

    def test_channel_scope_language_not_covered_returns_400(self, admin_client, make_cookie_version, lang_pl):
        definition = _cookie_definition("cookies-de", _channel("de-store", _language("de"), lang_pl))
        draft = make_cookie_version(definition, published=False)
        assert self._publish(admin_client, draft).status_code == 400

    def test_channel_scope_ignores_other_channels(self, admin_client, make_cookie_version, lang_pl, lang_en):
        _channel("de-store", _language("de"))
        definition = _cookie_definition("cookies-pl", _channel("pl-store", lang_pl, lang_en))
        draft = make_cookie_version(definition, published=False)
        assert self._publish(admin_client, draft).status_code == 200

    def test_channel_without_languages_passes(self, admin_client, cookie_definition, make_cookie_version, channel):
        draft = make_cookie_version(cookie_definition, published=False)
        assert self._publish(admin_client, draft).status_code == 200

    def test_second_global_definition_returns_400(self, admin_client, cookie_definition, make_cookie_version):
        make_cookie_version(cookie_definition)
        draft = make_cookie_version(_cookie_definition("cookie-banner-2"), published=False)
        response = self._publish(admin_client, draft)
        assert response.status_code == 400
        assert "Another active cookies definition" in response.json()["detail"]

    def test_inactive_global_definition_does_not_overlap(self, admin_client, cookie_definition, make_cookie_version):
        AgreementDefinition.objects.filter(pk=cookie_definition.pk).update(is_active=False)
        draft = make_cookie_version(_cookie_definition("cookie-banner-2"), published=False)
        assert self._publish(admin_client, draft).status_code == 200

    def test_global_and_channel_specific_publish(self, admin_client, cookie_definition, make_cookie_version, channel):
        make_cookie_version(cookie_definition)
        draft = make_cookie_version(_cookie_definition("cookies-eu", channel), published=False)
        assert self._publish(admin_client, draft).status_code == 200

    def test_definitions_sharing_a_channel_return_400(self, admin_client, make_cookie_version, channel, channel_2):
        _cookie_definition("cookies-eu", channel)
        draft = make_cookie_version(_cookie_definition("cookies-all", channel, channel_2), published=False)
        assert self._publish(admin_client, draft).status_code == 400

    def test_non_cookie_definition_skips_banner_checks(self, admin_client, draft_version):
        assert self._publish(admin_client, draft_version).status_code == 200

    def test_shipped_fixture_publishes(self, admin_client, lang_pl, lang_en):
        _channel("pl-store", lang_pl, lang_en)
        call_command("loaddata", "cookie_banner", verbosity=0)
        response = admin_client.post(_version_publish_url(100))
        assert response.status_code == 200
        assert response.json()["definition_slug"] == "cookie-banner"
