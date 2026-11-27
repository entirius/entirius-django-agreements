# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Management command loading the default legal pages with languages matched by ISO code."""

from django.core.management.base import BaseCommand, CommandError

from django_agreements.services import legal_pages_service


class Command(BaseCommand):
    help = "Load the default legal pages (terms, privacy, newsletter-policy), skipping languages ContentDB lacks"

    def handle(self, *args, **options):
        try:
            count, missing = legal_pages_service.load_legal_pages()
        except ImportError as exc:
            raise CommandError("django_contentdb is not installed.") from exc
        except LookupError as exc:
            raise CommandError(str(exc)) from exc
        for iso2 in missing:
            self.stdout.write(
                self.style.WARNING(f"Language {iso2} does not exist in ContentDB: skipped its legal pages")
            )
        self.stdout.write(self.style.SUCCESS(f"Loaded {count} legal page records"))
