# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for the public cookie consent log."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

CookieConsentAction = Literal["accept_all", "reject_all", "custom", "withdraw"]


class CookieConsentRequest(BaseModel):
    consent_id: UUID = Field(
        description="Random id the banner keeps in a first-party cookie",
        examples=["3f2b8c1e-7a4d-4e9b-9c2a-1d5e6f7a8b9c"],
    )
    revision: int = Field(ge=1, description="Banner revision returned by cookie-banner", examples=[12])
    language: str = Field(
        pattern=r"^[A-Za-z]{2}$", description="ISO 639-1 code the banner was shown in", examples=["pl"]
    )
    action: CookieConsentAction = Field(description="Button the visitor used", examples=["custom"])
    categories: dict[str, bool] = Field(
        min_length=1,
        description="Decision for every banner category (required categories must be true)",
        examples=[{"necessary": True, "analytics": True, "marketing": False}],
    )

    @field_validator("language")
    @classmethod
    def lowercase_language(cls, v: str) -> str:
        return v.lower()
