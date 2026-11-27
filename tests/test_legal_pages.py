# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Default legal pages loader: languages are matched by ISO code, never by pk."""

from io import StringIO

import pytest
import yaml
from django.core.management import CommandError, call_command

from django_agreements.services import legal_pages_service as service

ALL_LANGUAGES = {"EN": 11, "PL": 12, "DE": 13}


@pytest.fixture(scope="module")
def fixture_records():
    return yaml.safe_load(service.FIXTURE_PATH.read_text("utf-8"))


def _by_model(records, model):
    return [r for r in records if r["model"] == f"django_contentdb.{model}"]


class TestResolveRecords:
    def test_every_language_present_keeps_all_records(self, fixture_records):
        records, missing = service.resolve_records(fixture_records, ALL_LANGUAGES, 99)
        assert len(records) == len(fixture_records)
        assert missing == []

    def test_drafts_get_the_real_language_and_content_type_pks(self, fixture_records):
        records, _ = service.resolve_records(fixture_records, ALL_LANGUAGES, 99)
        drafts = _by_model(records, "draft")
        assert {d["fields"]["content_type"] for d in drafts} == {99}
        assert {d["fields"]["language"] for d in drafts} == {11, 12, 13}

    def test_missing_language_drops_its_variants_everywhere(self, fixture_records):
        # pk 3 would be ES in a database without DE: no German text may remain
        records, missing = service.resolve_records(fixture_records, {"EN": 1, "PL": 2}, 6)
        drafts = _by_model(records, "draft")
        assert missing == ["DE"]
        assert len(drafts) == 6
        assert {d["fields"]["language"] for d in drafts} == {1, 2}
        assert not any("(DE)" in d["fields"]["name"] for d in drafts)
        kept = {d["pk"] for d in drafts}
        assert {p["fields"]["draft"] for p in _by_model(records, "published")} == kept
        assert {link["fields"]["draft"] for link in _by_model(records, "drafttocontentset")} == kept
        assert all(set(r["fields"]["drafts"]) <= kept for r in _by_model(records, "route"))
        content_pks = {r["pk"] for r in _by_model(records, "content")}
        assert content_pks == {d["fields"]["content"] for d in drafts} | {
            p["fields"]["content"] for p in _by_model(records, "published")
        }

    def test_input_is_not_modified(self, fixture_records):
        before = yaml.safe_dump(fixture_records)
        service.resolve_records(fixture_records, {"EN": 1}, 6)
        assert yaml.safe_dump(fixture_records) == before


@pytest.mark.django_db
class TestLoadCommand:
    @pytest.fixture(autouse=True)
    def _contentdb(self):
        pytest.importorskip("django_contentdb")

    @pytest.fixture
    def attribute_set(self):
        from django_contentdb.models import AttributeSet

        return AttributeSet.objects.create(slug="legal", label="legal")

    @pytest.fixture
    def legal_type(self, attribute_set):
        from django_contentdb.models import ContentType

        return ContentType.objects.create(slug=service.LEGAL_PAGE_SLUG, label="legal page", attribute_set=attribute_set)

    @pytest.fixture
    def languages(self):
        from django_contentdb.models import Language

        # pk 3 is ES: the case that used to receive the German text
        for pk, iso3, iso2 in ((1, "ENG", "EN"), (2, "POL", "PL"), (3, "SPA", "ES")):
            Language.objects.create(pk=pk, iso3=iso3, iso2=iso2)

    def _run(self):
        out = StringIO()
        call_command("load_legal_pages", stdout=out)
        return out.getvalue()

    def test_german_text_never_lands_on_another_language(self, legal_type, languages):
        from django_contentdb.models import Draft

        output = self._run()
        assert "Language DE does not exist" in output
        names = {d.language.iso2: d.name for d in Draft.objects.select_related("language")}
        assert set(names) == {"EN", "PL"}
        assert not Draft.objects.filter(name__contains="(DE)").exists()
        assert Draft.objects.filter(language__iso2="ES").count() == 0

    def test_loads_every_language_that_exists(self, legal_type, languages):
        from django_contentdb.models import Draft, Language

        Language.objects.filter(iso2="ES").update(iso2="DE", iso3="DEU")
        assert "does not exist" not in self._run()
        assert Draft.objects.filter(language__iso2="DE", name__contains="(DE)").count() == 3

    def test_is_idempotent(self, legal_type, languages):
        from django_contentdb.models import Content, Draft, Published, Route

        self._run()
        counts = (Content.objects.count(), Draft.objects.count(), Published.objects.count(), Route.objects.count())
        self._run()
        assert (
            Content.objects.count(),
            Draft.objects.count(),
            Published.objects.count(),
            Route.objects.count(),
        ) == counts
        assert counts == (12, 6, 6, 3)

    def test_without_the_legal_page_content_type_it_fails_loudly(self, languages):
        with pytest.raises(CommandError, match="legal-page"):
            self._run()
