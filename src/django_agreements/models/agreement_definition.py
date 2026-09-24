# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models
from django_utils.models.base_model import BaseModel


class AgreementDefinition(BaseModel):
    """Top-level agreement definition (e.g., 'terms-of-service', 'marketing-email')."""

    CATEGORY_CHOICES = [
        ("mandatory", "Mandatory"),
        ("marketing", "Marketing"),
        ("informational", "Informational"),
        ("cookies", "Cookies"),
    ]

    CONSENT_CHANNEL_CHOICES = [
        ("general", "General"),
        ("email", "Email"),
        ("sms", "SMS"),
        ("push", "Push"),
        ("web", "Web"),
    ]

    DISPLAY_CONTEXT_CHOICES = [("checkout", "Checkout"), ("registration", "Registration"), ("newsletter", "Newsletter")]

    slug = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    consent_channel = models.CharField(max_length=10, choices=CONSENT_CHANNEL_CHOICES, default="general")
    channels = models.ManyToManyField("django_agreements.Channel", blank=True, related_name="definitions")
    content_route = models.CharField(max_length=200, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(
        default=False, help_text="System consents are fixture-managed and cannot be deleted via CMS"
    )
    display_contexts = models.JSONField(
        default=list, blank=True, help_text='Where this consent appears: ["checkout", "registration", "newsletter"]'
    )
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"
