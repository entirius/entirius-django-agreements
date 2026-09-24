---
title: Cookie Consent
description: Anonymous cookie consent log and cookie banner configuration — banner setup, channels and languages, the front-end contract, admin API, GDPR requests and retention.
---

The module stores the cookie banner (texts, categories, buttons) as a versioned agreement and logs every banner
decision anonymously in `CookieConsent`. A front end fetches the banner of its channel, shows it, and posts the
visitor's choice back; the admin API reads, exports, counts and erases the log.

## What It Stores

`CookieConsent` is an append-only log — one row per banner decision:

| Field | Meaning |
|---|---|
| `consent_id` | random UUID the front end keeps in a first-party cookie — the visitor's only identifier |
| `channel_idx` | channel the decision was made on |
| `language` | ISO 639-1 code the banner was shown in |
| `agreement_version` | the banner version (`PROTECT`) — its pk is the `revision` |
| `categories` | decision per category, e.g. `{"necessary": true, "analytics": true, "marketing": false}` |
| `action` | `accept_all`, `reject_all`, `custom` or `withdraw` |
| `created_at` | decision time |

Not stored: IP address, user agent, page URL. The proof of consent is the random id + banner version + language +
choice + time — enough to show what the visitor saw and chose (EDPB Guidelines 05/2020 ¶106 and ¶108; CNIL
deliberation 2020-092 §4) without any data that identifies the device.

Rows are never updated or deleted, with two exceptions: GDPR erasure (see [GDPR](#gdpr)) and the retention purge
(see [Retention](#retention)).

## Banner Configuration

A banner is an `AgreementDefinition` with `category="cookies"`. Its versions carry:

- `summary_t9n` — the banner body per language (limited HTML: `<a>`, `<b>`, `<i>`, `<u>`);
- `cookie_banner` — categories and button labels (JSON, allowed only on `cookies` definitions).

Create and edit versions through the admin API (`POST definitions/{slug}/versions/`, `PATCH versions/{pk}/`,
`POST versions/{pk}/publish/`). The `cookie_banner` shape, from the shipped fixture (texts shortened):

```json
{
  "categories": [
    {
      "key": "necessary",
      "required": true,
      "consent_mode": [],
      "label_t9n": {"pl": "Niezbędne", "en": "Necessary"},
      "description_t9n": {"pl": "Zapewniają działanie strony…", "en": "Keep the site working…"}
    },
    {
      "key": "analytics",
      "required": false,
      "consent_mode": ["analytics_storage"],
      "label_t9n": {"pl": "Analityczne", "en": "Analytics"},
      "description_t9n": {"pl": "Pokazują nam, jak korzystasz ze strony…", "en": "Show us how the site is used…"}
    },
    {
      "key": "marketing",
      "required": false,
      "consent_mode": ["ad_storage", "ad_user_data", "ad_personalization"],
      "label_t9n": {"pl": "Marketingowe", "en": "Marketing"},
      "description_t9n": {"pl": "Mierzą skuteczność reklam…", "en": "Measure ad performance…"}
    }
  ],
  "buttons_t9n": {
    "pl": {"accept_all": "Akceptuj wszystkie", "reject_all": "Odrzuć wszystkie", "customize": "Ustawienia", "save": "Zapisz wybór"},
    "en": {"accept_all": "Accept all", "reject_all": "Reject all", "customize": "Settings", "save": "Save choices"}
  }
}
```

Validation: category keys are unique, lowercase (`^[a-z][a-z0-9_]{1,31}$`); every category has a label and a
description in exactly the languages of `buttons_t9n`; all four button labels are non-empty; a required category
carries no `consent_mode` signals; signals are unique per category.

### Google Consent Mode

`consent_mode` lists the Consent Mode v2 signals a category grants. The front end sets a signal to `granted` when a
category that lists it is accepted, otherwise `denied`. The fixture maps:

| Category | `ad_storage` | `analytics_storage` | `ad_user_data` | `ad_personalization` |
|---|---|---|---|---|
| `necessary` (required) | — | — | — | — |
| `analytics` | | granted | | |
| `marketing` | granted | | granted | granted |

Only these four signals are accepted.

### Publishing rules

`version_service.publish_version()` refuses a `cookies` version when:

- the `cookie_banner` languages differ from the `summary_t9n` languages (one language set per version);
- a language of the definition's channels is missing — for a global definition, the languages of **every** channel;
- another active `cookies` definition covers the same scope: two global definitions, or two channel-specific
  definitions sharing a channel. A global and a channel-specific definition may coexist.

Publishing makes the version current and freezes it. **Revision = the version pk.** A new version gets a new
revision, so every front end asks its visitors again (see [Front-End Contract](#front-end-contract)).

### Default fixture

```bash
python manage.py loaddata cookie_banner
```

Loads a global definition `cookie-banner` (pk 100) with one draft version (pk 100) in Polish and English — brand-free
drafts for legal review. Load it **once**: a re-load resets both rows (the version becomes a draft again). Publish it
with `POST /api/agreements/v2/admin/versions/100/publish/`; later text changes are a new version, never an edit of
the fixture. It is not part of `default_agreements`.

## Channels, Languages and Domains

- A site is a channel × language. The banner is resolved per channel; the text language per request.
- One global banner (no channels) serves every channel; a channel-specific definition overrides it for its
  channels. Among several candidates the channel-specific one wins, then the lower `sort_order`.
- A global banner must cover the languages of every channel — publishing refuses it otherwise.
- `consent_id` lives in a first-party cookie, so each domain keeps its own id and asks on its own.
- The endpoints are called from the browser: the service's `CORS_ALLOWED_ORIGINS` must list every domain that
  shows the banner.

## Front-End Contract

Public endpoints, no authentication (no JWT, no `X-API-KEY`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/agreements/v2/{channel_idx}/cookie-banner/?language=pl` | current banner in one language |
| POST | `/api/agreements/v2/{channel_idx}/cookie-consents/` | log one decision (throttled) |

Flow:

1. **GET** the banner. Language: `language` → channel default language (each only when both the banner and the
   channel have it) → first banner language. Render `text`, `buttons` and `categories`; texts are already sanitised (limited HTML).
2. On the first decision, generate a UUID v4 as `consent_id` and keep it in a first-party cookie for
   `max_age_days` days, together with the `revision`.
3. **POST** the decision with `revision` and `language` echoed from the GET response. `categories` lists every
   banner category; required ones are `true`; `accept_all` = all `true`; `reject_all` and `withdraw` = every
   optional one `false`.
4. **409 `STALE_REVISION`** — a newer banner was published: GET it again and ask the visitor again.
5. A failed GET means **no consent**: keep every non-necessary tag denied.
6. A stored `revision` different from the current one also means the visitor must be asked again.

```http
GET /api/agreements/v2/default-europe/cookie-banner/?language=en
```

```json
{
  "revision": 100,
  "version_number": 1,
  "definition_slug": "cookie-banner",
  "language": "en",
  "max_age_days": 365,
  "text": "We use cookies. … <a href=\"/en/cookie-policy\">Cookie policy</a>",
  "buttons": {"accept_all": "Accept all", "reject_all": "Reject all", "customize": "Settings", "save": "Save choices"},
  "categories": [
    {"key": "necessary", "required": true, "consent_mode": [], "label": "Necessary", "description": "Keep the site working…"},
    {"key": "analytics", "required": false, "consent_mode": ["analytics_storage"], "label": "Analytics", "description": "…"},
    {"key": "marketing", "required": false, "consent_mode": ["ad_storage", "ad_user_data", "ad_personalization"], "label": "Marketing", "description": "…"}
  ]
}
```

```http
POST /api/agreements/v2/default-europe/cookie-consents/
Content-Type: application/json

{
  "consent_id": "3f2b8c1e-7a4d-4e9b-9c2a-1d5e6f7a8b9c",
  "revision": 100,
  "language": "en",
  "action": "custom",
  "categories": {"necessary": true, "analytics": true, "marketing": false}
}
```

`201 Created`:

```json
{
  "consent_id": "3f2b8c1e-7a4d-4e9b-9c2a-1d5e6f7a8b9c",
  "revision": 100,
  "language": "en",
  "action": "custom",
  "created_at": "2026-09-01T12:00:00Z"
}
```

Errors use the v2 envelope (`error`, `message`, `debug_id`, `details`):

| Status | `error` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | malformed body: `consent_id` not a UUID, `revision` < 1, `language` not two letters, unknown `action`, empty `categories` (field details in `details`) |
| 400 | `INVALID_REQUEST` | the decision does not fit the banner: language not in the banner or the channel, categories missing or unknown, a required category `false`, `action` contradicting `categories` |
| 404 | `NOT_FOUND` | unknown channel or no published banner for it |
| 409 | `STALE_REVISION` | `revision` is not the current banner version |
| 429 | `RATE_LIMITED` | POST throttle exceeded (scope `agreements_cookie_consent`, see [Configuration](/volkanos/modules/agreements/configuration/)) |

## Admin API

JWT + `IsAdminUser`, base `/api/agreements/v2/admin/`:

| Method | Path | Purpose |
|---|---|---|
| GET | `cookie-consents/` | paginated log, newest first |
| GET | `cookie-consents/export/` | the same filters, streamed as CSV |
| GET | `cookie-consents/stats/` | counts per UTC day, revision, language and action |
| GET | `cookie-consents/{consent_id}/` | every decision of one visitor, newest first |
| POST | `cookie-consents/{consent_id}/erase/` | GDPR erasure of one visitor |

List and export filters: `consent_id`, `channel_idx`, `language`, `action`, `revision` (version pk), `date_from`,
`date_to` (ISO 8601). Stats take `channel_idx`, `language`, `date_from`, `date_to`. A malformed filter is a 400.
Pagination: `page`, `page_size` (max 100). CSV columns: `created_at`, `consent_id`, `channel_idx`, `language`,
`definition_slug`, `version_number`, `revision`, `action`, `categories` (compact JSON).

**Stats days are UTC days** — a decision at 00:30 Warsaw time counts on the previous day.

The Django admin shows the log read-only (no add, change or delete).

## GDPR

The cookie log holds no email, so the email-keyed `gdpr.py` hooks (`gdpr_export`, `gdpr_erase`) do not touch it.
A visitor's request is served by `consent_id` — the value from their consent cookie — through the admin API:

- **Access / export:** `GET cookie-consents/{consent_id}/` — every decision of that id.
- **Erasure:** `POST cookie-consents/{consent_id}/erase/` — every row of the id gets **one new random**
  `consent_id`. The rows stay (statistics keep their counts), but nothing links them to the device any more; the
  response returns the number of rows moved. An unknown id erases 0 rows.

## Retention

| Setting | Default | Meaning |
|---|---|---|
| `AGREEMENTS_COOKIE_CONSENT_MAX_AGE_DAYS` | `365` | consent validity — returned as `max_age_days`, the cookie lifetime on every front end |
| `AGREEMENTS_COOKIE_CONSENT_RETENTION_DAYS` | `None` | proof retention for `purge_cookie_consents`; `None` = the command requires `--days` |

A decision justifies processing for at most `max_age_days` after `created_at`, so one cut-off is enough: the purge
deletes every row with `created_at` older than the retention, and refuses a retention shorter than the validity.
Recommended: **1461 days** (365 days of validity + 3 years for legal claims) — confirm with your lawyer.

```bash
python manage.py purge_cookie_consents --days 1461 --dry-run   # count only
python manage.py purge_cookie_consents                          # uses AGREEMENTS_COOKIE_CONSENT_RETENTION_DAYS
```

- Deletes in batches of 5000 rows.
- The module schedules nothing: the service runs the command from cron or Celery beat.
- Banner versions are never purged — the text proof stays (`PROTECT`).
- Stats are computed from the log, so they shrink with it.
