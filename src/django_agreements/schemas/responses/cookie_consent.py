# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for the public cookie banner and consent log."""

from datetime import datetime
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
