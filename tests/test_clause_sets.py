# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for legal clause sets: resolution, footer rendering, versioning, admin rules."""

import pytest
from django.contrib import admin
from django.test import RequestFactory

from django_agreements.admin import ClauseSetAdmin
from django_agreements.models import Channel, ClauseSet
from django_agreements.services import clause_set_service
from django_agreements.services.clause_set_service import ClauseSetMissing, render_legal_footer, resolve_clause_set


def _resolve(language_code, legal_basis="legitimate_interest"):
    return resolve_clause_set(channel_idx="default-europe", legal_basis=legal_basis, language_code=language_code)


@pytest.mark.django_db
class TestResolveClauseSet:
    def test_C03_footer_resolution_missing_raises(self, channel, lang_pl):
        with pytest.raises(ClauseSetMissing, match="default-europe/consent/pl"):
            _resolve("pl", legal_basis="consent")
        assert ClauseSet.objects.count() == 0

    def test_requested_language_current(self, make_clause_set, lang_pl, lang_en):
        make_clause_set(lang_en)
        expected = make_clause_set(lang_pl)
        assert _resolve("pl") == expected

    def test_falls_back_to_channel_default_language(self, channel, make_clause_set, lang_pl):
        channel.default_language = lang_pl
        channel.save()
        expected = make_clause_set(lang_pl)
        assert _resolve("de") == expected

    def test_unpublished_requested_language_falls_back_then_missing(self, channel, make_clause_set, lang_pl, lang_en):
        channel.default_language = lang_en
        channel.save()
        make_clause_set(lang_pl, published=False)
        with pytest.raises(ClauseSetMissing):
            _resolve("pl")

    def test_never_falls_back_to_another_basis(self, make_clause_set, lang_pl):
        make_clause_set(lang_pl, legal_basis="legitimate_interest")
        with pytest.raises(ClauseSetMissing):
            _resolve("pl", legal_basis="consent")

    def test_never_falls_back_to_another_channel(self, channel_2, make_clause_set, lang_pl):
        make_clause_set(lang_pl)
        with pytest.raises(ClauseSetMissing):
            resolve_clause_set(channel_idx="us-store", legal_basis="legitimate_interest", language_code="pl")

    def test_invalid_basis_raises_value_error(self, channel):
        with pytest.raises(ValueError, match="Invalid legal basis"):
            _resolve("pl", legal_basis="whim")

    def test_C03_resolve_upper_case_language(self, make_clause_set, lang_pl, lang_en):
        make_clause_set(lang_en)
        expected = make_clause_set(lang_pl)
        assert _resolve("PL") == expected == _resolve("pl")

    def test_unknown_channel_raises_does_not_exist(self, db):
        with pytest.raises(Channel.DoesNotExist):
            _resolve("pl")


@pytest.mark.django_db
class TestRenderLegalFooter:
    def test_render_legal_footer_three_clauses_and_recipient_placeholder(self, make_clause_set, lang_pl):
        clause_set = make_clause_set(
            lang_pl,
            info_clause="Info for {recipient_email}.",
            optout_clause="Opt out {recipient_email}.",
            retention_clause="Kept 12 months.",
        )
        footer = render_legal_footer(clause_set, recipient_email="jan@example.com")
        assert footer == "Info for jan@example.com.\n\nOpt out jan@example.com.\n\nKept 12 months."

    def test_render_legal_footer_keeps_literal_braces(self, make_clause_set, lang_pl):
        clause_set = make_clause_set(lang_pl, info_clause="Art. {14} {unknown} {recipient_email} {}")
        footer = render_legal_footer(clause_set, recipient_email="a@example.com")
        assert footer.startswith("Art. {14} {unknown} a@example.com {}")


@pytest.mark.django_db
class TestVersioning:
    def test_create_version_increments_per_triple(self, channel, lang_pl, lang_en, admin_user):
        texts = {"info_clause": "i", "optout_clause": "o", "retention_clause": "r"}
        args = {"channel": channel, "legal_basis": "consent", "texts": texts, "user": admin_user}
        first = clause_set_service.create_version(language=lang_pl, **args)
        second = clause_set_service.create_version(language=lang_pl, **args)
        other = clause_set_service.create_version(language=lang_en, **args)
        assert (first.version, second.version, other.version) == (1, 2, 1)
        assert second.published_at is None and not second.is_current
        assert second.created_by == admin_user

    def test_publish_makes_single_current_per_triple(self, make_clause_set, lang_pl, lang_en, admin_user):
        old = make_clause_set(lang_pl, version=1)
        other_language = make_clause_set(lang_en, version=1)
        new = make_clause_set(lang_pl, version=2, published=False)
        clause_set_service.publish(new, user=admin_user)
        old.refresh_from_db()
        other_language.refresh_from_db()
        assert new.is_current and new.published_at is not None
        assert not old.is_current
        assert other_language.is_current
        assert _resolve("pl") == new

    def test_publish_already_published_raises(self, make_clause_set, lang_pl, admin_user):
        old = make_clause_set(lang_pl, version=1)
        new = make_clause_set(lang_pl, version=2, published=False)
        clause_set_service.publish(new, user=admin_user)
        old.refresh_from_db()
        with pytest.raises(ValueError, match="already published"):
            clause_set_service.publish(old, user=admin_user)
        assert _resolve("pl") == new

    def test_published_clause_set_text_cannot_change(self, make_clause_set, lang_pl, lang_en):
        clause_set = make_clause_set(lang_pl)
        clause_set.info_clause = "Rewritten"
        with pytest.raises(ValueError, match="cannot be changed"):
            clause_set.save()
        clause_set.refresh_from_db()
        clause_set.language = lang_en
        with pytest.raises(ValueError, match="cannot be changed"):
            clause_set.save()
        clause_set.refresh_from_db()
        clause_set.is_current = False
        clause_set.save()
        assert ClauseSet.objects.get(pk=clause_set.pk).info_clause.startswith("Info pl")

    def test_draft_clause_set_text_can_change(self, make_clause_set, lang_pl):
        draft = make_clause_set(lang_pl, published=False)
        draft.info_clause = "Edited draft"
        draft.save()
        assert ClauseSet.objects.get(pk=draft.pk).info_clause == "Edited draft"


@pytest.mark.django_db
class TestClauseSetAdmin:
    def test_published_clause_set_texts_readonly_in_admin(self, make_clause_set, lang_pl, lang_en, admin_user):
        model_admin = ClauseSetAdmin(ClauseSet, admin.site)
        request = RequestFactory().get("/")
        request.user = admin_user
        published = model_admin.get_readonly_fields(request, make_clause_set(lang_pl))
        draft = model_admin.get_readonly_fields(request, make_clause_set(lang_en, published=False))
        assert set(clause_set_service.CLAUSE_FIELDS) <= set(published)
        assert not set(clause_set_service.CLAUSE_FIELDS) & set(draft)
        assert {"channel", "legal_basis", "language"} <= set(draft)
        assert not {"channel", "legal_basis", "language"} & set(model_admin.get_readonly_fields(request))

    def test_admin_add_routes_through_create_version(self, make_clause_set, channel, lang_pl, admin_user):
        make_clause_set(lang_pl, version=1)
        request = RequestFactory().post("/")
        request.user = admin_user
        texts = {"info_clause": "New info", "optout_clause": "New opt-out", "retention_clause": "New retention"}
        obj = ClauseSet(channel=channel, legal_basis="legitimate_interest", language=lang_pl, **texts)
        ClauseSetAdmin(ClauseSet, admin.site).save_model(request, obj, form=None, change=False)
        created = ClauseSet.objects.get(pk=obj.pk)
        assert (created.version, created.is_current, created.created_by) == (2, False, admin_user)
        assert created.info_clause == "New info"

    def test_admin_cannot_delete_published_clause_set(self, make_clause_set, lang_pl, lang_en, admin_user):
        model_admin = ClauseSetAdmin(ClauseSet, admin.site)
        request = RequestFactory().get("/")
        request.user = admin_user
        assert not model_admin.has_delete_permission(request, make_clause_set(lang_pl))
        assert model_admin.has_delete_permission(request, make_clause_set(lang_en, published=False))
        assert "delete_selected" not in model_admin.get_actions(request)
