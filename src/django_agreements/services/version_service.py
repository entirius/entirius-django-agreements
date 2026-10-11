# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Agreement version management service."""

from django.db.models import QuerySet
from django.utils import timezone
from pydantic import ValidationError

from django_agreements.models import AgreementDefinition, AgreementVersion, Channel

COOKIES_CATEGORY = "cookies"


def list_versions(*, definition_slug: str) -> QuerySet[AgreementVersion]:
    """List all versions for a definition."""
    definition = AgreementDefinition.objects.get(slug=definition_slug)
    return AgreementVersion.objects.filter(definition=definition).select_related("definition")


def get_version(*, pk: int) -> AgreementVersion:
    """Get version by PK. Raises ObjectDoesNotExist."""
    return AgreementVersion.objects.select_related("definition").get(pk=pk)


def get_current_version(*, definition: AgreementDefinition) -> AgreementVersion | None:
    """Return the current published version for a definition, or None."""
    return AgreementVersion.objects.filter(definition=definition, is_current=True).select_related("definition").first()


def _ensure_cookie_banner_allowed(definition: AgreementDefinition, cookie_banner: dict | None) -> None:
    if cookie_banner and definition.category != COOKIES_CATEGORY:
        raise ValueError("cookie_banner is only allowed for category=cookies.")


def create_version(
    *,
    definition_slug: str,
    summary_t9n: dict,
    content_published_id: int | None = None,
    cookie_banner: dict | None = None,
) -> AgreementVersion:
    """Create a new draft version with auto-incremented version_number."""
    definition = AgreementDefinition.objects.get(slug=definition_slug)
    _ensure_cookie_banner_allowed(definition, cookie_banner)
    last_version = AgreementVersion.objects.filter(definition=definition).order_by("-version_number").first()
    next_number = (last_version.version_number + 1) if last_version else 1

    return AgreementVersion.objects.create(
        definition=definition,
        version_number=next_number,
        summary_t9n=summary_t9n,
        content_published_id=content_published_id,
        cookie_banner=cookie_banner or {},
        is_current=False,
        published_at=None,
    )


def update_draft_version(
    *,
    pk: int,
    summary_t9n: dict | None = None,
    content_published_id: int | None = ...,
    cookie_banner: dict | None = None,
) -> AgreementVersion:
    """Update a draft version. Raises ValueError if already published."""
    version = AgreementVersion.objects.select_related("definition").get(pk=pk)
    if version.published_at:
        raise ValueError(f"Version {version.version_number} is published and cannot be edited.")
    if summary_t9n is not None:
        version.summary_t9n = summary_t9n
    if content_published_id is not ...:
        version.content_published_id = content_published_id
    if cookie_banner is not None:
        _ensure_cookie_banner_allowed(version.definition, cookie_banner)
        version.cookie_banner = cookie_banner
    version.save()
    return version


def publish_version(*, pk: int) -> AgreementVersion:
    """Publish a draft version. Sets published_at and is_current=True.

    Unsets is_current on any previously current version for the same definition.
    Raises ValueError if already published.
    """
    version = AgreementVersion.objects.select_related("definition").get(pk=pk)
    if version.published_at:
        raise ValueError(f"Version {version.version_number} is already published.")
    if version.definition.category == COOKIES_CATEGORY:
        _check_cookie_banner(version)

    # Unset previous current
    AgreementVersion.objects.filter(definition=version.definition, is_current=True).update(is_current=False)

    version.published_at = timezone.now()
    version.is_current = True
    version.save()
    return version


def _check_cookie_banner(version: AgreementVersion) -> None:
    """Refuse to publish an incomplete or ambiguous cookie banner. Raises ValueError naming the problem."""
    languages = _banner_languages(version.cookie_banner)
    summary_languages = set(version.summary_t9n)
    if languages != summary_languages:
        raise ValueError(
            f"Cookie banner languages {sorted(languages)} must match summary_t9n languages {sorted(summary_languages)}."
        )
    missing = _scope_languages(version.definition) - languages
    if missing:
        raise ValueError(f"Cookie banner is missing channel languages: {sorted(missing)}.")
    if _has_overlapping_cookie_definition(version.definition):
        raise ValueError("Another active cookies definition already covers this channel scope.")


def _banner_languages(cookie_banner: dict) -> set[str]:
    from django_agreements.schemas.requests.version import CookieBannerConfig

    try:
        config = CookieBannerConfig.model_validate(cookie_banner)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, err['loc'])) or 'config'}: {err['msg']}" for err in exc.errors())
        raise ValueError(f"Invalid cookie banner config — {problems}") from exc
    return config.languages


def _scope_languages(definition: AgreementDefinition) -> set[str]:
    """ISO 639-1 codes of the definition's channels, or of every channel when the definition is global."""
    channels = definition.channels.all()
    if not channels.exists():
        channels = Channel.objects.all()
    return {iso2.lower() for iso2 in channels.values_list("languages__iso2", flat=True) if iso2}


def _has_overlapping_cookie_definition(definition: AgreementDefinition) -> bool:
    """Two globals overlap; two channel-specific overlap when they share a channel; global vs specific do not."""
    others = AgreementDefinition.objects.filter(category=COOKIES_CATEGORY, is_active=True).exclude(pk=definition.pk)
    channel_ids = list(definition.channels.values_list("pk", flat=True))
    if not channel_ids:
        return others.filter(channels__isnull=True).exists()
    return others.filter(channels__in=channel_ids).exists()


def resolve_summary(
    version: AgreementVersion, language: str | None = None, channel_default_lang: str | None = None
) -> str:
    """Resolve summary_t9n with fallback: requested → channel default → first available."""
    from django_agreements.schemas.requests.version import sanitize_html

    t9n = version.summary_t9n or {}
    if not t9n:
        return ""

    if language and language in t9n:
        return sanitize_html(t9n[language])

    if channel_default_lang and channel_default_lang in t9n:
        return sanitize_html(t9n[channel_default_lang])

    # Fallback to first available
    return sanitize_html(next(iter(t9n.values()), ""))


def to_version_response_dict(version: AgreementVersion) -> dict:
    """Build VersionResponse dict from ORM instance."""
    from django_agreements.schemas.responses.version import VersionResponse

    return VersionResponse(
        id=version.pk,
        definition_slug=version.definition.slug,
        version_number=version.version_number,
        summary_t9n=version.summary_t9n,
        content_published_id=version.content_published_id,
        published_at=version.published_at,
        is_current=version.is_current,
        cookie_banner=version.cookie_banner,
        created_at=version.created_at,
    ).model_dump()


def fetch_content_text(published_id: int, language: str) -> str:
    """Fetch full legal text from ContentDB Published snapshot.

    Soft dependency — returns empty string if ContentDB not installed.
    """
    if not published_id:
        return ""

    try:
        from django_contentdb.models import Published
    except (ImportError, RuntimeError):
        return ""

    try:
        published = Published.objects.get(pk=published_id)
    except Published.DoesNotExist:
        return ""

    body = published.content.content if published.content else {}
    if isinstance(body, dict):
        # ContentDB JSON: try extracting text for language
        tiles = body.get("tiles", {})
        texts = []
        for tile in tiles.values():
            if isinstance(tile, dict):
                text = tile.get("description", "")
                if text:
                    texts.append(text)
        return "\n".join(texts) if texts else str(body)
    return str(body)
