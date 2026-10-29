# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Public API views for order agreement snapshots."""

from django.core.exceptions import ObjectDoesNotExist
from django_utils.api.client_ip import get_client_ip
from drf_spectacular.utils import OpenApiParameter, extend_schema
from process_logger import ProcessLogger
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements.api import raise_pydantic_as_drf
from django_agreements.api.public.authentication import APIKeyAuthentication
from django_agreements.api.public.permissions import HasAPIKeyOrJWT
from django_agreements.api.public.throttling import OrderAgreementThrottle
from django_agreements.schemas.requests.order_agreement import OrderAgreementRequest
from django_agreements.services import order_agreement_service

logger = ProcessLogger("PUBLIC_ORDER_AGREEMENT_API", module="django_agreements")


class PublicOrderAgreementViewSet(viewsets.ViewSet):
    """Public endpoint for recording order agreement acceptance."""

    authentication_classes = [APIKeyAuthentication, JWTAuthentication]  # a stale JWT beside a valid key is ignored
    permission_classes = [HasAPIKeyOrJWT]
    throttle_classes = [OrderAgreementThrottle]

    @extend_schema(
        summary="Record order agreement acceptance",
        description=(
            "Records agreement acceptance for an order. Creates both "
            "OrderAgreementSnapshot (with body_snapshot) and ConsentRecord. "
            "With checkout enabled the order must exist in the channel and the email must be the order's; "
            "an agreement already recorded for the order is not recorded again. Requires a valid `X-API-KEY` or a JWT."
        ),
        tags=["Order Agreements"],
        parameters=[
            OpenApiParameter(
                name="channel_idx", location=OpenApiParameter.PATH, type=str, description="Channel identifier"
            ),
            OpenApiParameter(name="order_id", location=OpenApiParameter.PATH, type=str, description="Order UUID"),
        ],
        responses={
            201: {"description": "Order agreements recorded"},
            400: {"description": "Validation error"},
            401: {"description": "Missing or invalid X-API-KEY and no JWT"},
            404: {"description": "No such order in the channel, or the email is not the order's"},
            429: {"description": "Too many requests"},
        },
    )
    def create(self, request: Request, channel_idx: str, order_id: str, **kwargs) -> Response:
        try:
            data = OrderAgreementRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        ip_address = get_client_ip(request)
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
        except order_agreement_service.OrderNotFound as exc:
            raise NotFound("Order not found.") from exc
        except ObjectDoesNotExist as e:
            logger.warning(e)
            raise ParseError("Invalid request.") from e
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        except Exception as e:
            logger.exception(e)
            raise
        return Response({"detail": "Order agreements recorded."}, status=status.HTTP_201_CREATED)
