# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for order agreement snapshots."""

from datetime import datetime

from pydantic import BaseModel, Field


class OrderAgreementResponse(BaseModel):
    id: int = Field(description="Primary key", examples=[1])
    order_id: str = Field(description="Order UUID", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    email: str = Field(description="Customer email", examples=["customer@example.com"])
    agreement_slug: str = Field(description="Agreement slug", examples=["terms-of-service"])
    agreement_name: str = Field(description="Agreement name", examples=["Terms of Service"])
    version_number: int = Field(description="Version number", examples=[3])
    language: str = Field(description="Language shown", examples=["en"])
    granted: bool = Field(description="Was accepted", examples=[True])
    created_at: datetime = Field(description="Acceptance timestamp", examples=["2024-06-01T12:00:00Z"])


class OrderAgreementListResponse(BaseModel):
    count: int = Field(description="Total snapshots for this order", examples=[3])
    results: list[OrderAgreementResponse] = Field(description="List of agreement snapshots", examples=[[]])
