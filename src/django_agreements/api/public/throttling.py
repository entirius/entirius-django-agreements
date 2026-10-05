# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Per-address throttles of the public consent endpoints — they create state and send mail.

``DEFAULT_THROTTLE_RATES[<scope>]`` overrides a rate; the class ``fallback_rate`` is the safety net when the scope
is unset or malformed. The fallback must not live in a class ``rate``: DRF's ``SimpleRateThrottle.__init__`` skips
``get_rate()`` when ``rate`` is set, which would silently disable the settings override.
"""

from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import AnonRateThrottle


class _ScopedAnonThrottle(AnonRateThrottle):
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


class SubscribeThrottle(_ScopedAnonThrottle):
    scope = "agreements_subscribe"
    fallback_rate = "5/min"


class ConsentSubmitThrottle(_ScopedAnonThrottle):
    scope = "agreements_consent"
    fallback_rate = "20/min"


class TokenActionThrottle(_ScopedAnonThrottle):
    scope = "agreements_token"
    fallback_rate = "10/min"
