# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for token_service — TDD (written before implementation).

These tests are intentionally RED until @dev-python implements
django_agreements/services/token_service.py.
"""

from unittest.mock import patch

# This import will FAIL until @dev-python implements token_service (expected RED state)
from django_agreements.services.token_service import generate_token, verify_token


class TestGenerateToken:
    def test_generate_token_returns_string(self):
        # Arrange / Act
        token = generate_token("user@example.com", "newsletter")

        # Assert
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_is_opaque(self):
        """Token must not contain the raw email in plaintext."""
        token = generate_token("user@example.com", "newsletter")

        assert "user@example.com" not in token

    def test_different_emails_produce_different_tokens(self):
        # Arrange
        token_alice = generate_token("alice@example.com", "newsletter")
        token_bob = generate_token("bob@example.com", "newsletter")

        # Assert
        assert token_alice != token_bob

    def test_different_consent_types_produce_different_tokens(self):
        # Arrange
        token_newsletter = generate_token("user@example.com", "newsletter")
        token_gdpr = generate_token("user@example.com", "gdpr-consent")

        # Assert
        assert token_newsletter != token_gdpr


class TestVerifyToken:
    def test_verify_valid_token(self):
        # Arrange
        token = generate_token("user@example.com", "newsletter")

        # Act
        result = verify_token(token)

        # Assert
        assert result is not None
        assert result["email"] == "user@example.com"
        assert result["consent_type"] == "newsletter"

    def test_token_contains_email_and_consent_type(self):
        # Arrange
        token = generate_token("alice@example.com", "gdpr-consent")

        # Act
        result = verify_token(token)

        # Assert
        assert result["email"] == "alice@example.com"
        assert result["consent_type"] == "gdpr-consent"

    def test_verify_tampered_token(self):
        # Arrange
        token = generate_token("user@example.com", "newsletter")
        tampered = token[:-5] + "XXXXX"

        # Act
        result = verify_token(tampered)

        # Assert
        assert result is None

    def test_verify_completely_invalid_token(self):
        # Act
        result = verify_token("not-a-valid-token-at-all")

        # Assert
        assert result is None

    def test_verify_empty_token(self):
        # Act
        result = verify_token("")

        # Assert
        assert result is None

    def test_verify_expired_token(self):
        """Token generated at Unix epoch (time=0) must be expired when verified now."""
        # Arrange — generate token in the far past (epoch 0)
        with patch("django.core.signing.time.time", return_value=0.0):
            token = generate_token("user@example.com", "newsletter")

        # Act — verify at current time (far future relative to epoch 0)
        result = verify_token(token)

        # Assert
        assert result is None

    def test_same_inputs_produce_consistent_valid_tokens(self):
        """Two tokens for the same inputs should both verify correctly."""
        # Arrange
        token1 = generate_token("user@example.com", "newsletter")
        token2 = generate_token("user@example.com", "newsletter")

        # Act
        result1 = verify_token(token1)
        result2 = verify_token(token2)

        # Assert — both valid, even if tokens differ (timestamp changes each call)
        assert result1 is not None
        assert result2 is not None
        assert result1["email"] == result2["email"]
        assert result1["consent_type"] == result2["consent_type"]
