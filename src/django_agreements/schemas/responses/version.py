# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for agreement versions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Primary key", examples=[1])
    definition_slug: str = Field(description="Parent definition slug", examples=["terms-of-service"])
    version_number: int = Field(description="Version number", examples=[3])
    summary_t9n: dict = Field(
        description="Checkbox label per language",
        examples=[{"en": "I accept the Terms of Service", "pl": "Akceptuję regulamin"}],
    )
    content_published_id: int | None = Field(None, description="ContentDB Published.pk", examples=[42])
    published_at: datetime | None = Field(
        None, description="Publication timestamp (null = draft)", examples=["2024-06-01T12:00:00Z"]
    )
    is_current: bool = Field(description="Whether this is the current published version", examples=[True])
    created_at: datetime = Field(description="Creation timestamp", examples=["2024-06-01T00:00:00Z"])


class VersionListResponse(BaseModel):
    count: int = Field(description="Total number of versions", examples=[3])
    next: str | None = Field(
        None,
        description="URL of next page",
        examples=["http://localhost:8000/api/agreements/v2/admin/versions/?page=2"],
    )
    previous: str | None = Field(None, description="URL of previous page", examples=[None])
    results: list[VersionResponse] = Field(description="List of versions", examples=[[]])
