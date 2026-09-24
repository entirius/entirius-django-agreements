# Changelog

## 2.2.0 — unreleased

- Cookie consent: `CookieConsent`, an append-only anonymous log of cookie banner decisions (`consent_id` UUID,
  channel, language, banner version, categories, action; no IP, user agent or URL).
- Cookie banner config on agreement versions: category `cookies`, `AgreementVersion.cookie_banner` (categories with
  Google Consent Mode signals, button labels per language); publish refuses a banner whose languages differ from
  `summary_t9n` or miss a channel language, and a second active `cookies` definition for the same channel scope.
- Public API v2: `GET {channel_idx}/cookie-banner/` (channel-specific banner beats the global one, language
  fallback) and `POST {channel_idx}/cookie-consents/` (throttle scope `agreements_cookie_consent`, fallback `30/min`;
  409 `STALE_REVISION` when the banner revision is outdated).
- Admin API v2: `GET cookie-consents/` (filters, pagination), `export/` (CSV), `stats/` (per UTC day, revision,
  language, action), `{consent_id}/` (history), `POST {consent_id}/erase/` (GDPR erasure: one new random id);
  read-only Django admin for the log.
- Management command `purge_cookie_consents` (`--days`, `--dry-run`); refuses a retention shorter than the consent
  validity.
- Settings `AGREEMENTS_COOKIE_CONSENT_MAX_AGE_DAYS` (default `365`) and `AGREEMENTS_COOKIE_CONSENT_RETENTION_DAYS`
  (default `None`).
- Migration `0004_cookie_consent`.
- The `cookies` category is kept out of the email-keyed flows: consent submit, status, people, `for-user` and the
  public definition list.
- Fixture `cookie_banner` (global PL/EN draft banner, loaded on demand).
- Tests: migration drift check and OpenAPI schema validation.
- Marketing subscribers list and CSV: `consent_channel` now carries the agreement's consent channel (it repeated the
  shop channel).
- Docs: `cookie-consent.md`; `signals.md` corrected to the code (`consent_changed`, sent only by the confirmation
  and unsubscribe links); `master-data.md` source values and dependency map corrected; ERD with `CookieConsent`.

## 2.1.0 — 2026-09-15

- `ClauseSet`: versioned legal clauses (information, opt-out, retention) per channel, legal
  basis and language; published sets are immutable, one current version per triple; edited
  only in the Django admin ("Publish selected" action).
- `ObjectionEvent`: append-only log of confirmed opt-outs, independent of `ConsentRecord`.
- `gdpr.py`: GDPR export and erasure hooks (pseudonymised consent, objection and order agreement snapshot rows;
  export also matches the token of an earlier erasure).
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
- Setting `LEADS_ANONYMISED_DOMAIN` (default `anonymised.invalid`, shared with leads and communicator) — the
  host of the erasure token; `AGREEMENTS_CLAUSE_PLACEHOLDER` names the only footer placeholder.
- Docs: module pages for the portal (`index`, `master-data`, `legal-pages`, `configuration`, `signals`, `erd`;
  `email-integration.md` removed), clause sets, publishing rules and GDPR hooks in `index.md` and
  `master-data.md`; ERD group "Legal Clauses & Objections".
- `.github/CODEOWNERS`: `@entirius/maintainers-backend`.

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
