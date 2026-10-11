# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models
from django_utils.models.base_model import BaseModel


class AgreementVersion(BaseModel):
    """Immutable version of an agreement definition. Once published, cannot be edited."""

    definition = models.ForeignKey(
        "django_agreements.AgreementDefinition", on_delete=models.CASCADE, related_name="versions"
    )
    version_number = models.PositiveIntegerField()
    summary_t9n = models.JSONField(
        default=dict, help_text='Checkbox label per language: {"en": "I accept...", "pl": "Akceptuję..."}'
    )
    content_published_id = models.IntegerField(
        null=True, blank=True, help_text="Soft reference to ContentDB Published.pk (full legal text)"
    )
    published_at = models.DateTimeField(null=True, blank=True, help_text="Null = draft, set = live")
    is_current = models.BooleanField(default=False, help_text="One True per definition — enforced by service layer")
    cookie_banner = models.JSONField(
        default=dict, blank=True, help_text="Cookie banner config (categories, buttons) — only for category=cookies"
    )

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(fields=["definition", "version_number"], name="unique_definition_version")
        ]

    def __str__(self) -> str:
        state = "published" if self.published_at else "draft"
        return f"{self.definition.slug} v{self.version_number} ({state})"
