# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Migrate CRM ConsentType/Consent data to django-agreements.

Maps ConsentType.name → AgreementDefinition.slug and creates ConsentRecords
from the CRM Consent table. Idempotent — skips records that already exist.
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

# Mapping: CRM ConsentType.name → AgreementDefinition slug
DEFAULT_SLUG_MAP = {
    "email": "marketing-email",
    "sms": "marketing-sms",
    "push": "marketing-push",
    "marketing": "marketing-email",
    "newsletter": "marketing-email",
    "terms": "terms-of-service",
    "privacy": "privacy-policy",
}


class Command(BaseCommand):
    help = "Migrate CRM Consent/ConsentType data to django-agreements ConsentRecords"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without making changes")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        try:
            from django_crm.models import Consent, ConsentType
        except ImportError:
            self.stderr.write("django_crm is not installed. Nothing to migrate.")
            return

        from django_agreements.models import AgreementDefinition, AgreementVersion, ConsentRecord

        consent_types = ConsentType.objects.all()
        if not consent_types.exists():
            self.stdout.write("No CRM ConsentTypes found. Nothing to migrate.")
            return

        # Build slug map from existing definitions
        slug_map = {}
        for ct in consent_types:
            name_lower = ct.name.lower().strip()
            slug = DEFAULT_SLUG_MAP.get(name_lower)
            if not slug:
                slug = name_lower.replace(" ", "-").replace("_", "-")
            if AgreementDefinition.objects.filter(slug=slug).exists():
                slug_map[ct.pk] = slug
            else:
                self.stderr.write(
                    f"  SKIP: CRM ConsentType '{ct.name}' (pk={ct.pk}) → no AgreementDefinition with slug='{slug}'"
                )

        if not slug_map:
            self.stderr.write("No CRM ConsentTypes could be mapped to AgreementDefinitions.")
            return

        self.stdout.write(f"Mapped {len(slug_map)} ConsentTypes:")
        for ct_pk, slug in slug_map.items():
            ct = ConsentType.objects.get(pk=ct_pk)
            self.stdout.write(f"  {ct.name} (pk={ct_pk}) → {slug}")

        # Pre-fetch definitions and versions outside the loop
        mapped_slugs = list(slug_map.values())
        definitions = {d.slug: d for d in AgreementDefinition.objects.filter(slug__in=mapped_slugs)}

        versions = {}
        for defn in definitions.values():
            version = AgreementVersion.objects.filter(definition=defn, is_current=True).first()
            if not version:
                version = AgreementVersion.objects.filter(definition=defn).order_by("-version_number").first()
            if version:
                versions[defn.slug] = version

        # Migrate consents
        crm_consents = Consent.objects.select_related("form", "consent_type").filter(
            consent_type_id__in=slug_map.keys()
        )

        total = crm_consents.count()
        self.stdout.write(f"\nMigrating {total} CRM Consent records...")

        created = 0
        skipped = 0
        errors = 0

        BATCH_SIZE = 500
        batch: list[ConsentRecord] = []

        for consent in crm_consents.iterator(chunk_size=BATCH_SIZE):
            slug = slug_map.get(consent.consent_type_id)
            if not slug:
                skipped += 1
                continue

            email = consent.form.email
            if not email:
                skipped += 1
                continue

            version = versions.get(slug)
            if not version:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  DRY-RUN: {email} → {slug} v{version.version_number} granted={consent.consent_bool}"
                )
                created += 1
                continue

            batch.append(
                ConsentRecord(
                    email=email,
                    agreement_version=version,
                    granted=consent.consent_bool,
                    source="import",
                    channel_idx="",
                    ip_address=None,
                    user_agent="crm-migration",
                )
            )
            created += 1

            if len(batch) >= BATCH_SIZE:
                self._flush(batch)
                batch.clear()

        if batch and not dry_run:
            self._flush(batch)

        prefix = "DRY-RUN: Would create" if dry_run else "Created"
        self.stdout.write(f"\n{prefix} {created} ConsentRecords, skipped {skipped}, errors {errors}")

    @transaction.atomic
    def _flush(self, batch: list) -> None:
        from django_agreements.models import ConsentRecord

        ConsentRecord.objects.bulk_create(batch, batch_size=500)
