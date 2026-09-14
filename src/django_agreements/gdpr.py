# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""GDPR hooks (art. 15 export, art. 17 erasure) discovered by `django_leads.gdpr.registry`.

`ConsentRecord`, `ObjectionEvent` and `OrderAgreementSnapshot` are append-only; erasure deliberately bypasses that
with queryset `update()`: the rows stay as the audit trail (what was consented, objected to or accepted with an
order, when), only the person is pseudonymised — email → the token leads and communicator use, IP and user agent
dropped. A snapshot keeps its accepted text and timestamps (order-retention obligation)."""

import hashlib
from typing import Any

from django.db import transaction
from django.db.models import Q

from django_agreements import settings as agreements_settings
from django_agreements.models import ConsentRecord, ObjectionEvent, OrderAgreementSnapshot

CONSENT_FIELDS = ("id", "email", "agreement_version_id", "granted", "source", "ip_address", "user_agent",
                  "channel_idx", "created_at")  # fmt: skip
OBJECTION_FIELDS = ("id", "channel__idx", "email", "source", "reason", "clause_set_id", "created_at")
SNAPSHOT_FIELDS = ("id", "order_id", "email", "agreement_version_id", "body_snapshot", "language", "granted",
                   "ip_address", "user_agent", "created_at")  # fmt: skip


def anonymised_address(email: str) -> str:
    """Same token as `django_leads.utils.emails.anonymised_address` (never import across; a test pins the parity)."""
    digest = hashlib.sha256((email or "").strip().lower().encode()).hexdigest()
    return f"anon-{digest[:16]}@{agreements_settings.LEADS_ANONYMISED_DOMAIN}"


def _of_email(email: str) -> Q:
    """The plain address, or its token after an earlier erasure or retention."""
    return Q(email__iexact=email.strip()) | Q(email=anonymised_address(email))


def gdpr_export(email: str) -> dict[str, Any]:
    return {
        "ConsentRecord": list(ConsentRecord.objects.filter(_of_email(email)).values(*CONSENT_FIELDS)),
        "ObjectionEvent": list(ObjectionEvent.objects.filter(_of_email(email)).values(*OBJECTION_FIELDS)),
        "OrderAgreementSnapshot": list(
            OrderAgreementSnapshot.objects.filter(_of_email(email)).values(*SNAPSHOT_FIELDS)
        ),
    }


def gdpr_erase(email: str) -> dict[str, int]:
    plain, token = Q(email__iexact=email.strip()), anonymised_address(email)
    with transaction.atomic():
        consents = ConsentRecord.objects.filter(plain).update(email=token, ip_address=None, user_agent="")
        objections = ObjectionEvent.objects.filter(plain).update(email=token)
        snapshots = OrderAgreementSnapshot.objects.filter(plain).update(email=token, ip_address=None, user_agent="")
    return {"consent_records": consents, "objection_events": objections, "order_agreement_snapshots": snapshots}
