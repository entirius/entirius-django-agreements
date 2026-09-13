# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for clause sets."""

from pydantic import BaseModel, ConfigDict, Field

from django_agreements.enums import LegalBasis


class ClauseSetListQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel_idx: str | None = Field(None, description="Filter by channel idx", examples=["default-europe"])
    legal_basis: LegalBasis | None = Field(None, description="Filter by legal basis", examples=["consent"])
    language: str | None = Field(
        None, description="Filter by language (ISO 639-1)", examples=["pl"], pattern=r"^[a-zA-Z]{2}$"
    )
    current: bool | None = Field(None, description="Only current (true) or non-current (false)", examples=[True])
