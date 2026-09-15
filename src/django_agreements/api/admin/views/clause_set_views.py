# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for legal clause sets (read-only)."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from pydantic import ValidationError
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements.api import raise_pydantic_as_drf
from django_agreements.api.admin.pagination import AdminPageNumberPagination
from django_agreements.api.admin.permissions import IsAdminUser
from django_agreements.enums import LegalBasis
from django_agreements.schemas.requests.clause_set import ClauseSetListQuery
from django_agreements.schemas.responses.clause_set import ClauseSetListResponse
from django_agreements.services import clause_set_service

_ERROR_RESPONSES = {
    400: {"description": "Invalid filter"},
    401: {"description": "Authentication required"},
    403: {"description": "Permission denied"},
}


class ClauseSetViewSet(viewsets.ViewSet):
    """Admin read-only access to legal clause sets."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="List clause sets",
        description="Returns paginated legal clause sets with optional filters. Editing happens in the Django admin.",
        tags=["Agreement Clause Sets"],
        parameters=[
            OpenApiParameter(name="channel_idx", location=OpenApiParameter.QUERY, type=str, description="Channel idx"),
            OpenApiParameter(name="legal_basis", location=OpenApiParameter.QUERY, type=str, enum=LegalBasis.values),
            OpenApiParameter(name="language", location=OpenApiParameter.QUERY, type=str, description="ISO 639-1"),
            OpenApiParameter(name="current", location=OpenApiParameter.QUERY, type=bool, description="Current only"),
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=int, description="Page number"),
        ],
        responses={200: ClauseSetListResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, **kwargs) -> Response:
        try:
            query = ClauseSetListQuery.model_validate(request.query_params.dict())
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)
        qs = clause_set_service.list_clause_sets(**query.model_dump())
        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        return Response(
            ClauseSetListResponse(
                count=paginator.page.paginator.count,
                next=paginator.get_next_link(),
                previous=paginator.get_previous_link(),
                results=[clause_set_service.to_clause_set_response_dict(cs) for cs in page],
            ).model_dump()
        )
