# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models

SOURCE_CHECKOUT = "checkout"
SOURCE_REGISTRATION = "registration"
SOURCE_CONSENT_PAGE = "consent-page"
SOURCE_NEWSLETTER_SIGNUP = "newsletter-signup"
SOURCE_API = "api"
SOURCE_IMPORT = "import"
SOURCE_CRM_V1 = "crm-v1"
SOURCE_DOUBLE_OPTIN_PENDING = "double-optin-pending"
SOURCE_DOUBLE_OPTIN_CONFIRMED = "double-optin-confirmed"
SOURCE_UNSUBSCRIBED = "unsubscribed"


class ConsentRecord(models.Model):
    """Append-only audit log for consent grants and withdrawals.

    No updates, no deletes. Every consent change creates a new row.
    """

    SOURCE_CHOICES = [
        (SOURCE_CHECKOUT, "Checkout"),
        (SOURCE_REGISTRATION, "Registration"),
        (SOURCE_CONSENT_PAGE, "Consent Page"),
        (SOURCE_NEWSLETTER_SIGNUP, "Newsletter Signup"),
        (SOURCE_API, "API"),
        (SOURCE_IMPORT, "Import"),
        (SOURCE_CRM_V1, "CRM v1 Bridge"),
        (SOURCE_DOUBLE_OPTIN_PENDING, "Double Opt-In Pending"),
        (SOURCE_DOUBLE_OPTIN_CONFIRMED, "Double Opt-In Confirmed"),
        (SOURCE_UNSUBSCRIBED, "Unsubscribed"),
    ]

    email = models.EmailField(db_index=True)
    customer_id = models.IntegerField(
        null=True, blank=True, help_text="Soft reference to customer account (no FK to django-accounts)"
    )
    agreement_version = models.ForeignKey(
        "django_agreements.AgreementVersion", on_delete=models.PROTECT, related_name="consent_records", db_index=True
    )
    granted = models.BooleanField(help_text="True=consent given, False=withdrawn")
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    channel_idx = models.CharField(
        max_length=128, blank=True, default="", help_text="Which channel this consent was given in (audit trail)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email", "-created_at"], name="idx_consent_email_date")]

    def __str__(self) -> str:
        action = "granted" if self.granted else "withdrawn"
        return f"{self.email} {action} {self.agreement_version}"
