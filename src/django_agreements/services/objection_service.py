# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Objection (opt-out) audit log — append-only, independent of ConsentRecord."""

from django_agreements.models import Channel, ClauseSet, ObjectionEvent


def record_objection(
    *, channel_idx: str, email: str, source: str, reason: str = "", clause_set: ClauseSet | None = None
) -> ObjectionEvent:
    """Append one ObjectionEvent for the channel. Raises Channel.DoesNotExist."""
    channel = Channel.objects.get(idx=channel_idx)
    return ObjectionEvent.objects.create(
        channel=channel, email=email, source=source, reason=reason, clause_set=clause_set
    )
