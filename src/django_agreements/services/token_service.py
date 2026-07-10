# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Token generation and verification for newsletter double opt-in."""

from django.conf import settings
from django.core import signing

SALT = "newsletter-consent-token"


def generate_token(email: str, consent_type: str) -> str:
    """Generate a signed, timestamped token containing email and consent_type."""
    payload = {"email": email, "consent_type": consent_type}
    return signing.dumps(payload, salt=SALT)


def verify_token(token: str) -> dict | None:
    """Verify token signature and expiry. Returns payload dict or None."""
    max_age = getattr(settings, "NEWSLETTER_TOKEN_MAX_AGE", 86400)
    try:
        return signing.loads(token, salt=SALT, max_age=max_age)
    except (signing.BadSignature, signing.SignatureExpired):
        return None


def verify_token_or_raise(token: str) -> dict:
    """Verify token and return payload. Raises ValueError if invalid or expired."""
    payload = verify_token(token)
    if payload is None:
        raise ValueError("Invalid or expired token.")
    return payload
