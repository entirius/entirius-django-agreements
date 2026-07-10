# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for content history and consent text."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContentSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    published_id: int = Field(description="ContentDB Published.pk", examples=[42])
    created_at: datetime = Field(description="When this snapshot was published", examples=["2024-06-01T12:00:00Z"])
    language: str = Field(description="Language ISO2 code", examples=["en"])
    text_preview: str = Field(
        description="First 200 chars, HTML stripped", examples=["These Terms of Service govern..."]
    )
    text_html: str = Field(
        description="Full legal text HTML", examples=["<p>These Terms of Service govern your use of our services.</p>"]
    )
    draft_uid: str = Field(description="ContentDB Draft UUID for Builder link", examples=["a1b2c3d4"])
    warnings: list[str] = Field(
        default_factory=list,
        description="Structure validation warnings",
        examples=[["Expected exactly 1 section-text section, found 2"]],
    )


class ContentHistoryListResponse(BaseModel):
    definition_slug: str = Field(description="Parent definition slug", examples=["terms-of-service"])
    content_route: str = Field(description="ContentDB route path", examples=["regulamin"])
    snapshots: list[ContentSnapshotResponse] = Field(
        description="Published snapshots ordered by date desc", examples=[[]]
    )


class ConsentTextResponse(BaseModel):
    consent_id: int = Field(description="ConsentRecord.pk", examples=[1])
    consent_date: datetime = Field(description="When consent was given", examples=["2024-06-01T12:00:00Z"])
    agreement_slug: str = Field(description="Definition slug", examples=["terms-of-service"])
    agreement_name: str = Field(description="Definition display name", examples=["Terms of Service"])
    version_number: int = Field(description="Version that was active at consent time", examples=[3])
    published_id: int | None = Field(None, description="ContentDB Published.pk (null if not found)", examples=[42])
    published_at: datetime | None = Field(
        None, description="When the legal text was published", examples=["2024-06-01T12:00:00Z"]
    )
    text_html: str = Field(description="Legal text HTML that was live at consent time", examples=["<p>Terms...</p>"])
    language: str = Field(description="Language ISO2", examples=["en"])
