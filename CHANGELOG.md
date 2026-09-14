# Changelog

## 2.1.0 — unreleased

- `ClauseSet`: versioned legal clauses (information, opt-out, retention) per channel, legal
  basis and language; published sets are immutable, one current version per triple; edited
  only in the Django admin ("Publish selected" action).
- `ObjectionEvent`: append-only log of confirmed opt-outs, independent of `ConsentRecord`.
- `gdpr.py`: GDPR export and erasure hooks (pseudonymised consent and objection rows).
- `LegalBasis` enum (`django_agreements.enums`) — the platform-wide GDPR legal basis definition.
- `clause_set_service.resolve_clause_set()` (requested language → channel default language →
  `ClauseSetMissing`), `render_legal_footer()` (plain text, `{recipient_email}` placeholder),
  `publish()`, `create_version()`; `objection_service.record_objection()`.
- Read-only admin API v2 `GET clause-sets/` (filters `channel_idx`, `legal_basis`, `language`, `current`).
- Published clause sets can be neither deleted (admin) nor changed (`ClauseSet.save()` raises
  `ValueError`); `publish()` raises on an already-published set; `ObjectionEvent.clause_set` is
  `PROTECT` (migration `0003_objection_clause_set_protect`).
- `published_at` of a published clause set is locked too (no un-publish); the guard honours
  `update_fields` and also runs on fixture loads (`pre_save`, `raw=True`).
- Clause set language lookups (resolver, admin API `language` filter) are case-insensitive.
- `Channel` natural key (`idx`) for fixtures.
- Migration `0002_clause_sets`.

## 2.0.0 — 2026-07-10

- Initial public release: GDPR-compliant consent management — versioned agreement
  definitions with immutable published versions, an append-only ConsentRecord
  audit trail, and per-order legal text snapshots.
- Admin API v2 (definitions, versions, consent log, people, content history) and
  channel-scoped public API v2 (definitions, consent submit/status/withdraw,
  order agreements) with a `for-user` display-context endpoint.
- ContentDB integration for legal page content with time-based text lookup.
- Newsletter double opt-in with HMAC confirmation links; the confirmation email
  honors the subscriber's language (explicit request, then channel default, then
  `EMAIL_DEFAULT_LANGUAGE`).
- Default fixtures: 5 system agreement definitions with published versions in
  EN, PL, and DE.
- CRM v1 consent migration command (`migrate_crm_consents`).
- Migrations squashed into a single initial migration for the Entirius epoch.
