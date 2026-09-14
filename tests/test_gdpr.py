# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""GDPR hooks: export by email, erasure pseudonymises the append-only rows."""

import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder

from django_agreements import gdpr
from django_agreements.models import ConsentRecord, ObjectionEvent
from django_agreements.services.objection_service import record_objection

EMAIL = "lead@example.com"


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
    assert counts == {"consent_records": 1, "objection_events": 1}
    token = gdpr.anonymised_address(EMAIL)
    consent = ConsentRecord.objects.get(email=token)
    assert (consent.ip_address, consent.user_agent, consent.granted) == (None, "", True)
    assert ObjectionEvent.objects.get().email == token and ObjectionEvent.objects.get().reason == "STOP"
    assert not ConsentRecord.objects.filter(email__iexact=EMAIL).exists()
    assert ConsentRecord.objects.filter(email="other@example.com").exists()
    assert gdpr.gdpr_export(EMAIL) == {"ConsentRecord": [], "ObjectionEvent": []}
