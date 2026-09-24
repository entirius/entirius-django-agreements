# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Public API views for the cookie banner and the anonymous cookie consent log."""

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from process_logger import ProcessLogger
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.exceptions import APIException, NotFound, ParseError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from django_agreements.api import raise_pydantic_as_drf
from django_agreements.api.public.throttling import CookieConsentThrottle
from django_agreements.models import CookieConsent
from django_agreements.schemas.requests.cookie_consent import CookieConsentRequest
from django_agreements.schemas.responses.cookie_consent import CookieBannerResponse, CookieConsentRecordedResponse
from django_agreements.services import cookie_consent_service

logger = ProcessLogger("PUBLIC_COOKIE_CONSENT_API", module="django_agreements")

_TAGS = ["Public Cookie Consent"]
_NOT_FOUND = "No published cookie banner for this channel."
_CHANNEL_PARAMETER = OpenApiParameter(
    name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
)


class StaleRevisionConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "stale_revision"
    default_detail = "Cookie banner revision is outdated — fetch cookie-banner again."


class PublicCookieBannerViewSet(viewsets.ViewSet):
    """The channel's current cookie banner in the visitor's language."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get the cookie banner",
        description=(
            "Returns the published cookie banner of the channel (a channel-specific banner beats the global one). "
            "Language: requested → channel default → first banner language. Send `revision` back with the decision."
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
            404: OpenApiResponse(description="Unknown channel or no published banner"),
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
        return Response(CookieBannerResponse.model_validate(payload).model_dump())


def _record(channel_idx: str, data: CookieConsentRequest) -> CookieConsent:
    try:
        return cookie_consent_service.record(channel_idx=channel_idx, **data.model_dump())
    except cookie_consent_service.StaleRevisionError as exc:
        raise StaleRevisionConflict() from exc
    except ObjectDoesNotExist as exc:
        raise NotFound(_NOT_FOUND) from exc
    except ValueError as exc:
        raise ParseError(str(exc)) from exc
    except Exception as e:
        logger.exception(e)
        raise


class PublicCookieConsentViewSet(viewsets.ViewSet):
    """Anonymous log of cookie banner decisions."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [CookieConsentThrottle]

    @extend_schema(
        summary="Record a cookie banner decision",
        description=(
            "Logs one decision for the banner `revision` in `language`. `categories` must list every banner "
            "category; required ones are true, `accept_all` means all true, `reject_all`/`withdraw` mean every "
            "optional one false. 409 `stale_revision` when a newer banner was published — fetch it again."
        ),
        tags=_TAGS,
        parameters=[_CHANNEL_PARAMETER],
        request=CookieConsentRequest,
        responses={
            201: CookieConsentRecordedResponse,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Unknown channel or no published banner"),
            409: OpenApiResponse(description="Stale banner revision (code stale_revision)"),
            429: OpenApiResponse(description="Too many requests"),
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
