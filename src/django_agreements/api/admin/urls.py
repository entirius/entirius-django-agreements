# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.urls import path

from django_agreements.api.admin.views.channel_views import ChannelViewSet
from django_agreements.api.admin.views.clause_set_views import ClauseSetViewSet
from django_agreements.api.admin.views.consent_views import (
    ConsentViewSet,
    MarketingSubscribersViewSet,
    OrderAgreementViewSet,
    PeopleViewSet,
)
from django_agreements.api.admin.views.content_history_views import ContentHistoryViewSet
from django_agreements.api.admin.views.definition_views import DefinitionViewSet
from django_agreements.api.admin.views.token_views import TokenViewSet
from django_agreements.api.admin.views.version_views import VersionDetailViewSet, VersionViewSet

urlpatterns = [
    # Channels
    path("channels/", ChannelViewSet.as_view({"get": "list"}), name="admin-channel-list"),
    path("channels/sync/", ChannelViewSet.as_view({"post": "sync"}), name="admin-channel-sync"),
    # Legal clause sets (read-only)
    path("clause-sets/", ClauseSetViewSet.as_view({"get": "list"}), name="admin-clause-set-list"),
    # Definitions
    path("definitions/", DefinitionViewSet.as_view({"get": "list", "post": "create"}), name="admin-definition-list"),
    path(
        "definitions/<str:slug>/",
        DefinitionViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="admin-definition-detail",
    ),
    # Versions (nested under definition)
    path(
        "definitions/<str:slug>/versions/",
        VersionViewSet.as_view({"get": "list", "post": "create"}),
        name="admin-version-list",
    ),
    # Version detail + update + publish (by PK)
    path(
        "versions/<int:pk>/",
        VersionDetailViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="admin-version-detail",
    ),
    path("versions/<int:pk>/publish/", VersionDetailViewSet.as_view({"post": "publish"}), name="admin-version-publish"),
    # People (deduplicated consent holders)
    path("people/", PeopleViewSet.as_view({"get": "list"}), name="admin-people-list"),
    path("people/<str:email>/", PeopleViewSet.as_view({"get": "retrieve"}), name="admin-people-detail"),
    # Consent records (read-only, kept for backward compat)
    path("consents/", ConsentViewSet.as_view({"get": "list"}), name="admin-consent-list"),
    path("consents/<str:email>/history/", ConsentViewSet.as_view({"get": "history"}), name="admin-consent-history"),
    # Order agreements (read-only)
    path(
        "orders/<str:order_id>/agreements/",
        OrderAgreementViewSet.as_view({"get": "list"}),
        name="admin-order-agreements",
    ),
    # Marketing subscribers
    path(
        "marketing-subscribers/",
        MarketingSubscribersViewSet.as_view({"get": "list"}),
        name="admin-marketing-subscribers-list",
    ),
    path(
        "marketing-subscribers/export/",
        MarketingSubscribersViewSet.as_view({"get": "export"}),
        name="admin-marketing-subscribers-export",
    ),
    # Token generation
    path(
        "tokens/generate-unsubscribe-url/",
        TokenViewSet.as_view({"post": "generate_unsubscribe_url"}),
        name="admin-generate-unsubscribe-url",
    ),
    # Content history
    path(
        "definitions/<str:slug>/content-history/",
        ContentHistoryViewSet.as_view({"get": "list"}),
        name="admin-content-history",
    ),
    path(
        "people/<str:email>/consent-text/<int:record_id>/",
        ContentHistoryViewSet.as_view({"get": "consent_text"}),
        name="admin-consent-text",
    ),
]
