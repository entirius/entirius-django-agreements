# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic request schemas for consent records."""

from pydantic import BaseModel, Field, field_validator

from django_agreements import settings as agreements_settings


class ConsentItem(BaseModel):
    slug: str = Field(description="Agreement definition slug", examples=["marketing-email"])
    granted: bool = Field(description="True = consent given, False = withdrawn", examples=[True])


class ConsentSubmitRequest(BaseModel):
    email: str = Field(description="Email address of the consenting person", examples=["user@example.com"])
    agreements: list[ConsentItem] = Field(
        description="List of consent decisions", examples=[[{"slug": "marketing-email", "granted": True}]], min_length=1
    )
    source: str = Field(description="Where the consent was given", examples=["checkout"])

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        allowed = agreements_settings.PUBLIC_CONSENT_SOURCES
        if v not in allowed:
            raise ValueError(f"Invalid source '{v}'. Must be one of: {sorted(allowed)}.")
        return v


class ConsentWithdrawRequest(BaseModel):
    slugs: list[str] = Field(
        description="Agreement slugs to withdraw consent for",
        examples=[["marketing-email", "marketing-sms"]],
        min_length=1,
    )


class NewsletterSubscribeRequest(BaseModel):
    email: str = Field(description="Email address to subscribe", examples=["user@example.com"])
    language: str | None = Field(
        default=None,
        description="Preferred language for the confirmation email (ISO 639-1, two letters). "
        "Falls back to the channel's default language, then to EMAIL_DEFAULT_LANGUAGE.",
        examples=["pl", "en"],
        pattern=r"^[a-zA-Z]{2}$",
    )


class TokenRequest(BaseModel):
    token: str = Field(description="Signed confirmation or unsubscribe token", examples=["eyJ..."])


class GenerateUnsubscribeUrlRequest(BaseModel):
    email: str = Field(description="Email address to generate unsubscribe URL for", examples=["user@example.com"])
    consent_type: str = Field(description="Agreement slug for the consent type", examples=["marketing-email"])
