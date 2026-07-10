# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for agreement definitions."""

from typing import Literal

from pydantic import BaseModel, Field

AgreementCategory = Literal["mandatory", "marketing", "informational"]
AgreementConsentChannel = Literal["general", "email", "sms", "push", "web"]
AgreementDisplayContext = Literal["checkout", "registration", "newsletter"]


class DefinitionCreateRequest(BaseModel):
    slug: str = Field(description="Unique slug identifier", examples=["terms-of-service"], min_length=1, max_length=80)
    name: str = Field(
        description="Human-readable display name", examples=["Terms of Service"], min_length=1, max_length=200
    )
    category: AgreementCategory = Field(
        description="Agreement category: mandatory, marketing, or informational", examples=["mandatory"]
    )
    consent_channel: AgreementConsentChannel = Field(
        "general", description="Consent delivery channel: general, email, sms, push, web", examples=["general"]
    )
    channel_ids: list[int] = Field(
        default_factory=list, description="Channel PKs (empty = global, visible to all channels)", examples=[[1, 2]]
    )
    content_route: str = Field(
        "", description="ContentDB route to full legal document", examples=["regulamin"], max_length=200
    )
    display_contexts: list[AgreementDisplayContext] = Field(
        default_factory=list,
        description="Where this consent appears: checkout, registration, newsletter",
        examples=[["checkout", "registration"]],
    )
    is_active: bool = Field(True, description="Whether this definition is active", examples=[True])
    sort_order: int = Field(0, description="Display sort order (lower = first)", examples=[1], ge=0)


class DefinitionUpdateRequest(BaseModel):
    name: str | None = Field(
        None, description="Human-readable display name", examples=["Terms of Service"], min_length=1, max_length=200
    )
    category: AgreementCategory | None = Field(None, description="Agreement category", examples=["mandatory"])
    consent_channel: AgreementConsentChannel | None = Field(
        None, description="Consent delivery channel", examples=["email"]
    )
    channel_ids: list[int] | None = Field(
        None, description="Channel PKs (null = unchanged, [] = global)", examples=[[1, 2]]
    )
    content_route: str | None = Field(
        None, description="ContentDB route to full legal document", examples=["regulamin"], max_length=200
    )
    display_contexts: list[AgreementDisplayContext] | None = Field(
        None, description="Where this consent appears (null = unchanged)", examples=[["checkout", "registration"]]
    )
    is_active: bool | None = Field(None, description="Whether this definition is active", examples=[True])
    sort_order: int | None = Field(None, description="Display sort order (lower = first)", examples=[1], ge=0)
