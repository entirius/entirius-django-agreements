# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models

SOURCE_COMMUNICATOR = "communicator"
SOURCE_MANUAL = "manual"
SOURCE_API = "api"


class ObjectionEvent(models.Model):
    """Append-only log of confirmed objections (opt-outs). No updates, no deletes."""

    SOURCE_CHOICES = [(SOURCE_COMMUNICATOR, "Communicator"), (SOURCE_MANUAL, "Manual"), (SOURCE_API, "API")]

    channel = models.ForeignKey("django_agreements.Channel", on_delete=models.PROTECT, related_name="objection_events")
    email = models.EmailField(db_index=True)
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    reason = models.TextField(blank=True)
    clause_set = models.ForeignKey(
        "django_agreements.ClauseSet", null=True, blank=True, on_delete=models.PROTECT, related_name="objection_events"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.email} objected ({self.source})"
