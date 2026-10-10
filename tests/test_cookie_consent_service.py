# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Cookie consent service: banner resolution, language fallback, decision validation."""

import re
import uuid

import pytest

from django_agreements.models import AgreementDefinition, AgreementVersion, Channel, CookieConsent
from django_agreements.services import cookie_consent_service as service

ALL_TRUE = {"necessary": True, "analytics": True}
OPTIONAL_FALSE = {"necessary": True, "analytics": False}


def _cookie_definition(slug, *channels, sort_order=100):
    definition = AgreementDefinition.objects.create(
        slug=slug, name=slug, category="cookies", consent_channel="web", sort_order=sort_order
    )
    definition.channels.add(*channels)
    return definition


def _record(channel_idx, version, **overrides):
    fields = {
        "channel_idx": channel_idx,
        "consent_id": uuid.uuid4(),
        "revision": version.pk,
        "language": "pl",
        "action": "accept_all",
        "categories": dict(ALL_TRUE),
    }
    return service.record(**{**fields, **overrides})


@pytest.mark.django_db
class TestGetBanner:
    def test_channel_specific_beats_global(self, channel, cookie_definition, make_cookie_version):
        make_cookie_version(cookie_definition)
        specific = make_cookie_version(_cookie_definition("cookie-specific", channel, sort_order=500))
        assert service.get_banner(channel.idx) == (channel, specific)

    def test_global_serves_any_existing_channel(self, channel, channel_2, cookie_definition, make_cookie_version):
        version = make_cookie_version(cookie_definition)
        assert service.get_banner(channel.idx)[1] == version
        assert service.get_banner(channel_2.idx)[1] == version

    def test_channel_scoped_definition_invisible_on_other_channel(self, channel, channel_2, make_cookie_version):
        make_cookie_version(_cookie_definition("cookie-a", channel))
        with pytest.raises(AgreementVersion.DoesNotExist):
            service.get_banner(channel_2.idx)

    def test_unknown_channel(self, cookie_definition, make_cookie_version):
        make_cookie_version(cookie_definition)
        with pytest.raises(Channel.DoesNotExist):
            service.get_banner("nope")

    def test_no_current_version(self, channel, cookie_definition, make_cookie_version):
        make_cookie_version(cookie_definition, published=False)
        with pytest.raises(AgreementVersion.DoesNotExist):
            service.get_banner(channel.idx)

    def test_inactive_definition(self, channel, cookie_definition, make_cookie_version):
        make_cookie_version(cookie_definition)
        AgreementDefinition.objects.filter(pk=cookie_definition.pk).update(is_active=False)
        with pytest.raises(AgreementVersion.DoesNotExist):
            service.get_banner(channel.idx)


@pytest.mark.django_db
class TestResolveLanguage:
    @pytest.fixture
    def version(self, cookie_definition, make_cookie_version):
        return make_cookie_version(cookie_definition, languages=("pl", "en", "de"))

    def test_requested(self, channel, version):
        assert service.resolve_language(channel, version, "EN") == "en"

    def test_channel_default(self, channel, version, lang_en):
        channel.default_language = lang_en
        channel.save()
        assert service.resolve_language(channel, version, "fr") == "en"

    def test_first_key(self, channel, version):
        assert service.resolve_language(channel, version, None) == "pl"

    def test_requested_outside_channel_languages_falls_back(self, channel, version, lang_pl, lang_en):
        channel.default_language = lang_en
        channel.save()
        channel.languages.add(lang_pl)
        assert service.resolve_language(channel, version, "de") == "en"


@pytest.mark.django_db
class TestRecord:
    @pytest.fixture
    def version(self, cookie_definition, make_cookie_version):
        return make_cookie_version(cookie_definition)

    @pytest.mark.parametrize(
        ("action", "categories"),
        [("accept_all", ALL_TRUE), ("reject_all", OPTIONAL_FALSE), ("custom", ALL_TRUE), ("withdraw", OPTIONAL_FALSE)],
    )
    def test_happy_path_stores_row(self, channel, version, action, categories):
        consent = _record(channel.idx, version, action=action, categories=dict(categories), language="en")
        stored = CookieConsent.objects.get()
        assert stored == consent
        assert (stored.channel_idx, stored.language, stored.agreement_version, stored.action) == (
            channel.idx,
            "en",
            version,
            action,
        )
        assert stored.categories == categories

    @pytest.mark.parametrize(
        ("action", "categories", "message"),
        [
            ("custom", {"necessary": True}, "missing: ['analytics']"),
            ("custom", {**ALL_TRUE, "marketing": False}, "unknown: ['marketing']"),
            ("custom", {"necessary": False, "analytics": False}, "Required categories"),
            ("accept_all", OPTIONAL_FALSE, "accept_all"),
            ("reject_all", ALL_TRUE, "reject_all"),
            ("withdraw", ALL_TRUE, "withdraw"),
        ],
    )
    def test_invalid_choice(self, channel, version, action, categories, message):
        with pytest.raises(ValueError, match=re.escape(message)):
            _record(channel.idx, version, action=action, categories=dict(categories))
        assert not CookieConsent.objects.exists()

    def test_stale_revision(self, channel, cookie_definition, version, make_cookie_version):
        AgreementVersion.objects.filter(pk=version.pk).update(is_current=False)
        current = make_cookie_version(cookie_definition)
        with pytest.raises(service.StaleRevisionError) as exc_info:
            _record(channel.idx, version)
        assert exc_info.value.current_revision == current.pk

    def test_language_not_in_version(self, channel, version):
        with pytest.raises(ValueError, match="not available"):
            _record(channel.idx, version, language="de")

    def test_language_outside_channel_languages(self, channel, version, lang_pl):
        channel.languages.add(lang_pl)
        with pytest.raises(ValueError, match="not a language of channel"):
            _record(channel.idx, version, language="en")
