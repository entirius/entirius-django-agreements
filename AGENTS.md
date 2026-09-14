# AGENTS.md

Consent & Agreements module for Volkanos — distribution `entirius-django-agreements`,
Django app `django_agreements`. GDPR-compliant agreement versioning, consent tracking with
append-only audit trail, and order agreement snapshots.

## Commands

| Command | Meaning |
|---|---|
| `make install` | sync dependencies (uv, incl. extras) |
| `make check` | lint + format-check (ruff) |
| `make fix` | auto-fix lint + format |
| `make test` | test suite (pytest + pytest-django) |

## Conventions

- English only: code, docs, commits, branches, PRs.
- MPL-2.0: every non-trivial source file carries the license header (pre-commit inserts it).
- Toolchain: uv + ruff + hatchling + pytest; all config in `pyproject.toml`; `uv.lock` committed.
- Git flow: `master` (production) + `develop` (integration); changes land via PR; semver tag on `master`.
- Never rename the package / Django app_label / DB table prefix `django_agreements` — it is a schema contract.
- Migrations are part of the public contract — never edit an already released migration.
- Default: do not commit — git is the user's call.

## Architecture

- `models/` — `Channel` (own scoping model, no FK to PIM), `AgreementDefinition` (slug, category,
  channels M2M), `AgreementVersion` (immutable, auto-versioned), `ConsentRecord` (append-only audit
  log), `OrderAgreementSnapshot` (per-order text freeze), `ClauseSet` (versioned legal clauses per
  channel × `LegalBasis` × language), `ObjectionEvent` (append-only opt-out log).
- `enums.py` — `LegalBasis`, the platform-wide legal basis definition (leads imports it).
- `services/` — channel sync from PIM, definition/version CRUD with system-consent guards,
  legal content history (ContentDB snapshots), consent recording and queries, order snapshots,
  HMAC token service for consent confirmation links, clause set resolution + legal footer
  rendering (`clause_set_service`), objection recording (`objection_service`).
- `schemas/` — pydantic request/response models.
- `api/` — `admin/` (v2, JWT + IsAdminUser) and `public/` (v2, AllowAny, channel-scoped).

Layer rule: `API → Services → Models → DB`. No ORM in views.

## Gotchas

- Optional integrations are lazy imports with `try/except ImportError` fallbacks:
  `django_pim` (channel sync no-op), `django_contentdb` (legal snapshots return empty),
  `django_email` (newsletter signup email skipped), `django_crm` (consent migration command aborts).
- `ConsentRecord` is append-only — never update or delete rows; state queries take the latest record.
- `AgreementVersion` is immutable once published; only draft versions accept PATCH.
- `ClauseSet` is immutable once published — a text change is a new version (admin add → `create_version`,
  then "Publish selected"). One `is_current` per (channel, basis, language) is enforced by
  `clause_set_service.publish()`, not by the DB. `ClauseSet.save()` raises `ValueError` on a changed text,
  channel, basis, language or `published_at` of a published row (un-publishing included); with `update_fields`
  only the listed locked fields are compared, so `is_current` toggles work on stale instances. Fixture loads
  (`raw=True`) skip `save()` — a `pre_save` receiver applies the same guard, so re-running the seed with changed
  clause text fails loudly instead of rewriting the row (changed text = new pk + version). `publish()` raises on
  an already-published set; the admin cannot delete published sets and objections `PROTECT` their clause set.
  Queryset `.update()` bypasses every guard — only the service uses it, for `is_current`.
- `gdpr.py` (discovered by django_leads): export `ConsentRecord`, `ObjectionEvent` and `OrderAgreementSnapshot` rows by
  the plain email **or** its token (rows pseudonymised by an earlier erasure stay exportable); erasure is the one
  deliberate exception to append-only — a queryset `update()` pseudonymises `email` to the leads token
  (`LEADS_ANONYMISED_DOMAIN`), drops `ip_address` and `user_agent`; rows stay as the audit trail. A snapshot keeps its
  `body_snapshot`, language, `granted` and timestamps: what was accepted with an order is an order-retention obligation.
  `gdpr.anonymised_address` is a local copy of `django_leads.utils.emails.anonymised_address` (no dependency on leads);
  `tests/test_gdpr.py::test_token_parity_with_django_leads` compares them on tricky inputs when leads is installed.
- `resolve_clause_set()` falls back only to the channel's default language — never to another basis or channel.
  Footer placeholders are `str.replace` of `{recipient_email}` only; other braces stay verbatim.
- Seeded clause texts (emporium `fixtures/django_agreements.cfg.yaml`) are `TEST —` placeholders: the lawyer's
  texts are pasted in the admin as a new version and published before the staging canary.
