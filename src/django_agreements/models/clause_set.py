# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.conf import settings
from django.db import models
from django_utils.models.base_model import BaseModel

from django_agreements.enums import LegalBasis


class ClauseSet(BaseModel):
    """Versioned legal clauses per channel, legal basis and language. Immutable once published."""

    channel = models.ForeignKey("django_agreements.Channel", on_delete=models.PROTECT, related_name="clause_sets")
    legal_basis = models.CharField(max_length=32, choices=LegalBasis.choices)
    language = models.ForeignKey(
        "django_regional.Language", on_delete=models.PROTECT, related_name="agreements_clause_sets"
    )
    version = models.PositiveIntegerField()
    info_clause = models.TextField()
    optout_clause = models.TextField()
    retention_clause = models.TextField()
    is_current = models.BooleanField(default=False, help_text="One True per triple — enforced by service layer")
    published_at = models.DateTimeField(null=True, blank=True, help_text="Null = draft, set = live")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["channel", "legal_basis", "language", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "legal_basis", "language", "version"], name="unique_clause_set_version"
            )
        ]

    def __str__(self) -> str:
        return f"{self.channel_id}/{self.legal_basis}/{self.language_id} v{self.version}"
