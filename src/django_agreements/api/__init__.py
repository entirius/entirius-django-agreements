"""Agreements API package."""

from pydantic import ValidationError as PydanticValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError


def raise_pydantic_as_drf(exc: PydanticValidationError) -> None:
    """Convert Pydantic ValidationError to DRF ValidationError."""
    detail: dict[str, list[str]] = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"]) or "non_field_errors"
        detail.setdefault(field, []).append(error["msg"])
    raise DRFValidationError(detail)
