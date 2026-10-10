# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Every public consent action that creates state or sends mail is throttled (the cache is cleared per test).

Throttles run before the handler, so refused bodies count too: a burst of empty requests reaches the limit.
"""

from unittest.mock import patch

import pytest
from django.urls import reverse

from django_agreements.api.public.throttling import ConsentSubmitThrottle

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("name", "method", "limit"),
    [
        ("public-consent-submit", "post", 20),
        ("public-consent-withdraw", "post", 20),
        ("public-consent-confirm", "post", 10),
        ("public-consent-unsubscribe", "get", 10),
    ],
)
def test_action_is_throttled_after_its_limit(api_client, channel, name, method, limit):
    url = reverse(name, kwargs={"channel_idx": channel.idx})
    statuses = [getattr(api_client, method)(url, {}, format="json").status_code for _ in range(limit + 1)]
    assert 429 not in statuses[:limit]
    assert statuses[limit] == 429


def test_throttle_is_per_address(api_client, channel):
    url = reverse("public-consent-confirm", kwargs={"channel_idx": channel.idx})
    for _ in range(10):
        api_client.post(url, {}, format="json", REMOTE_ADDR="192.0.2.10")
    assert api_client.post(url, {}, format="json", REMOTE_ADDR="192.0.2.10").status_code == 429
    assert api_client.post(url, {}, format="json", REMOTE_ADDR="192.0.2.99").status_code != 429


@pytest.mark.parametrize(
    ("rates", "expected"),
    [
        ({}, "20/min"),
        ({"agreements_consent": "3/hour"}, "3/hour"),
        ({"agreements_consent": None}, "20/min"),
        ({"agreements_consent": "garbage"}, "20/min"),
    ],
)
def test_scope_overrides_and_the_fallback_holds(rates, expected):
    with patch.object(ConsentSubmitThrottle, "THROTTLE_RATES", rates):
        assert ConsentSubmitThrottle().rate == expected
