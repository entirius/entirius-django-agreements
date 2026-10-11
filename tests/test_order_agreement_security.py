# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The public order-agreement write is throttled, bound to a real order and idempotent per order."""

import sys
import types
import uuid
from unittest.mock import patch

import pytest
from django.urls import reverse

from django_agreements.models import ConsentRecord, OrderAgreementSnapshot
from django_agreements.services import order_agreement_service

pytestmark = pytest.mark.django_db

EMAIL = "customer@test.com"
BODY = {"email": EMAIL, "slugs": ["terms-of-service"], "language": "en"}


def _url(order_id=None, channel_idx="default-europe"):
    kwargs = {"channel_idx": channel_idx, "order_id": str(order_id or uuid.uuid4())}
    return reverse("public-order-agreements", kwargs=kwargs)


def _order_emails(emails):
    return patch.object(order_agreement_service, "_order_emails", return_value=emails)


def test_write_is_throttled_after_its_limit(api_client):
    statuses = [api_client.post(_url(), {}, format="json").status_code for _ in range(21)]
    assert 429 not in statuses[:20]
    assert statuses[20] == 429


@pytest.mark.parametrize("order_emails", [[], ["someone.else@test.com"]], ids=["no-such-order", "wrong-email"])
def test_unknown_order_and_foreign_email_get_the_same_404(api_client, published_version, order_emails):
    with _order_emails(order_emails) as lookup:
        response = api_client.post(_url(), BODY, format="json")
    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found."}
    assert lookup.call_args.args[1] == "default-europe"
    assert not OrderAgreementSnapshot.objects.exists()
    assert not ConsentRecord.objects.exists()


def test_malformed_order_id_is_not_an_order(api_client, published_version):
    url = reverse("public-order-agreements", kwargs={"channel_idx": "default-europe", "order_id": "not-a-uuid"})
    assert api_client.post(url, BODY, format="json").status_code == 404
    assert not OrderAgreementSnapshot.objects.exists()


def test_order_email_matches_case_insensitively(api_client, published_version):
    with _order_emails([None, " Customer@Test.com "]):
        response = api_client.post(_url(), BODY, format="json")
    assert response.status_code == 201
    assert OrderAgreementSnapshot.objects.count() == 1


def test_without_checkout_the_write_is_accepted(api_client, published_version):
    with _order_emails(None):
        assert api_client.post(_url(), BODY, format="json").status_code == 201


class _RaisingModule(types.ModuleType):
    def __getattr__(self, name):
        raise RuntimeError("Model class django_checkout.models.Order isn't in an application in INSTALLED_APPS.")


@pytest.mark.parametrize("models_module", [None, _RaisingModule("django_checkout.models")], ids=["absent", "disabled"])
def test_checkout_absent_or_not_enabled_means_no_order_check(monkeypatch, models_module):
    monkeypatch.setitem(sys.modules, "django_checkout", types.ModuleType("django_checkout"))
    monkeypatch.setitem(sys.modules, "django_checkout.models", models_module)
    assert order_agreement_service._order_emails(uuid.uuid4(), "default-europe") is None


class _FakeOrders:
    """Stands in for ``Order.objects``: records the filter and answers with one row or none."""

    def __init__(self, row):
        self.row, self.filters = row, None

    def filter(self, **filters):
        self.filters = filters
        return self

    def values_list(self, *fields):
        self.fields = fields
        return self

    def first(self):
        return self.row


@pytest.mark.parametrize(
    ("row", "emails"),
    [
        (("a@test.com", "b@test.com"), ["a@test.com", "b@test.com"]),
        ((None, "b@test.com"), [None, "b@test.com"]),
        (None, []),
    ],
    ids=["both", "one-null", "no-row"],
)
def test_order_lookup_is_scoped_to_the_order_and_the_channel(monkeypatch, row, emails):
    orders = _FakeOrders(row)
    models = types.ModuleType("django_checkout.models")
    models.Order = types.SimpleNamespace(objects=orders)
    monkeypatch.setitem(sys.modules, "django_checkout", types.ModuleType("django_checkout"))
    monkeypatch.setitem(sys.modules, "django_checkout.models", models)
    order_id = uuid.uuid4()

    assert order_agreement_service._order_emails(order_id, "default-europe") == emails
    assert orders.filters == {"order_id": order_id, "channel__idx": "default-europe"}
    assert orders.fields == ("billing_email", "shipping_email")


def test_concurrent_duplicate_write_is_absorbed(api_client, published_version):
    url = _url()
    with _order_emails(None):
        api_client.post(url, BODY, format="json")
        with patch.object(order_agreement_service, "_recorded_version_ids", return_value=set()):
            assert api_client.post(url, BODY, format="json").status_code == 201
    assert OrderAgreementSnapshot.objects.count() == 1
    assert ConsentRecord.objects.count() == 1


def test_second_write_for_the_same_order_creates_no_duplicates(api_client, published_version):
    url = _url()
    with _order_emails(None):
        first = api_client.post(url, BODY, format="json")
        second = api_client.post(url, {**BODY, "slugs": ["terms-of-service", "terms-of-service"]}, format="json")
    assert (first.status_code, second.status_code) == (201, 201)
    assert OrderAgreementSnapshot.objects.count() == 1
    assert ConsentRecord.objects.count() == 1
