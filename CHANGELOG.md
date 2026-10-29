# Changelog

## 3.0.1 — 2026-10-29

### Security

- Behaviour change: the public write endpoints now require a valid `X-API-KEY` or a JWT: consent create, consent
  withdraw, newsletter subscribe and order agreements. A missing or refused key answers 401. They used to accept anonymous callers, so anyone could record
  or forge consent for any address and bypass double opt-in. Storefronts must send the key (it is public in the
  bundle; it keeps anonymous scripts off the writes). Left open: the cookie consent POST (the anonymous log carries no personal data; it keeps its per-client
  throttle), the GETs (definitions, cookie banner), consent status
  (JWT, unchanged), and the token links confirm and unsubscribe, where the signed token is the proof.
- Consent create with a key alone (no JWT) refuses every `marketing`-category agreement, grant or withdrawal, with
  HTTP 400 pointing to newsletter subscribe. The body email is only a claim there, so the key could subscribe or
  unsubscribe a stranger and skip double opt-in. Enforced in `consent_service.record_multiple_consents` through the
  new `email_verified` parameter (default `True`, so CRM and other internal callers are unchanged; the public view
  passes `False` without a JWT). A JWT keeps the old behaviour.
- Consent withdraw still needs a JWT (the e-mail comes from it); a key alone is refused with 401.
- Per-client throttles read the client address from `settings.CLIENT_IP_HEADER` (new, optional, e.g.
  `HTTP_CF_CONNECTING_IP`) through `django_utils.api.client_ip.ClientIPThrottleMixin`; without it the DRF address is
  used as before. Behind a proxy without it, every client shared the proxy's bucket.
- New throttle scope `agreements_subscribe_address` (fallback `3/hour`, keyed on a hash of the normalised e-mail
  address, never the address): caps the confirmation mails one address can receive. Subscribe answers 429 beyond it.
  Existing scopes and rates are unchanged.
- The `ip_address` stored on consent records and order snapshots is the client address from `CLIENT_IP_HEADER` when
  set (it was always `REMOTE_ADDR`, the proxy behind a proxy).
- Requires `entirius-django-utils>=2.4.1`.

## 3.0.0 — 2026-10-12

- OpenAPI: URL examples use `https://api.example.com` and `https://shop.example.com` instead of `localhost`.
  Metadata only.

### Security

- The public order-agreement write (`POST <channel>/orders/<order_id>/agreements/`) is throttled per address (scope
  `agreements_order`, 20/min, overridable through `DEFAULT_THROTTLE_RATES`). It had no throttle, so anyone could
  grow the snapshot and consent tables without limit.
- The same write is bound to a real order where `django_checkout` is enabled: the order must exist in the channel
  of the URL and the e-mail must be its billing or shipping e-mail (case-insensitive). Otherwise the answer is 404,
  the same for an unknown order and for a foreign e-mail. Before, any order id and any address were accepted, which
  let an anonymous caller forge consent evidence. Without `django_checkout` enabled the write is accepted as before.
- A second write for the same order skips the agreement versions already recorded: no second snapshot, no second
  consent record. It used to fail with HTTP 500 on the unique constraint. The snapshots and the consent records of
  one write are stored in one transaction.
- Legal text taken from stored page content (`text_html` of the content history and of the consent-time lookup) is
  sanitised before it leaves `extract_legal_html`: with a content module that ships its sanitiser, the same
  allowlist as on its write path; otherwise structure tags only (headings, paragraphs, lists, tables, links with a
  safe `href`). It used to return the stored HTML as it was, scripts and event handlers included.
- Links in sanitised agreement HTML (checkbox labels, the structure-only legal text) keep an `href` only without a
  scheme or with `http`, `https` or `mailto`, read the way a browser reads it. The former check refused the literal
  prefixes `javascript:` and `data:` only, which a leading space or an embedded tab got past.
- The public order-agreement write refuses a `cookies` definition (HTTP 400, as for an unknown slug): the cookie
  banner stays out of the email-keyed consent log on this path too.

## 2.2.0 — 2026-10-10

- Cookie consent: `CookieConsent`, an append-only anonymous log of cookie banner decisions (`consent_id` UUID,
  channel, language, banner version, categories, action; no IP, user agent or URL).
- Cookie banner config on agreement versions: category `cookies`, `AgreementVersion.cookie_banner` (categories with
  Google Consent Mode signals, button labels and settings dialog texts `preferences_title` / `close_label` per
  language in `texts_t9n`); publish refuses a banner whose languages differ from
  `summary_t9n` or miss a channel language, and a second active `cookies` definition for the same channel scope.
- Public API v2: `GET {channel_idx}/cookie-banner/` (channel-specific banner beats the global one, language
  fallback) and `POST {channel_idx}/cookie-consents/` (throttle scope `agreements_cookie_consent`, fallback `30/min`;
  409 `STALE_REVISION` when the banner revision is outdated). Both endpoints answer errors in the v2 envelope
  (`VALIDATION_ERROR`, `INVALID_REQUEST`, `NOT_FOUND`, `STALE_REVISION`, `RATE_LIMITED`); a 200 banner is sent
  with `Cache-Control: public, max-age=300`.
- Admin API v2 (access area `agreements.consents`): `GET cookie-consents/` (filters, pagination), `export/` (CSV), `stats/` (per UTC day, revision,
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
- Access: the module declares its own access areas on its AppConfig and its admin views (copied from the
  entirius-django-access defaults; behaviour unchanged).
- The newsletter subscribe key is verified by django-access when installed: `APIKeyAuthentication` accepts an access
  token with scope `agreements.subscribe` (channel pin included) and never compares `AGREEMENTS_API_KEY`, which lives
  on as an imported legacy token. Without django-access nothing changes.
- Every public consent action that creates state or sends mail is throttled per address: `consents/` and
  `consents/withdraw/` (scope `agreements_consent`, 20/min), `newsletter/subscribe/` (`agreements_subscribe`,
  5/min), `consents/confirm/` and `consents/unsubscribe/` (`agreements_token`, 10/min). Before, only subscribe was.
  `DEFAULT_THROTTLE_RATES[<scope>]` overrides a rate; the class fallback holds when it is missing or malformed.
- The legacy `AGREEMENTS_API_KEY` comparison is constant-time (`secrets.compare_digest`).

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
