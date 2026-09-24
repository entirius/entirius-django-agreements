# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Management command removing cookie consent proofs past their retention period."""

from django.core.management.base import BaseCommand, CommandError

from django_agreements import settings as agreements_settings
from django_agreements.services import cookie_consent_service


class Command(BaseCommand):
    help = "Delete cookie consents older than --days (default: AGREEMENTS_COOKIE_CONSENT_RETENTION_DAYS)"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, help="Retention in days; at least the cookie consent validity")
        parser.add_argument("--dry-run", action="store_true", help="Count the rows, delete nothing")

    def handle(self, *args, **options):
        days = options["days"]
        if days is None:
            days = agreements_settings.COOKIE_CONSENT_RETENTION_DAYS
        if days is None:
            raise CommandError("Pass --days or set AGREEMENTS_COOKIE_CONSENT_RETENTION_DAYS.")
        try:
            count = cookie_consent_service.purge_older_than(days, dry_run=options["dry_run"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        verb = "Would delete" if options["dry_run"] else "Deleted"
        self.stdout.write(self.style.SUCCESS(f"{verb} {count} cookie consents older than {days} days"))
