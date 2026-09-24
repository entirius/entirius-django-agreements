# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for agreement versions."""

import html
import re
from html.parser import HTMLParser
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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


ConsentModeSignal = Literal["ad_storage", "analytics_storage", "ad_user_data", "ad_personalization"]

COOKIE_BANNER_EXAMPLE = {
    "categories": [
        {
            "key": "necessary",
            "required": True,
            "consent_mode": [],
            "label_t9n": {"en": "Necessary", "pl": "Niezbędne"},
            "description_t9n": {"en": "Keep the site working.", "pl": "Zapewniają działanie strony."},
        },
        {
            "key": "analytics",
            "required": False,
            "consent_mode": ["analytics_storage"],
            "label_t9n": {"en": "Analytics", "pl": "Analityczne"},
            "description_t9n": {"en": "Show us how the site is used.", "pl": "Pokazują, jak korzystasz ze strony."},
        },
    ],
    "buttons_t9n": {
        "en": {"accept_all": "Accept all", "reject_all": "Reject all", "customize": "Settings", "save": "Save choices"},
        "pl": {
            "accept_all": "Akceptuj wszystkie",
            "reject_all": "Odrzuć wszystkie",
            "customize": "Ustawienia",
            "save": "Zapisz wybór",
        },
    },
}


class CookieCategoryConfig(BaseModel):
    key: str = Field(
        pattern=r"^[a-z][a-z0-9_]{1,31}$",
        description="Category key stored in consent decisions",
        examples=["analytics"],
    )
    required: bool = Field(description="Always on, cannot be declined (e.g. necessary cookies)", examples=[False])
    consent_mode: list[ConsentModeSignal] = Field(
        description="Google Consent Mode signals granted with this category (empty for a required category)",
        examples=[["analytics_storage"]],
    )
    label_t9n: dict = Field(description="Category label per language (limited HTML)", examples=[{"en": "Analytics"}])
    description_t9n: dict = Field(
        description="Category description per language (limited HTML: <a>, <b>, <i>, <u>)",
        examples=[{"en": "Show us how the site is used."}],
    )

    @field_validator("label_t9n", "description_t9n")
    @classmethod
    def validate_t9n(cls, v: dict) -> dict:
        return _sanitize_summary_t9n(v)

    @field_validator("consent_mode")
    @classmethod
    def validate_consent_mode_unique(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("consent_mode contains duplicate signals.")
        return v

    @model_validator(mode="after")
    def validate_required_has_no_signals(self) -> "CookieCategoryConfig":
        if self.required and self.consent_mode:
            raise ValueError(f"Required category '{self.key}' cannot carry consent_mode signals.")
        return self


class CookieBannerButtons(BaseModel):
    accept_all: str = Field(min_length=1, description="'Accept all' button label", examples=["Accept all"])
    reject_all: str = Field(min_length=1, description="'Reject all' button label", examples=["Reject all"])
    customize: str = Field(min_length=1, description="Button opening category settings", examples=["Settings"])
    save: str = Field(min_length=1, description="Button saving a custom choice", examples=["Save choices"])

    @field_validator("accept_all", "reject_all", "customize", "save")
    @classmethod
    def validate_label(cls, v: str) -> str:
        return sanitize_html(v)


class CookieBannerConfig(BaseModel):
    """Cookie banner configuration of a `cookies` agreement version. Banner body text = summary_t9n."""

    categories: list[CookieCategoryConfig] = Field(
        min_length=1, description="Cookie categories in display order", examples=[COOKIE_BANNER_EXAMPLE["categories"]]
    )
    buttons_t9n: dict[str, CookieBannerButtons] = Field(
        min_length=1, description="Button labels per language", examples=[COOKIE_BANNER_EXAMPLE["buttons_t9n"]]
    )

    @field_validator("buttons_t9n")
    @classmethod
    def validate_button_languages(cls, v: dict) -> dict:
        for key in v:
            if not _LANG_KEY_RE.match(key):
                raise ValueError(f"Invalid language key '{key}'. Must be a 2-letter ISO 639-1 code (e.g. 'en').")
        return v

    @model_validator(mode="after")
    def validate_consistency(self) -> "CookieBannerConfig":
        keys = [category.key for category in self.categories]
        if len(keys) != len(set(keys)):
            raise ValueError("Category keys must be unique.")
        languages = self.languages
        for category in self.categories:
            if set(category.label_t9n) != languages or set(category.description_t9n) != languages:
                raise ValueError(f"Category '{category.key}' must have texts in exactly {sorted(languages)}.")
        return self

    @property
    def languages(self) -> set[str]:
        return set(self.buttons_t9n)


class VersionCreateRequest(BaseModel):
    summary_t9n: dict = Field(
        description="Checkbox label per language (supports limited HTML: <a>, <b>, <i>, <u>)",
        examples=[_SUMMARY_EXAMPLE],
    )
    content_published_id: int | None = Field(
        None, description="ContentDB Published.pk for full legal text (null for marketing agreements)", examples=[42]
    )
    cookie_banner: CookieBannerConfig | None = Field(
        None, description="Cookie banner config — only for category=cookies", examples=[COOKIE_BANNER_EXAMPLE]
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
    cookie_banner: CookieBannerConfig | None = Field(
        None,
        description="Cookie banner config — only for category=cookies (null = unchanged)",
        examples=[COOKIE_BANNER_EXAMPLE],
    )

    @field_validator("summary_t9n")
    @classmethod
    def validate_summary_t9n(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        return _sanitize_summary_t9n(v)
