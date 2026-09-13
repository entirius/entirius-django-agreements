# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for the append-only objection log."""

import pytest
from django.db.models import ProtectedError

from django_agreements.models import Channel, ConsentRecord, ObjectionEvent
from django_agreements.services.objection_service import record_objection


@pytest.mark.django_db
class TestRecordObjection:
    def test_C23_objection_recorded(self, channel, make_clause_set, lang_pl):
        clause_set = make_clause_set(lang_pl)
        first = record_objection(
            channel_idx="default-europe",
            email="lead@example.com",
            source="communicator",
            reason="STOP reply",
            clause_set=clause_set,
        )
        second = record_objection(channel_idx="default-europe", email="lead@example.com", source="communicator")
        assert ObjectionEvent.objects.count() == 2
        assert (first.channel, first.email, first.reason, first.clause_set) == (
            channel,
            "lead@example.com",
            "STOP reply",
            clause_set,
        )
        assert (second.reason, second.clause_set) == ("", None)
        assert ConsentRecord.objects.count() == 0

    def test_C23_objection_keeps_clause_set_on_delete_attempt(self, channel, make_clause_set, lang_pl):
        clause_set = make_clause_set(lang_pl, published=False)
        objection = record_objection(
            channel_idx="default-europe", email="lead@example.com", source="manual", clause_set=clause_set
        )
        with pytest.raises(ProtectedError):
            clause_set.delete()
        objection.refresh_from_db()
        assert objection.clause_set == clause_set

    def test_unknown_channel_raises(self, db):
        with pytest.raises(Channel.DoesNotExist):
            record_objection(channel_idx="nope", email="a@example.com", source="manual")
