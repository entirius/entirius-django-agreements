# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Load and publish the default cookie banner (`fixtures/cookie_banner.yaml`)."""

from django.core.management import call_command

from django_agreements.models import AgreementDefinition, AgreementVersion
from django_agreements.services import version_service

BANNER_SLUG = "cookie-banner"


def publish_default_banner() -> AgreementVersion | None:
    """Load the default banner when absent and publish its draft; returns the published version, None if nothing to do.

    Idempotent: a present definition is never re-loaded (that would turn its published version back into a draft)
    and a published banner is left alone. Raises ValueError from `publish_version` (e.g. missing channel languages).
    """
    if not AgreementDefinition.objects.filter(slug=BANNER_SLUG).exists():
        call_command("loaddata", "cookie_banner", verbosity=0)
    draft = AgreementVersion.objects.filter(definition__slug=BANNER_SLUG, published_at__isnull=True).first()
    if draft is None:
        return None
    return version_service.publish_version(pk=draft.pk)
