# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Legal clause sets: resolution per legal basis and language, footer rendering, versioning."""

from django.db import transaction
from django.db.models import Max, QuerySet
from django.utils import timezone
from django_regional.models import Language

from django_agreements import settings as agreements_settings
from django_agreements.enums import LegalBasis
from django_agreements.models import Channel, ClauseSet

CLAUSE_FIELDS = ("info_clause", "optout_clause", "retention_clause")


class ClauseSetMissing(LookupError):
    """No published current clause set for the requested channel, basis and language."""


def _current(channel: Channel, legal_basis: str, language_filter: dict) -> ClauseSet | None:
    return ClauseSet.objects.filter(
        channel=channel, legal_basis=legal_basis, is_current=True, published_at__isnull=False, **language_filter
    ).first()


def resolve_clause_set(*, channel_idx: str, legal_basis: str, language_code: str) -> ClauseSet:
    """Current clause set for the language, falling back to the channel default language.

    Raises ValueError (unknown basis), Channel.DoesNotExist, ClauseSetMissing.
    """
    if legal_basis not in LegalBasis.values:
        raise ValueError(f"Invalid legal basis '{legal_basis}'. Must be one of: {LegalBasis.values}.")
    channel = Channel.objects.get(idx=channel_idx)
    clause_set = _current(channel, legal_basis, {"language__iso2": language_code.lower()})
    if clause_set is None and channel.default_language_id:
        clause_set = _current(channel, legal_basis, {"language_id": channel.default_language_id})
    if clause_set is None:
        raise ClauseSetMissing(f"no clause set for {channel_idx}/{legal_basis}/{language_code}")
    return clause_set


def render_legal_footer(clause_set: ClauseSet, *, recipient_email: str) -> str:
    """Plain-text footer: info, opt-out and retention clauses separated by a blank line."""
    placeholder = agreements_settings.AGREEMENTS_CLAUSE_PLACEHOLDER
    clauses = (getattr(clause_set, field).replace(placeholder, recipient_email) for field in CLAUSE_FIELDS)
    return "\n\n".join(clauses)


def publish(clause_set: ClauseSet, *, user) -> ClauseSet:
    """Publish a clause set and make it the only current one for its (channel, basis, language).

    Raises ValueError if already published — a previous text becomes current again as a new version.
    """
    if clause_set.published_at:
        raise ValueError(f"Clause set {clause_set} is already published.")
    with transaction.atomic():
        ClauseSet.objects.filter(
            channel_id=clause_set.channel_id,
            legal_basis=clause_set.legal_basis,
            language_id=clause_set.language_id,
            is_current=True,
        ).exclude(pk=clause_set.pk).update(is_current=False)
        clause_set.published_at = timezone.now()
        clause_set.is_current = True
        clause_set.save(update_fields=["published_at", "is_current", "modified_at"])
    return clause_set


def create_version(*, channel: Channel, legal_basis: str, language: Language, texts: dict[str, str], user) -> ClauseSet:
    """Create an unpublished clause set with version = max + 1 for its (channel, basis, language)."""
    siblings = ClauseSet.objects.filter(channel=channel, legal_basis=legal_basis, language=language)
    last = siblings.aggregate(last=Max("version"))["last"] or 0
    return ClauseSet.objects.create(
        channel=channel,
        legal_basis=legal_basis,
        language=language,
        version=last + 1,
        created_by=user,
        **{field: texts.get(field, "") for field in CLAUSE_FIELDS},
    )


def list_clause_sets(
    *,
    channel_idx: str | None = None,
    legal_basis: str | None = None,
    language: str | None = None,
    current: bool | None = None,
) -> QuerySet[ClauseSet]:
    """Clause sets for the admin API, optionally filtered."""
    qs = ClauseSet.objects.select_related("channel", "language")
    filters = {
        "channel__idx": channel_idx,
        "legal_basis": legal_basis,
        "language__iso2": language,
        "is_current": current,
    }
    return qs.filter(**{key: value for key, value in filters.items() if value is not None})


def to_clause_set_response_dict(clause_set: ClauseSet) -> dict:
    """Build the admin API response dict (select_related channel + language)."""
    return {
        "id": clause_set.pk,
        "channel_idx": clause_set.channel.idx,
        "legal_basis": clause_set.legal_basis,
        "language": clause_set.language.iso2,
        "version": clause_set.version,
        "is_current": clause_set.is_current,
        "published_at": clause_set.published_at,
        **{field: getattr(clause_set, field) for field in CLAUSE_FIELDS},
    }
