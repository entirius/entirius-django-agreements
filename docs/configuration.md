---
title: "Configuration"
description: "Django settings for the django-agreements module — language fallback, newsletter double opt-in, token expiry, storefront URL, and cookie consent validity, retention and throttling."
---

## Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `T9N_DEFAULT_LANG` | `str` | `"en"` | Language code used as fallback when a requested language is not available in `summary_t9n`. |
| `NEWSLETTER_DOUBLE_OPTIN` | `bool` | `True` | When `True`, newsletter consent requires email confirmation before becoming active. |
| `NEWSLETTER_TOKEN_MAX_AGE` | `int` | `86400` | Maximum age (in seconds) for newsletter confirmation tokens. Default is 24 hours. |
| `STOREFRONT_BASE_URL` | `str` | `"http://localhost:3000"` | Base URL of the storefront. Used when building confirmation and unsubscribe links in emails. |
| `NEWSLETTER_CONFIRM_PATH` | `str` | `"/newsletter/confirm"` | Path appended to `STOREFRONT_BASE_URL` for the newsletter confirmation endpoint. |
| `AGREEMENTS_API_KEY` | `str` | `""` | Key the storefront sends as `X-API-KEY` to the public endpoints. With `entirius-django-access` installed it is not compared: the key is an access token with scope `agreements.subscribe` (the setting's value is imported as a legacy token). |
| `AGREEMENTS_PUBLIC_CONSENT_SOURCES` | `tuple[str, ...]` | `("checkout", "registration", "consent-page", "newsletter-signup")` | Consent sources accepted from the public submission API; internal sources are set by the service only. |
| `LEADS_ANONYMISED_DOMAIN` | `str` | `"anonymised.invalid"` | Host part of the token that replaces an erased email (`gdpr_erase`). Must equal the value used by leads and communicator. |
| `AGREEMENTS_COOKIE_CONSENT_MAX_AGE_DAYS` | `int` | `365` | Cookie consent validity in days. Returned by the public banner endpoint as `max_age_days` — the consent cookie lifetime on every front end, and the minimum `purge_cookie_consents` retention. |
| `AGREEMENTS_COOKIE_CONSENT_RETENTION_DAYS` | `int \| None` | `None` | Cookie consent proof retention for `purge_cookie_consents`. `None` = the command requires `--days`. Recommended `1461`, see [Cookie Consent](/volkanos/modules/agreements/cookie-consent/#retention). |

## Throttling

The public cookie consent POST is throttled per client IP with the DRF scope `agreements_cookie_consent`. Without a
valid rate for the scope the endpoint falls back to `30/min`. Override in the service settings:

```python
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["agreements_cookie_consent"] = "60/min"
```

## Example Override

Add to your Django `settings_local.py`:

```python
T9N_DEFAULT_LANG = "pl"
NEWSLETTER_DOUBLE_OPTIN = True
NEWSLETTER_TOKEN_MAX_AGE = 3600          # 1 hour
STOREFRONT_BASE_URL = "https://myshop.example.com"
NEWSLETTER_CONFIRM_PATH = "/newsletter/confirm"
```

The confirmation link sent to subscribers is constructed as:

```
{STOREFRONT_BASE_URL}{NEWSLETTER_CONFIRM_PATH}?token={signed_token}
```
