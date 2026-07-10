# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Public API views for order agreement snapshots."""

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import OpenApiParameter, extend_schema
from process_logger import ProcessLogger
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.exceptions import ParseError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from django_agreements.api import raise_pydantic_as_drf
from django_agreements.schemas.requests.order_agreement import OrderAgreementRequest
from django_agreements.services import order_agreement_service

logger = ProcessLogger("PUBLIC_ORDER_AGREEMENT_API", module="django_agreements")


class PublicOrderAgreementViewSet(viewsets.ViewSet):
    """Public endpoint for recording order agreement acceptance."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Record order agreement acceptance",
        description=(
            "Records agreement acceptance for an order. Creates both "
            "OrderAgreementSnapshot (with body_snapshot) and ConsentRecord."
        ),
        tags=["Order Agreements"],
        parameters=[
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
            ),
            OpenApiParameter(name="order_id", location=OpenApiParameter.PATH, type=str, description="Order UUID"),
        ],
        responses={201: {"description": "Order agreements recorded"}, 400: {"description": "Validation error"}},
    )
    def create(self, request: Request, channel_idx: str, order_id: str, **kwargs) -> Response:
        try:
            data = OrderAgreementRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:2048]

        try:
            order_agreement_service.record_order_agreements(
                order_id=order_id,
                email=data.email,
                slugs=data.slugs,
                language=data.language,
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
        return Response({"detail": "Order agreements recorded."}, status=status.HTTP_201_CREATED)
