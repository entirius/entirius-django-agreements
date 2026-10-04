# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.apps import AppConfig


class DjangoAgreementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_agreements"
    verbose_name = "Agreements"
    is_volkanos = True
    # Copied 1:1 from entirius-django-access cf538d2 catalogue defaults;
    # the access defaults stay until this module's release.
    access_areas = [
        {"key": "agreements.definitions", "label": "Agreement texts and versions"},
        {"key": "agreements.consents", "label": "Consents, people and subscribers", "sensitive": ("pii",)},
    ]
    access_token_scopes = [
        {
            "key": "agreements.subscribe",
            "label": "Newsletter subscription",
            "publishable": True,
            "routes": ("/api/agreements/v2/{channel_idx}/newsletter/subscribe/",),
        },
    ]
    # ContentHistoryViewSet serves a definition's content history and a person's consent text: one class, two areas,
    # so its two routes keep path rules, narrowed from the default consents rule and catch-all (no catch-all).
    # Every other admin view carries access_area.
    access_route_rules = [
        {"pattern": r"api/agreements/v2/admin/people/[^/]+/consent-text/", "area": "agreements.consents"},
        {"pattern": r"api/agreements/v2/admin/definitions/[^/]+/content-history/", "area": "agreements.definitions"},
    ]

    def ready(self) -> None:
        import django_agreements.signals  # noqa: F401
