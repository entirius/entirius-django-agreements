---
title: Master Data Architecture
description: How agreement definitions, versions, consent records, cookie consents, and order snapshots fit together in the django-agreements module.
---

django-agreements separates **master data** (agreement definitions and their versions) from
**transactional data** (consent records and order snapshots). This page explains the
architecture and the constraints that enforce GDPR compliance.

## Entity Roles

| Entity | Role | Mutable? |
|--------|------|----------|
| `AgreementDefinition` | Master: the agreement type (slug, category, channel scope) | Yes (soft-delete only) |
| `AgreementVersion` | Master: versioned content snapshot | Immutable once published |
| `Channel` | Master: channel scoping mirror from PIM | Synced from PIM |
| `ConsentRecord` | Transaction: append-only audit trail | Never (no updates, no deletes; GDPR erasure pseudonymises the person) |
| `OrderAgreementSnapshot` | Transaction: text frozen at order acceptance | Never (GDPR erasure pseudonymises the person) |
| `ClauseSet` | Master: legal clauses per channel × `LegalBasis` × language | Immutable once published |
| `ObjectionEvent` | Transaction: append-only log of confirmed opt-outs | Never (GDPR erasure pseudonymises the email) |
| `CookieConsent` | Transaction: append-only anonymous log of cookie banner decisions | Never (erasure re-randomises `consent_id`; the retention purge deletes old rows) |

## AgreementDefinition

Defines *what* an agreement is — its slug, category, consent channel, and which storefronts
it applies to.

```
AgreementDefinition
├── slug (unique)       "terms-of-service", "marketing-email"
├── name                Display name shown in admin
├── category            "mandatory" | "marketing" | "informational" | "cookies"
├── consent_channel     "general" | "email" | "sms" | "push" | "web"
├── channels (M2M)      empty = global, set = restricted to those channels
├── content_route       ContentDB route for full legal text (nullable for marketing)
├── is_active           False = soft-deleted
└── sort_order          Display order on consent page
```

**Channel scoping (Pattern 2):** The public API returns definitions where `channels` includes
the requested channel OR `channels` is empty. Never filter to channel-only — always include
global definitions.

Deleting a definition sets `is_active=False`. Hard deletes are never allowed — consent
records reference their version permanently.

## AgreementVersion

Each definition gets one or more versions. A version holds the translated checkbox label
(`summary_t9n`) and an optional pointer to the full legal text in ContentDB.

```
AgreementVersion
├── definition (FK)         Parent definition
├── version_number          Auto-incremented per definition (1, 2, 3...)
├── summary_t9n (JSON)      {"en": "I accept the terms", "pl": "Akceptuję regulamin"}
├── content_published_id    Soft ref to ContentDB Published (nullable for marketing)
├── published_at            null = draft, timestamp = live
├── is_current              Only one version per definition can be True
└── cookie_banner (JSON)    Categories + buttons — only for category "cookies", else {}
```

:::caution
`is_current` is enforced by the service layer (`version_service.publish_version()`), not the
database. Always use the service — never set `is_current` directly in admin or migrations.
:::

**Version lifecycle:**
1. Admin creates a draft version (published_at=null, is_current=False)
2. Admin edits `summary_t9n`, links ContentDB route
3. Admin publishes → `published_at` set, previous `is_current` version cleared

Once published, a version is immutable. Any content change requires a new version.

## Channel (Pattern 2 Scoping)

Agreements uses its own `Channel` model (Pattern 2 — local mirror). It is **not** a
foreign key to django-pim. Channels are synced via `sync_agreement_channels` management
command or the admin "Sync from PIM" action.

```
Channel
├── idx (unique)            Matches PIM Channel.idx (shared key)
├── name
├── default_language (FK)   FK → django_regional.Language
└── languages (M2M)         All languages for this channel
```

`Channel.save()` automatically adds `default_language` to the `languages` M2M.

## ConsentRecord

The audit trail. Every consent event — grant or withdrawal — creates a new row.

```
ConsentRecord
├── email (indexed)         Universal identifier, no FK to django-accounts
├── customer_id             Soft ref to customer account (nullable)
├── agreement_version (FK)  Which version was accepted/withdrawn (PROTECT)
├── granted                 True = given, False = withdrawn
├── source                  "checkout" | "registration" | "consent-page" |
│                           "newsletter-signup" | "api" | "import" |
│                           "crm-v1" | "double-optin-pending" |
│                           "double-optin-confirmed" | "unsubscribed"
├── ip_address
├── user_agent
└── channel_idx             Channel where consent was given
```

:::danger
ConsentRecord is **append-only**. No updates. No deletes. Every consent change is a new row.
This is the GDPR burden-of-proof record. Any code that calls `.save()` on an existing
ConsentRecord or `.delete()` on one is a bug.
:::

**Reading consent status:** use `consent_service.is_consented(email, slug)` — it reads the
latest record by `created_at` per `(email, agreement_version__definition__slug)`.

**Double opt-in:** When `source="double-optin-pending"`, the consent is not yet effective.
The marketing email sends a confirmation link. On click, a second record is created with
`source="double-optin-confirmed"`. `is_consented()` ignores `double-optin-pending` records.

**Cookie banners are not email consents:** definitions with `category="cookies"` are excluded from every
email-keyed flow — consent submit, status, people, marketing subscribers and the public definition lists.
Their decisions live in `CookieConsent`.

## OrderAgreementSnapshot

Freezes the legal text shown to the customer at checkout. Each accepted agreement creates
one row per order.

```
OrderAgreementSnapshot
├── order_id (UUID, indexed)    Matches Order.order_id (no FK to django-checkout)
├── email
├── agreement_version (FK)      PROTECT
├── body_snapshot               Full legal text at acceptance time (denormalized)
├── language                    ISO2 of the text shown
├── granted
├── ip_address
└── user_agent
```

`(order_id, agreement_version)` is unique — one snapshot per agreement per order.
`body_snapshot` is fetched from ContentDB at acceptance time and stored directly — the
customer always sees the exact text they agreed to, even if the ContentDB document changes later.

## ClauseSet and ObjectionEvent

```
ClauseSet
├── channel (FK)                PROTECT
├── legal_basis                 LegalBasis: consent | legitimate_interest | contract
├── language (FK)               django_regional.Language, PROTECT
├── version                     unique per (channel, legal_basis, language)
├── info_clause / optout_clause / retention_clause
├── is_current                  one True per triple — service-enforced
├── published_at                null = draft; locked once set
└── created_by (FK)             SET_NULL

ObjectionEvent
├── channel (FK)                PROTECT
├── email                       indexed
├── source                      communicator | manual | api
├── reason
└── clause_set (FK, nullable)   PROTECT — the clause text the person objected under
```

`ObjectionEvent` is independent of `ConsentRecord`: an objection to processing on legitimate interest is not
a consent withdrawal. Publishing rules and GDPR hooks: [Overview](/volkanos/modules/agreements/).

## CookieConsent

```
CookieConsent
├── consent_id (UUID)           Random id from the visitor's consent cookie — no email, IP or user agent
├── channel_idx                 Channel the banner was shown on
├── language                    ISO2 of the banner text
├── agreement_version (FK)      The cookies version decided on (PROTECT) — its pk is the "revision"
├── categories (JSON)           {"necessary": true, "analytics": false, ...}
├── action                      accept_all | reject_all | custom | withdraw
└── created_at
```

Append-only; the only writes to existing rows are the GDPR erasure (every row of a `consent_id` gets one new random
id) and the retention purge. Details: [Cookie Consent](/volkanos/modules/agreements/cookie-consent/).

## ContentDB Integration

Mandatory agreements (terms-of-service, privacy-policy) link their full text to ContentDB
via `AgreementVersion.content_published_id` (soft reference — no FK, avoids circular deps).

Marketing agreements (marketing-email, marketing-sms, marketing-push) have no ContentDB
link — the full text is in `summary_t9n`.

At order acceptance, `version_service.fetch_content_text()` fetches the text from ContentDB:

```python
# Soft dependency — ImportError-safe
try:
    from django_contentdb.models import Published
    text = Published.objects.get(pk=content_published_id).content["body"]
except ImportError:
    text = ""
```

## consent_changed

`consent_service.confirm_consent()` and `revoke_consent()` — the double opt-in confirmation and unsubscribe
links — send `consent_changed` after writing the new record. Other writes (`record_consent()` and the public
submit / withdraw endpoints) and cookie decisions send nothing.

```python
from django_agreements.signals import consent_changed

# kwargs: email (str), consent_type (str), granted (bool), source (str)
```

See [Signals](/volkanos/modules/agreements/signals/) for the contract.

## Dependency Map

```
django-agreements
├── depends on:   django_regional.Language (hard)
├── soft depends: django_contentdb.Published (ImportError-safe)
├── soft depends: django_pim.Channel (sync only, ImportError-safe)
├── soft depends: django_email (newsletter confirmation email, ImportError-safe)
└── depended on:  django-leads (LegalBasis, clause sets, discovers gdpr.py)
                  django-checkout (via OrderAgreementSnapshot UUID ref)
```

No FK dependencies on django-accounts (email as identifier) or django-checkout (UUID as
order reference). Loose coupling by design.
