# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Characterization of today's agreements key contract (X-API-KEY on newsletter subscribe).

The key is ``settings.AGREEMENTS_API_KEY``: one value, no channel, no scope. Pins what subscribe answers — quirks
included — so moving the check onto another key store cannot change a status or a body. Keys come only from the
``make_api_key`` helper.
"""

import secrets
from unittest.mock import patch

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

SUBSCRIBE_BODY = {"email": "subscriber@example.com"}


@pytest.fixture(autouse=True)
def _marketing(channel, channel_2, marketing_published_version):
    """Both channels exist and the marketing definition is published, so a passing key reaches the service."""


@pytest.fixture(autouse=True)
def _no_confirmation_email():
    with patch("django_agreements.api.public.views.consent_views._send_confirmation_email"):
        yield


def _subscribe(api_client, key: str | None, channel_idx: str = "default-europe"):
    url = reverse("public-newsletter-subscribe", kwargs={"channel_idx": channel_idx})
    headers = {} if key is None else {"HTTP_X_API_KEY": key}
    return api_client.post(url, SUBSCRIBE_BODY, format="json", **headers)


def test_no_jwt_and_no_key_is_401(api_client, make_api_key):
    make_api_key()
    response = _subscribe(api_client, None)
    assert response.status_code == 401
    assert response.json() == {"detail": "API key or authentication required."}


def test_wrong_key_is_refused_like_no_key(api_client, make_api_key):
    make_api_key()
    missing = _subscribe(api_client, None)
    wrong_key = secrets.token_hex(32)
    wrong = _subscribe(api_client, wrong_key)
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
    assert wrong_key not in wrong.content.decode()


def test_right_key_subscribes(api_client, make_api_key):
    response = _subscribe(api_client, make_api_key())
    assert response.status_code == 201
    assert response.json() == {"detail": "If eligible, a confirmation will be sent."}


def test_key_is_not_bound_to_a_channel(api_client, make_api_key):
    assert _subscribe(api_client, make_api_key(), channel_idx="us-store").status_code == 201


def test_customer_jwt_subscribes_without_a_key(user_client, make_api_key):
    make_api_key()
    assert _subscribe(user_client, None).status_code == 201


def test_public_definitions_answer_without_a_key(api_client, make_api_key):
    make_api_key()
    response = api_client.get(reverse("public-definition-list", kwargs={"channel_idx": "default-europe"}))
    assert response.status_code == 200


@pytest.fixture
def without_access():
    """Force the legacy branch of the key check whichever way the suite runs."""
    with patch("django_agreements.api.public.authentication.apps.is_installed", return_value=False):
        yield


def test_legacy_setting_key_subscribes(api_client, settings, without_access):
    settings.AGREEMENTS_API_KEY = secrets.token_hex(32)
    assert _subscribe(api_client, settings.AGREEMENTS_API_KEY).status_code == 201


def test_legacy_wrong_key_is_refused(api_client, settings, without_access):
    settings.AGREEMENTS_API_KEY = secrets.token_hex(32)
    assert _subscribe(api_client, secrets.token_hex(32)).status_code == 401


def test_legacy_empty_setting_refuses_every_key(api_client, settings, without_access):
    settings.AGREEMENTS_API_KEY = ""
    assert _subscribe(api_client, "anything").status_code == 401


def test_subscribe_is_throttled_for_anonymous_callers(api_client, make_api_key):
    raw = make_api_key()
    statuses = [_subscribe(api_client, raw).status_code for _ in range(6)]
    assert statuses == [201] * 5 + [429]
