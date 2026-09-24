# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Throttle for the anonymous cookie consent log.

The class-level ``fallback_rate`` is the safety net — a missing or malformed
``DEFAULT_THROTTLE_RATES["agreements_cookie_consent"]`` must never leave the
endpoint unthrottled. The fallback must NOT live in a class-level ``rate``:
DRF's ``SimpleRateThrottle.__init__`` only calls ``get_rate()`` when ``rate``
is unset, so a class ``rate`` silently disables the service override.
"""

from rest_framework.throttling import AnonRateThrottle


class CookieConsentThrottle(AnonRateThrottle):
    scope = "agreements_cookie_consent"
    fallback_rate = "30/min"

    def __init__(self) -> None:
        # Resolve config-or-fallback BEFORE super().__init__ — DRF skips get_rate() when self.rate is set.
        self.rate = self.get_rate()
        super().__init__()

    def get_rate(self) -> str:
        try:
            rate = super().get_rate()
        except Exception:  # noqa: BLE001 — DRF raises ImproperlyConfigured when the scope has no rate
            return self.fallback_rate
        if not rate or "/" not in rate:  # a malformed rate must not disable throttling
            return self.fallback_rate
        return rate
