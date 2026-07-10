# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API view for generating unsubscribe URLs."""

from drf_spectacular.utils import extend_schema
from pydantic import ValidationError
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_agreements import settings as agreements_settings
from django_agreements.api import raise_pydantic_as_drf
from django_agreements.api.admin.permissions import IsAdminUser
from django_agreements.schemas.requests.consent import GenerateUnsubscribeUrlRequest
from django_agreements.schemas.responses.consent import UnsubscribeUrlResponse
from django_agreements.services.token_service import generate_token


class TokenViewSet(viewsets.ViewSet):
    """Admin endpoint for generating signed unsubscribe URLs."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Generate unsubscribe URL",
        description="Generate a signed unsubscribe URL for a given email and consent type.",
        tags=["Consent Records"],
        responses={
            200: UnsubscribeUrlResponse,
            400: {"description": "Validation error"},
            401: {"description": "Authentication required"},
            403: {"description": "Permission denied"},
        },
    )
    def generate_unsubscribe_url(self, request: Request, **kwargs) -> Response:
        try:
            data = GenerateUnsubscribeUrlRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)

        token = generate_token(data.email, data.consent_type)
        base_url = agreements_settings.STOREFRONT_BASE_URL
        confirm_path = agreements_settings.NEWSLETTER_CONFIRM_PATH
        url = f"{base_url}{confirm_path}?token={token}&action=unsubscribe"

        response = UnsubscribeUrlResponse(url=url)
        return Response(response.model_dump())
