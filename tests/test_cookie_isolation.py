# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The cookie banner (category=cookies) never shows up in the email-keyed consent features."""

import pytest
from django.urls import reverse

from django_agreements.models import AgreementDefinition
from django_agreements.services import consent_service

EMAIL = "user@test.com"
COOKIES = "cookie-banner"
TERMS = "terms-of-service"


@pytest.fixture
def banner(cookie_definition, make_cookie_version):
    """Published global cookie banner offered in the checkout context, next to published terms."""
    cookie_definition.display_contexts = ["checkout"]
    cookie_definition.save()
    return make_cookie_version(cookie_definition)


@pytest.fixture
def terms(definition, published_version):
    definition.display_contexts = ["checkout"]
    definition.save()
    return definition


def _slugs(response):
    return {row["slug"] for row in response.json()["results"]}


@pytest.mark.django_db
class TestServices:
    def test_consent_status_has_no_cookies(self, banner, terms):
        assert set(consent_service.get_consent_status(EMAIL)) == {TERMS}

    def test_person_detail_has_no_cookies(self, banner, terms):
        assert set(consent_service.get_person_detail(EMAIL)["current_status"]) == {TERMS}

    def test_definitions_for_user_has_no_cookies(self, banner, terms):
        rows = consent_service.get_definitions_for_user(channel_idx="default-europe", context="checkout")
        assert {row["slug"] for row in rows} == {TERMS}

    def test_record_consent_treats_cookies_as_unknown(self, banner):
        with pytest.raises(AgreementDefinition.DoesNotExist):
            consent_service.record_consent(email=EMAIL, slug=COOKIES, granted=True, source="checkout")

    def test_record_multiple_consents_treats_cookies_as_unknown(self, banner):
        with pytest.raises(ValueError, match=f"Agreement '{COOKIES}' not found."):
            consent_service.record_multiple_consents(
                email=EMAIL, agreements=[{"slug": COOKIES, "granted": True}], source="checkout"
            )


@pytest.mark.django_db
class TestApi:
    def test_public_definitions_hide_cookies(self, api_client, banner, terms):
        url = reverse("public-definition-list", kwargs={"channel_idx": "default-europe"})
        assert _slugs(api_client.get(url)) == {TERMS}

    def test_public_for_user_hides_cookies(self, api_client, banner, terms):
        url = reverse("public-definition-for-user", kwargs={"channel_idx": "default-europe"})
        assert _slugs(api_client.get(url, {"context": "checkout"})) == {TERMS}

    def test_admin_definitions_keep_cookies(self, admin_client, banner, terms):
        assert _slugs(admin_client.get(reverse("admin-definition-list"))) == {COOKIES, TERMS}

    def test_public_consent_submit_with_cookies_slug_is_400(self, api_client, banner):
        url = reverse("public-consent-submit", kwargs={"channel_idx": "default-europe"})
        payload = {"email": EMAIL, "agreements": [{"slug": COOKIES, "granted": True}], "source": "checkout"}
        assert api_client.post(url, payload, format="json").status_code == 400
