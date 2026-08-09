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

## Pages

- [Master Data Architecture](/volkanos/modules/agreements/master-data/) — entity roles, versioning, channel scoping, signal integration
- [Database Diagrams](/volkanos/modules/agreements/erd/) — auto-generated ER diagrams
- [Legal Pages](/volkanos/modules/agreements/legal-pages/) — content structure, versioning, consent-to-text traceability
- [Signals](/volkanos/modules/agreements/signals/) — `consent_changed_signal` contract and receiver patterns
