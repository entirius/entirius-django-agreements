# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Consent record management service — append-only audit log."""

from django.conf import settings
from django.db.models import Exists, Max, OuterRef, Prefetch, QuerySet, Subquery

from django_agreements.models import AgreementDefinition, AgreementVersion, ConsentRecord
from django_agreements.models.consent_record import (
    SOURCE_DOUBLE_OPTIN_CONFIRMED,
    SOURCE_DOUBLE_OPTIN_PENDING,
    SOURCE_UNSUBSCRIBED,
)
from django_agreements.services import token_service
from django_agreements.services.version_service import COOKIES_CATEGORY

# System consent display rules — controls special behavior beyond display_contexts.
# always_show: True = always render checkbox (e.g., terms must be re-accepted per order).
# skip_if_authenticated: True = hide if user is logged in and already consented.
SYSTEM_DISPLAY_RULES: dict[str, dict] = {
    "terms-of-service": {"always_show": True, "skip_if_authenticated": False},
    "privacy-policy": {"always_show": False, "skip_if_authenticated": True},
    "marketing-email": {"always_show": False, "skip_if_authenticated": False},
}


def record_consent(
    *,
    email: str,
    slug: str,
    granted: bool,
    source: str,
    channel_idx: str = "",
    customer_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str = "",
) -> ConsentRecord:
    """Record a consent grant or withdrawal. Always creates a new row."""
    # A cookie banner is not an email consent — its slug behaves as unknown here.
    definition = AgreementDefinition.objects.exclude(category=COOKIES_CATEGORY).get(slug=slug)
    current_version = AgreementVersion.objects.filter(definition=definition, is_current=True).first()
    if not current_version:
        raise ValueError(f"No published version for agreement '{slug}'.")

    return ConsentRecord.objects.create(
        email=email,
        customer_id=customer_id,
        agreement_version=current_version,
        granted=granted,
        source=source,
        ip_address=ip_address,
        user_agent=user_agent,
        channel_idx=channel_idx,
    )


def record_multiple_consents(
    *,
    email: str,
    agreements: list[dict],
    source: str,
    channel_idx: str = "",
    customer_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str = "",
) -> list[ConsentRecord]:
    """Record multiple consent decisions at once.

    agreements: [{"slug": "terms-of-service", "granted": True}, ...]

    """
    slugs = [item["slug"] for item in agreements]

    definitions_by_slug = {
        defn.slug: defn
        for defn in AgreementDefinition.objects.filter(slug__in=slugs).exclude(category=COOKIES_CATEGORY)
    }
    for slug in slugs:
        if slug not in definitions_by_slug:
            raise ValueError(f"Agreement '{slug}' not found.")

    versions_by_definition_id = {
        v.definition_id: v
        for v in AgreementVersion.objects.filter(definition__in=definitions_by_slug.values(), is_current=True)
    }
    for slug in slugs:
        defn = definitions_by_slug[slug]
        if defn.pk not in versions_by_definition_id:
            raise ValueError(f"No published version for agreement '{slug}'.")

    records = [
        ConsentRecord(
            email=email,
            customer_id=customer_id,
            agreement_version=versions_by_definition_id[definitions_by_slug[item["slug"]].pk],
            granted=item["granted"],
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
            channel_idx=channel_idx,
        )
        for item in agreements
    ]
    return ConsentRecord.objects.bulk_create(records)


def is_consented(email: str, slug: str) -> bool:
    """Check if email has active (granted) consent for the given agreement slug.

    Returns the granted value of the most recent ConsentRecord.
    Excludes double-optin-pending records (not yet confirmed).
    """
    latest = (
        ConsentRecord.objects.filter(email=email, agreement_version__definition__slug=slug)
        .exclude(source=SOURCE_DOUBLE_OPTIN_PENDING)
        .order_by("-created_at")
        .first()
    )
    return latest.granted if latest else False


def get_consent_status(email: str) -> dict[str, bool]:
    """Get current consent status for all agreements for an email.

    Returns {slug: granted_bool} based on most recent record per definition.
    Excludes double-optin-pending records (not yet confirmed).
    Uses a single annotated query — one correlated subquery per definition row.
    """
    latest_granted = Subquery(
        ConsentRecord.objects.filter(email=email, agreement_version__definition=OuterRef("pk"))
        .exclude(source=SOURCE_DOUBLE_OPTIN_PENDING)
        .order_by("-created_at")
        .values("granted")[:1]
    )
    definitions = (
        AgreementDefinition.objects.filter(is_active=True)
        .exclude(category=COOKIES_CATEGORY)
        .annotate(latest_granted=latest_granted)
    )
    return {defn.slug: bool(defn.latest_granted) for defn in definitions}


def list_consent_records(
    *,
    email: str | None = None,
    slug: str | None = None,
    channel_idx: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> QuerySet[ConsentRecord]:
    """List consent records with optional filters."""
    qs = ConsentRecord.objects.select_related("agreement_version", "agreement_version__definition").all()

    if email:
        qs = qs.filter(email__iexact=email)

    if slug:
        qs = qs.filter(agreement_version__definition__slug=slug)

    if channel_idx:
        qs = qs.filter(channel_idx=channel_idx)

    if date_from:
        qs = qs.filter(created_at__gte=date_from)

    if date_to:
        qs = qs.filter(created_at__lte=date_to)

    return qs


def get_consent_record(*, pk: int, email: str) -> ConsentRecord:
    """Get a single ConsentRecord by pk, scoped to email. Raises ObjectDoesNotExist if not found."""
    return ConsentRecord.objects.select_related("agreement_version__definition").get(pk=pk, email=email)


def get_consent_history(email: str) -> QuerySet[ConsentRecord]:
    """Full consent history for an email address."""
    return (
        ConsentRecord.objects.filter(email__iexact=email)
        .select_related("agreement_version", "agreement_version__definition")
        .order_by("-created_at")
    )


def list_consent_people(*, search: str | None = None) -> QuerySet:
    """List unique emails with consent count and last activity.

    Returns a ValuesQuerySet of dicts: {email, consent_count, last_activity}.
    """
    from django.db.models import Count

    qs = (
        ConsentRecord.objects.values("email")
        .annotate(consent_count=Count("id"), last_activity=Max("created_at"))
        .order_by("-last_activity")
    )
    if search:
        qs = qs.filter(email__icontains=search)
    return qs


def get_person_detail(email: str) -> dict:
    """Get consent summary + full history for a single email.

    Returns: {email, current_status: {slug: {status, category, name}}, history: QuerySet}
    Uses a single annotated query instead of N+1 per-definition lookups.
    """
    latest_granted = Subquery(
        ConsentRecord.objects.filter(email=email, agreement_version__definition=OuterRef("pk"))
        .exclude(source=SOURCE_DOUBLE_OPTIN_PENDING)
        .order_by("-created_at")
        .values("granted")[:1]
    )
    has_pending = Exists(
        ConsentRecord.objects.filter(
            email=email, source=SOURCE_DOUBLE_OPTIN_PENDING, granted=True, agreement_version__definition=OuterRef("pk")
        )
    )
    definitions = (
        AgreementDefinition.objects.filter(is_active=True)
        .exclude(category=COOKIES_CATEGORY)
        .annotate(latest_granted=latest_granted, has_pending=has_pending)
    )

    detailed_status = {}
    for defn in definitions:
        if defn.latest_granted:
            status_str = "granted"
        elif defn.has_pending:
            status_str = "pending"
        else:
            status_str = "withdrawn"
        detailed_status[defn.slug] = {"status": status_str, "category": defn.category, "name": defn.name}

    return {"email": email, "current_status": detailed_status, "history": get_consent_history(email)}


def get_definitions_for_user(
    *,
    channel_idx: str,
    context: str,
    email: str | None = None,
    is_authenticated: bool = False,
    language: str | None = None,
    channel_default_lang: str | None = None,
) -> list[dict]:
    """Return definitions relevant for a user in a given context.

    Rules:
    - Filters by display_contexts containing the requested context.
    - always_show (terms-of-service): always rendered regardless of prior consent.
    - skip_if_authenticated (privacy-policy): hidden if user is logged in
      and already consented (accepted during signup).
    - Other consents: hidden if already consented.

    When language and/or channel_default_lang are provided, the resolved summary
    text is included in the returned dicts (key: 'summary').
    """
    from django.db.models import Q

    from django_agreements.services import version_service

    qs = (
        AgreementDefinition.objects.filter(is_active=True, display_contexts__contains=[context])
        .exclude(category=COOKIES_CATEGORY)
        .filter(Q(channels__idx=channel_idx) | Q(channels__isnull=True))
        .distinct()
        .prefetch_related(
            Prefetch(
                "versions", queryset=AgreementVersion.objects.filter(is_current=True), to_attr="current_version_list"
            )
        )
    )

    status_map = get_consent_status(email) if email else {}

    results = []
    for defn in qs:
        current = defn.current_version_list[0] if defn.current_version_list else None
        if not current:
            continue

        already_consented = status_map.get(defn.slug, False)
        rules = SYSTEM_DISPLAY_RULES.get(defn.slug, {})

        # Skip logic
        if already_consented and not rules.get("always_show", False):
            if rules.get("skip_if_authenticated", False) and is_authenticated:
                continue
            if not rules.get("skip_if_authenticated", False):
                continue

        summary = version_service.resolve_summary(current, language, channel_default_lang)

        results.append(
            {
                "slug": defn.slug,
                "name": defn.name,
                "category": defn.category,
                "consent_channel": defn.consent_channel,
                "content_route": defn.content_route,
                "sort_order": defn.sort_order,
                "is_system": defn.is_system,
                "already_consented": already_consented,
                "required": defn.category == "mandatory",
                "version_number": current.version_number,
                "summary": summary,
            }
        )

    results.sort(key=lambda x: x["sort_order"])
    return results


def list_active_marketing_subscribers(slug: str | None = None) -> QuerySet:
    """Return active marketing subscribers.

    Finds the latest non-pending ConsentRecord per (email, definition) pair
    and returns only those where granted=True.
    """
    latest_record_pk = (
        ConsentRecord.objects.filter(
            email=OuterRef("email"), agreement_version__definition=OuterRef("agreement_version__definition")
        )
        .exclude(source=SOURCE_DOUBLE_OPTIN_PENDING)
        .order_by("-created_at")
        .values("pk")[:1]
    )

    definitions = AgreementDefinition.objects.filter(category="marketing")
    if slug:
        definitions = definitions.filter(slug=slug)

    return (
        ConsentRecord.objects.filter(
            agreement_version__definition__in=definitions, granted=True, pk=Subquery(latest_record_pk)
        )
        .select_related("agreement_version__definition")
        .order_by("agreement_version__definition__slug", "email")
    )


def request_consent(*, email: str, consent_type: str, channel_idx: str = "") -> ConsentRecord:
    """Create a consent record.

    When NEWSLETTER_DOUBLE_OPTIN is True (default): creates a pending record
    and the caller is expected to send a confirmation email.
    When False: immediately records confirmed consent without email confirmation.
    """
    double_optin = getattr(settings, "NEWSLETTER_DOUBLE_OPTIN", True)
    if double_optin:
        source = SOURCE_DOUBLE_OPTIN_PENDING
    else:
        source = SOURCE_DOUBLE_OPTIN_CONFIRMED
    return record_consent(email=email, slug=consent_type, granted=True, source=source, channel_idx=channel_idx)


def confirm_consent(token: str) -> ConsentRecord:
    """Verify token and create a confirmed consent record."""
    payload = token_service.verify_token_or_raise(token)
    record = record_consent(
        email=payload["email"], slug=payload["consent_type"], granted=True, source=SOURCE_DOUBLE_OPTIN_CONFIRMED
    )
    from django_agreements.signals import consent_changed

    consent_changed.send(
        sender=ConsentRecord,
        email=payload["email"],
        consent_type=payload["consent_type"],
        granted=True,
        source=SOURCE_DOUBLE_OPTIN_CONFIRMED,
    )
    return record


def revoke_consent(token: str) -> ConsentRecord:
    """Verify token and create an unsubscribed consent record."""
    payload = token_service.verify_token_or_raise(token)
    record = record_consent(
        email=payload["email"], slug=payload["consent_type"], granted=False, source=SOURCE_UNSUBSCRIBED
    )
    from django_agreements.signals import consent_changed

    consent_changed.send(
        sender=ConsentRecord,
        email=payload["email"],
        consent_type=payload["consent_type"],
        granted=False,
        source=SOURCE_UNSUBSCRIBED,
    )
    return record


def to_consent_response_dict(record) -> dict:
    """Build consent response dict from ORM instance with select_related."""
    from django_agreements.schemas.responses.consent import ConsentRecordResponse

    return ConsentRecordResponse(
        id=record.pk,
        email=record.email,
        customer_id=record.customer_id,
        agreement_slug=record.agreement_version.definition.slug,
        agreement_name=record.agreement_version.definition.name,
        category=record.agreement_version.definition.category,
        version_number=record.agreement_version.version_number,
        granted=record.granted,
        source=record.source,
        ip_address=str(record.ip_address) if record.ip_address else None,
        channel_idx=record.channel_idx,
        created_at=record.created_at,
    ).model_dump()
