# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""GDPR hooks (art. 15 export, art. 17 erasure) discovered by `django_leads.gdpr.registry`.

`ConsentRecord` and `ObjectionEvent` are append-only; erasure deliberately bypasses that with queryset `update()`:
the rows stay as the audit trail (what was consented or objected to, when), only the person is pseudonymised —
email → the token leads and communicator use, IP and user agent dropped."""

import hashlib
from typing import Any

from django.db import transaction

from django_agreements import settings as agreements_settings
from django_agreements.models import ConsentRecord, ObjectionEvent

CONSENT_FIELDS = ("id", "email", "agreement_version_id", "granted", "source", "ip_address", "user_agent",
                  "channel_idx", "created_at")  # fmt: skip
OBJECTION_FIELDS = ("id", "channel__idx", "email", "source", "reason", "clause_set_id", "created_at")


def anonymised_address(email: str) -> str:
    """Same token as `django_leads.utils.emails.anonymised_address` (never import across)."""
    digest = hashlib.sha256((email or "").strip().lower().encode()).hexdigest()
    return f"anon-{digest[:16]}@{agreements_settings.LEADS_ANONYMISED_DOMAIN}"


def gdpr_export(email: str) -> dict[str, Any]:
    email = email.strip()
    return {
        "ConsentRecord": list(ConsentRecord.objects.filter(email__iexact=email).values(*CONSENT_FIELDS)),
        "ObjectionEvent": list(ObjectionEvent.objects.filter(email__iexact=email).values(*OBJECTION_FIELDS)),
    }


def gdpr_erase(email: str) -> dict[str, int]:
    email, token = email.strip(), anonymised_address(email)
    with transaction.atomic():
        consents = ConsentRecord.objects.filter(email__iexact=email).update(email=token, ip_address=None, user_agent="")
        objections = ObjectionEvent.objects.filter(email__iexact=email).update(email=token)
    return {"consent_records": consents, "objection_events": objections}
