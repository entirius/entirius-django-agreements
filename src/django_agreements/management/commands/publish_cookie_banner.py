# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Management command loading and publishing the default cookie banner."""

from django.core.management.base import BaseCommand, CommandError

from django_agreements.services import cookie_banner_service


class Command(BaseCommand):
    help = "Load the default cookie banner (cookie_banner fixture) and publish its draft; safe to re-run"

    def handle(self, *args, **options):
        try:
            version = cookie_banner_service.publish_default_banner()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if version is None:
            self.stdout.write("Cookie banner already published: nothing to do")
            return
        self.stdout.write(self.style.SUCCESS(f"Published cookie banner version {version.pk}"))
