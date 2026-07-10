# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Agreement definition management service."""

from django.db.models import Prefetch, Q, QuerySet

from django_agreements.models import AgreementDefinition, AgreementVersion
from django_agreements.services import channel_service

_CURRENT_VERSION_PREFETCH = Prefetch(
    "versions", queryset=AgreementVersion.objects.filter(is_current=True), to_attr="current_version_list"
)


def list_definitions(
    *,
    include_inactive: bool = False,
    category: str | None = None,
    consent_channel: str | None = None,
    channel_idx: str | None = None,
    search: str | None = None,
) -> QuerySet[AgreementDefinition]:
    """List definitions with optional filters."""
    qs = AgreementDefinition.objects.prefetch_related("channels", _CURRENT_VERSION_PREFETCH).all()

    if not include_inactive:
        qs = qs.filter(is_active=True)

    if category:
        categories = [c.strip() for c in category.split(",")]
        qs = qs.filter(category__in=categories)

    if consent_channel:
        qs = qs.filter(consent_channel=consent_channel)

    if channel_idx:
        qs = qs.filter(Q(channels__idx=channel_idx) | Q(channels__isnull=True))

    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(slug__icontains=search))

    return qs.distinct()


def get_definition(*, slug: str) -> AgreementDefinition:
    """Get definition by slug. Raises ObjectDoesNotExist if not found."""
    return AgreementDefinition.objects.prefetch_related("channels", _CURRENT_VERSION_PREFETCH).get(slug=slug)


def create_definition(
    *,
    slug: str,
    name: str,
    category: str,
    consent_channel: str = "general",
    content_route: str = "",
    is_active: bool = True,
    sort_order: int = 0,
    channel_ids: list[int] | None = None,
    display_contexts: list[str] | None = None,
) -> AgreementDefinition:
    """Create a new agreement definition. is_system is never set via API."""
    definition = AgreementDefinition.objects.create(
        slug=slug,
        name=name,
        category=category,
        consent_channel=consent_channel,
        content_route=content_route,
        is_active=is_active,
        sort_order=sort_order,
        display_contexts=display_contexts or [],
    )
    if channel_ids:
        channels = channel_service.get_channels_by_pks(channel_ids)
        definition.channels.set(channels)
    return AgreementDefinition.objects.prefetch_related("channels", _CURRENT_VERSION_PREFETCH).get(pk=definition.pk)


_SYSTEM_PROTECTED_FIELDS = {"slug", "category", "consent_channel"}

ALLOWED_UPDATE_FIELDS = {
    "name",
    "category",
    "consent_channel",
    "content_route",
    "is_active",
    "sort_order",
    "display_contexts",
}


def update_definition(*, slug: str, **kwargs) -> AgreementDefinition:
    """Update definition fields. Returns updated instance.

    Only ALLOWED_UPDATE_FIELDS may be changed. System definitions cannot change
    slug, category, or consent_channel.
    """
    definition = AgreementDefinition.objects.get(slug=slug)
    channel_ids = kwargs.pop("channel_ids", None)

    unknown = set(kwargs.keys()) - ALLOWED_UPDATE_FIELDS
    if unknown:
        raise ValueError(f"Cannot update fields: {', '.join(sorted(unknown))}.")

    if definition.is_system:
        blocked = _SYSTEM_PROTECTED_FIELDS & set(kwargs.keys())
        if blocked:
            raise ValueError(f"System agreements cannot change: {', '.join(sorted(blocked))}.")

    for field, value in kwargs.items():
        setattr(definition, field, value)
    definition.save()

    if channel_ids is not None:
        if channel_ids:
            channels = channel_service.get_channels_by_pks(channel_ids)
            definition.channels.set(channels)
        else:
            definition.channels.clear()

    return AgreementDefinition.objects.prefetch_related("channels", _CURRENT_VERSION_PREFETCH).get(pk=definition.pk)


def get_existing_by_slug(slug: str) -> AgreementDefinition | None:
    """Return definition by slug (including inactive), or None."""
    return AgreementDefinition.objects.filter(slug=slug).first()


def delete_definition(*, slug: str) -> None:
    """Soft-delete definition (set is_active=False). System definitions cannot be deleted."""
    definition = AgreementDefinition.objects.get(slug=slug)
    if definition.is_system:
        raise ValueError("System agreements cannot be deleted.")
    definition.is_active = False
    definition.save()


def create_or_reactivate_definition(
    *,
    slug: str,
    name: str,
    category: str,
    consent_channel: str = "general",
    content_route: str = "",
    is_active: bool = True,
    sort_order: int = 0,
    channel_ids: list[int] | None = None,
    display_contexts: list[str] | None = None,
) -> tuple["AgreementDefinition", bool]:
    """Create a new definition or reactivate a soft-deleted one.

    Returns (instance, was_created). Raises ValueError if an active definition
    with the same slug already exists.
    """
    existing = get_existing_by_slug(slug)
    if existing:
        if not existing.is_active:
            defn = update_definition(
                slug=slug,
                name=name,
                category=category,
                consent_channel=consent_channel,
                content_route=content_route,
                is_active=True,
                sort_order=sort_order,
                channel_ids=channel_ids,
                display_contexts=display_contexts,
            )
            return defn, False
        raise ValueError(f"Definition with slug '{slug}' already exists.")

    defn = create_definition(
        slug=slug,
        name=name,
        category=category,
        consent_channel=consent_channel,
        content_route=content_route,
        is_active=is_active,
        sort_order=sort_order,
        channel_ids=channel_ids,
        display_contexts=display_contexts,
    )
    return defn, True


def to_definition_response_dict(defn) -> dict:
    """Build DefinitionResponse dict from ORM instance with prefetched relations."""
    from django_agreements.schemas.responses.definition import DefinitionResponse

    current_list = getattr(defn, "current_version_list", None)
    current = current_list[0] if current_list else None
    return DefinitionResponse(
        id=defn.pk,
        slug=defn.slug,
        name=defn.name,
        category=defn.category,
        consent_channel=defn.consent_channel,
        channel_ids=[ch.pk for ch in defn.channels.all()],
        content_route=defn.content_route,
        is_active=defn.is_active,
        is_system=defn.is_system,
        display_contexts=defn.display_contexts,
        sort_order=defn.sort_order,
        current_version_number=current.version_number if current else None,
        created_at=defn.created_at,
        modified_at=defn.modified_at,
    ).model_dump()
