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
- Emits `consent_changed_signal` for downstream integrations (double opt-in, unsubscribe)

## Architecture

```
Admin API (/api/agreements/v2/admin/)
  → AgreementDefinition + AgreementVersion management
  → ConsentRecord read-only log

Public API (/api/agreements/v2/{channel_idx}/)
  → Definitions (active + published, language-resolved)
  → Consent submit / status / withdraw
  → Order agreement record
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

## Pages

- [Master Data Architecture](/volkanos/modules/agreements/master-data/) — entity roles, versioning, channel scoping, signal integration
- [Database Diagrams](/volkanos/modules/agreements/erd/) — auto-generated ER diagrams
- [Legal Pages](/volkanos/modules/agreements/legal-pages/) — content structure, versioning, consent-to-text traceability
- [Signals](/volkanos/modules/agreements/signals/) — `consent_changed_signal` contract and receiver patterns
