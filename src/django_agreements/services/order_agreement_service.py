# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Order agreement snapshot service."""

import uuid

from django.db.models import QuerySet

from django_agreements.models import AgreementDefinition, AgreementVersion, ConsentRecord, OrderAgreementSnapshot
from django_agreements.models.consent_record import SOURCE_CHECKOUT
from django_agreements.services import version_service


def record_order_agreements(
    *,
    order_id: uuid.UUID,
    email: str,
    slugs: list[str],
    language: str = "en",
    channel_idx: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
) -> list[OrderAgreementSnapshot]:
    """Record agreement acceptance for an order.

    Creates both OrderAgreementSnapshot (with body_snapshot) and ConsentRecord
    for each accepted agreement. Uses bulk_create for performance.
    """
    definitions = {d.slug: d for d in AgreementDefinition.objects.filter(slug__in=slugs)}
    for slug in slugs:
        if slug not in definitions:
            raise ValueError(f"Agreement '{slug}' not found.")

    versions = {
        v.definition_id: v
        for v in AgreementVersion.objects.filter(definition__in=definitions.values(), is_current=True).select_related(
            "definition"
        )
    }
    for slug in slugs:
        defn = definitions[slug]
        if defn.pk not in versions:
            raise ValueError(f"No published version for agreement '{slug}'.")

    snapshot_objs = []
    consent_objs = []

    for slug in slugs:
        defn = definitions[slug]
        current_version = versions[defn.pk]

        # Fetch full text from ContentDB (or empty if not applicable)
        body_text = version_service.fetch_content_text(current_version.content_published_id, language)
        # For marketing agreements without ContentDB, use summary_t9n
        if not body_text:
            body_text = version_service.resolve_summary(current_version, language)

        snapshot_objs.append(
            OrderAgreementSnapshot(
                order_id=order_id,
                email=email,
                agreement_version=current_version,
                body_snapshot=body_text,
                language=language,
                granted=True,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        consent_objs.append(
            ConsentRecord(
                email=email,
                agreement_version=current_version,
                granted=True,
                source=SOURCE_CHECKOUT,
                ip_address=ip_address,
                user_agent=user_agent,
                channel_idx=channel_idx,
            )
        )

    OrderAgreementSnapshot.objects.bulk_create(snapshot_objs)
    ConsentRecord.objects.bulk_create(consent_objs)

    return list(
        OrderAgreementSnapshot.objects.filter(
            order_id=order_id, agreement_version__in=versions.values()
        ).select_related("agreement_version", "agreement_version__definition")
    )


def get_order_agreements(*, order_id: uuid.UUID) -> QuerySet[OrderAgreementSnapshot]:
    """Get all agreement snapshots for an order."""
    return OrderAgreementSnapshot.objects.filter(order_id=order_id).select_related(
        "agreement_version", "agreement_version__definition"
    )


def to_snapshot_response_dict(snapshot) -> dict:
    """Build order agreement response dict from ORM instance."""
    from django_agreements.schemas.responses.order_agreement import OrderAgreementResponse

    return OrderAgreementResponse(
        id=snapshot.pk,
        order_id=str(snapshot.order_id),
        email=snapshot.email,
        agreement_slug=snapshot.agreement_version.definition.slug,
        agreement_name=snapshot.agreement_version.definition.name,
        version_number=snapshot.agreement_version.version_number,
        language=snapshot.language,
        granted=snapshot.granted,
        created_at=snapshot.created_at,
    ).model_dump()
