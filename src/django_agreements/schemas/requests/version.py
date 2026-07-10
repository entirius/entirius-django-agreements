# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for agreement versions."""

import html
import re
from html.parser import HTMLParser

from pydantic import BaseModel, Field, field_validator

_SUMMARY_EXAMPLE = {"en": "I accept the Terms of Service", "pl": "Akceptuję regulamin"}
_LANG_KEY_RE = re.compile(r"^[a-z]{2}$")
_ALLOWED_TAGS = {"a", "b", "i", "u"}


class _AllowlistSanitizer(HTMLParser):
    """Strip all tags except _ALLOWED_TAGS. Escapes text content."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag not in _ALLOWED_TAGS:
            return
        attr_str = ""
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value and not value.lower().startswith(("javascript:", "data:")):
                    attr_str = f' href="{html.escape(value)}"'
        self._parts.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _ALLOWED_TAGS:
            self._parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self._parts.append(html.escape(data))

    def get_output(self) -> str:
        return "".join(self._parts)


def sanitize_html(text: str) -> str:
    """Sanitize HTML using the allowlist parser. Safe to import from service layer."""
    parser = _AllowlistSanitizer()
    parser.feed(text)
    return parser.get_output()


def _sanitize_summary_t9n(value: dict) -> dict:
    for key, text in value.items():
        if not isinstance(key, str) or not _LANG_KEY_RE.match(key):
            raise ValueError(f"Invalid language key '{key}'. Must be a 2-letter ISO 639-1 code (e.g. 'en').")
        if not isinstance(text, str):
            raise ValueError(f"Value for key '{key}' must be a string.")
    return {key: sanitize_html(text) for key, text in value.items()}


class VersionCreateRequest(BaseModel):
    summary_t9n: dict = Field(
        description="Checkbox label per language (supports limited HTML: <a>, <b>, <i>, <u>)",
        examples=[_SUMMARY_EXAMPLE],
    )
    content_published_id: int | None = Field(
        None, description="ContentDB Published.pk for full legal text (null for marketing agreements)", examples=[42]
    )

    @field_validator("summary_t9n")
    @classmethod
    def validate_summary_t9n(cls, v: dict) -> dict:
        return _sanitize_summary_t9n(v)


class VersionUpdateRequest(BaseModel):
    """Update a draft version. Only provided fields are changed."""

    summary_t9n: dict | None = Field(
        None,
        description="Checkbox label per language (supports limited HTML: <a>, <b>, <i>, <u>)",
        examples=[_SUMMARY_EXAMPLE],
    )
    content_published_id: int | None = Field(None, description="ContentDB Published.pk (null to clear)", examples=[42])

    @field_validator("summary_t9n")
    @classmethod
    def validate_summary_t9n(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        return _sanitize_summary_t9n(v)
