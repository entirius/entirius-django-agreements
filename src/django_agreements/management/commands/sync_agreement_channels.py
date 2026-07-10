# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Management command to sync agreement channels from PIM."""

from django.core.management.base import BaseCommand

from django_agreements.services import channel_service


class Command(BaseCommand):
    help = "Sync agreement channels from PIM Channel model"

    def handle(self, *args, **options):
        count = channel_service.sync_channels_from_pim()
        self.stdout.write(self.style.SUCCESS(f"Synced {count} channels from PIM."))
