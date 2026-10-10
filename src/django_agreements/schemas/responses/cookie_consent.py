# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for the cookie banner and the cookie consent log (public and admin)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CookieBannerButtonsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    accept_all: str = Field(description="'Accept all' button label", examples=["Accept all"])
    reject_all: str = Field(description="'Reject all' button label", examples=["Reject all"])
    customize: str = Field(description="Button opening category settings", examples=["Settings"])
    save: str = Field(description="Button saving a custom choice", examples=["Save choices"])


class CookieCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str = Field(description="Category key to send back in the consent decision", examples=["analytics"])
    required: bool = Field(description="Always on, cannot be declined", examples=[False])
    consent_mode: list[str] = Field(
        description="Google Consent Mode signals granted with this category", examples=[["analytics_storage"]]
    )
    label: str = Field(description="Category label (limited HTML)", examples=["Analytics"])
    description: str = Field(
        description="Category description (limited HTML: <a>, <b>, <i>, <u>)",
        examples=["Show us how the site is used."],
    )


class CookieBannerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    revision: int = Field(description="Banner revision to send back with the consent decision", examples=[12])
    version_number: int = Field(description="Version number of the banner definition", examples=[1])
    definition_slug: str = Field(description="Banner definition slug", examples=["cookie-banner"])
    language: str = Field(description="ISO 639-1 code of the texts below", examples=["en"])
    max_age_days: int = Field(description="Days a consent stays valid (consent cookie lifetime)", examples=[365])
    text: str = Field(
        description="Banner body (limited HTML: <a>, <b>, <i>, <u>)",
        examples=['We use cookies. <a href="/en/cookie-policy">Cookie policy</a>'],
    )
    buttons: CookieBannerButtonsResponse = Field(
        description="Button labels",
        examples=[{"accept_all": "Accept all", "reject_all": "Reject all", "customize": "Settings", "save": "Save"}],
    )
    preferences_title: str | None = Field(
        description="Title of the category settings dialog; null for a banner without `texts_t9n`",
        examples=["Cookie settings"],
    )
    close_label: str | None = Field(
        description="Accessible label of the close (X) button; null for a banner without `texts_t9n`",
        examples=["Close"],
    )
    categories: list[CookieCategoryResponse] = Field(
        description="Cookie categories in display order",
        examples=[
            [
                {
                    "key": "necessary",
                    "required": True,
                    "consent_mode": [],
                    "label": "Necessary",
                    "description": "Keep the site working.",
                }
            ]
        ],
    )


class CookieConsentRecordedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consent_id: UUID = Field(
        description="Consent id from the request", examples=["3f2b8c1e-7a4d-4e9b-9c2a-1d5e6f7a8b9c"]
    )
    revision: int = Field(description="Banner revision the decision was recorded for", examples=[12])
    language: str = Field(description="ISO 639-1 code the banner was shown in", examples=["pl"])
    action: str = Field(description="Recorded action", examples=["custom"])
    created_at: datetime = Field(description="Decision timestamp", examples=["2026-09-01T12:00:00Z"])


_CONSENT_ID_EXAMPLE = "3f2b8c1e-7a4d-4e9b-9c2a-1d5e6f7a8b9c"


class CookieConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Log row id", examples=[42])
    consent_id: UUID = Field(
        description="Visitor's consent id (from the consent cookie)", examples=[_CONSENT_ID_EXAMPLE]
    )
    channel_idx: str = Field(description="Channel the decision was made on", examples=["default-europe"])
    language: str = Field(description="ISO 639-1 code the banner was shown in", examples=["pl"])
    revision: int = Field(description="Banner revision (agreement version id)", examples=[12])
    version_number: int = Field(description="Version number of the banner definition", examples=[1])
    definition_slug: str = Field(description="Banner definition slug", examples=["cookie-banner"])
    action: str = Field(description="accept_all, reject_all, custom or withdraw", examples=["custom"])
    categories: dict[str, bool] = Field(
        description="Decision per category", examples=[{"necessary": True, "analytics": True, "marketing": False}]
    )
    created_at: datetime = Field(description="Decision timestamp", examples=["2026-09-01T12:00:00Z"])


class CookieConsentListResponse(BaseModel):
    count: int = Field(description="Total number of decisions matching the filters", examples=[120])
    next: str | None = Field(
        None,
        description="URL of the next page",
        examples=["http://localhost:8000/api/agreements/v2/admin/cookie-consents/?page=2"],
    )
    previous: str | None = Field(None, description="URL of the previous page", examples=[None])
    results: list[CookieConsentResponse] = Field(description="Decisions on this page, newest first", examples=[[]])


class CookieConsentStatsRow(BaseModel):
    day: date = Field(description="UTC day", examples=["2026-09-01"])
    revision: int = Field(description="Banner revision (agreement version id)", examples=[12])
    version_number: int = Field(description="Version number of the banner definition", examples=[1])
    language: str = Field(description="ISO 639-1 code the banner was shown in", examples=["pl"])
    action: str = Field(description="accept_all, reject_all, custom or withdraw", examples=["accept_all"])
    count: int = Field(description="Number of decisions", examples=[57])


class CookieConsentStatsResponse(BaseModel):
    results: list[CookieConsentStatsRow] = Field(
        description="Counts ordered by day, revision, language, action",
        examples=[
            [
                {
                    "day": "2026-09-01",
                    "revision": 12,
                    "version_number": 1,
                    "language": "pl",
                    "action": "accept_all",
                    "count": 57,
                }
            ]
        ],
    )


class CookieConsentEraseResponse(BaseModel):
    erased: int = Field(description="Decisions moved to a new random consent id", examples=[3])
