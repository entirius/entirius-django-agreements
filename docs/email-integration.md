# Planned: django-email Integration

When django-email is refactored to support marketing emails, the following
integration points with django-agreements should be implemented.

## Double Opt-In for Marketing Consent

When a user grants `marketing-email` consent (via public API or CRM bridge),
the consent should NOT be immediately active. Instead:

1. `consent_service.record_consent(slug="marketing-email", granted=True)` creates
   a ConsentRecord with `source="pending-confirmation"`
2. django-email sends a confirmation email using a new `MarketingOptInEmail` service
   (following the same pattern as `NewAccountEmail` in django-accounts)
3. Confirmation link contains a signed HMAC token (reuse `EmailConfirmationHMAC`
   pattern from django-accounts)
4. User clicks link → `POST /api/agreements/v2/{channel}/consents/confirm/` endpoint
   creates a new ConsentRecord with `source="email-confirmation"` and `granted=True`
5. Only after confirmation does the consent become effective

The `is_consented()` service method should check that the LATEST ConsentRecord
for marketing-email has `source != "pending-confirmation"`. This ensures
double opt-in compliance.

## Unsubscribe Links

Every marketing email sent by django-email MUST include an unsubscribe link.
The link should:

1. Contain a signed token identifying the email address and agreement slug
2. Point to a public endpoint: `GET /api/agreements/v2/{channel}/consents/unsubscribe/?token=...`
3. The endpoint creates a ConsentRecord with `granted=False` and `source="email-unsubscribe"`
4. Works WITHOUT authentication (anonymous withdrawal per GDPR Art. 7(3))
5. Shows a simple confirmation page (can be a static page or storefront route)

Token format: HMAC-signed JSON `{email, slug, timestamp}` with configurable expiry.
Use `django.core.signing.TimestampSigner` for simplicity.

## List-Unsubscribe Header

django-email should add `List-Unsubscribe` and `List-Unsubscribe-Post` headers
to all marketing emails (RFC 8058). The URL in the header points to the same
unsubscribe endpoint.

## Email Service Integration Points

- `consent_service.is_consented(email, "marketing-email")` — check before sending
- `consent_service.record_consent(email, "marketing-email", granted=False, source="email-unsubscribe")` — on unsubscribe
- `consent_service.get_consent_status(email)` — for email preference center

## django-email Module Changes Needed

1. New `MarketingOptInEmail` service (extends `EmailService`)
2. New `MarketingOptInTemplate` model (channel + language scoped)
3. Unsubscribe token generation utility
4. `List-Unsubscribe` header injection in `EmailTemplate.send()`
5. Pre-send consent check in marketing email services
