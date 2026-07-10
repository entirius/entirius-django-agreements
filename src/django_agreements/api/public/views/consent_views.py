# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Public API views for consent submission and status."""

import uuid

from django.conf import settings as django_settings
from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import OpenApiParameter, extend_schema
from process_logger import ProcessLogger
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, ParseError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements import settings as agreements_settings
from django_agreements.api import raise_pydantic_as_drf
from django_agreements.api.public.authentication import APIKeyAuthentication
from django_agreements.schemas.requests.consent import (
    ConsentSubmitRequest,
    ConsentWithdrawRequest,
    NewsletterSubscribeRequest,
    TokenRequest,
)
from django_agreements.schemas.responses.consent import ConsentStatusResponse
from django_agreements.services import channel_service, consent_service, token_service

logger = ProcessLogger("PUBLIC_CONSENT_API", module="django_agreements")


def _send_confirmation_email(email: str, channel_idx: str, language: str | None) -> None:
    """Generate token and send newsletter confirmation via django-email.

    Module-level helper (not a ViewSet staticmethod) — avoids the class-name
    self-reference bug and keeps the view thin. django-email is treated as
    optional: ImportError/ProgrammingError early-return, any other exception
    is logged with full stack so support can trace SMTP / config failures.
    """
    from django.core.exceptions import ObjectDoesNotExist
    from django.db.utils import ProgrammingError

    try:
        from django_email.language import resolve_email_language
        from django_email.service.agreements.newsletter_signup import NewsletterSignupEmail
    except (ImportError, RuntimeError) as exc:
        logger.warning(f"django-email unavailable: {type(exc).__name__}")
        return

    try:
        channel = channel_service.get_channel(channel_idx)
    except (ObjectDoesNotExist, ProgrammingError) as exc:
        logger.warning(f"Channel {channel_idx!r} lookup failed: {type(exc).__name__}")
        channel = None

    resolved_lang = resolve_email_language(language, channel)

    token = token_service.generate_token(email, "marketing-email")
    base_url = agreements_settings.STOREFRONT_BASE_URL
    confirm_path = agreements_settings.NEWSLETTER_CONFIRM_PATH
    confirmation_link = f"{base_url}{confirm_path}?token={token}"
    unsubscribe_url = f"{base_url}/newsletter/unsubscribe?token={token}"

    try:
        service = NewsletterSignupEmail(language=resolved_lang, channel_idx=channel_idx)
        service.send(email=[email], confirmation_link=confirmation_link, unsubscribe_url=unsubscribe_url)
    except Exception as exc:
        logger.add_log_param_once("email", email)
        logger.add_log_param_once("channel_idx", channel_idx)
        logger.exception(exc)


class SubscribeThrottle(AnonRateThrottle):
    rate = "5/min"


class ConsentSubmitThrottle(AnonRateThrottle):
    rate = "20/min"


class TokenActionThrottle(AnonRateThrottle):
    rate = "10/min"


class PublicConsentViewSet(viewsets.ViewSet):
    """Public consent submission and status."""

    authentication_classes = [JWTAuthentication, APIKeyAuthentication]
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Submit consent",
        description=(
            "Record consent decisions for multiple agreements at once. "
            "When called with a valid JWT the email is always taken from the token — "
            "the body `email` field is ignored. "
            "Unauthenticated (guest checkout) requests use the body email."
        ),
        tags=["Consents"],
        parameters=[
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
            )
        ],
        responses={201: {"description": "Consent recorded"}, 400: {"description": "Validation error"}},
    )
    @action(detail=False, methods=["post"], throttle_classes=[ConsentSubmitThrottle])
    def create(self, request: Request, channel_idx: str, **kwargs) -> Response:
        try:
            data = ConsentSubmitRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        # Authenticated users are bound to their JWT identity — body email is ignored.
        # Guest (unauthenticated) flows use the email supplied in the request body.
        email = request.user.email if (request.user and request.user.is_authenticated) else data.email

        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:2048]

        try:
            consent_service.record_multiple_consents(
                email=email,
                agreements=[a.model_dump() for a in data.agreements],
                source=data.source,
                channel_idx=channel_idx,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except ObjectDoesNotExist as e:
            logger.warning(e)
            raise ParseError("Invalid request.") from e
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        except Exception as e:
            logger.exception(e)
            raise
        return Response({"detail": "Consent recorded."}, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Get consent status",
        description="Returns current consent status for all agreements. Requires JWT authentication. Email is taken from the token.",
        tags=["Consents"],
        parameters=[
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
            )
        ],
        responses={200: ConsentStatusResponse, 401: {"description": "Authentication required"}},
    )
    def status_check(self, request: Request, channel_idx: str, **kwargs) -> Response:
        if not (request.user and request.user.is_authenticated):
            return Response(
                {
                    "error": "UNAUTHORIZED",
                    "message": "Authentication required.",
                    "debug_id": uuid.uuid4().hex[:8],
                    "details": [],
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        email = request.user.email
        consents = consent_service.get_consent_status(email=email)
        response = ConsentStatusResponse(email=email, consents=consents)
        return Response(response.model_dump())

    @extend_schema(
        summary="Withdraw consent",
        description="Withdraw consent for one or more agreements. Requires JWT authentication. Email is taken from the token.",
        tags=["Consents"],
        parameters=[
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
            )
        ],
        responses={
            200: {"description": "Consent withdrawn"},
            400: {"description": "Validation error"},
            401: {"description": "Authentication required"},
        },
    )
    @action(detail=False, methods=["post"], throttle_classes=[ConsentSubmitThrottle])
    def withdraw(self, request: Request, channel_idx: str, **kwargs) -> Response:
        if not (request.user and request.user.is_authenticated):
            return Response(
                {
                    "error": "UNAUTHORIZED",
                    "message": "Authentication required.",
                    "debug_id": uuid.uuid4().hex[:8],
                    "details": [],
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            data = ConsentWithdrawRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        email = request.user.email
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:2048]

        try:
            consent_service.record_multiple_consents(
                email=email,
                agreements=[{"slug": s, "granted": False} for s in data.slugs],
                source="consent-page",
                channel_idx=channel_idx,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except ObjectDoesNotExist as e:
            logger.warning(e)
            raise ParseError("Invalid request.") from e
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        except Exception as e:
            logger.exception(e)
            raise
        return Response({"detail": "Consent withdrawn."})

    @extend_schema(
        summary="Subscribe to newsletter",
        description="Start double opt-in flow for marketing-email consent.",
        tags=["Consents"],
        parameters=[
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
            )
        ],
        responses={
            201: {"description": "Confirmation will be sent if eligible"},
            400: {"description": "Validation error"},
        },
    )
    @action(detail=False, methods=["post"], throttle_classes=[SubscribeThrottle])
    def subscribe(self, request: Request, channel_idx: str, **kwargs) -> Response:
        is_authenticated = request.user and request.user.is_authenticated
        if not is_authenticated and request.auth != "api_key":
            raise AuthenticationFailed("API key or authentication required.")

        try:
            data = NewsletterSubscribeRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        try:
            consent_service.request_consent(email=data.email, consent_type="marketing-email", channel_idx=channel_idx)
        except ObjectDoesNotExist as e:
            logger.warning(e)
            raise ParseError("Invalid request.") from e
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        except Exception as e:
            logger.exception(e)
            raise

        if getattr(django_settings, "NEWSLETTER_DOUBLE_OPTIN", True):
            _send_confirmation_email(data.email, channel_idx, data.language)

        return Response({"detail": "If eligible, a confirmation will be sent."}, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Confirm consent",
        description="Verify double opt-in token and activate consent.",
        tags=["Consents"],
        parameters=[
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
            )
        ],
        responses={200: {"description": "Consent confirmed"}, 400: {"description": "Invalid or expired token"}},
    )
    @action(detail=False, methods=["post"], throttle_classes=[TokenActionThrottle])
    def confirm(self, request: Request, channel_idx: str, **kwargs) -> Response:
        try:
            data = TokenRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        try:
            consent_service.confirm_consent(data.token)
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        except Exception as e:
            logger.exception(e)
            raise
        return Response({"detail": "Consent confirmed."})

    @extend_schema(
        summary="Unsubscribe via token",
        description="Revoke consent using a signed token from an email link (GDPR Art. 7).",
        tags=["Consents"],
        parameters=[
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
            ),
            OpenApiParameter(
                name="token",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Signed unsubscribe token",
                required=True,
            ),
        ],
        responses={200: {"description": "Consent revoked"}, 400: {"description": "Invalid or expired token"}},
    )
    @action(detail=False, methods=["get"], throttle_classes=[TokenActionThrottle])
    def unsubscribe(self, request: Request, channel_idx: str, **kwargs) -> Response:
        token = request.query_params.get("token")
        if not token:
            raise ParseError("Token query parameter is required.")

        try:
            consent_service.revoke_consent(token)
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        except Exception as e:
            logger.exception(e)
            raise
        return Response({"detail": "You have been unsubscribed."})
