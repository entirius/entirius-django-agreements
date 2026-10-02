# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import secrets

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from django_agreements.models import AgreementDefinition, AgreementVersion, Channel


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


@pytest.fixture
def make_api_key(settings):
    """Configure the key the module accepts today and return its raw value.

    agreements has one key, ``settings.AGREEMENTS_API_KEY`` — not bound to a channel or a scope, so both
    arguments are accepted and ignored. The key contract tests go through this helper only, so moving the check
    onto another key store changes this function, never the assertions. Values are random and never printed.
    """

    def make_api_key(channel=None, scope: str | None = None) -> str:
        raw = secrets.token_hex(32)
        settings.AGREEMENTS_API_KEY = raw
        return raw

    return make_api_key
