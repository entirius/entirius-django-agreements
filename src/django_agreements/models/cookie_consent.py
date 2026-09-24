# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models

ACTION_ACCEPT_ALL = "accept_all"
ACTION_REJECT_ALL = "reject_all"
ACTION_CUSTOM = "custom"
ACTION_WITHDRAW = "withdraw"


class CookieConsent(models.Model):
    """Append-only log of anonymous cookie banner decisions.

    Proof of consent = consent_id + agreement version + language + categories + time.
    No IP, user agent or URL is stored (data minimisation).
    """

    ACTION_CHOICES = [
        (ACTION_ACCEPT_ALL, "Accept all"),
        (ACTION_REJECT_ALL, "Reject all"),
        (ACTION_CUSTOM, "Custom"),
        (ACTION_WITHDRAW, "Withdraw"),
    ]

    consent_id = models.UUIDField(help_text="Random id the banner keeps in a first-party cookie")
    channel_idx = models.CharField(max_length=128)
    language = models.CharField(max_length=2, help_text="ISO 639-1 code the banner was shown in")
    agreement_version = models.ForeignKey(
        "django_agreements.AgreementVersion", on_delete=models.PROTECT, related_name="cookie_consents"
    )
    categories = models.JSONField(help_text='Decision per category: {"analytics": true, "marketing": false}')
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["consent_id", "-created_at"], name="idx_cookie_consent_id_date"),
            models.Index(fields=["channel_idx", "created_at"], name="idx_cookie_channel_date"),
            models.Index(fields=["created_at"], name="idx_cookie_created"),
        ]

    def __str__(self) -> str:
        return f"{self.consent_id} {self.action} {self.agreement_version}"
