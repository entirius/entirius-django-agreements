# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Load the default legal pages (`fixtures/legal_pages.yaml`) with languages resolved by ISO code.

The fixture names its languages by placeholder pk (1 = EN, 2 = PL, 3 = DE) because ContentDB `Language` has no
natural key. Those pks only match a database that happens to number its languages the same way, so the loader
swaps them for the real rows and leaves out the variants whose language is not configured.
"""

from pathlib import Path
from typing import Any

import yaml
from django.core import serializers
from django.db import transaction

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "legal_pages.yaml"
LEGAL_PAGE_SLUG = "legal-page"
FIXTURE_LANGUAGES = {1: "EN", 2: "PL", 3: "DE"}

_CONTENT = "django_contentdb.content"
_DRAFT = "django_contentdb.draft"
_PUBLISHED = "django_contentdb.published"
_ROUTE = "django_contentdb.route"
_DRAFT_LINK = "django_contentdb.drafttocontentset"

Record = dict[str, Any]


def _skipped_drafts(records: list[Record], language_pks: dict[str, int]) -> set[int]:
    return {
        r["pk"]
        for r in records
        if r["model"] == _DRAFT and FIXTURE_LANGUAGES[r["fields"]["language"]] not in language_pks
    }


def _orphaned_contents(records: list[Record], skipped: set[int]) -> set[int]:
    """Body and snapshot Content rows of the skipped drafts."""
    contents = set()
    for r in records:
        if r["model"] == _DRAFT and r["pk"] in skipped:
            contents.add(r["fields"]["content"])
        elif r["model"] == _PUBLISHED and r["fields"]["draft"] in skipped:
            contents.add(r["fields"]["content"])
    return contents


def _is_dropped(record: Record, skipped: set[int], contents: set[int]) -> bool:
    model, fields = record["model"], record["fields"]
    return (
        (model == _DRAFT and record["pk"] in skipped)
        or (model in (_PUBLISHED, _DRAFT_LINK) and fields["draft"] in skipped)
        or (model == _CONTENT and record["pk"] in contents)
    )


def _adapt(record: Record, language_pks: dict[str, int], content_type_pk: int, skipped: set[int]) -> Record:
    fields = dict(record["fields"])
    if record["model"] == _DRAFT:
        fields["language"] = language_pks[FIXTURE_LANGUAGES[fields["language"]]]
        fields["content_type"] = content_type_pk
    elif record["model"] == _ROUTE:
        fields["drafts"] = [pk for pk in fields["drafts"] if pk not in skipped]
    return {**record, "fields": fields}


def resolve_records(
    records: list[Record], language_pks: dict[str, int], content_type_pk: int
) -> tuple[list[Record], list[str]]:
    """Return the records to save and the ISO codes of the fixture languages that were left out."""
    skipped = _skipped_drafts(records, language_pks)
    contents = _orphaned_contents(records, skipped)
    kept = [_adapt(r, language_pks, content_type_pk, skipped) for r in records if not _is_dropped(r, skipped, contents)]
    missing = sorted(set(FIXTURE_LANGUAGES.values()) - set(language_pks))
    return kept, missing


def load_legal_pages() -> tuple[int, list[str]]:
    """Save the default legal pages; return the number of rows written and the missing language codes.

    Idempotent: rows carry fixed pks, so a second run updates them in place.
    Raises LookupError when ContentDB has no `legal-page` content type.
    """
    from django_contentdb.models import ContentType, Language

    content_type = ContentType.objects.filter(slug=LEGAL_PAGE_SLUG).first()
    if content_type is None:
        raise LookupError(f"ContentDB content type '{LEGAL_PAGE_SLUG}' does not exist")
    wanted = set(FIXTURE_LANGUAGES.values())
    language_pks = {
        iso2.upper(): pk for pk, iso2 in Language.objects.values_list("pk", "iso2") if iso2.upper() in wanted
    }
    records, missing = resolve_records(yaml.safe_load(FIXTURE_PATH.read_text("utf-8")), language_pks, content_type.pk)
    with transaction.atomic():
        for obj in serializers.deserialize("python", records):
            obj.save()
    return len(records), missing
