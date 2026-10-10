---
title: Signals
description: The consent_changed signal contract — when it fires, its kwargs, and a receiver example.
---

## consent_changed

**Location:** `src/django_agreements/signals/signals.py`

**Import:**

```python
from django_agreements.signals import consent_changed
```

### When Emitted

Sent only by the token flows of `consent_service`, after the new `ConsentRecord` row is written:

| Sender function | When | `granted` | `source` |
|---|---|---|---|
| `confirm_consent(token)` | double opt-in confirmation link (`POST consents/confirm/`) | `True` | `"double-optin-confirmed"` |
| `revoke_consent(token)` | unsubscribe link (`GET consents/unsubscribe/`) | `False` | `"unsubscribed"` |

Not sent by `record_consent()`, `record_multiple_consents()`, `request_consent()` or the public consent submit /
withdraw endpoints — a receiver never sees checkout, registration, consent-page or pending double opt-in records.
Cookie banner decisions (`CookieConsent`) emit no signal.

### Kwargs

| Kwarg | Type | Description |
|-----|------|-------------|
| `sender` | `type` | `ConsentRecord` model class |
| `email` | `str` | Email address from the signed token |
| `consent_type` | `str` | Agreement definition slug (e.g. `"marketing-email"`) |
| `granted` | `bool` | `True` = confirmed, `False` = unsubscribed |
| `source` | `str` | `"double-optin-confirmed"` or `"unsubscribed"` |

No channel is passed — the token carries none.

### Known Receivers

None in the platform modules. The signal is an extension point for services.

### Usage Example

```python
from django_agreements.signals import consent_changed


def on_consent_changed(sender, email: str, consent_type: str, granted: bool, source: str, **kwargs) -> None:
    if consent_type != "marketing-email":
        return
    ...


# In AppConfig.ready():
consent_changed.connect(on_consent_changed, dispatch_uid="my_service.on_consent_changed")
```

### Notes

- Sent synchronously, inside the request that handled the link, after the database write — safe to read the new
  consent state.
- Accept `**kwargs` in receivers so a future kwarg does not break them.
