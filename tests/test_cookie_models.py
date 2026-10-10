# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for the cookie consent log model and the cookies category."""

import uuid

import pytest
from django.db.models import ProtectedError

from django_agreements.models import AgreementDefinition, AgreementVersion, CookieConsent
from django_agreements.models.cookie_consent import ACTION_ACCEPT_ALL, ACTION_REJECT_ALL


def _consent(version, action=ACTION_ACCEPT_ALL):
    return CookieConsent.objects.create(
        consent_id=uuid.uuid4(),
        channel_idx="default-europe",
        language="pl",
        agreement_version=version,
        categories={"necessary": True, "analytics": action == ACTION_ACCEPT_ALL},
        action=action,
    )


@pytest.mark.django_db
class TestCookieConsent:
    def test_create_and_newest_first(self, cookie_definition, make_cookie_version):
        version = make_cookie_version(cookie_definition)
        first = _consent(version)
        second = _consent(version, action=ACTION_REJECT_ALL)
        assert list(CookieConsent.objects.all()) == [second, first]
        assert str(second) == f"{second.consent_id} reject_all {version}"

    def test_version_with_consent_cannot_be_deleted(self, cookie_definition, make_cookie_version):
        version = make_cookie_version(cookie_definition)
        _consent(version)
        with pytest.raises(ProtectedError):
            version.delete()


@pytest.mark.django_db
class TestCookieFields:
    def test_cookie_banner_defaults_to_empty_dict(self, definition):
        version = AgreementVersion.objects.create(definition=definition, version_number=1)
        assert version.cookie_banner == {}

    def test_cookies_category_passes_full_clean(self):
        definition = AgreementDefinition(slug="cookie-banner", name="Cookie banner", category="cookies")
        definition.full_clean()
