# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.db import models


class LegalBasis(models.TextChoices):
    """GDPR legal basis for processing — the platform-wide definition."""

    CONSENT = "consent", "Consent (art. 6(1)(a))"
    LEGITIMATE_INTEREST = "legitimate_interest", "Legitimate interest (art. 6(1)(f))"
    CONTRACT = "contract", "Contract (art. 6(1)(b))"
