---
title: Legal Pages
description: How legal documents (terms, privacy policy) are stored in ContentDB, versioned, and linked to consent records.
sidebar:
  order: 3
---

## Overview

Legal pages = ContentDB pages linked to AgreementDefinitions via `content_route`.
Mandatory agreements (terms of service, privacy policy) store their full text in ContentDB.
Marketing agreements store their text inline in `summary_t9n` — no legal page needed.
Cookie banners (`category="cookies"`) keep the banner body inline in `summary_t9n` as well and link to the
cookie policy from it; the log of banner decisions has no consent-text lookup — the version (`revision`) is the proof.

Each publish in ContentDB creates a new immutable Published record. Old snapshots are preserved,
making it possible to look up what legal text was active at any point in time.

## Content Structure Constraint

Legal pages MUST use a specific ContentDB structure:

- Exactly 1 section with `core_type: "section-text"`
- Exactly 1 tile with `core_type: "tile-txt-btn"`
- Full legal text as HTML in the tile's `description` field

This constraint exists for historical rendering — simple, predictable structure
guarantees that past versions always render correctly. The `validate_legal_page_structure()`
service function checks compliance and surfaces warnings in the CMS.

Non-compliant pages still work (the extractor falls back to concatenating all tile
descriptions), but the CMS shows amber warning badges on non-standard snapshots.

## Data Flow

```
ContentDB Content (JSON)
  → Published (immutable snapshot, new one per publish)
    → AgreementVersion.content_published_id (soft FK)
      → AgreementDefinition.content_route (links to ContentDB Route)

ConsentRecord.created_at
  → time-based lookup against Published snapshots
    → legal text that was live when user gave consent
```

### Time-based lookup

`get_legal_text_at_time(content_route, timestamp, language)` finds the Published record
that was active at a given moment:

```python
Published.objects.filter(
    draft__routes__url=content_route,
    draft__language__iso2=language,
    created_at__lte=timestamp,
).order_by("-created_at").first()
```

## Version History

The admin API exposes full content history per definition:

```
GET /api/agreements/v2/admin/definitions/{slug}/content-history/?language=en
```

Returns all Published snapshots with:
- Publication date
- Language
- Text preview (first 200 chars, HTML stripped)
- Full HTML
- Draft UUID (for linking to CMS Builder)
- Structure validation warnings

The CMS shows this as a collapsible "Legal Page History" section in the agreement
edit view. Latest snapshot gets a "Current" badge.

## Consent-to-Text Traceability

GDPR Article 7 requires demonstrating what the user consented to. The consent text
endpoint resolves this:

```
GET /api/agreements/v2/admin/people/{email}/consent-text/{record_id}/
```

This endpoint:
1. Looks up the ConsentRecord by ID + email
2. Gets the definition's `content_route` and the record's `created_at` timestamp
3. Finds the Published snapshot that was live at that moment
4. Returns the exact legal text HTML + metadata

The CMS shows a "View text" button on each consent record in the Legal tab of the
person detail view.

## Editing Legal Pages

Edit legal pages in the CMS Builder (same workflow as static pages, but use the
constrained section-text + tile-txt-btn structure).

After editing:
1. Save draft → Publish → new Published snapshot created automatically
2. Create a new AgreementVersion only if the checkbox label (`summary_t9n`) changes
3. Legal text change alone = just republish the ContentDB page (same AgreementVersion)

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `admin/definitions/{slug}/content-history/` | GET | List all published snapshots for a legal page |
| `admin/people/{email}/consent-text/{record_id}/` | GET | Get legal text at time of consent |

Both endpoints require JWT + admin permissions.

## Service Functions

Located in `django_agreements/services/content_history_service.py`:

| Function | Purpose |
|----------|---------|
| `extract_legal_html(content_json)` | Extract legal text HTML from ContentDB JSON |
| `validate_legal_page_structure(content_json)` | Check structure compliance, return warnings |
| `list_legal_snapshots(content_route, language)` | List all Published snapshots for a route |
| `get_legal_text_at_time(content_route, at_time, language)` | Find snapshot active at a timestamp |
