# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for consent records."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConsentRecordResponse(BaseModel):
    id: int = Field(description="Primary key", examples=[1])
    email: str = Field(description="Email address", examples=["user@example.com"])
    customer_id: int | None = Field(None, description="Customer account ID", examples=[42])
    agreement_slug: str = Field(description="Agreement definition slug", examples=["marketing-email"])
    agreement_name: str = Field(description="Agreement display name", examples=["Email Marketing Consent"])
    category: str = Field(description="Agreement category", examples=["marketing"])
    version_number: int = Field(description="Version number", examples=[1])
    granted: bool = Field(description="Consent granted or withdrawn", examples=[True])
    source: str = Field(description="Consent source", examples=["checkout"])
    ip_address: str | None = Field(None, description="Client IP address", examples=["192.168.1.1"])
    channel_idx: str = Field(description="Channel where consent was given", examples=["default-europe"])
    created_at: datetime = Field(description="Record timestamp", examples=["2024-06-01T12:00:00Z"])


class ConsentRecordListResponse(BaseModel):
    count: int = Field(description="Total number of records", examples=[42])
    next: str | None = Field(
        None,
        description="URL of next page",
        examples=["http://localhost:8000/api/agreements/v2/admin/consents/?page=2"],
    )
    previous: str | None = Field(None, description="URL of previous page", examples=[None])
    results: list[ConsentRecordResponse] = Field(description="List of consent records", examples=[[]])


class ConsentStatusResponse(BaseModel):
    """Current consent status per agreement slug."""

    email: str = Field(description="Email address", examples=["user@example.com"])
    consents: dict[str, bool] = Field(
        description="Slug → granted status",
        examples=[{"terms-of-service": True, "marketing-email": False, "marketing-sms": False}],
    )


class UnsubscribeUrlResponse(BaseModel):
    url: str = Field(
        description="Signed unsubscribe URL",
        examples=["http://localhost:3000/newsletter/confirm?token=eyJ...&action=unsubscribe"],
    )


class ConsentPersonResponse(BaseModel):
    """Summary of a person's consent activity."""

    email: str = Field(description="Email address", examples=["user@example.com"])
    consent_count: int = Field(description="Total consent records", examples=[5])
    last_activity: datetime = Field(description="Most recent consent event", examples=["2024-06-01T12:00:00Z"])


class ConsentPersonListResponse(BaseModel):
    count: int = Field(description="Total unique emails", examples=[100])
    next: str | None = Field(
        None, description="URL of next page", examples=["http://localhost:8000/api/agreements/v2/admin/people/?page=2"]
    )
    previous: str | None = Field(None, description="URL of previous page", examples=[None])
    results: list[ConsentPersonResponse] = Field(description="List of people", examples=[[]])


class ConsentStatusItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = Field(description="granted, withdrawn, or pending", examples=["granted"])
    category: str = Field(description="mandatory, marketing, or informational", examples=["marketing"])
    name: str = Field(description="Human-readable agreement name", examples=["Email Marketing Consent"])


class ConsentPersonDetailResponse(BaseModel):
    """Full consent detail for a single email."""

    email: str = Field(description="Email address", examples=["user@example.com"])
    current_status: dict[str, ConsentStatusItem] = Field(
        description="Current consent status per slug with status, category, and name",
        examples=[
            {
                "marketing-email": {"status": "pending", "category": "marketing", "name": "Email Marketing Consent"},
                "terms-of-service": {"status": "granted", "category": "mandatory", "name": "Terms of Service"},
            }
        ],
    )
    history: list[ConsentRecordResponse] = Field(description="Full consent history (newest first)", examples=[[]])


class MarketingSubscriberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str = Field(description="Subscriber email", examples=["user@example.com"])
    agreement_slug: str = Field(description="Agreement definition slug", examples=["marketing-email"])
    agreement_name: str = Field(description="Agreement name", examples=["Email Marketing Consent"])
    consent_channel: str = Field(
        description="Consent channel of the agreement (email, sms, push, web, general)", examples=["email"]
    )
    granted_at: datetime = Field(description="When consent was granted", examples=["2024-06-01T12:00:00Z"])
    channel_idx: str = Field(description="Channel identifier", examples=["default-europe"])


class MarketingSubscriberListResponse(BaseModel):
    count: int = Field(description="Total number of active subscribers", examples=[50])
    results: list[MarketingSubscriberResponse] = Field(description="Active marketing subscribers", examples=[[]])
