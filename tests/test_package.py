# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Package-level guards: migration drift, OpenAPI schema, shipped cookie banner fixture."""

from io import StringIO
from pathlib import Path

import pytest
import yaml
from django.core.management import call_command
from django.test import override_settings

from django_agreements.schemas.requests.version import CookieBannerConfig, sanitize_html

FIXTURE = Path(__file__).resolve().parent.parent / "src" / "django_agreements" / "fixtures" / "cookie_banner.yaml"


def test_migrations_are_complete(db):
    # --no-migrations replaces MIGRATION_MODULES; without the override makemigrations sees no migrations at all
    with override_settings(MIGRATION_MODULES={}):
        call_command("makemigrations", "django_agreements", "--check", "--dry-run", stdout=StringIO())


def test_openapi_schema_validates(tmp_path):
    # no --fail-on-warn: the plain ViewSets warn "unable to guess serializer" (pre-existing, not a schema error)
    call_command("spectacular", "--validate", "--file", str(tmp_path / "schema.yaml"))


@pytest.fixture(scope="module")
def banner_version():
    rows = yaml.safe_load(FIXTURE.read_text())
    return next(row["fields"] for row in rows if row["model"] == "django_agreements.agreementversion")


def _texts(fields):
    banner = fields["cookie_banner"]
    yield from fields["summary_t9n"].values()
    for category in banner["categories"]:
        yield from category["label_t9n"].values()
        yield from category["description_t9n"].values()
    for buttons in banner["buttons_t9n"].values():
        yield from buttons.values()


def test_cookie_banner_fixture_config_is_valid(banner_version):
    config = CookieBannerConfig.model_validate(banner_version["cookie_banner"])
    assert config.languages == set(banner_version["summary_t9n"]) == {"pl", "en"}


def test_cookie_banner_fixture_is_stored_sanitised(banner_version):
    texts = list(_texts(banner_version))
    assert texts
    assert [text for text in texts if text != sanitize_html(text)] == []
