# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import uuid

from django.db import models


class OrderAgreementSnapshot(models.Model):
    """Per-order text freeze of agreement acceptance. Preserves exactly what customer saw."""

    order_id = models.UUIDField(
        db_index=True, default=uuid.uuid4, help_text="Matches Order.order_id (no FK to django-checkout)"
    )
    email = models.EmailField()
    agreement_version = models.ForeignKey(
        "django_agreements.AgreementVersion", on_delete=models.PROTECT, related_name="order_snapshots"
    )
    body_snapshot = models.TextField(help_text="Full legal text at acceptance time (denormalized from ContentDB)")
    language = models.CharField(max_length=5, help_text="Language version shown to customer (iso2)")
    granted = models.BooleanField(default=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["order_id", "agreement_version"], name="unique_order_agreement_version")
        ]

    def __str__(self) -> str:
        return f"Order {self.order_id} — {self.agreement_version}"
