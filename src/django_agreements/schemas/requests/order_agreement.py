# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for order agreement snapshots."""

from pydantic import BaseModel, Field


class OrderAgreementRequest(BaseModel):
    email: str = Field(description="Customer email", examples=["customer@example.com"])
    slugs: list[str] = Field(
        description="Agreement definition slugs accepted at checkout",
        examples=[["terms-of-service", "privacy-policy", "marketing-email"]],
        min_length=1,
    )
    language: str = Field("en", description="Language version shown to customer (iso2)", examples=["en"], max_length=5)
