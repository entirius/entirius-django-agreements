# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for consent records (read-only audit log) and people view."""

from django.http import StreamingHttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements.api.admin.pagination import AdminPageNumberPagination
from django_agreements.api.admin.permissions import IsAdminUser
from django_agreements.schemas.responses.consent import (
    ConsentPersonDetailResponse,
    ConsentPersonListResponse,
    ConsentPersonResponse,
    ConsentRecordListResponse,
    ConsentStatusItem,
    MarketingSubscriberListResponse,
    MarketingSubscriberResponse,
)
from django_agreements.schemas.responses.order_agreement import OrderAgreementListResponse
from django_agreements.services import consent_service, order_agreement_service

_ERROR_RESPONSES = {401: {"description": "Authentication required"}, 403: {"description": "Permission denied"}}


@extend_schema_view(list=extend_schema(summary="List consent records", tags=["Consent Records"]))
class ConsentViewSet(viewsets.ViewSet):
    """Admin read-only access to consent records."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    access_area = "agreements.consents"

    @extend_schema(
        summary="List consent records",
        description="Returns paginated consent records with optional filters.",
        parameters=[
            OpenApiParameter(
                name="email", location=OpenApiParameter.QUERY, type=str, description="Filter by email address"
            ),
            OpenApiParameter(
                name="slug", location=OpenApiParameter.QUERY, type=str, description="Filter by agreement slug"
            ),
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.QUERY, type=str, description="Filter by channel"
            ),
            OpenApiParameter(
                name="date_from",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Filter records from date (ISO 8601)",
            ),
            OpenApiParameter(
                name="date_to",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Filter records to date (ISO 8601)",
            ),
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=int, description="Page number"),
        ],
        responses={200: ConsentRecordListResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, **kwargs) -> Response:
        qs = consent_service.list_consent_records(
            email=request.query_params.get("email"),
            slug=request.query_params.get("slug"),
            channel_idx=request.query_params.get("channel_idx"),
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
        )
        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = [consent_service.to_consent_response_dict(r) for r in page]
        response = ConsentRecordListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response.model_dump())

    @extend_schema(
        summary="Get consent history for email",
        description="Returns full consent history for a specific email address.",
        tags=["Consent Records"],
        parameters=[
            OpenApiParameter(name="email", location=OpenApiParameter.PATH, type=str, description="Email address")
        ],
        responses={200: ConsentRecordListResponse, **_ERROR_RESPONSES},
    )
    def history(self, request: Request, email: str, **kwargs) -> Response:
        qs = consent_service.get_consent_history(email=email)
        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = [consent_service.to_consent_response_dict(r) for r in page]
        response = ConsentRecordListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response.model_dump())


@extend_schema_view(list=extend_schema(summary="List consent people", tags=["Consent People"]))
class PeopleViewSet(viewsets.ViewSet):
    """Admin view of unique consent holders (deduplicated by email)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    access_area = "agreements.consents"

    @extend_schema(
        summary="List consent people",
        description="Returns unique emails with consent count and last activity.",
        parameters=[
            OpenApiParameter(name="search", location=OpenApiParameter.QUERY, type=str, description="Search by email"),
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=int, description="Page number"),
            OpenApiParameter(
                name="page_size", location=OpenApiParameter.QUERY, type=int, description="Items per page (max 100)"
            ),
        ],
        responses={200: ConsentPersonListResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, **kwargs) -> Response:
        qs = consent_service.list_consent_people(search=request.query_params.get("search"))
        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = [
            ConsentPersonResponse(
                email=row["email"], consent_count=row["consent_count"], last_activity=row["last_activity"]
            ).model_dump()
            for row in page
        ]
        response = ConsentPersonListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response.model_dump())

    @extend_schema(
        summary="Get person consent detail",
        description="Returns current consent status and full history for an email.",
        tags=["Consent People"],
        parameters=[
            OpenApiParameter(name="email", location=OpenApiParameter.PATH, type=str, description="Email address")
        ],
        responses={200: ConsentPersonDetailResponse, **_ERROR_RESPONSES},
    )
    def retrieve(self, request: Request, email: str, **kwargs) -> Response:
        detail = consent_service.get_person_detail(email=email)
        history_records = [consent_service.to_consent_response_dict(r) for r in detail["history"][:100]]
        current_status = {slug: ConsentStatusItem(**item) for slug, item in detail["current_status"].items()}
        response = ConsentPersonDetailResponse(
            email=detail["email"], current_status=current_status, history=history_records
        )
        return Response(response.model_dump())


_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    """Prefix formula-injection characters so spreadsheet apps don't execute them."""
    s = str(value)
    if s.startswith(_CSV_INJECTION_PREFIXES):
        return f"'{s}"
    return s


def _csv_rows(queryset):
    """Generator yielding CSV rows for marketing subscribers."""
    yield "email,agreement,consent_channel,granted_at,channel\r\n"
    for record in queryset:
        row = (
            f"{_csv_safe(record.email)},"
            f"{_csv_safe(record.agreement_version.definition.slug)},"
            f"{_csv_safe(record.channel_idx)},"
            f"{record.created_at.isoformat()},"
            f"{_csv_safe(record.channel_idx)}\r\n"
        )
        yield row


@extend_schema_view(list=extend_schema(summary="List active marketing subscribers", tags=["Marketing Subscribers"]))
class MarketingSubscribersViewSet(viewsets.ViewSet):
    """Admin read-only access to active marketing consent subscribers."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    access_area = "agreements.consents"
    pagination_class = AdminPageNumberPagination

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        return self.paginator.paginate_queryset(queryset, self.request)

    def get_paginated_response(self, data):
        return self.paginator.get_paginated_response(data)

    @extend_schema(
        summary="List active marketing subscribers",
        description=(
            "Returns all emails with active (granted) marketing consent. "
            "Only the latest confirmed record per email/definition pair is considered."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Filter by agreement slug (e.g. marketing-email)",
            ),
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=int, description="Page number"),
            OpenApiParameter(
                name="page_size", location=OpenApiParameter.QUERY, type=int, description="Items per page (max 100)"
            ),
        ],
        responses={200: MarketingSubscriberListResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, **kwargs) -> Response:
        slug = request.query_params.get("slug")
        qs = consent_service.list_active_marketing_subscribers(slug=slug)
        page = self.paginate_queryset(qs)
        results = [
            MarketingSubscriberResponse(
                email=record.email,
                agreement_slug=record.agreement_version.definition.slug,
                agreement_name=record.agreement_version.definition.name,
                consent_channel=record.channel_idx,
                granted_at=record.created_at,
                channel_idx=record.channel_idx,
            ).model_dump()
            for record in page
        ]
        return self.get_paginated_response(results)

    @extend_schema(
        summary="Export active marketing subscribers as CSV",
        description=(
            "Streams a CSV file of all active marketing subscribers. "
            "Columns: email, agreement, consent_channel, granted_at, channel."
        ),
        tags=["Marketing Subscribers"],
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.QUERY,
                type=str,
                description="Filter by agreement slug (e.g. marketing-email)",
            )
        ],
        responses={200: {"description": "CSV file download"}},
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request: Request, **kwargs) -> StreamingHttpResponse:
        slug = request.query_params.get("slug")
        qs = consent_service.list_active_marketing_subscribers(slug=slug)
        response = StreamingHttpResponse(_csv_rows(qs), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="marketing-subscribers.csv"'
        return response


@extend_schema_view(list=extend_schema(summary="Get order agreement snapshots", tags=["Order Agreements"]))
class OrderAgreementViewSet(viewsets.ViewSet):
    """Admin read-only access to order agreement snapshots."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    access_area = "agreements.consents"

    @extend_schema(
        summary="Get order agreement snapshots",
        description="Returns all agreement snapshots for a specific order.",
        parameters=[
            OpenApiParameter(name="order_id", location=OpenApiParameter.PATH, type=str, description="Order UUID")
        ],
        responses={200: OrderAgreementListResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, order_id: str, **kwargs) -> Response:
        qs = order_agreement_service.get_order_agreements(order_id=order_id)
        results = [order_agreement_service.to_snapshot_response_dict(s) for s in qs]
        response = OrderAgreementListResponse(count=len(results), results=results)
        return Response(response.model_dump())
