# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Configuration health checks (tag ``entirius_config``), aggregated by django-munin.

Warnings only: a config gap must never stop ``runserver`` or ``migrate``.
"""

from django.conf import settings
from django.core import checks

CODE = "agreements.storefront_url"
FIX_URL = "https://github.com/entirius/entirius-django-agreements/blob/master/docs/configuration.md#storefront-url"


class _Subject(dict):
    """Row metadata munin reads as a dict; `manage.py check` prints `str(obj)` as the label, so name the subject."""

    def __str__(self) -> str:
        return self.get("scope") or "settings"


@checks.register("entirius_config", CODE)
def storefront_url_set(app_configs=None, **kwargs) -> list[checks.CheckMessage]:
    """Unset, the module falls back to a dev URL: every newsletter mail links to a page no subscriber can open."""
    if hasattr(settings, "STOREFRONT_BASE_URL"):
        return []
    return [
        checks.Warning(
            "Storefront URL not set",
            hint=(
                "Set STOREFRONT_BASE_URL to the storefront's address; until then the newsletter confirmation and "
                "unsubscribe links point at http://localhost:3000."
            ),
            id=CODE,
            obj=_Subject(scope="", state="unconfigured", severity="high", fix_url=FIX_URL),
        )
    ]
