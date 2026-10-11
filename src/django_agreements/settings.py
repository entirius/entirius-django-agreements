# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.conf import settings

DEBUG = getattr(settings, "DEBUG", False)

# Host of the tokens that replace erased addresses (same setting as django_leads and django_communicator).
LEADS_ANONYMISED_DOMAIN = getattr(settings, "LEADS_ANONYMISED_DOMAIN", "anonymised.invalid")

# Default language for T9N fallback
T9N_DEFAULT_LANG = getattr(settings, "T9N_DEFAULT_LANG", "en")

# Sources accepted from the public consent submission API.
# Internal sources (api, import, crm-v1, double-optin-*, unsubscribed) are set by the service only.
PUBLIC_CONSENT_SOURCES: tuple[str, ...] = getattr(
    settings, "AGREEMENTS_PUBLIC_CONSENT_SOURCES", ("checkout", "registration", "consent-page", "newsletter-signup")
)

# Cookie consent validity in days — returned by the public banner endpoint so every front sets the same cookie lifetime.
COOKIE_CONSENT_MAX_AGE_DAYS = getattr(settings, "AGREEMENTS_COOKIE_CONSENT_MAX_AGE_DAYS", 365)

# Cookie consent proof retention in days (purge_cookie_consents); None = the command requires --days.
COOKIE_CONSENT_RETENTION_DAYS = getattr(settings, "AGREEMENTS_COOKIE_CONSENT_RETENTION_DAYS", None)

# Newsletter double opt-in
NEWSLETTER_DOUBLE_OPTIN = getattr(settings, "NEWSLETTER_DOUBLE_OPTIN", True)
NEWSLETTER_TOKEN_MAX_AGE = getattr(settings, "NEWSLETTER_TOKEN_MAX_AGE", 86400)

# Storefront URL for confirmation/unsubscribe links
STOREFRONT_BASE_URL = getattr(settings, "STOREFRONT_BASE_URL", "http://localhost:3000")
NEWSLETTER_CONFIRM_PATH = getattr(settings, "NEWSLETTER_CONFIRM_PATH", "/newsletter/confirm")

# API key for public endpoints (storefront uses X-API-KEY header)
AGREEMENTS_API_KEY = getattr(settings, "AGREEMENTS_API_KEY", "")

# Well-known slug constants
MARKETING_EMAIL_SLUG = "marketing-email"

# The only placeholder render_legal_footer() substitutes in clause texts (plain str.replace, never str.format)
AGREEMENTS_CLAUSE_PLACEHOLDER = "{recipient_email}"
