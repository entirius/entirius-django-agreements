# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""GDPR hooks: export by email, erasure pseudonymises the append-only rows."""

import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder

from django_agreements import gdpr
from django_agreements.models import ConsentRecord, ObjectionEvent, OrderAgreementSnapshot
from django_agreements.services.objection_service import record_objection

EMAIL = "lead@example.com"
TRICKY_EMAILS = (" Foo@Bar.PL ", "UPPER@EXAMPLE.COM", "zoë@exämple.test", "jan+leads@example.com", "\tTab@x.test\n")


def snapshot(version, email: str = EMAIL) -> OrderAgreementSnapshot:
    return OrderAgreementSnapshot.objects.create(
        email=email, agreement_version=version, body_snapshot="Terms accepted with the order", language="pl",
        ip_address="10.0.0.2", user_agent="Mozilla",
    )  # fmt: skip


@pytest.mark.django_db
def test_L17_gdpr_erase_pseudonymises_consent_and_objection_rows(channel, published_version):
    ConsentRecord.objects.create(
        email=EMAIL, agreement_version=published_version, granted=True, source="api", ip_address="10.0.0.1",
        user_agent="Mozilla", channel_idx="default-europe",
    )  # fmt: skip
    ConsentRecord.objects.create(
        email="other@example.com", agreement_version=published_version, granted=True, source="api"
    )
    record_objection(channel_idx="default-europe", email="Lead@Example.com", source="communicator", reason="STOP")

    exported = gdpr.gdpr_export(" LEAD@example.com ")
    counts = gdpr.gdpr_erase(EMAIL)

    assert len(exported["ConsentRecord"]) == len(exported["ObjectionEvent"]) == 1
    assert exported["ConsentRecord"][0]["ip_address"] == "10.0.0.1"
    json.dumps(exported, cls=DjangoJSONEncoder)
    assert counts == {"consent_records": 1, "objection_events": 1, "order_agreement_snapshots": 0}
    token = gdpr.anonymised_address(EMAIL)
    consent = ConsentRecord.objects.get(email=token)
    assert (consent.ip_address, consent.user_agent, consent.granted) == (None, "", True)
    assert ObjectionEvent.objects.get().email == token and ObjectionEvent.objects.get().reason == "STOP"
    assert not ConsentRecord.objects.filter(email__iexact=EMAIL).exists()
    assert ConsentRecord.objects.filter(email="other@example.com").exists()
    assert [row["email"] for row in gdpr.gdpr_export(EMAIL)["ConsentRecord"]] == [token]


@pytest.mark.django_db
def test_L17_order_agreement_snapshot_exported_and_pseudonymised(published_version):
    own, other = snapshot(published_version), snapshot(published_version, "other@example.com")
    accepted_at = own.created_at

    exported = gdpr.gdpr_export(" Lead@Example.com ")
    counts = gdpr.gdpr_erase(EMAIL)

    assert [row["id"] for row in exported["OrderAgreementSnapshot"]] == [own.pk]
    assert exported["OrderAgreementSnapshot"][0]["body_snapshot"] == "Terms accepted with the order"
    assert exported["OrderAgreementSnapshot"][0]["ip_address"] == "10.0.0.2"
    json.dumps(exported, cls=DjangoJSONEncoder)
    assert counts["order_agreement_snapshots"] == 1
    own.refresh_from_db()
    assert (own.email, own.ip_address, own.user_agent) == (gdpr.anonymised_address(EMAIL), None, "")
    assert (own.body_snapshot, own.created_at, own.granted) == ("Terms accepted with the order", accepted_at, True)
    other.refresh_from_db()
    assert (other.email, other.ip_address) == ("other@example.com", "10.0.0.2")


@pytest.mark.django_db
def test_L17_export_after_erase_matches_the_token(channel, published_version):
    ConsentRecord.objects.create(email=EMAIL, agreement_version=published_version, granted=True, source="api")
    record_objection(channel_idx="default-europe", email=EMAIL, source="communicator", reason="STOP")
    snapshot(published_version)
    gdpr.gdpr_erase(EMAIL)

    exported = gdpr.gdpr_export(EMAIL.upper())

    token = gdpr.anonymised_address(EMAIL)
    assert [len(rows) for rows in exported.values()] == [1, 1, 1]
    assert {row["email"] for rows in exported.values() for row in rows} == {token}
    assert gdpr.gdpr_export("other@example.com") == {
        "ConsentRecord": [],
        "ObjectionEvent": [],
        "OrderAgreementSnapshot": [],
    }


def test_token_parity_with_django_leads():
    leads_emails = pytest.importorskip("django_leads.utils.emails", reason="django_leads is not installed")
    for raw in TRICKY_EMAILS:
        assert gdpr.anonymised_address(raw) == leads_emails.anonymised_address(raw)
