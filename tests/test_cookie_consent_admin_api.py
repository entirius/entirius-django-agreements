# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Admin API of the cookie consent log: auth, filters, CSV export, stats, history and erasure."""

import csv
import io
import json
import uuid
from datetime import UTC, datetime

import pytest
from django.urls import reverse

from django_agreements.models import CookieConsent

LIST_URL = reverse("admin-cookie-consent-list")
EXPORT_URL = reverse("admin-cookie-consent-export")
STATS_URL = reverse("admin-cookie-consent-stats")
VISITOR = uuid.UUID("3f2b8c1e-7a4d-4e9b-9c2a-1d5e6f7a8b9c")
DAY_1 = datetime(2026, 9, 1, 10, tzinfo=UTC)
DAY_2 = datetime(2026, 9, 2, 10, tzinfo=UTC)


def _history_url(consent_id):
    return reverse("admin-cookie-consent-history", kwargs={"consent_id": consent_id})


def _erase_url(consent_id):
    return reverse("admin-cookie-consent-erase", kwargs={"consent_id": consent_id})


@pytest.fixture
def version(cookie_definition, make_cookie_version):
    return make_cookie_version(cookie_definition)


@pytest.fixture
def log(version):
    """Create a decision at `created_at` (default DAY_1)."""

    def _log(created_at=DAY_1, consent_id=VISITOR, **fields):
        values = {
            "channel_idx": "default-europe",
            "language": "pl",
            "agreement_version": version,
            "categories": {"necessary": True, "analytics": False},
            "action": "reject_all",
            **fields,
        }
        row = CookieConsent.objects.create(consent_id=consent_id, **values)
        CookieConsent.objects.filter(pk=row.pk).update(created_at=created_at)
        row.refresh_from_db()
        return row

    return _log


def _read_csv(response):
    return list(csv.reader(io.StringIO(b"".join(response.streaming_content).decode())))


def _all_urls():
    return [LIST_URL, EXPORT_URL, STATS_URL, _history_url(VISITOR)]


@pytest.mark.django_db
class TestAuth:
    @pytest.mark.parametrize("url", _all_urls())
    def test_get_without_token_is_401(self, api_client, url):
        assert api_client.get(url).status_code == 401

    @pytest.mark.parametrize("url", _all_urls())
    def test_get_as_regular_user_is_403(self, user_client, url):
        assert user_client.get(url).status_code == 403

    @pytest.mark.parametrize("url", _all_urls())
    def test_get_as_admin_is_200(self, admin_client, url):
        assert admin_client.get(url).status_code == 200

    def test_erase_without_token_is_401(self, api_client):
        assert api_client.post(_erase_url(VISITOR)).status_code == 401

    def test_erase_as_regular_user_is_403(self, user_client):
        assert user_client.post(_erase_url(VISITOR)).status_code == 403

    def test_erase_as_admin_is_200(self, admin_client):
        assert admin_client.post(_erase_url(VISITOR)).status_code == 200


@pytest.mark.django_db
class TestList:
    def test_row_shape(self, admin_client, log, version):
        row = log(action="custom", categories={"necessary": True, "analytics": True})
        result = admin_client.get(LIST_URL).json()["results"][0]
        assert result == {
            "id": row.pk,
            "consent_id": str(VISITOR),
            "channel_idx": "default-europe",
            "language": "pl",
            "revision": version.pk,
            "version_number": version.version_number,
            "definition_slug": "cookie-banner",
            "action": "custom",
            "categories": {"necessary": True, "analytics": True},
            "created_at": "2026-09-01T10:00:00Z",
        }

    @pytest.mark.parametrize(
        ("param", "match", "other"),
        [
            ("consent_id", {"consent_id": VISITOR}, {"consent_id": uuid.uuid4()}),
            ("channel_idx", {"channel_idx": "us-store"}, {"channel_idx": "default-europe"}),
            ("language", {"language": "en"}, {"language": "pl"}),
            ("action", {"action": "withdraw"}, {"action": "reject_all"}),
        ],
    )
    def test_filter(self, admin_client, log, param, match, other):
        expected = log(**match)
        log(**other)
        value = str(match[param])
        results = admin_client.get(LIST_URL, {param: value}).json()["results"]
        assert [r["id"] for r in results] == [expected.pk]

    def test_filter_revision(self, admin_client, log, cookie_definition, make_cookie_version):
        log()
        newer = make_cookie_version(cookie_definition)
        expected = log(agreement_version=newer)
        results = admin_client.get(LIST_URL, {"revision": newer.pk}).json()["results"]
        assert [r["id"] for r in results] == [expected.pk]

    def test_filter_date_from(self, admin_client, log):
        log(DAY_1)
        expected = log(DAY_2)
        results = admin_client.get(LIST_URL, {"date_from": "2026-09-02T00:00:00Z"}).json()["results"]
        assert [r["id"] for r in results] == [expected.pk]

    def test_filter_date_to(self, admin_client, log):
        expected = log(DAY_1)
        log(DAY_2)
        results = admin_client.get(LIST_URL, {"date_to": "2026-09-01T23:59:59Z"}).json()["results"]
        assert [r["id"] for r in results] == [expected.pk]

    @pytest.mark.parametrize(
        ("param", "value"), [("date_from", "yesterday"), ("revision", "abc"), ("consent_id", "not-a-uuid")]
    )
    def test_invalid_filter_is_400(self, admin_client, param, value):
        assert admin_client.get(LIST_URL, {param: value}).status_code == 400

    def test_newest_first_and_page_size(self, admin_client, log):
        rows = [log(datetime(2026, 9, day, tzinfo=UTC)) for day in (1, 2, 3)]
        data = admin_client.get(LIST_URL, {"page_size": 2}).json()
        assert data["count"] == 3
        assert [r["id"] for r in data["results"]] == [rows[2].pk, rows[1].pk]
        assert data["next"] is not None
        assert data["previous"] is None


@pytest.mark.django_db
class TestExport:
    def test_headers(self, admin_client, log):
        log()
        response = admin_client.get(EXPORT_URL)
        assert response["Content-Type"] == "text/csv"
        assert response["Content-Disposition"] == 'attachment; filename="cookie-consents.csv"'

    def test_categories_json_is_one_cell(self, admin_client, log, version):
        log(action="custom", categories={"necessary": True, "analytics": True})
        header, row = _read_csv(admin_client.get(EXPORT_URL))
        assert header == [
            "created_at",
            "consent_id",
            "channel_idx",
            "language",
            "definition_slug",
            "version_number",
            "revision",
            "action",
            "categories",
        ]
        assert row[:-1] == [
            "2026-09-01T10:00:00+00:00",
            str(VISITOR),
            "default-europe",
            "pl",
            "cookie-banner",
            str(version.version_number),
            str(version.pk),
            "custom",
        ]
        assert json.loads(row[-1]) == {"necessary": True, "analytics": True}

    def test_formula_channel_is_prefixed(self, admin_client, log):
        log(channel_idx="=HYPERLINK(1)")
        _, row = _read_csv(admin_client.get(EXPORT_URL))
        assert row[2] == "'=HYPERLINK(1)"

    def test_uses_list_filters(self, admin_client, log):
        log(action="withdraw")
        log(action="reject_all")
        rows = _read_csv(admin_client.get(EXPORT_URL, {"action": "withdraw"}))
        assert [row[7] for row in rows[1:]] == ["withdraw"]


@pytest.mark.django_db
class TestStats:
    def test_groups_by_day_revision_language_action(
        self, admin_client, log, version, cookie_definition, make_cookie_version
    ):
        newer = make_cookie_version(cookie_definition)
        log(DAY_1, action="accept_all")
        log(DAY_1, action="accept_all")
        log(DAY_1, action="reject_all", language="en")
        log(DAY_2, action="accept_all")
        log(DAY_2, action="accept_all", agreement_version=newer)
        results = admin_client.get(STATS_URL).json()["results"]
        rows = [(r["day"], r["revision"], r["version_number"], r["language"], r["action"], r["count"]) for r in results]
        assert rows == [
            ("2026-09-01", version.pk, 1, "en", "reject_all", 1),
            ("2026-09-01", version.pk, 1, "pl", "accept_all", 2),
            ("2026-09-02", version.pk, 1, "pl", "accept_all", 1),
            ("2026-09-02", newer.pk, 2, "pl", "accept_all", 1),
        ]

    def test_filters(self, admin_client, log):
        log(DAY_1, language="en")
        log(DAY_2, language="pl", channel_idx="us-store")
        assert len(admin_client.get(STATS_URL, {"language": "en"}).json()["results"]) == 1
        assert len(admin_client.get(STATS_URL, {"channel_idx": "us-store"}).json()["results"]) == 1
        assert len(admin_client.get(STATS_URL, {"date_from": "2026-09-02T00:00:00Z"}).json()["results"]) == 1
        assert len(admin_client.get(STATS_URL, {"date_to": "2026-09-01T23:59:59Z"}).json()["results"]) == 1

    def test_invalid_date_is_400(self, admin_client):
        assert admin_client.get(STATS_URL, {"date_to": "31/12/2026"}).status_code == 400


@pytest.mark.django_db
class TestHistoryAndErase:
    def test_history_newest_first(self, admin_client, log):
        older = log(DAY_1)
        newer = log(DAY_2, action="accept_all")
        log(DAY_2, consent_id=uuid.uuid4())
        data = admin_client.get(_history_url(VISITOR)).json()
        assert [r["id"] for r in data["results"]] == [newer.pk, older.pk]

    def test_unknown_id_is_empty(self, admin_client):
        assert admin_client.get(_history_url(uuid.uuid4())).json()["count"] == 0

    def test_erase_makes_history_unlinkable(self, admin_client, log):
        rows = [log(DAY_1), log(DAY_2)]
        other = log(DAY_2, consent_id=uuid.uuid4())
        response = admin_client.post(_erase_url(VISITOR))
        assert response.json() == {"erased": 2}
        assert admin_client.get(_history_url(VISITOR)).json()["count"] == 0
        assert CookieConsent.objects.count() == 3
        new_ids = set(CookieConsent.objects.filter(pk__in=[r.pk for r in rows]).values_list("consent_id", flat=True))
        assert len(new_ids) == 1
        assert new_ids.isdisjoint({VISITOR, other.consent_id})
        other.refresh_from_db()
        assert admin_client.get(_history_url(other.consent_id)).json()["count"] == 1

    def test_erase_unknown_id_touches_nothing(self, admin_client, log):
        log()
        assert admin_client.post(_erase_url(uuid.uuid4())).json() == {"erased": 0}
        assert CookieConsent.objects.get().consent_id == VISITOR


@pytest.mark.django_db
@pytest.mark.urls("tests.admin_urls")
class TestDjangoAdmin:
    @pytest.fixture
    def site_client(self, client, admin_user):
        client.force_login(admin_user)
        return client

    def test_changelist_renders(self, site_client, log):
        log()
        response = site_client.get(reverse("admin:django_agreements_cookieconsent_changelist"), {"q": str(VISITOR)})
        assert response.status_code == 200
        assert str(VISITOR) in response.content.decode()

    def test_add_change_delete_forbidden(self, site_client, log):
        row = log()
        assert site_client.get(reverse("admin:django_agreements_cookieconsent_add")).status_code == 403
        change = site_client.post(
            reverse("admin:django_agreements_cookieconsent_change", args=[row.pk]), {"action": "custom"}
        )
        assert change.status_code == 403
        assert (
            site_client.post(reverse("admin:django_agreements_cookieconsent_delete", args=[row.pk])).status_code == 403
        )
        row.refresh_from_db()
        assert row.action == "reject_all"
