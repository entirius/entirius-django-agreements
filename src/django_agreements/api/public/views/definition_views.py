# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Public API views for agreement definitions."""

import uuid

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from process_logger import ProcessLogger
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements.api.admin.pagination import AdminPageNumberPagination
from django_agreements.schemas.responses.definition import (
    PublicDefinitionListResponse,
    PublicDefinitionResponse,
    UserDefinitionListResponse,
    UserDefinitionResponse,
)
from django_agreements.services import channel_service, consent_service, definition_service, version_service

logger = ProcessLogger("PUBLIC_DEFINITION_API", module="django_agreements")


def _resolve_channel_default_lang(channel_idx: str) -> str | None:
    """Return channel default language iso2, or None if unavailable."""
    try:
        channel = channel_service.get_channel(idx=channel_idx)
        if channel.default_language:
            return channel.default_language.iso2
    except ObjectDoesNotExist:
        return None
    return None


@extend_schema_view(list=extend_schema(summary="List active agreement definitions", tags=["Agreements"]))
class PublicDefinitionViewSet(viewsets.ViewSet):
    """Public read-only access to active agreement definitions for a channel."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    @extend_schema(
        summary="List active agreement definitions",
        description=(
            "Returns active definitions visible in the requested channel "
            "(global + channel-matched). Includes resolved summary text."
        ),
        parameters=[
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
            ),
            OpenApiParameter(
                name="category",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Filter by category (comma-separated: mandatory,marketing)",
            ),
            OpenApiParameter(
                name="language",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Language code for summary resolution (iso2)",
            ),
        ],
        responses={200: PublicDefinitionListResponse},
    )
    def list(self, request: Request, channel_idx: str, **kwargs) -> Response:
        language = request.query_params.get("language")
        category = request.query_params.get("category")
        channel_default_lang = _resolve_channel_default_lang(channel_idx)

        qs = definition_service.list_definitions(
            include_inactive=False, category=category, channel_idx=channel_idx, include_cookies=False
        )
        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = []
        for defn in page:
            current_list = getattr(defn, "current_version_list", None)
            current = current_list[0] if current_list else None
            if not current:
                continue
            summary = version_service.resolve_summary(current, language, channel_default_lang)
            results.append(
                PublicDefinitionResponse(
                    slug=defn.slug,
                    name=defn.name,
                    category=defn.category,
                    consent_channel=defn.consent_channel,
                    content_route=defn.content_route,
                    sort_order=defn.sort_order,
                    summary=summary,
                    version_number=current.version_number,
                ).model_dump()
            )

        response = PublicDefinitionListResponse(
            count=len(results), next=paginator.get_next_link(), previous=paginator.get_previous_link(), results=results
        )
        return Response(response.model_dump())

    @extend_schema(
        summary="List definitions for user context",
        description=(
            "Returns definitions relevant for a specific user and context "
            "(checkout, registration, newsletter). Applies system consent rules "
            "and filters out already-accepted consents where appropriate."
        ),
        tags=["Agreements"],
        parameters=[
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
            ),
            OpenApiParameter(
                name="context",
                location=OpenApiParameter.QUERY,
                type=str,
                required=True,
                description="Display context: checkout, registration, or newsletter",
            ),
            OpenApiParameter(
                name="is_authenticated",
                location=OpenApiParameter.QUERY,
                type=bool,
                description="Whether user is logged in (affects privacy-policy display)",
            ),
            OpenApiParameter(
                name="language",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Language code for summary resolution (iso2)",
            ),
        ],
        responses={200: UserDefinitionListResponse, 400: {"description": "Validation error"}},
    )
    def for_user(self, request: Request, channel_idx: str, **kwargs) -> Response:
        context = request.query_params.get("context", "")
        if request.user and request.user.is_authenticated:
            email = request.user.email
        else:
            email = None  # guests never expose consent state
        is_authenticated = request.user and request.user.is_authenticated
        language = request.query_params.get("language")

        if not context:
            return Response(
                {
                    "error": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "debug_id": uuid.uuid4().hex[:8],
                    "details": [
                        {
                            "field": "context",
                            "location": "query",
                            "issue": "REQUIRED",
                            "description": "context query parameter is required.",
                        }
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        channel_default_lang = _resolve_channel_default_lang(channel_idx)

        definitions = consent_service.get_definitions_for_user(
            channel_idx=channel_idx,
            context=context,
            email=email,
            is_authenticated=is_authenticated,
            language=language,
            channel_default_lang=channel_default_lang,
        )
        results = [
            UserDefinitionResponse(
                slug=defn_dict["slug"],
                name=defn_dict["name"],
                category=defn_dict["category"],
                consent_channel=defn_dict["consent_channel"],
                content_route=defn_dict["content_route"],
                sort_order=defn_dict["sort_order"],
                summary=defn_dict["summary"],
                is_system=defn_dict["is_system"],
                already_consented=defn_dict["already_consented"],
                required=defn_dict["required"],
                version_number=defn_dict["version_number"],
            ).model_dump()
            for defn_dict in definitions
        ]

        response = UserDefinitionListResponse(count=len(results), results=results)
        return Response(response.model_dump())
