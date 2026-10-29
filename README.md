# entirius-django-agreements

A Django module for consents and legal agreements in Entirius, the open-source modular ecommerce platform. It
versions agreement texts, records every consent and objection in an append-only audit trail, and freezes the text
a customer accepted with each order. The CMS manages agreements over an admin API; the storefront uses a public API.

[![PyPI](https://img.shields.io/pypi/v/entirius-django-agreements.svg)](https://pypi.org/project/entirius-django-agreements/)
[![Python](https://img.shields.io/pypi/pyversions/entirius-django-agreements.svg)](https://pypi.org/project/entirius-django-agreements/)
[![License: MPL-2.0](https://img.shields.io/badge/license-MPL--2.0-blue.svg)](https://github.com/entirius/entirius-django-agreements/blob/develop/LICENSE)

## What it does

- Defines agreements per sales channel and keeps immutable, numbered versions of their text.
- Records consents and withdrawals per email address as an append-only audit log.
- Stores a snapshot of the accepted agreement texts with every order.
- Handles newsletter signup with double opt-in confirmation links.
- Versions legal clauses per channel, legal basis and language, and records objections.
- Exports and pseudonymises personal data for GDPR requests.

## Installation

```shell
uv add entirius-django-agreements
pip install entirius-django-agreements
```

```python
INSTALLED_APPS = [
    ...
    "django_utils",
    "django_regional",
    "django_agreements",
]

# urls.py
urlpatterns = [
    path("", include("django_agreements.urls")),
]
```

No setting is required: every setting has a default. Reference:
https://github.com/entirius/entirius-django-agreements/blob/develop/docs/configuration.md

Every public write endpoint (consent create, withdraw, newsletter subscribe, order agreements) needs a
key in the `X-API-KEY` header or a JWT; the signed-token links (confirm, unsubscribe), the cookie consent POST and the GETs do not. Where `django_access` is installed the key
is an access token with the scope `agreements.subscribe`:

`POST consents/` with a key alone (no JWT) refuses every `marketing`-category agreement with HTTP 400: the body email
is only a claim, so marketing consent goes through newsletter subscribe (double opt-in). With a JWT it is accepted.
`consent_service.record_multiple_consents(..., email_verified=False)` enforces this; the default is `True` for
internal callers.

```shell
python manage.py access_token create --application storefront --create-application --scope agreements.subscribe --channel default
```

Without `django_access`, the key is the value of the `AGREEMENTS_API_KEY` setting.

## Quick start

```python
from django_agreements.services.consent_service import get_consent_status, is_consented

is_consented("customer@example.com", "marketing-email")   # latest record for one agreement
get_consent_status("customer@example.com")                # every agreement slug -> granted
```

Channels are copied from the product module when it is installed:

```shell
python manage.py sync_agreement_channels
```

## Requirements

- Python 3.11 or newer, Django 5.0 or newer.
- Entirius packages pulled in: `entirius-django-utils`, `entirius-django-regional`, `entirius-py-process-logger`.

## Documentation

- Module docs: https://github.com/entirius/entirius-django-agreements/tree/develop/docs
- Entirius documentation: https://docs.entirius.com/
- Changelog: https://github.com/entirius/entirius-django-agreements/blob/develop/CHANGELOG.md

## Part of Entirius

This module runs inside the Entirius backend service (Volkanos); the leads module builds on its legal bases and consents.

- Backend service: https://github.com/entirius/entirius-service-volkanos
- Docker harness: https://github.com/entirius/entirius-zeno
- Sibling modules: https://github.com/entirius/entirius-django-regional, https://github.com/entirius/entirius-django-leads,
  https://github.com/entirius/entirius-django-access

## Development

```shell
make install     # sync dependencies (uv)
make check       # lint + format check (ruff)
make test        # test suite (pytest + pytest-django, needs PostgreSQL via DATABASE_URL)
```

Development and agent instructions: https://github.com/entirius/entirius-django-agreements/blob/develop/AGENTS.md

## License

Mozilla Public License 2.0 (MPL-2.0) — see https://github.com/entirius/entirius-django-agreements/blob/develop/LICENSE.
