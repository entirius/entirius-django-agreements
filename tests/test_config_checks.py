# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The `agreements.storefront_url` configuration health check."""

from django.core import checks

from django_agreements.checks import CODE, FIX_URL, storefront_url_set


def test_set_storefront_url_is_healthy(settings):
    settings.STOREFRONT_BASE_URL = "https://shop.example.com"
    assert storefront_url_set() == []


def test_unset_storefront_url_warns_with_the_fix(settings):
    del settings.STOREFRONT_BASE_URL
    [warning] = storefront_url_set()
    assert isinstance(warning, checks.Warning)
    assert warning.id == CODE
    assert "http://localhost:3000" in warning.hint
    assert warning.obj == {"scope": "", "state": "unconfigured", "severity": "high", "fix_url": FIX_URL}


def test_check_runs_under_the_entirius_config_tag(settings):
    del settings.STOREFRONT_BASE_URL
    found = checks.run_checks(tags=["entirius_config"])
    assert [message.id for message in found if message.id == CODE] == [CODE]
