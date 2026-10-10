# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.urls import path

from django_agreements.api.public.views.consent_views import PublicConsentViewSet
from django_agreements.api.public.views.cookie_consent_views import (
    PublicCookieBannerViewSet,
    PublicCookieConsentViewSet,
)
from django_agreements.api.public.views.definition_views import PublicDefinitionViewSet
from django_agreements.api.public.views.order_agreement_views import PublicOrderAgreementViewSet

urlpatterns = [
    # Definitions (channel-scoped)
    path(
        "<str:channel_idx>/definitions/",
        PublicDefinitionViewSet.as_view({"get": "list"}),
        name="public-definition-list",
    ),
    path(
        "<str:channel_idx>/definitions/for-user/",
        PublicDefinitionViewSet.as_view({"get": "for_user"}),
        name="public-definition-for-user",
    ),
    # Consents
    path("<str:channel_idx>/consents/", PublicConsentViewSet.as_view({"post": "create"}), name="public-consent-submit"),
    path(
        "<str:channel_idx>/consents/status/",
        PublicConsentViewSet.as_view({"get": "status_check"}),
        name="public-consent-status",
    ),
    path(
        "<str:channel_idx>/consents/withdraw/",
        PublicConsentViewSet.as_view({"post": "withdraw"}),
        name="public-consent-withdraw",
    ),
    # Newsletter subscribe (double opt-in)
    path(
        "<str:channel_idx>/newsletter/subscribe/",
        PublicConsentViewSet.as_view({"post": "subscribe"}),
        name="public-newsletter-subscribe",
    ),
    # Consent confirm (double opt-in callback)
    path(
        "<str:channel_idx>/consents/confirm/",
        PublicConsentViewSet.as_view({"post": "confirm"}),
        name="public-consent-confirm",
    ),
    # Consent unsubscribe (token-based, GDPR Art. 7)
    path(
        "<str:channel_idx>/consents/unsubscribe/",
        PublicConsentViewSet.as_view({"get": "unsubscribe"}),
        name="public-consent-unsubscribe",
    ),
    # Cookie banner and anonymous cookie consent log
    path(
        "<str:channel_idx>/cookie-banner/",
        PublicCookieBannerViewSet.as_view({"get": "retrieve"}),
        name="public-cookie-banner",
    ),
    path(
        "<str:channel_idx>/cookie-consents/",
        PublicCookieConsentViewSet.as_view({"post": "create"}),
        name="public-cookie-consent-submit",
    ),
    # Order agreements
    path(
        "<str:channel_idx>/orders/<str:order_id>/agreements/",
        PublicOrderAgreementViewSet.as_view({"post": "create"}),
        name="public-order-agreements",
    ),
]
