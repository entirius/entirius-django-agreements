# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Content history service for legal page snapshots via ContentDB."""

from datetime import datetime
from html.parser import HTMLParser


class _TextStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _strip_html(html: str) -> str:
    stripper = _TextStripper()
    stripper.feed(html)
    return stripper.get_text()


def extract_legal_html(content_json: dict) -> str:
    """Return HTML from the first tile-txt-btn tile, or concatenate all descriptions."""
    tiles: dict = content_json.get("tiles", {})
    if not tiles:
        return ""

    for tile in tiles.values():
        if isinstance(tile, dict) and tile.get("core_type") == "tile-txt-btn":
            return tile.get("description", "")

    # Fallback: concatenate all tile descriptions
    parts = [
        tile.get("description", "") for tile in tiles.values() if isinstance(tile, dict) and tile.get("description")
    ]
    return "\n".join(parts)


def validate_legal_page_structure(content_json: dict) -> list[str]:
    """Return list of warning strings; empty list means valid."""
    warnings: list[str] = []
    tiles: dict = content_json.get("tiles", {})
    sections: dict = content_json.get("sections", {})

    text_sections = [s for s in sections.values() if isinstance(s, dict) and s.get("core_type") == "section-text"]
    if len(text_sections) != 1:
        warnings.append(f"Expected 1 section-text section, found {len(text_sections)}.")

    txt_btn_tiles = [t for t in tiles.values() if isinstance(t, dict) and t.get("core_type") == "tile-txt-btn"]
    if len(txt_btn_tiles) != 1:
        warnings.append(f"Expected 1 tile-txt-btn tile, found {len(txt_btn_tiles)}.")
    elif not txt_btn_tiles[0].get("description"):
        warnings.append("tile-txt-btn description is empty.")

    return warnings


def list_legal_snapshots(content_route: str, language: str | None = None) -> list[dict]:
    """Return Published snapshots for a legal page route, newest first."""
    try:
        from django_contentdb.models import Published, Route
    except (ImportError, RuntimeError):
        return []

    try:
        route = Route.objects.get(url=content_route)
    except Route.DoesNotExist:
        return []

    # Route→Draft relationship: M2M field named "drafts"
    if hasattr(route, "drafts"):
        drafts = route.drafts.all()
    elif hasattr(route, "draft"):
        drafts = route.draft.all()
    else:
        return []

    if language:
        drafts = drafts.filter(language__iso2__iexact=language)

    published_qs = (
        Published.objects.filter(draft__in=drafts).select_related("draft__language", "content").order_by("-created_at")
    )

    results = []
    for pub in published_qs:
        content_json: dict = pub.content.content if pub.content else {}
        text_html = extract_legal_html(content_json)
        text_preview = _strip_html(text_html)[:200]
        results.append(
            {
                "published_id": pub.pk,
                "created_at": pub.created_at,
                "language": pub.draft.language.iso2 if pub.draft and pub.draft.language else None,
                "text_preview": text_preview,
                "text_html": text_html,
                "draft_uid": str(pub.draft_id) if pub.draft_id else "",
                "warnings": validate_legal_page_structure(content_json),
            }
        )
    return results


def get_legal_text_at_time(content_route: str, at_time: datetime, language: str = "en") -> dict | None:
    """Return the Published snapshot active at `at_time`, or None."""
    try:
        from django_contentdb.models import Published
    except (ImportError, RuntimeError):
        return None

    pub = (
        Published.objects.filter(
            draft__routes__url=content_route, draft__language__iso2__iexact=language, created_at__lte=at_time
        )
        .select_related("content")
        .order_by("-created_at")
        .first()
    )
    if not pub:
        return None

    content_json: dict = pub.content.content if pub.content else {}
    return {"published_id": pub.pk, "created_at": pub.created_at, "text_html": extract_legal_html(content_json)}
