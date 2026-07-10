# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""API key authentication for public endpoints."""

from django.conf import settings as django_settings
from rest_framework.authentication import BaseAuthentication


class APIKeyAuthentication(BaseAuthentication):
    """Validate X-API-KEY header against AGREEMENTS_API_KEY setting."""

    def authenticate(self, request):
        key = request.META.get("HTTP_X_API_KEY")
        expected = getattr(django_settings, "AGREEMENTS_API_KEY", "")
        if not key or not expected or key != expected:
            return None  # Let other auth backends try (e.g., JWT)
        return (None, "api_key")

    def authenticate_header(self, request):
        return "X-API-KEY"
