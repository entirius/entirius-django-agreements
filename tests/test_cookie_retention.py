# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Retention purge of the cookie consent log: service and purge_cookie_consents command."""

import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from django_agreements import settings as agreements_settings
from django_agreements.models import CookieConsent
from django_agreements.services import cookie_consent_service

RETENTION = 1461


@pytest.fixture
def log_aged(cookie_definition, make_cookie_version):
    """Create a decision `age_days` old."""
    version = make_cookie_version(cookie_definition)

    def _log(age_days):
        row = CookieConsent.objects.create(
            consent_id=uuid.uuid4(),
            channel_idx="default-europe",
            language="pl",
            agreement_version=version,
            categories={"necessary": True, "analytics": False},
            action="reject_all",
        )
        CookieConsent.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(days=age_days))
        return row

    return _log


def _purge(*args):
    out = StringIO()
    call_command("purge_cookie_consents", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestPurgeOlderThan:
    def test_deletes_only_older_rows(self, log_aged):
        old = log_aged(RETENTION + 1)
        recent = log_aged(RETENTION - 1)
        assert cookie_consent_service.purge_older_than(RETENTION) == 1
        assert list(CookieConsent.objects.values_list("pk", flat=True)) == [recent.pk]
        assert not CookieConsent.objects.filter(pk=old.pk).exists()

    def test_shorter_than_consent_validity_is_refused(self):
        with pytest.raises(ValueError, match="shorter than the cookie consent validity"):
            cookie_consent_service.purge_older_than(agreements_settings.COOKIE_CONSENT_MAX_AGE_DAYS - 1)

    def test_dry_run_deletes_nothing(self, log_aged):
        log_aged(RETENTION + 1)
        assert cookie_consent_service.purge_older_than(RETENTION, dry_run=True) == 1
        assert CookieConsent.objects.count() == 1

    def test_batches(self, log_aged, django_assert_num_queries):
        for _ in range(5):
            log_aged(RETENTION + 1)
        log_aged(1)
        # three batches of pks (2 + 2 + 1), one DELETE each, then the empty lookup that ends the loop
        with django_assert_num_queries(7):
            assert cookie_consent_service.purge_older_than(RETENTION, batch_size=2) == 5
        assert CookieConsent.objects.count() == 1


@pytest.mark.django_db
class TestPurgeCommand:
    def test_no_days_and_no_setting_is_an_error(self, monkeypatch):
        monkeypatch.setattr(agreements_settings, "COOKIE_CONSENT_RETENTION_DAYS", None)
        with pytest.raises(CommandError, match="--days"):
            _purge()

    def test_setting_is_used(self, monkeypatch, log_aged):
        monkeypatch.setattr(agreements_settings, "COOKIE_CONSENT_RETENTION_DAYS", RETENTION)
        log_aged(RETENTION + 1)
        log_aged(1)
        assert _purge() == f"Deleted 1 cookie consents older than {RETENTION} days\n"
        assert CookieConsent.objects.count() == 1

    def test_dry_run_output(self, log_aged):
        log_aged(RETENTION + 1)
        assert (
            _purge("--days", str(RETENTION), "--dry-run")
            == f"Would delete 1 cookie consents older than {RETENTION} days\n"
        )
        assert CookieConsent.objects.count() == 1

    def test_too_short_retention_is_refused(self):
        with pytest.raises(CommandError, match="shorter than the cookie consent validity"):
            _purge("--days", "10")
