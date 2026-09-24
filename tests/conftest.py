# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from django_agreements.models import AgreementDefinition, AgreementVersion, Channel


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters live in the process-wide cache — isolate every test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username="admin", email="admin@test.com", password="admin123")


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(username="user", email="user@test.com", password="user123")


@pytest.fixture
def admin_client(api_client, admin_user):
    token = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return api_client


@pytest.fixture
def user_client(api_client, regular_user):
    token = RefreshToken.for_user(regular_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return api_client


@pytest.fixture
def channel(db):
    return Channel.objects.create(idx="default-europe", name="Default Europe")


@pytest.fixture
def channel_2(db):
    return Channel.objects.create(idx="us-store", name="US Store")


@pytest.fixture
def definition(db):
    return AgreementDefinition.objects.create(
        slug="terms-of-service", name="Terms of Service", category="mandatory", consent_channel="general", sort_order=1
    )


@pytest.fixture
def marketing_definition(db):
    return AgreementDefinition.objects.create(
        slug="marketing-email",
        name="Email Marketing Consent",
        category="marketing",
        consent_channel="email",
        sort_order=10,
    )


@pytest.fixture
def published_version(definition):
    from django.utils import timezone

    return AgreementVersion.objects.create(
        definition=definition,
        version_number=1,
        summary_t9n={"en": "I accept the Terms of Service", "pl": "Akceptuję regulamin"},
        published_at=timezone.now(),
        is_current=True,
    )


@pytest.fixture
def draft_version(definition):
    return AgreementVersion.objects.create(
        definition=definition,
        version_number=2,
        summary_t9n={"en": "I accept the updated Terms of Service"},
        published_at=None,
        is_current=False,
    )


@pytest.fixture
def marketing_published_version(marketing_definition):
    from django.utils import timezone

    return AgreementVersion.objects.create(
        definition=marketing_definition,
        version_number=1,
        summary_t9n={"en": "I consent to receive marketing emails"},
        published_at=timezone.now(),
        is_current=True,
    )


@pytest.fixture
def lang_pl(db):
    from django_regional.models import Language

    return Language.objects.create(iso2="pl", iso3="pol", name_en="Polish", name_pl="polski")


@pytest.fixture
def lang_en(db):
    from django_regional.models import Language

    return Language.objects.create(iso2="en", iso3="eng", name_en="English", name_pl="angielski")


@pytest.fixture
def make_clause_set(channel):
    """Create a clause set on `channel`; published + current unless published=False."""

    def _make(language, legal_basis="legitimate_interest", version=1, published=True, **texts):
        from django.utils import timezone

        from django_agreements.models import ClauseSet

        return ClauseSet.objects.create(
            channel=channel,
            legal_basis=legal_basis,
            language=language,
            version=version,
            info_clause=texts.get("info_clause", f"Info {language.iso2} for {{recipient_email}}"),
            optout_clause=texts.get("optout_clause", f"Opt-out {language.iso2}"),
            retention_clause=texts.get("retention_clause", f"Retention {language.iso2}"),
            is_current=published,
            published_at=timezone.now() if published else None,
        )

    return _make


def _cookie_banner(languages=("pl", "en")) -> dict:
    """A valid cookie banner config with texts in `languages`."""

    def t9n(text):
        return {lang: f"{text} {lang}" for lang in languages}

    buttons = {"accept_all": "Accept all", "reject_all": "Reject all", "customize": "Settings", "save": "Save"}
    return {
        "categories": [
            {
                "key": "necessary",
                "required": True,
                "consent_mode": [],
                "label_t9n": t9n("Necessary"),
                "description_t9n": t9n("Always on"),
            },
            {
                "key": "analytics",
                "required": False,
                "consent_mode": ["analytics_storage"],
                "label_t9n": t9n("Analytics"),
                "description_t9n": t9n("Site usage"),
            },
        ],
        "buttons_t9n": {lang: dict(buttons) for lang in languages},
    }


@pytest.fixture
def cookie_banner():
    """Builder of a valid cookie banner config: cookie_banner(languages=("pl", "en"))."""
    return _cookie_banner


@pytest.fixture
def cookie_definition(db):
    """A global (no channels) cookies definition."""
    return AgreementDefinition.objects.create(
        slug="cookie-banner", name="Cookie banner", category="cookies", consent_channel="web", sort_order=100
    )


@pytest.fixture
def make_cookie_version(db):
    """Create a cookies version with a valid banner; published + current unless published=False."""

    def _make(definition, published=True, languages=("pl", "en"), **overrides):
        from django.utils import timezone

        last = definition.versions.order_by("-version_number").first()
        fields = {
            "definition": definition,
            "version_number": last.version_number + 1 if last else 1,
            "summary_t9n": {lang: f"We use cookies {lang}" for lang in languages},
            "cookie_banner": _cookie_banner(languages),
            "published_at": timezone.now() if published else None,
            "is_current": published,
        }
        return AgreementVersion.objects.create(**{**fields, **overrides})

    return _make
