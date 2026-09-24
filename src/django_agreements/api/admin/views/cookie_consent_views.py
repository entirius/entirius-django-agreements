# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for the anonymous cookie consent log: list, export, stats, history and erasure."""

import csv
import json
from collections.abc import Callable, Iterator
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements.api.admin.pagination import AdminPageNumberPagination
from django_agreements.api.admin.permissions import IsAdminUser
from django_agreements.api.admin.views.consent_views import _ERROR_RESPONSES, _csv_safe
from django_agreements.models import CookieConsent
from django_agreements.schemas.responses.cookie_consent import (
    CookieConsentEraseResponse,
    CookieConsentListResponse,
    CookieConsentResponse,
    CookieConsentStatsResponse,
)
from django_agreements.services import cookie_consent_service

_TAGS = ["Cookie Consents"]
_INVALID_FILTER = "Invalid filter: dates must be ISO 8601, revision an integer, consent_id a UUID."
_CSV_COLUMNS = [
    "created_at",
    "consent_id",
    "channel_idx",
    "language",
    "definition_slug",
    "version_number",
    "revision",
    "action",
    "categories",
]


def _query(name: str, description: str, value_type=str) -> OpenApiParameter:
    return OpenApiParameter(name=name, location=OpenApiParameter.QUERY, type=value_type, description=description)


_STATS_PARAMETERS = [
    _query("channel_idx", "Filter by channel"),
    _query("language", "Filter by banner language (iso2)"),
    _query("date_from", "Decisions from this date/time (ISO 8601)"),
    _query("date_to", "Decisions up to this date/time (ISO 8601)"),
]
_LIST_PARAMETERS = [
    _query("consent_id", "Filter by the visitor's consent id", OpenApiTypes.UUID),
    _query("action", "Filter by action: accept_all, reject_all, custom, withdraw"),
    _query("revision", "Filter by banner revision (agreement version id)", int),
    *_STATS_PARAMETERS,
]
_PAGE_PARAMETERS = [
    _query("page", "Page number", int),
    _query("page_size", "Items per page (max 100)", int),
]
_CONSENT_ID_PARAMETER = OpenApiParameter(
    name="consent_id", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="Visitor's consent id"
)


def _filtered(request: Request, service_call: Callable, names: list[OpenApiParameter]):
    """Call the service with the query filters in `names`; a malformed value is a 400, never a 500."""
    filters = {param.name: request.query_params.get(param.name) for param in names}
    try:
        return service_call(**filters)
    except (ValueError, DjangoValidationError) as exc:
        raise ValidationError(_INVALID_FILTER) from exc


def _to_response(row: CookieConsent) -> dict:
    version = row.agreement_version
    return CookieConsentResponse(
        id=row.pk,
        consent_id=row.consent_id,
        channel_idx=row.channel_idx,
        language=row.language,
        revision=version.pk,
        version_number=version.version_number,
        definition_slug=version.definition.slug,
        action=row.action,
        categories=row.categories,
        created_at=row.created_at,
    ).model_dump()


def _paginated(request: Request, queryset: QuerySet) -> Response:
    paginator = AdminPageNumberPagination()
    page = paginator.paginate_queryset(queryset, request)
    response = CookieConsentListResponse(
        count=paginator.page.paginator.count,
        next=paginator.get_next_link(),
        previous=paginator.get_previous_link(),
        results=[_to_response(row) for row in page],
    )
    return Response(response.model_dump())


class _Echo:
    """Pseudo-buffer: csv.writer returns each formatted line instead of storing it."""

    def write(self, value: str) -> str:
        return value


def _csv_cells(row: CookieConsent) -> list[str]:
    version = row.agreement_version
    cells = [
        row.created_at.isoformat(),
        row.consent_id,
        row.channel_idx,
        row.language,
        version.definition.slug,
        version.version_number,
        version.pk,
        row.action,
        json.dumps(row.categories, separators=(",", ":")),
    ]
    return [_csv_safe(cell) for cell in cells]


def _csv_rows(queryset: QuerySet) -> Iterator[str]:
    writer = csv.writer(_Echo())
    yield writer.writerow(_CSV_COLUMNS)
    for row in queryset.iterator(chunk_size=2000):
        yield writer.writerow(_csv_cells(row))


class CookieConsentViewSet(viewsets.ViewSet):
    """Admin access to the cookie consent log; erasure is the only write."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="List cookie consents",
        description="Paginated cookie banner decisions, newest first, with optional filters.",
        tags=_TAGS,
        parameters=[*_LIST_PARAMETERS, *_PAGE_PARAMETERS],
        responses={
            200: CookieConsentListResponse,
            400: OpenApiResponse(description="Invalid filter"),
            **_ERROR_RESPONSES,
        },
    )
    def list(self, request: Request, **kwargs) -> Response:
        return _paginated(request, _filtered(request, cookie_consent_service.list_consents, _LIST_PARAMETERS))

    @extend_schema(
        summary="Export cookie consents as CSV",
        description="Streams the filtered decisions as CSV. Columns: " + ", ".join(_CSV_COLUMNS) + ".",
        tags=_TAGS,
        parameters=_LIST_PARAMETERS,
        responses={
            200: OpenApiResponse(description="CSV file download"),
            400: OpenApiResponse(description="Invalid filter"),
            **_ERROR_RESPONSES,
        },
    )
    def export(self, request: Request, **kwargs) -> StreamingHttpResponse:
        queryset = _filtered(request, cookie_consent_service.list_consents, _LIST_PARAMETERS)
        response = StreamingHttpResponse(_csv_rows(queryset), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="cookie-consents.csv"'
        return response

    @extend_schema(
        summary="Cookie consent statistics",
        description="Decision counts per UTC day, banner revision, language and action.",
        tags=_TAGS,
        parameters=_STATS_PARAMETERS,
        responses={
            200: CookieConsentStatsResponse,
            400: OpenApiResponse(description="Invalid filter"),
            **_ERROR_RESPONSES,
        },
    )
    def stats(self, request: Request, **kwargs) -> Response:
        rows = _filtered(request, cookie_consent_service.daily_stats, _STATS_PARAMETERS)
        return Response(CookieConsentStatsResponse(results=rows).model_dump())

    @extend_schema(
        summary="Cookie consent history of a visitor",
        description="Every decision of one consent id, newest first (GDPR access request). Unknown id → count 0.",
        tags=_TAGS,
        parameters=[_CONSENT_ID_PARAMETER, *_PAGE_PARAMETERS],
        responses={200: CookieConsentListResponse, **_ERROR_RESPONSES},
    )
    def history(self, request: Request, consent_id: UUID, **kwargs) -> Response:
        return _paginated(request, cookie_consent_service.history(consent_id))

    @extend_schema(
        summary="Erase a visitor's cookie consent id",
        description=(
            "GDPR erasure: every decision of the id gets one new random consent id. "
            "Rows stay for statistics but can no longer be linked to the device."
        ),
        tags=_TAGS,
        request=None,
        parameters=[_CONSENT_ID_PARAMETER],
        responses={200: CookieConsentEraseResponse, **_ERROR_RESPONSES},
    )
    def erase(self, request: Request, consent_id: UUID, **kwargs) -> Response:
        erased = cookie_consent_service.erase(consent_id)
        return Response(CookieConsentEraseResponse(erased=erased).model_dump())
