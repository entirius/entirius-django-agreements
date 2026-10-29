# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Permission of the public write endpoints: a valid X-API-KEY or a JWT.

The key ships in the storefront bundle, so it is public in effect; it only keeps anonymous scripts off the writes.
"""

from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission

from django_agreements.api.public.authentication import API_KEY_AUTH


class HasAPIKeyOrJWT(BasePermission):
    """``APIKeyAuthentication`` leaves a missing or refused key anonymous; this is where that is refused."""

    def has_permission(self, request, view) -> bool:
        if request.auth == API_KEY_AUTH or (request.user and request.user.is_authenticated):
            return True
        raise NotAuthenticated("API key or authentication required.")
