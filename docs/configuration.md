---
title: "Configuration"
description: "Django settings for the django-agreements module — language fallback, newsletter double opt-in, token expiry, and storefront URL."
---

## Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `T9N_DEFAULT_LANG` | `str` | `"en"` | Language code used as fallback when a requested language is not available in `summary_t9n`. |
| `NEWSLETTER_DOUBLE_OPTIN` | `bool` | `True` | When `True`, newsletter consent requires email confirmation before becoming active. |
| `NEWSLETTER_TOKEN_MAX_AGE` | `int` | `86400` | Maximum age (in seconds) for newsletter confirmation tokens. Default is 24 hours. |
| `STOREFRONT_BASE_URL` | `str` | `"http://localhost:3000"` | Base URL of the storefront. Used when building confirmation and unsubscribe links in emails. |
| `NEWSLETTER_CONFIRM_PATH` | `str` | `"/newsletter/confirm"` | Path appended to `STOREFRONT_BASE_URL` for the newsletter confirmation endpoint. |

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
