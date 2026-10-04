# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for agreement definitions."""

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements.api import raise_pydantic_as_drf
from django_agreements.api.admin.pagination import AdminPageNumberPagination
from django_agreements.api.admin.permissions import IsAdminUser
from django_agreements.schemas.requests.definition import DefinitionCreateRequest, DefinitionUpdateRequest
from django_agreements.schemas.responses.definition import DefinitionListResponse, DefinitionResponse
from django_agreements.services import definition_service

_ERROR_RESPONSES = {
    400: {"description": "Validation error"},
    401: {"description": "Authentication required"},
    403: {"description": "Permission denied"},
    404: {"description": "Not found"},
}


@extend_schema_view(
    list=extend_schema(summary="List agreement definitions", tags=["Agreement Definitions"]),
    create=extend_schema(summary="Create agreement definition", tags=["Agreement Definitions"]),
    retrieve=extend_schema(summary="Retrieve agreement definition", tags=["Agreement Definitions"]),
    partial_update=extend_schema(summary="Update agreement definition", tags=["Agreement Definitions"]),
    destroy=extend_schema(summary="Delete agreement definition", tags=["Agreement Definitions"]),
)
class DefinitionViewSet(viewsets.ViewSet):
    """Admin CRUD for agreement definitions."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    access_area = "agreements.definitions"

    @extend_schema(
        summary="List agreement definitions",
        description="Returns a paginated list of all agreement definitions.",
        parameters=[
            OpenApiParameter(
                name="category",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Filter by category (comma-separated: mandatory,marketing)",
            ),
            OpenApiParameter(
                name="consent_channel",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Filter by consent channel (email, sms, push, web, general)",
            ),
            OpenApiParameter(
                name="is_active", location=OpenApiParameter.QUERY, type=bool, description="Filter by active status"
            ),
            OpenApiParameter(
                name="search", location=OpenApiParameter.QUERY, type=str, description="Search by name or slug"
            ),
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=int, description="Page number"),
            OpenApiParameter(
                name="page_size", location=OpenApiParameter.QUERY, type=int, description="Items per page (max 100)"
            ),
        ],
        responses={200: DefinitionListResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, **kwargs) -> Response:
        qs = definition_service.list_definitions(
            include_inactive=True,
            category=request.query_params.get("category"),
            consent_channel=request.query_params.get("consent_channel"),
            search=request.query_params.get("search"),
        )

        # Filter by is_active if explicitly provided
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")

        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = [definition_service.to_definition_response_dict(d) for d in page]
        response = DefinitionListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response.model_dump())

    @extend_schema(
        summary="Create agreement definition",
        description="Creates a new agreement definition.",
        responses={201: DefinitionResponse, **_ERROR_RESPONSES},
    )
    def create(self, request: Request, **kwargs) -> Response:
        try:
            data = DefinitionCreateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        existing = definition_service.get_existing_by_slug(data.slug)
        if existing:
            if not existing.is_active:
                defn, _ = definition_service.create_or_reactivate_definition(
                    slug=data.slug,
                    name=data.name,
                    category=data.category,
                    consent_channel=data.consent_channel,
                    content_route=data.content_route,
                    is_active=data.is_active,
                    sort_order=data.sort_order,
                    channel_ids=data.channel_ids,
                    display_contexts=data.display_contexts,
                )
                return Response(definition_service.to_definition_response_dict(defn), status=status.HTTP_201_CREATED)
            raise ParseError(f"Definition with slug '{data.slug}' already exists.")
        try:
            defn = definition_service.create_definition(
                slug=data.slug,
                name=data.name,
                category=data.category,
                consent_channel=data.consent_channel,
                content_route=data.content_route,
                is_active=data.is_active,
                sort_order=data.sort_order,
                channel_ids=data.channel_ids,
                display_contexts=data.display_contexts,
            )
        except IntegrityError as exc:
            raise ParseError(f"Definition with slug '{data.slug}' already exists.") from exc
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        return Response(definition_service.to_definition_response_dict(defn), status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Retrieve agreement definition",
        description="Returns a single agreement definition by slug.",
        parameters=[
            OpenApiParameter(name="slug", location=OpenApiParameter.PATH, type=str, description="Definition slug")
        ],
        responses={200: DefinitionResponse, **_ERROR_RESPONSES},
    )
    def retrieve(self, request: Request, slug: str, **kwargs) -> Response:
        try:
            defn = definition_service.get_definition(slug=slug)
        except ObjectDoesNotExist as exc:
            raise NotFound() from exc
        return Response(definition_service.to_definition_response_dict(defn))

    @extend_schema(
        summary="Update agreement definition",
        description="Partially updates an agreement definition. Only provided fields are changed.",
        parameters=[
            OpenApiParameter(name="slug", location=OpenApiParameter.PATH, type=str, description="Definition slug")
        ],
        responses={200: DefinitionResponse, **_ERROR_RESPONSES},
    )
    def partial_update(self, request: Request, slug: str, **kwargs) -> Response:
        try:
            data = DefinitionUpdateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)
        updates = data.model_dump(exclude_none=True)
        try:
            defn = definition_service.update_definition(slug=slug, **updates)
        except ObjectDoesNotExist as exc:
            raise NotFound() from exc
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        return Response(definition_service.to_definition_response_dict(defn))

    @extend_schema(
        summary="Delete agreement definition",
        description="Soft-deletes (deactivates) an agreement definition.",
        parameters=[
            OpenApiParameter(name="slug", location=OpenApiParameter.PATH, type=str, description="Definition slug")
        ],
        responses={204: None, **_ERROR_RESPONSES},
    )
    def destroy(self, request: Request, slug: str, **kwargs) -> Response:
        try:
            definition_service.delete_definition(slug=slug)
        except ObjectDoesNotExist as exc:
            raise NotFound() from exc
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)
