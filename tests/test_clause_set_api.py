# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for the read-only clause set admin API and the 0002 migration."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.urls import reverse

CLAUSE_SET_LIST_URL = reverse("admin-clause-set-list")


@pytest.mark.django_db
class TestClauseSetListApi:
    def test_clause_sets_list_requires_admin(self, api_client):
        assert api_client.get(CLAUSE_SET_LIST_URL).status_code == 401

    def test_clause_sets_list_rejects_regular_user(self, user_client):
        assert user_client.get(CLAUSE_SET_LIST_URL).status_code == 403

    def test_clause_sets_filter_current(self, admin_client, make_clause_set, lang_pl, lang_en):
        current = make_clause_set(lang_pl)
        make_clause_set(lang_en, published=False)
        response = admin_client.get(CLAUSE_SET_LIST_URL, {"current": "true", "channel_idx": "default-europe"})
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        item = body["results"][0]
        assert item["id"] == current.pk
        assert (item["channel_idx"], item["language"], item["version"]) == ("default-europe", "pl", 1)
        assert set(item) == {
            "id",
            "channel_idx",
            "legal_basis",
            "language",
            "version",
            "is_current",
            "published_at",
            "info_clause",
            "optout_clause",
            "retention_clause",
        }

    def test_clause_sets_filter_basis_and_language(self, admin_client, make_clause_set, lang_pl, lang_en):
        make_clause_set(lang_pl, legal_basis="consent")
        make_clause_set(lang_en, legal_basis="consent")
        make_clause_set(lang_pl)
        response = admin_client.get(CLAUSE_SET_LIST_URL, {"legal_basis": "consent", "language": "EN"})
        assert response.json()["count"] == 1

    def test_clause_sets_invalid_filter_returns_400(self, admin_client):
        response = admin_client.get(CLAUSE_SET_LIST_URL, {"legal_basis": "whim"})
        assert response.status_code == 400
        assert "legal_basis" in response.json()


@pytest.mark.django_db(transaction=True)
@override_settings(MIGRATION_MODULES={})
def test_migrations_apply_from_0001():
    """Unapply 0002 down to the released 0001 schema, then migrate forward again."""
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes(), fake=True)
    executor.loader.build_graph()
    executor.migrate([("django_agreements", "0001_initial")])
    tables = connection.introspection.table_names()
    assert "django_agreements_clauseset" not in tables
    executor.loader.build_graph()
    executor.migrate([("django_agreements", "0002_clause_sets")])
    tables = connection.introspection.table_names()
    assert {"django_agreements_clauseset", "django_agreements_objectionevent"} <= set(tables)
