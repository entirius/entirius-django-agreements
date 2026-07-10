# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API views for agreement channels."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements.api.admin.pagination import AdminPageNumberPagination
from django_agreements.api.admin.permissions import IsAdminUser
from django_agreements.services import channel_service


@extend_schema_view(list=extend_schema(summary="List agreement channels", tags=["Agreement Channels"]))
class ChannelViewSet(viewsets.ViewSet):
    """Admin read-only access to agreement channels with sync action."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="List agreement channels",
        description="Returns all agreement channels.",
        responses={
            200: {"description": "Paginated channel list"},
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
        },
    )
    def list(self, request: Request, **kwargs) -> Response:
        qs = channel_service.list_channels()
        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = [channel_service.to_channel_response_dict(ch) for ch in page]
        return Response(
            {
                "count": paginator.page.paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": results,
            }
        )

    @extend_schema(
        summary="Sync channels from PIM",
        description="Syncs agreement channels from PIM Channel model. Idempotent.",
        tags=["Agreement Channels"],
        responses={
            200: {"description": "Sync result with count"},
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
        },
    )
    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request: Request, **kwargs) -> Response:
        count = channel_service.sync_channels_from_pim()
        return Response({"synced": count}, status=status.HTTP_200_OK)
