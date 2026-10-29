# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Per-address throttles of the public consent and order-agreement endpoints — they create state and send mail.

``DEFAULT_THROTTLE_RATES[<scope>]`` overrides a rate; the class ``fallback_rate`` is the safety net when the scope
is unset or malformed. The fallback must not live in a class ``rate``: DRF's ``SimpleRateThrottle.__init__`` skips
``get_rate()`` when ``rate`` is set, which would silently disable the settings override.
"""

import hashlib

from django.core.exceptions import ImproperlyConfigured
from django_utils.api.client_ip import ClientIPThrottleMixin
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class _FallbackRateMixin:
    fallback_rate: str

    def __init__(self) -> None:
        self.rate = self.get_rate()
        super().__init__()

    def get_rate(self) -> str:
        try:
            rate = super().get_rate()
        except ImproperlyConfigured:  # scope missing from DEFAULT_THROTTLE_RATES
            return self.fallback_rate
        if not rate or "/" not in rate:  # a malformed rate must not disable throttling
            return self.fallback_rate
        return rate


class _ScopedAnonThrottle(ClientIPThrottleMixin, _FallbackRateMixin, AnonRateThrottle):
    """Per client address: ``settings.CLIENT_IP_HEADER`` when set (behind a proxy), DRF ``get_ident`` otherwise."""


class SubscribeThrottle(_ScopedAnonThrottle):
    scope = "agreements_subscribe"
    fallback_rate = "5/min"


class SubscribeAddressThrottle(_FallbackRateMixin, SimpleRateThrottle):
    """Per e-mail address: caps the confirmation mails one address can be sent, whoever asks.

    The cache key carries a hash of the normalised address, never the address itself.
    """

    scope = "agreements_subscribe_address"
    fallback_rate = "3/hour"

    def get_cache_key(self, request, view) -> str | None:
        email = request.data.get("email") if hasattr(request.data, "get") else None
        if not isinstance(email, str) or not email.strip():
            return None  # a refused body sends no mail; the per-client throttle still counts it
        digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}


class ConsentSubmitThrottle(_ScopedAnonThrottle):
    scope = "agreements_consent"
    fallback_rate = "20/min"


class TokenActionThrottle(_ScopedAnonThrottle):
    scope = "agreements_token"
    fallback_rate = "10/min"


class OrderAgreementThrottle(_ScopedAnonThrottle):
    scope = "agreements_order"
    fallback_rate = "20/min"


class CookieConsentThrottle(_ScopedAnonThrottle):
    scope = "agreements_cookie_consent"
    fallback_rate = "30/min"
