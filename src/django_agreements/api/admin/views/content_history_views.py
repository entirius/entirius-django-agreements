# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for content history and consent text retrieval."""

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements.api.admin.permissions import IsAdminUser
from django_agreements.schemas.responses.content_history import (
    ConsentTextResponse,
    ContentHistoryListResponse,
    ContentSnapshotResponse,
)
from django_agreements.services import consent_service, content_history_service, definition_service

_ERROR_RESPONSES = {
    400: {"description": "Validation error"},
    401: {"description": "Authentication required"},
    403: {"description": "Permission denied"},
    404: {"description": "Not found"},
}


class ContentHistoryViewSet(viewsets.ViewSet):
    """Admin endpoints for legal page version history and consent text retrieval."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="List legal page snapshots",
        description=(
            "Returns all ContentDB Published snapshots for the legal page linked to "
            "a definition, ordered by date descending. Returns 404 if the definition "
            "has no content_route (marketing agreements)."
        ),
        tags=["Content History"],
        parameters=[
            OpenApiParameter(
                name="slug", location=OpenApiParameter.PATH, type=str, description="Agreement definition slug"
            ),
            OpenApiParameter(
                name="language",
                location=OpenApiParameter.QUERY,
                type=str,
                required=False,
                description="Filter snapshots by language ISO2 (e.g. 'en')",
            ),
        ],
        responses={200: ContentHistoryListResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, slug: str, **kwargs) -> Response:
        try:
            definition = definition_service.get_definition(slug=slug)
        except ObjectDoesNotExist as exc:
            raise NotFound("Agreement definition not found.") from exc

        if not definition.content_route:
            raise NotFound("This definition has no legal page (content_route is empty).")

        language = request.query_params.get("language")
        raw_snapshots = content_history_service.list_legal_snapshots(definition.content_route, language)

        snapshots = [
            ContentSnapshotResponse(
                published_id=s["published_id"],
                created_at=s["created_at"],
                language=s["language"] or "",
                text_preview=s["text_preview"],
                text_html=s["text_html"],
                draft_uid=s["draft_uid"] or "",
                warnings=s["warnings"],
            )
            for s in raw_snapshots
        ]

        response = ContentHistoryListResponse(
            definition_slug=slug, content_route=definition.content_route, snapshots=snapshots
        )
        return Response(response.model_dump())

    @extend_schema(
        summary="Retrieve legal text at consent time",
        description=(
            "Returns the legal text HTML that was live when a specific consent was given. "
            "Looks up the ConsentRecord by record_id, verifies it belongs to the given email, "
            "then fetches the ContentDB snapshot active at that moment."
        ),
        tags=["Content History"],
        parameters=[
            OpenApiParameter(
                name="email", location=OpenApiParameter.PATH, type=str, description="Consent holder email address"
            ),
            OpenApiParameter(
                name="record_id", location=OpenApiParameter.PATH, type=int, description="ConsentRecord primary key"
            ),
            OpenApiParameter(
                name="language",
                location=OpenApiParameter.QUERY,
                type=str,
                required=False,
                description="Language ISO2 for the legal text (default: 'en')",
            ),
        ],
        responses={200: ConsentTextResponse, **_ERROR_RESPONSES},
    )
    def consent_text(self, request: Request, email: str, record_id: int, **kwargs) -> Response:
        try:
            record = consent_service.get_consent_record(pk=record_id, email=email)
        except ObjectDoesNotExist as exc:
            raise NotFound("Consent record not found.") from exc

        definition = record.agreement_version.definition
        content_route = definition.content_route

        if not content_route:
            raise NotFound("This agreement has no legal page (content_route is empty).")

        language = request.query_params.get("language", "en")
        snapshot = content_history_service.get_legal_text_at_time(content_route, record.created_at, language)

        if snapshot is None:
            raise NotFound("No legal text snapshot found for this consent date.")

        response = ConsentTextResponse(
            consent_id=record.pk,
            consent_date=record.created_at,
            agreement_slug=definition.slug,
            agreement_name=definition.name,
            version_number=record.agreement_version.version_number,
            published_id=snapshot["published_id"],
            published_at=snapshot["created_at"],
            text_html=snapshot["text_html"],
            language=language,
        )
        return Response(response.model_dump())
