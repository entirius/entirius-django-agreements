# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.conf import settings
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django_utils.models.base_model import BaseModel

from django_agreements.enums import LegalBasis

LOCKED_FIELDS = (
    "channel_id",
    "legal_basis",
    "language_id",
    "info_clause",
    "optout_clause",
    "retention_clause",
    "published_at",
)


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

    def save(self, *args, **kwargs):
        self.refuse_published_change(kwargs.get("update_fields"))
        super().save(*args, **kwargs)

    def refuse_published_change(self, update_fields=None) -> None:
        """Raise ValueError when a saved locked field differs from the stored published row."""
        fields = _saved_locked_fields(update_fields)
        if self.pk is None or not fields:
            return
        stored = ClauseSet.objects.filter(pk=self.pk, published_at__isnull=False).values(*fields).first()
        if stored and any(stored[field] != getattr(self, field) for field in fields):
            raise ValueError(f"Clause set {self} is published and cannot be changed.")


def _saved_locked_fields(update_fields) -> list[str]:
    """Locked fields written by this save — all of them unless `update_fields` narrows the save."""
    if update_fields is None:
        return list(LOCKED_FIELDS)
    return [field for field in LOCKED_FIELDS if {field, field.removesuffix("_id")} & set(update_fields)]


@receiver(pre_save, sender=ClauseSet)
def refuse_raw_published_change(sender, instance: ClauseSet, raw: bool, update_fields=None, **kwargs) -> None:
    """Fixture loads (`raw=True`) skip `save()` — apply the same guard so loaddata cannot rewrite published rows."""
    if raw:
        instance.refuse_published_change(update_fields)
