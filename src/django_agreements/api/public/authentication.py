# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""API key authentication for public endpoints.

With ``django_access`` installed the key is an access token with scope ``agreements.subscribe`` checked by
``verify_api_key`` (channel pin included); ``AGREEMENTS_API_KEY`` lives on as an imported legacy token and is never
compared on that path. Without the module: the ``AGREEMENTS_API_KEY`` setting, as before.
"""

import secrets
from types import SimpleNamespace

from django.apps import apps
from django.conf import settings as django_settings
from rest_framework.authentication import BaseAuthentication

SUBSCRIBE_SCOPE = "agreements.subscribe"
_HEADER = "HTTP_X_API_KEY"


class APIKeyAuthentication(BaseAuthentication):
    """Validate the X-API-KEY header; a missing or refused key leaves the request anonymous."""

    def authenticate(self, request):
        key = request.META.get(_HEADER)
        if not key or not _key_is_valid(request, key):
            return None  # Let other auth backends try (e.g., JWT)
        return (None, "api_key")

    def authenticate_header(self, request):
        return "X-API-KEY"


def _key_is_valid(request, key: str) -> bool:
    if apps.is_installed("django_access"):
        return _token_is_valid(request, key)
    expected = getattr(django_settings, "AGREEMENTS_API_KEY", "")
    return bool(expected) and secrets.compare_digest(key.encode(), expected.encode())


def _token_is_valid(request, key: str) -> bool:
    """``verify_api_key`` sees only X-API-KEY: the X-API-ADMIN-KEY alias never stands in here."""
    from django_access.services.tokens import verify_api_key

    channel_idx = (request.parser_context or {}).get("kwargs", {}).get("channel_idx")
    token = verify_api_key(SimpleNamespace(META={_HEADER: key}), SUBSCRIBE_SCOPE, channel_idx)
    if token is not None:
        request.access_token = token
    return token is not None
