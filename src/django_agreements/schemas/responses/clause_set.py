# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for clause sets."""

from datetime import datetime

from pydantic import BaseModel, Field


class ClauseSetResponse(BaseModel):
    id: int = Field(description="Primary key", examples=[1])
    channel_idx: str = Field(description="Channel identifier", examples=["default-europe"])
    legal_basis: str = Field(description="GDPR legal basis", examples=["legitimate_interest"])
    language: str = Field(description="Language (ISO 639-1)", examples=["pl"])
    version: int = Field(description="Version within (channel, basis, language)", examples=[1])
    is_current: bool = Field(description="Current version for its triple", examples=[True])
    published_at: datetime | None = Field(None, description="Null = draft", examples=["2026-09-01T12:00:00Z"])
    info_clause: str = Field(description="Information clause", examples=["Your address {recipient_email} ..."])
    optout_clause: str = Field(description="Opt-out wording", examples=["Reply STOP to opt out."])
    retention_clause: str = Field(description="Retention statement", examples=["We keep your data for 12 months."])


class ClauseSetListResponse(BaseModel):
    count: int = Field(description="Total number of clause sets", examples=[4])
    next: str | None = Field(
        None,
        description="URL of next page",
        examples=["http://localhost:8000/api/agreements/v2/admin/clause-sets/?page=2"],
    )
    previous: str | None = Field(None, description="URL of previous page", examples=[None])
    results: list[ClauseSetResponse] = Field(description="List of clause sets", examples=[[]])
