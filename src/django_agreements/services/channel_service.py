# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Channel management and sync service."""

import logging

from django.db.models import QuerySet

from django_agreements.models import Channel

logger = logging.getLogger(__name__)


def list_channels() -> QuerySet[Channel]:
    """Return all agreement channels."""
    return Channel.objects.select_related("default_language").prefetch_related("languages").all()


def get_channel(idx: str) -> Channel:
    """Get channel by idx. Raises DoesNotExist if not found."""
    return Channel.objects.get(idx=idx)


def get_channels_by_pks(pks: list[int]) -> list[Channel]:
    """Resolve channel PKs to Channel instances."""
    channels = list(Channel.objects.filter(pk__in=pks))
    if len(channels) != len(pks):
        found = {ch.pk for ch in channels}
        missing = [pk for pk in pks if pk not in found]
        raise ValueError(f"Channels not found: {missing}")
    return channels


def sync_channels_from_pim() -> int:
    """Sync agreement Channels from PIM Channel model.

    Creates or updates local channels keyed by idx.
    Returns count of synced channels.
    """
    try:
        from django_pim.models import Channel as PimChannel
    except ImportError:
        logger.info("django_pim not installed, skipping channel sync")
        return 0

    from django_regional.models import Language

    pim_channels = list(PimChannel.objects.prefetch_related("languages").select_related("default_language").all())

    # Batch language lookup — collect all default_language iso2 values upfront
    default_iso2s = {ch.default_language.iso2.lower() for ch in pim_channels if ch.default_language}
    lang_by_iso2 = (
        {lang.iso2.lower(): lang for lang in Language.objects.filter(iso2__in=default_iso2s)} if default_iso2s else {}
    )

    count = 0
    for pim_channel in pim_channels:
        local_lang = None
        if pim_channel.default_language:
            local_lang = lang_by_iso2.get(pim_channel.default_language.iso2.lower())

        ag_channel, _ = Channel.objects.update_or_create(
            idx=pim_channel.idx, defaults={"name": pim_channel.name, "default_language": local_lang}
        )

        pim_lang_iso2s = [lang.iso2 for lang in pim_channel.languages.all()]
        local_langs = Language.objects.filter(iso2__in=pim_lang_iso2s)
        ag_channel.languages.set(local_langs)

        count += 1

    return count


def to_channel_response_dict(ch) -> dict:
    """Build channel response dict from ORM instance with prefetched relations."""
    return {
        "id": ch.pk,
        "idx": ch.idx,
        "name": ch.name,
        "default_language_iso2": (ch.default_language.iso2 if ch.default_language else None),
        "language_codes": [lang.iso2 for lang in ch.languages.all()],
    }
