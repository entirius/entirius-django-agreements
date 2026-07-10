# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for agreement definitions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Primary key", examples=[1])
    slug: str = Field(description="Unique slug identifier", examples=["terms-of-service"])
    name: str = Field(description="Display name", examples=["Terms of Service"])
    category: str = Field(description="Agreement category", examples=["mandatory"])
    consent_channel: str = Field(description="Consent delivery channel", examples=["general"])
    channel_ids: list[int] = Field(default_factory=list, description="Channel PKs (empty = global)", examples=[[1, 2]])
    content_route: str = Field(description="ContentDB route to legal document", examples=["regulamin"])
    is_active: bool = Field(description="Whether active", examples=[True])
    is_system: bool = Field(description="System consent (fixture-managed, cannot be deleted via CMS)", examples=[False])
    display_contexts: list[str] = Field(
        default_factory=list, description="Where this consent appears", examples=[["checkout", "registration"]]
    )
    sort_order: int = Field(description="Display sort order", examples=[1])
    current_version_number: int | None = Field(None, description="Current published version number", examples=[3])
    created_at: datetime = Field(description="Creation timestamp", examples=["2024-01-01T00:00:00Z"])
    modified_at: datetime = Field(description="Last update timestamp", examples=["2024-06-01T00:00:00Z"])


class DefinitionListResponse(BaseModel):
    count: int = Field(description="Total number of definitions", examples=[5])
    next: str | None = Field(
        None,
        description="URL of next page",
        examples=["http://localhost:8000/api/agreements/v2/admin/definitions/?page=2"],
    )
    previous: str | None = Field(None, description="URL of previous page", examples=[None])
    results: list[DefinitionResponse] = Field(description="List of definitions", examples=[[]])


class PublicDefinitionResponse(BaseModel):
    """Public definition response — includes resolved summary text."""

    slug: str = Field(description="Agreement slug", examples=["terms-of-service"])
    name: str = Field(description="Display name", examples=["Terms of Service"])
    category: str = Field(description="Category", examples=["mandatory"])
    consent_channel: str = Field(description="Consent channel type", examples=["general"])
    content_route: str = Field(description="Route to full legal page", examples=["regulamin"])
    sort_order: int = Field(description="Display order", examples=[1])
    summary: str = Field(
        description="Resolved checkbox label (may contain limited HTML: <a>, <b>, <i>, <u>)",
        examples=['I accept the <a href="/terms">Terms of Service</a>'],
    )
    version_number: int = Field(description="Current version number", examples=[3])


class PublicDefinitionListResponse(BaseModel):
    count: int = Field(description="Total number of active definitions", examples=[5])
    next: str | None = Field(
        None,
        description="URL of next page",
        examples=["http://localhost:8000/api/agreements/v2/default-europe/definitions/?page=2"],
    )
    previous: str | None = Field(None, description="URL of previous page", examples=[None])
    results: list[PublicDefinitionResponse] = Field(description="List of definitions", examples=[[]])


class UserDefinitionResponse(BaseModel):
    """Definition filtered for a specific user context — includes consent state."""

    slug: str = Field(description="Agreement slug", examples=["terms-of-service"])
    name: str = Field(description="Display name", examples=["Terms of Service"])
    category: str = Field(description="Category", examples=["mandatory"])
    consent_channel: str = Field(description="Consent channel type", examples=["general"])
    content_route: str = Field(description="Route to full legal page", examples=["regulamin"])
    sort_order: int = Field(description="Display order", examples=[1])
    summary: str = Field(
        description="Resolved checkbox label (may contain limited HTML)",
        examples=['I accept the <a href="/terms">Terms of Service</a>'],
    )
    is_system: bool = Field(description="System consent flag", examples=[True])
    already_consented: bool = Field(description="Whether user has already accepted this agreement", examples=[False])
    required: bool = Field(description="Whether this consent is mandatory", examples=[True])
    version_number: int = Field(description="Current version number", examples=[1])


class UserDefinitionListResponse(BaseModel):
    count: int = Field(description="Number of definitions for this context", examples=[3])
    results: list[UserDefinitionResponse] = Field(description="Filtered definitions", examples=[[]])
