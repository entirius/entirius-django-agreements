# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for content history service and admin API endpoints."""

from datetime import UTC, datetime

import pytest
from django.urls import reverse

from django_agreements.services.content_history_service import (
    extract_legal_html,
    get_legal_text_at_time,
    list_legal_snapshots,
    validate_legal_page_structure,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TILE_TXT_BTN_JSON = {
    "tiles": {"uuid-1": {"core_type": "tile-txt-btn", "description": "<p>Legal terms here</p>"}},
    "sections": {"s-1": {"core_type": "section-text"}},
    "tiles_order": ["uuid-1"],
    "sections_order": ["s-1"],
}


# ---------------------------------------------------------------------------
# Service: extract_legal_html
# ---------------------------------------------------------------------------


class TestExtractLegalHtml:
    """Test extract_legal_html() — pure function, no DB."""

    def test_extracts_description_from_tile_txt_btn(self):
        result = extract_legal_html(TILE_TXT_BTN_JSON)
        assert result == "<p>Legal terms here</p>"

    def test_returns_empty_for_empty_dict(self):
        result = extract_legal_html({})
        assert result == ""

    def test_returns_empty_when_tiles_key_missing(self):
        result = extract_legal_html({"sections": {}, "tiles_order": []})
        assert result == ""

    def test_returns_empty_when_tiles_is_empty(self):
        result = extract_legal_html({"tiles": {}, "sections": {}})
        assert result == ""

    def test_fallback_concatenates_all_tile_descriptions(self):
        content_json = {
            "tiles": {
                "uuid-1": {"core_type": "tile-other", "description": "<p>Part 1</p>"},
                "uuid-2": {"core_type": "tile-other", "description": "<p>Part 2</p>"},
            },
            "sections": {},
            "tiles_order": ["uuid-1", "uuid-2"],
            "sections_order": [],
        }
        result = extract_legal_html(content_json)
        assert "<p>Part 1</p>" in result
        assert "<p>Part 2</p>" in result

    def test_fallback_skips_tiles_with_empty_description(self):
        content_json = {
            "tiles": {
                "uuid-1": {"core_type": "tile-other", "description": ""},
                "uuid-2": {"core_type": "tile-other", "description": "<p>Only this</p>"},
            },
            "sections": {},
            "tiles_order": ["uuid-1", "uuid-2"],
            "sections_order": [],
        }
        result = extract_legal_html(content_json)
        assert "<p>Only this</p>" in result
        assert result.count("<p>Only this</p>") == 1

    def test_prefers_tile_txt_btn_over_other_tiles(self):
        content_json = {
            "tiles": {
                "uuid-other": {"core_type": "tile-other", "description": "<p>Other</p>"},
                "uuid-main": {"core_type": "tile-txt-btn", "description": "<p>Main legal</p>"},
            },
            "sections": {"s-1": {"core_type": "section-text"}},
            "tiles_order": ["uuid-other", "uuid-main"],
            "sections_order": ["s-1"],
        }
        result = extract_legal_html(content_json)
        assert result == "<p>Main legal</p>"

    def test_returns_empty_description_from_tile_txt_btn_when_missing(self):
        content_json = {
            "tiles": {"uuid-1": {"core_type": "tile-txt-btn"}},
            "sections": {"s-1": {"core_type": "section-text"}},
            "tiles_order": ["uuid-1"],
            "sections_order": ["s-1"],
        }
        result = extract_legal_html(content_json)
        assert result == ""


# ---------------------------------------------------------------------------
# Service: validate_legal_page_structure
# ---------------------------------------------------------------------------


class TestValidateLegalPageStructure:
    """Test validate_legal_page_structure() — pure function, no DB."""

    def test_valid_structure_returns_no_warnings(self):
        warnings = validate_legal_page_structure(TILE_TXT_BTN_JSON)
        assert warnings == []

    def test_multiple_sections_returns_warning(self):
        content_json = {
            "tiles": {"uuid-1": {"core_type": "tile-txt-btn", "description": "<p>Text</p>"}},
            "sections": {"s-1": {"core_type": "section-text"}, "s-2": {"core_type": "section-text"}},
            "tiles_order": ["uuid-1"],
            "sections_order": ["s-1", "s-2"],
        }
        warnings = validate_legal_page_structure(content_json)
        assert any("section" in w.lower() for w in warnings)

    def test_missing_description_returns_warning(self):
        content_json = {
            "tiles": {"uuid-1": {"core_type": "tile-txt-btn", "description": ""}},
            "sections": {"s-1": {"core_type": "section-text"}},
            "tiles_order": ["uuid-1"],
            "sections_order": ["s-1"],
        }
        warnings = validate_legal_page_structure(content_json)
        assert any("description" in w.lower() or "empty" in w.lower() for w in warnings)

    def test_no_tile_txt_btn_returns_warning(self):
        content_json = {
            "tiles": {"uuid-1": {"core_type": "tile-other", "description": "text"}},
            "sections": {"s-1": {"core_type": "section-text"}},
            "tiles_order": ["uuid-1"],
            "sections_order": ["s-1"],
        }
        warnings = validate_legal_page_structure(content_json)
        assert any("tile-txt-btn" in w for w in warnings)

    def test_empty_dict_returns_warnings(self):
        warnings = validate_legal_page_structure({})
        assert len(warnings) > 0

    def test_zero_sections_returns_warning(self):
        content_json = {
            "tiles": {"uuid-1": {"core_type": "tile-txt-btn", "description": "<p>Text</p>"}},
            "sections": {},
            "tiles_order": ["uuid-1"],
            "sections_order": [],
        }
        warnings = validate_legal_page_structure(content_json)
        assert any("section" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# Service: list_legal_snapshots (DB-dependent, requires ContentDB)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListLegalSnapshots:
    """Smoke tests for list_legal_snapshots().

    Full integration requires ContentDB models. If not installed, the service
    returns [] immediately — verify that contract holds.
    """

    def test_returns_empty_list_for_nonexistent_route(self):
        result = list_legal_snapshots("nonexistent-route-that-does-not-exist")
        assert result == []

    def test_returns_list_type(self):
        result = list_legal_snapshots("any-route")
        assert isinstance(result, list)

    def test_language_filter_does_not_raise(self):
        result = list_legal_snapshots("any-route", language="en")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Service: get_legal_text_at_time (DB-dependent, requires ContentDB)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetLegalTextAtTime:
    """Smoke tests for get_legal_text_at_time()."""

    def test_returns_none_for_nonexistent_route(self):
        result = get_legal_text_at_time("nonexistent-route", datetime.now(tz=UTC))
        assert result is None

    def test_returns_none_type_not_raises(self):
        at_time = datetime(2020, 1, 1, tzinfo=UTC)
        result = get_legal_text_at_time("any-route", at_time, language="en")
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# API: ContentHistory — auth tests
# ---------------------------------------------------------------------------


def _content_history_url(slug: str) -> str:
    return reverse("admin-content-history", kwargs={"slug": slug})


def _consent_text_url(email: str, record_id: int) -> str:
    return reverse("admin-consent-text", kwargs={"email": email, "record_id": record_id})


@pytest.mark.django_db
class TestContentHistoryAuth:
    """401 / 403 / 200 auth checks for content-history list endpoint."""

    def test_no_token_returns_401(self, api_client):
        url = _content_history_url("terms-of-service")
        response = api_client.get(url)
        assert response.status_code == 401

    def test_regular_user_returns_403(self, user_client, definition):
        url = _content_history_url("terms-of-service")
        response = user_client.get(url)
        assert response.status_code == 403

    def test_admin_nonexistent_definition_returns_404(self, admin_client):
        url = _content_history_url("nonexistent-slug")
        response = admin_client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestConsentTextAuth:
    """401 / 403 / 404 auth checks for consent-text endpoint."""

    def test_no_token_returns_401(self, api_client):
        url = _consent_text_url("test@test.com", 999)
        response = api_client.get(url)
        assert response.status_code == 401

    def test_regular_user_returns_403(self, user_client):
        url = _consent_text_url("test@test.com", 999)
        response = user_client.get(url)
        assert response.status_code == 403

    def test_admin_nonexistent_record_returns_404(self, admin_client):
        url = _consent_text_url("nobody@test.com", 999999)
        response = admin_client.get(url)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# API: ContentHistory — list behaviour
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestContentHistoryList:
    """Functional tests for the content-history list endpoint."""

    def test_definition_without_content_route_returns_404(self, admin_client, definition):
        # definition fixture has no content_route (empty string by default)
        url = _content_history_url("terms-of-service")
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_definition_with_content_route_returns_200_with_empty_snapshots(self, admin_client, definition):
        # Give the definition a content_route that points to a non-existent ContentDB page
        definition.content_route = "regulamin-test"
        definition.save()

        url = _content_history_url("terms-of-service")
        response = admin_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data["definition_slug"] == "terms-of-service"
        assert data["content_route"] == "regulamin-test"
        assert isinstance(data["snapshots"], list)
        # ContentDB not seeded in test DB → snapshots is empty
        assert data["snapshots"] == []

    def test_marketing_definition_without_content_route_returns_404(self, admin_client, marketing_definition):
        # Marketing definitions intentionally have no content_route
        url = _content_history_url("marketing-email")
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_response_shape_matches_schema(self, admin_client, definition):
        definition.content_route = "some-legal-route"
        definition.save()

        url = _content_history_url("terms-of-service")
        response = admin_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert "definition_slug" in data
        assert "content_route" in data
        assert "snapshots" in data

    def test_language_query_param_accepted(self, admin_client, definition):
        definition.content_route = "some-legal-route"
        definition.save()

        url = _content_history_url("terms-of-service")
        response = admin_client.get(url, {"language": "pl"})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# API: ConsentText — behaviour
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConsentText:
    """Functional tests for the consent-text endpoint."""

    def test_404_for_nonexistent_record(self, admin_client):
        url = _consent_text_url("nobody@test.com", 999999)
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_404_when_email_does_not_match_record(self, admin_client, published_version):
        from django_agreements.services import consent_service

        # Record consent under alice, query with bob's email
        record = consent_service.record_consent(
            email="alice@test.com", slug="terms-of-service", granted=True, source="checkout"
        )
        url = _consent_text_url("bob@test.com", record.pk)
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_404_for_marketing_consent_without_content_route(self, admin_client, marketing_published_version):
        from django_agreements.services import consent_service

        record = consent_service.record_consent(
            email="user@test.com", slug="marketing-email", granted=True, source="registration"
        )
        url = _consent_text_url("user@test.com", record.pk)
        response = admin_client.get(url)
        # marketing-email has no content_route → 404
        assert response.status_code == 404

    def test_mandatory_consent_with_content_route_returns_404_when_contentdb_empty(
        self, admin_client, definition, published_version
    ):
        from django_agreements.services import consent_service

        # Give definition a content_route but ContentDB has no matching snapshot
        definition.content_route = "terms-test"
        definition.save()

        record = consent_service.record_consent(
            email="user@test.com", slug="terms-of-service", granted=True, source="checkout"
        )
        url = _consent_text_url("user@test.com", record.pk)
        response = admin_client.get(url)
        # No ContentDB snapshot → 404
        assert response.status_code == 404
