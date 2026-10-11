# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Public API views for the cookie banner and the anonymous cookie consent log."""

import uuid

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from process_logger import ProcessLogger
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.exceptions import APIException, NotFound, ParseError, Throttled
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import exception_handler

from django_agreements.api import raise_pydantic_as_drf
from django_agreements.api.public.throttling import CookieConsentThrottle
from django_agreements.models import CookieConsent
from django_agreements.schemas.requests.cookie_consent import CookieConsentRequest
from django_agreements.schemas.responses.cookie_consent import CookieBannerResponse, CookieConsentRecordedResponse
from django_agreements.services import cookie_consent_service

logger = ProcessLogger("PUBLIC_COOKIE_CONSENT_API", module="django_agreements")

_TAGS = ["Public Cookie Consent"]
_NOT_FOUND = "No published cookie banner for this channel."
_BANNER_CACHE_CONTROL = "public, max-age=300"
_CHANNEL_PARAMETER = OpenApiParameter(
    name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
)


class StaleRevisionConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "stale_revision"
    default_detail = "Cookie banner revision is outdated — fetch cookie-banner again."


class InvalidCookieChoice(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid_request"
    default_detail = "The decision does not fit the cookie banner."


_ERROR_CODES = [
    (DRFValidationError, "VALIDATION_ERROR"),
    (ParseError, "VALIDATION_ERROR"),
    (InvalidCookieChoice, "INVALID_REQUEST"),
    (NotFound, "NOT_FOUND"),
    (StaleRevisionConflict, "STALE_REVISION"),
    (Throttled, "RATE_LIMITED"),
]


def _validation_details(detail) -> list[dict]:
    if not isinstance(detail, dict):
        return []
    return [
        {"field": field, "location": "body", "issue": "INVALID", "description": str(message)}
        for field, messages in detail.items()
        for message in (messages if isinstance(messages, list) else [messages])
    ]


def _envelope_exception_handler(exc, context):
    """DRF errors of the cookie endpoints as the v2 envelope (error, message, debug_id, details)."""
    response = exception_handler(exc, context)
    code = next((code for exc_class, code in _ERROR_CODES if isinstance(exc, exc_class)), None)
    if response is None or code is None:
        return response
    is_validation = isinstance(exc, DRFValidationError)
    response.data = {
        "error": code,
        "message": "Request validation failed." if is_validation else str(exc.detail),
        "debug_id": uuid.uuid4().hex[:8],
        "details": _validation_details(exc.detail) if is_validation else [],
    }
    return response


class _EnvelopeErrorsMixin:
    def get_exception_handler(self):
        return _envelope_exception_handler


class PublicCookieBannerViewSet(_EnvelopeErrorsMixin, viewsets.ViewSet):
    """The channel's current cookie banner in the visitor's language."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get the cookie banner",
        description=(
            "Returns the published cookie banner of the channel (a channel-specific banner beats the global one). "
            "Language: requested → channel default → first banner language. Send `revision` back with the decision. "
            "Cached publicly for 5 minutes — after a 409 fetch it again bypassing the cache."
        ),
        tags=_TAGS,
        parameters=[
            _CHANNEL_PARAMETER,
            OpenApiParameter(
                name="language", location=OpenApiParameter.QUERY, type=str, description="Preferred language (iso2)"
            ),
        ],
        responses={
            200: CookieBannerResponse,
            404: OpenApiResponse(description="Unknown channel or no published banner (NOT_FOUND)"),
        },
    )
    def retrieve(self, request: Request, channel_idx: str, **kwargs) -> Response:
        try:
            channel, version = cookie_consent_service.get_banner(channel_idx)
        except ObjectDoesNotExist as exc:
            raise NotFound(_NOT_FOUND) from exc
        except Exception as e:
            logger.exception(e)
            raise
        language = cookie_consent_service.resolve_language(channel, version, request.query_params.get("language"))
        payload = cookie_consent_service.banner_payload(version, language)
        response = Response(CookieBannerResponse.model_validate(payload).model_dump())
        response["Cache-Control"] = _BANNER_CACHE_CONTROL
        return response


def _record(channel_idx: str, data: CookieConsentRequest) -> CookieConsent:
    try:
        return cookie_consent_service.record(channel_idx=channel_idx, **data.model_dump())
    except cookie_consent_service.StaleRevisionError as exc:
        raise StaleRevisionConflict() from exc
    except ObjectDoesNotExist as exc:
        raise NotFound(_NOT_FOUND) from exc
    except ValueError as exc:
        raise InvalidCookieChoice(str(exc)) from exc
    except Exception as e:
        logger.exception(e)
        raise


class PublicCookieConsentViewSet(_EnvelopeErrorsMixin, viewsets.ViewSet):
    """Anonymous log of cookie banner decisions."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [CookieConsentThrottle]

    @extend_schema(
        summary="Record a cookie banner decision",
        description=(
            "Logs one decision for the banner `revision` in `language`. `categories` must list every banner "
            "category; required ones are true, `accept_all` means all true, `reject_all`/`withdraw` mean every "
            "optional one false. 409 `STALE_REVISION` when a newer banner was published — fetch it again. "
            "Errors use the v2 envelope (error, message, debug_id, details)."
        ),
        tags=_TAGS,
        parameters=[_CHANNEL_PARAMETER],
        request=CookieConsentRequest,
        responses={
            201: CookieConsentRecordedResponse,
            400: OpenApiResponse(
                description="Malformed body (VALIDATION_ERROR) or a decision not fitting the banner (INVALID_REQUEST)"
            ),
            404: OpenApiResponse(description="Unknown channel or no published banner (NOT_FOUND)"),
            409: OpenApiResponse(description="Stale banner revision (STALE_REVISION)"),
            429: OpenApiResponse(description="Too many requests (RATE_LIMITED)"),
        },
    )
    def create(self, request: Request, channel_idx: str, **kwargs) -> Response:
        try:
            data = CookieConsentRequest.model_validate(request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)
        consent = _record(channel_idx, data)
        response = CookieConsentRecordedResponse(
            consent_id=consent.consent_id,
            revision=consent.agreement_version_id,
            language=consent.language,
            action=consent.action,
            created_at=consent.created_at,
        )
        return Response(response.model_dump(), status=status.HTTP_201_CREATED)
