# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The access path: with django_access installed the subscribe key is an access token (``agreements.subscribe``).

``AGREEMENTS_API_KEY`` reaches it only through the import (``make_api_key``); the setting is never compared on this
path.
"""

import secrets
from datetime import timedelta
from unittest.mock import patch

import pytest

pytest.importorskip("django_access")

from django.urls import reverse  # noqa: E402
from django.utils import timezone  # noqa: E402
from django_access.models import ApiToken, Application  # noqa: E402
from django_access.services.access_service import Actor  # noqa: E402
from django_access.services.tokens import hash_key, issue_token, revoke_token  # noqa: E402

from django_agreements.api.public.authentication import SUBSCRIBE_SCOPE  # noqa: E402

pytestmark = pytest.mark.django_db

CHANNEL, OTHER = "default-europe", "us-store"
SYSTEM = Actor()


@pytest.fixture(autouse=True)
def _marketing(channel, channel_2, marketing_published_version):
    """Both channels exist and the marketing definition is published, so a passing key reaches the service."""


@pytest.fixture(autouse=True)
def _no_confirmation_email():
    with patch("django_agreements.api.public.views.consent_views._send_confirmation_email"):
        yield


@pytest.fixture
def issue(db):
    application = Application.objects.create(name="agreements-tests")

    def issue(scope: str = SUBSCRIBE_SCOPE, channel_idx: str | None = CHANNEL) -> tuple[ApiToken, str]:
        return issue_token(application, scopes=[scope], channel_idx=channel_idx, expires_at=None, actor=SYSTEM)

    return issue


def _subscribe(api_client, key: str | None, channel_idx: str = CHANNEL, header: str = "HTTP_X_API_KEY"):
    url = reverse("public-newsletter-subscribe", kwargs={"channel_idx": channel_idx})
    headers = {} if key is None else {header: key}
    return api_client.post(url, {"email": "subscriber@example.com"}, format="json", **headers)


def test_token_subscribes_on_its_channel(api_client, issue):
    token, raw = issue()
    assert _subscribe(api_client, raw).status_code == 201
    token.refresh_from_db()
    assert token.last_used_at is not None


def test_unpinned_token_subscribes_on_any_channel(api_client, issue):
    _, raw = issue(channel_idx=None)
    assert _subscribe(api_client, raw, channel_idx=OTHER).status_code == 201


def test_pinned_token_on_another_channel_is_refused(api_client, issue):
    _, raw = issue(channel_idx=OTHER)
    assert _subscribe(api_client, raw).status_code == 401


def test_revoked_token_is_refused(api_client, issue):
    token, raw = issue()
    assert _subscribe(api_client, raw).status_code == 201
    revoke_token(token, actor=SYSTEM)
    assert _subscribe(api_client, raw).status_code == 401


def test_setting_not_imported_is_refused(api_client, settings):
    settings.AGREEMENTS_API_KEY = secrets.token_hex(32)
    assert _subscribe(api_client, settings.AGREEMENTS_API_KEY).status_code == 401


def test_imported_setting_without_expiry_keeps_working(api_client, make_api_key):
    raw = make_api_key()
    token = ApiToken.objects.get(key_hash=hash_key(raw))
    assert (token.legacy, token.expires_at, token.scopes) == (True, None, [SUBSCRIBE_SCOPE])
    assert _subscribe(api_client, raw).status_code == 201


def test_admin_key_header_never_stands_in(api_client, issue):
    _, raw = issue()
    assert _subscribe(api_client, raw, header="HTTP_X_API_ADMIN_KEY").status_code == 401


def _failing_keys(issue) -> dict[str, str]:
    """The five ways a key fails, each a real token except ``unknown``."""
    expired, expired_raw = issue()
    ApiToken.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    revoked, revoked_raw = issue()
    revoke_token(revoked, actor=SYSTEM)
    return {
        "unknown": "ent_api_" + secrets.token_urlsafe(32),
        "expired": expired_raw,
        "revoked": revoked_raw,
        "wrong scope": issue("contact_forms.submit")[1],
        "wrong channel": issue(channel_idx=OTHER)[1],
    }


def test_every_failure_gives_the_no_key_response(api_client, issue):
    missing = _subscribe(api_client, None)
    expected = (missing.status_code, missing.content)
    outcomes = {kind: _subscribe(api_client, raw) for kind, raw in _failing_keys(issue).items()}
    answers = {kind: (response.status_code, response.content) for kind, response in outcomes.items()}
    assert set(answers.values()) == {expected}, answers
    assert expected[0] == 401
