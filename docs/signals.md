---
title: Signals
description: The consent_changed_signal contract — when it fires, providing args, and receiver patterns.
---

## consent_changed_signal

**Location:** `src/django_agreements/signals/consent_signals.py`

**Import:**

```python
from django_agreements.signals import consent_changed_signal
```

### When Emitted

Sent by `consent_service.record_consent()` immediately after a `ConsentRecord` row is
committed to the database. Fired on every consent change — both grant (`granted=True`)
and withdrawal (`granted=False`).

### Providing Args

| Arg | Type | Description |
|-----|------|-------------|
| `sender` | `type` | `ConsentRecord` model class |
| `email` | `str` | Email address of the user |
| `slug` | `str` | Agreement slug (e.g., `"marketing-email"`) |
| `granted` | `bool` | `True` = consent given, `False` = withdrawn |
| `channel_idx` | `str` | Channel identifier where consent was recorded |
| `source` | `str` | Source of the consent (see `ConsentRecord.source` choices) |

### Known Receivers

| Module | `dispatch_uid` | What it does |
|--------|---------------|--------------|
| `django_email` | `django_email.on_consent_changed` | Triggers double opt-in email when `slug="marketing-email"` and `granted=True` |

### Usage Example

```python
from django_agreements.signals import consent_changed_signal

def on_consent_changed(
    sender,
    email: str,
    slug: str,
    granted: bool,
    channel_idx: str,
    source: str,
    **kwargs,
) -> None:
    if slug != "marketing-email":
        return
    if granted:
        newsletter_service.send_confirmation_email(email=email, channel_idx=channel_idx)
    else:
        newsletter_service.cancel_subscription(email=email)


# In AppConfig.ready():
consent_changed_signal.connect(
    on_consent_changed,
    dispatch_uid="django_email.on_consent_changed",
)
```

### Notes

- Signal fires **after** the database write — safe to read the new consent state.
- `source="pending-confirmation"` records are created before double opt-in completes.
  Receivers that only want confirmed consents should filter out this source.
- This signal is a **public API contract** — providing_args will not change without
  versioning (`consent_changed_v2_signal`).
