# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Cookie banner resolution and the anonymous cookie consent log."""

from uuid import UUID

from django.db.models import Q

from django_agreements import settings as agreements_settings
from django_agreements.models import AgreementVersion, Channel, CookieConsent
from django_agreements.models.cookie_consent import ACTION_ACCEPT_ALL, ACTION_REJECT_ALL, ACTION_WITHDRAW
from django_agreements.schemas.requests.version import sanitize_html
from django_agreements.services.version_service import COOKIES_CATEGORY


class StaleRevisionError(Exception):
    """The submitted banner revision is not the one currently published for the channel."""

    def __init__(self, current_revision: int) -> None:
        super().__init__(f"Cookie banner revision is outdated; current revision is {current_revision}.")
        self.current_revision = current_revision


def get_banner(channel_idx: str) -> tuple[Channel, AgreementVersion]:
    """Current cookie banner of a channel: a channel-specific definition beats a global one.

    Raises Channel.DoesNotExist for an unknown channel, AgreementVersion.DoesNotExist when nothing is published.
    """
    channel = Channel.objects.select_related("default_language").prefetch_related("languages").get(idx=channel_idx)
    candidates = list(
        AgreementVersion.objects.filter(
            is_current=True, definition__category=COOKIES_CATEGORY, definition__is_active=True
        )
        .filter(Q(definition__channels=channel) | Q(definition__channels__isnull=True))
        .select_related("definition")
    )
    if not candidates:
        raise AgreementVersion.DoesNotExist("No published cookie banner for this channel.")
    specific = set(channel.definitions.values_list("pk", flat=True))
    candidates.sort(key=lambda v: (v.definition_id not in specific, v.definition.sort_order, v.definition_id))
    return channel, candidates[0]


def _channel_languages(channel: Channel) -> set[str]:
    return {language.iso2.lower() for language in channel.languages.all()}


def resolve_language(channel: Channel, version: AgreementVersion, requested: str | None) -> str:
    """Requested language → channel default → first banner language, limited to the channel's languages."""
    available = set(version.summary_t9n)
    channel_languages = _channel_languages(channel)
    allowed = available & channel_languages if channel_languages else available
    default = channel.default_language.iso2.lower() if channel.default_language else None
    for candidate in ((requested or "").lower(), default):
        if candidate in allowed:
            return candidate
    return next(iter(version.summary_t9n))


def _category_payload(category: dict, language: str) -> dict:
    return {
        "key": category["key"],
        "required": category["required"],
        "consent_mode": category["consent_mode"],
        "label": sanitize_html(category["label_t9n"][language]),
        "description": sanitize_html(category["description_t9n"][language]),
    }


def banner_payload(version: AgreementVersion, language: str) -> dict:
    """Banner texts, buttons and categories of `version` in `language`."""
    banner = version.cookie_banner
    return {
        "revision": version.pk,
        "version_number": version.version_number,
        "definition_slug": version.definition.slug,
        "language": language,
        "max_age_days": agreements_settings.COOKIE_CONSENT_MAX_AGE_DAYS,
        "text": sanitize_html(version.summary_t9n[language]),
        "buttons": {name: sanitize_html(label) for name, label in banner["buttons_t9n"][language].items()},
        "categories": [_category_payload(category, language) for category in banner["categories"]],
    }


def record(
    *, channel_idx: str, consent_id: UUID, revision: int, language: str, action: str, categories: dict[str, bool]
) -> CookieConsent:
    """Log one banner decision. Raises StaleRevisionError, ValueError, or DoesNotExist (see get_banner)."""
    channel, version = get_banner(channel_idx)
    if revision != version.pk:
        raise StaleRevisionError(version.pk)
    _validate_language(channel, version, language)
    _validate_choice(version.cookie_banner["categories"], action, categories)
    return CookieConsent.objects.create(
        consent_id=consent_id,
        channel_idx=channel.idx,
        language=language,
        agreement_version=version,
        categories=categories,
        action=action,
    )


def _validate_language(channel: Channel, version: AgreementVersion, language: str) -> None:
    if language not in version.summary_t9n:
        raise ValueError(f"Language '{language}' is not available in this cookie banner.")
    channel_languages = _channel_languages(channel)
    if channel_languages and language not in channel_languages:
        raise ValueError(f"Language '{language}' is not a language of channel '{channel.idx}'.")


def _validate_choice(config: list[dict], action: str, categories: dict[str, bool]) -> None:
    """Categories must match the banner exactly and agree with the action."""
    required = {category["key"]: category["required"] for category in config}
    missing, unknown = sorted(required.keys() - categories.keys()), sorted(categories.keys() - required.keys())
    if missing or unknown:
        raise ValueError(f"Categories must match the banner — missing: {missing}, unknown: {unknown}.")
    declined = sorted(key for key, is_required in required.items() if is_required and not categories[key])
    if declined:
        raise ValueError(f"Required categories must be true: {declined}.")
    optional = {categories[key] for key, is_required in required.items() if not is_required}
    if action == ACTION_ACCEPT_ALL and False in optional:
        raise ValueError("accept_all requires every category to be true.")
    if action in (ACTION_REJECT_ALL, ACTION_WITHDRAW) and True in optional:
        raise ValueError(f"{action} requires every non-required category to be false.")
