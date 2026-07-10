# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for agreement versions."""

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements.api import raise_pydantic_as_drf
from django_agreements.api.admin.pagination import AdminPageNumberPagination
from django_agreements.api.admin.permissions import IsAdminUser
from django_agreements.schemas.requests.version import VersionCreateRequest, VersionUpdateRequest
from django_agreements.schemas.responses.version import VersionListResponse, VersionResponse
from django_agreements.services import version_service

_ERROR_RESPONSES = {
    400: {"description": "Validation error"},
    401: {"description": "Authentication required"},
    403: {"description": "Permission denied"},
    404: {"description": "Not found"},
}


@extend_schema_view(
    list=extend_schema(summary="List agreement versions", tags=["Agreement Versions"]),
    create=extend_schema(summary="Create agreement version", tags=["Agreement Versions"]),
)
class VersionViewSet(viewsets.ViewSet):
    """Admin CRUD for agreement versions (nested under definition)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="List agreement versions",
        description="Returns all versions for a definition, ordered by version_number descending.",
        parameters=[
            OpenApiParameter(name="slug", location=OpenApiParameter.PATH, type=str, description="Definition slug"),
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=int, description="Page number"),
        ],
        responses={200: VersionListResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, slug: str, **kwargs) -> Response:
        try:
            qs = version_service.list_versions(definition_slug=slug)
        except ObjectDoesNotExist as exc:
            raise NotFound("Agreement definition not found.") from exc
        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = [version_service.to_version_response_dict(v) for v in page]
        response = VersionListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response.model_dump())

    @extend_schema(
        summary="Create agreement version",
        description="Creates a new draft version for the definition.",
        parameters=[
            OpenApiParameter(name="slug", location=OpenApiParameter.PATH, type=str, description="Definition slug")
        ],
        responses={201: VersionResponse, **_ERROR_RESPONSES},
    )
    def create(self, request: Request, slug: str, **kwargs) -> Response:
        try:
            data = VersionCreateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)
        try:
            version = version_service.create_version(
                definition_slug=slug, summary_t9n=data.summary_t9n, content_published_id=data.content_published_id
            )
        except ObjectDoesNotExist as exc:
            raise NotFound("Agreement definition not found.") from exc
        return Response(version_service.to_version_response_dict(version), status=status.HTTP_201_CREATED)


@extend_schema_view(
    retrieve=extend_schema(summary="Retrieve agreement version", tags=["Agreement Versions"]),
    partial_update=extend_schema(summary="Update draft version", tags=["Agreement Versions"]),
)
class VersionDetailViewSet(viewsets.ViewSet):
    """Version detail, update draft, and publish actions."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Retrieve agreement version",
        description="Returns a single version by its primary key.",
        parameters=[
            OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=int, description="Version primary key")
        ],
        responses={200: VersionResponse, **_ERROR_RESPONSES},
    )
    def retrieve(self, request: Request, pk: int, **kwargs) -> Response:
        try:
            version = version_service.get_version(pk=int(pk))
        except ObjectDoesNotExist as exc:
            raise NotFound() from exc
        return Response(version_service.to_version_response_dict(version))

    @extend_schema(
        summary="Update draft version",
        description="Updates a draft version. Returns 400 if already published.",
        parameters=[
            OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=int, description="Version primary key")
        ],
        responses={200: VersionResponse, **_ERROR_RESPONSES},
    )
    def partial_update(self, request: Request, pk: int, **kwargs) -> Response:
        try:
            data = VersionUpdateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)
        updates = {}
        if data.summary_t9n is not None:
            updates["summary_t9n"] = data.summary_t9n
        if data.content_published_id is not None:
            updates["content_published_id"] = data.content_published_id
        try:
            version = version_service.update_draft_version(pk=int(pk), **updates)
        except ObjectDoesNotExist as exc:
            raise NotFound() from exc
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        return Response(version_service.to_version_response_dict(version))

    @extend_schema(
        summary="Publish agreement version",
        description="Publishes a draft version. Sets published_at and is_current=True.",
        tags=["Agreement Versions"],
        parameters=[
            OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=int, description="Version primary key")
        ],
        responses={200: VersionResponse, **_ERROR_RESPONSES},
    )
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request: Request, pk: int, **kwargs) -> Response:
        try:
            version = version_service.publish_version(pk=int(pk))
        except ObjectDoesNotExist as exc:
            raise NotFound() from exc
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        return Response(version_service.to_version_response_dict(version))
