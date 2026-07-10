# django-agreements

Consent & Agreements module for the Volkanos ecommerce platform. Provides GDPR-compliant agreement
versioning, consent tracking with full audit trail, and order agreement snapshots.

## Installation

```shell
pip install entirius-django-agreements
```

Add the app to your project:

```python
INSTALLED_APPS = [
    ...
    "django_regional",
    "django_agreements",
]
```

## Development

```shell
make install     # sync dependencies (uv)
make check       # lint + format check (ruff)
make test        # test suite (pytest + pytest-django)
```

Development and agent instructions: [AGENTS.md](AGENTS.md).

## License

Mozilla Public License 2.0 — see [LICENSE](LICENSE).
