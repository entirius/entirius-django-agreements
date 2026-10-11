---
title: Agreements & Consent
description: GDPR-compliant agreement versioning, consent tracking, and order agreement snapshots for the Volkanos platform.
sidebar:
  label: Overview
  collapsed: true
---

django-agreements provides GDPR-compliant consent management as a proper legal
compliance domain: versioned agreement text, an append-only audit trail, and
per-order acceptance snapshots.

## What It Does

- Agreement definitions with category and consent channel classification
- Immutable versioning — every published version is a permanent record
- Append-only ConsentRecord audit trail (grant and withdrawal events)
- Per-order text freeze via OrderAgreementSnapshot
- Channel scoping — agreements can be global or restricted to specific storefronts
- Full legal text stored in ContentDB (mandatory agreements) or inline (marketing)
- Emits `consent_changed` when a double opt-in link is confirmed or an unsubscribe link is used
- Versioned legal clause sets per channel × legal basis × language, and an append-only objection log
- GDPR export and erasure hooks for the consent, objection and order snapshot rows
- Cookie consent: banner configuration on `cookies` agreement versions, an anonymous append-only decision log
  (`CookieConsent`), admin list/export/stats/erasure and a retention purge command

## Architecture

```
Admin API (/api/agreements/v2/admin/)
  → AgreementDefinition + AgreementVersion management
  → ConsentRecord read-only log
  → Cookie consent log: cookie-consents/ · export/ · stats/ · {consent_id}/ · {consent_id}/erase/

Public API (/api/agreements/v2/{channel_idx}/)
  → Definitions (active + published, language-resolved)
  → Consent submit / status / withdraw
  → Order agreement record
  → Cookie banner (GET cookie-banner/) and decision log (POST cookie-consents/)
```

## Default Agreement Types

Shipped via `fixtures/default_agreements.yaml`:

| Slug | Category | Channel |
|------|----------|---------|
| `terms-of-service` | mandatory | general |
| `privacy-policy` | mandatory | general |
| `marketing-email` | marketing | email |
| `marketing-sms` | marketing | sms |
| `marketing-push` | marketing | push |

All ship as drafts. Admin must set `summary_t9n` and publish before use.

The cookie banner ships separately (`fixtures/cookie_banner.yaml`, slug `cookie-banner`, category `cookies`, PL/EN
draft) — see [Cookie Consent](/volkanos/modules/agreements/cookie-consent/).

## Legal Clauses

`ClauseSet` holds the legal texts that accompany outbound messages — information clause, opt-out
wording, retention statement — versioned per channel, `LegalBasis` (`consent`, `legitimate_interest`,
`contract`) and language. Texts are edited only in the Django admin; publishing makes a version the
single current one for its triple, and published texts are read-only.

```python
from django_agreements.services.clause_set_service import render_legal_footer, resolve_clause_set

clause_set = resolve_clause_set(channel_idx="default-europe", legal_basis="legitimate_interest", language_code="pl")
footer = render_legal_footer(clause_set, recipient_email="lead@example.com")
```

Resolution: requested language → channel default language → `ClauseSetMissing`. The footer is plain
text; `{recipient_email}` is the only placeholder (`AGREEMENTS_CLAUSE_PLACEHOLDER`). Confirmed opt-outs
are appended with `objection_service.record_objection()` as `ObjectionEvent` rows. Admin API:
`GET /api/agreements/v2/admin/clause-sets/?channel_idx=&legal_basis=&language=&current=true` (read-only).
Language lookups (resolver and the `language` filter) are case-insensitive.

`LegalBasis` (`django_agreements.enums`) is the platform-wide definition of the GDPR legal basis; other
modules (leads) import it instead of declaring their own.

### Publishing rules

- A new text is a new version: in the admin, add a clause set (`clause_set_service.create_version()`
  numbers it), then run "Publish selected" (`publish()`), which makes it the single `is_current` row of
  its triple. `publish()` raises on an already-published set.
- One current version per triple is enforced by the service, not by a database constraint.
- A published set is locked: `ClauseSet.save()` raises `ValueError` when the channel, basis, language,
  any clause text or `published_at` changes (no un-publishing). With `update_fields` only the listed
  fields are compared, so toggling `is_current` works.
- Fixture loads (`loaddata`, `raw=True`) skip `save()`; a `pre_save` receiver applies the same guard, so a
  re-seed with changed text fails instead of rewriting a published row.
- Published sets cannot be deleted in the admin, and `ObjectionEvent.clause_set` is `PROTECT`.
- Queryset `.update()` bypasses the guards — only the service uses it, for `is_current`.

## GDPR Export and Erasure

`django_agreements.gdpr` exposes `gdpr_export(email)` and `gdpr_erase(email)`, discovered at call time by
the leads GDPR registry (`<app>.gdpr` of every installed app); agreements itself does not depend on leads.

| Hook | Behaviour |
|---|---|
| `gdpr_export` | `ConsentRecord`, `ObjectionEvent` and `OrderAgreementSnapshot` rows matching the plain email (case-insensitive) **or** its erasure token — rows pseudonymised earlier stay exportable |
| `gdpr_erase` | one transaction of queryset `update()`s: `email` → token, `ip_address` and `user_agent` cleared (objections keep no IP); returns the row count per model |

The token is `anon-<first 16 hex of sha256(lowercased email)>@<LEADS_ANONYMISED_DOMAIN>` — the same token
leads and communicator write, so one erased person matches across modules. Erasure is the one deliberate
exception to append-only: the rows stay as the audit trail (what was consented to, objected to or accepted
with an order, and when). An order snapshot keeps `body_snapshot`, language, `granted` and timestamps — an
order-retention obligation.

## Pages

- [Master Data Architecture](/volkanos/modules/agreements/master-data/) — entity roles, versioning, channel scoping, signal integration
- [Database Diagrams](/volkanos/modules/agreements/erd/) — auto-generated ER diagrams
- [Legal Pages](/volkanos/modules/agreements/legal-pages/) — content structure, versioning, consent-to-text traceability
- [Cookie Consent](/volkanos/modules/agreements/cookie-consent/) — banner configuration, front-end contract, admin API, GDPR, retention
- [Signals](/volkanos/modules/agreements/signals/) — `consent_changed` contract and a receiver example
- [Configuration](/volkanos/modules/agreements/configuration/) — Django settings
