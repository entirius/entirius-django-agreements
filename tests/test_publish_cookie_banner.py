# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""publish_cookie_banner: loads the default banner once, publishes it, never stacks or reverts versions."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from django_agreements.models import AgreementDefinition, AgreementVersion


@pytest.fixture
def four_language_channel(channel, lang_pl, lang_en):
    from django_regional.models import Language

    extra = [Language.objects.create(iso2=c, iso3=f"{c}x", name_en=c, name_pl=c) for c in ("de", "es")]
    channel.languages.add(lang_pl, lang_en, *extra)
    return channel


def _run() -> str:
    out = StringIO()
    call_command("publish_cookie_banner", stdout=out)
    return out.getvalue()


def test_loads_and_publishes(four_language_channel):
    assert "Published cookie banner version 100" in _run()
    version = AgreementVersion.objects.get(pk=100)
    assert version.published_at and version.is_current


def test_rerun_keeps_the_published_version(four_language_channel):
    _run()
    published_at = AgreementVersion.objects.get(pk=100).published_at
    assert "nothing to do" in _run()
    assert AgreementVersion.objects.filter(definition__slug="cookie-banner").count() == 1
    assert AgreementVersion.objects.get(pk=100).published_at == published_at


def test_completes_an_interrupted_run(four_language_channel):
    call_command("loaddata", "cookie_banner", verbosity=0)
    assert "Published" in _run()
    assert AgreementDefinition.objects.filter(slug="cookie-banner").count() == 1


def test_unsupported_channel_language_is_a_command_error(channel, lang_pl, lang_en):
    from django_regional.models import Language

    channel.languages.add(lang_pl, lang_en, Language.objects.create(iso2="fr", iso3="fra", name_en="fr", name_pl="fr"))
    with pytest.raises(CommandError, match=r"\['fr'\].*Add their texts"):
        _run()
    assert AgreementVersion.objects.get(pk=100).published_at is None
