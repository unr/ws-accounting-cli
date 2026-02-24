"""Tests for AI privacy sanitization."""

from ws_accounting.ai.privacy import sanitize_description, sanitize_for_ai


class TestSanitizeDescription:
    """Test sensitive data redaction from transaction descriptions."""

    def test_credit_card_spaced(self):
        """16-digit card numbers with spaces are redacted."""
        text = "Payment from 4111 1111 1111 1111"
        assert sanitize_description(text) == "Payment from [CARD]"

    def test_credit_card_dashed(self):
        """16-digit card numbers with dashes are redacted."""
        text = "Charge to 4111-1111-1111-1111"
        assert sanitize_description(text) == "Charge to [CARD]"

    def test_credit_card_continuous(self):
        """16 consecutive digits are redacted."""
        text = "Card 4111111111111111 used"
        assert sanitize_description(text) == "Card [CARD] used"

    def test_account_number_9_digits(self):
        """9-digit account numbers are redacted."""
        text = "Transfer from acct 123456789"
        assert sanitize_description(text) == "Transfer from acct [ACCT]"

    def test_account_number_12_digits(self):
        """12-digit account numbers are redacted."""
        text = "Deposit to 123456789012"
        assert sanitize_description(text) == "Deposit to [ACCT]"

    def test_ssn_redaction(self):
        """SSN pattern (123-45-6789) is redacted."""
        text = "SSN 123-45-6789 on file"
        assert sanitize_description(text) == "SSN [SSN] on file"

    def test_email_redaction(self):
        """Email addresses are redacted."""
        text = "Receipt sent to user@example.com"
        assert sanitize_description(text) == "Receipt sent to [EMAIL]"

    def test_email_complex(self):
        """Complex email addresses are redacted."""
        text = "From john.doe+tag@sub.example.co.uk"
        assert sanitize_description(text) == "From [EMAIL]"

    def test_masked_card_pattern(self):
        """Masked card patterns like xxxx1234 are redacted."""
        text = "Payment on card xxxx1234"
        assert sanitize_description(text) == "Payment on card [CARD]"

    def test_masked_card_uppercase(self):
        """Masked card patterns XXXX1234 are redacted."""
        text = "Refund to XXXX5678"
        assert sanitize_description(text) == "Refund to [CARD]"

    def test_masked_card_with_dash(self):
        """Masked card xxxx-1234 with dash."""
        text = "Card ending xxxx-9012"
        assert sanitize_description(text) == "Card ending [CARD]"

    def test_normal_text_passes_through(self):
        """Normal merchant names and amounts pass through unchanged."""
        text = "WHOLE FOODS #10234 AUSTIN TX"
        assert sanitize_description(text) == text

    def test_short_numbers_preserved(self):
        """Short numbers (store IDs, etc.) are not redacted."""
        text = "Store #12345 Purchase $42.50"
        assert sanitize_description(text) == text

    def test_date_like_numbers_preserved(self):
        """Date-like patterns are not false-positive redacted."""
        text = "Payment 2026-01-15"
        assert sanitize_description(text) == text

    def test_multiple_patterns_in_one_string(self):
        """Multiple sensitive items are all redacted."""
        text = "Card 4111-1111-1111-1111 user@test.com"
        result = sanitize_description(text)
        assert "[CARD]" in result
        assert "[EMAIL]" in result
        assert "4111" not in result
        assert "user@" not in result


class TestSanitizeForAi:
    """Test batch sanitization."""

    def test_batch_sanitize(self):
        """sanitize_for_ai processes a list of descriptions."""
        descriptions = [
            "WHOLE FOODS #1234",
            "Card 4111111111111111 payment",
            "SSN 123-45-6789 file",
        ]
        result = sanitize_for_ai(descriptions)
        assert len(result) == 3
        assert result[0] == "WHOLE FOODS #1234"
        assert "[CARD]" in result[1]
        assert "[SSN]" in result[2]

    def test_empty_list(self):
        """Empty list returns empty list."""
        assert sanitize_for_ai([]) == []

    def test_preserves_order(self):
        """Order of descriptions is preserved."""
        descriptions = ["First", "Second", "Third"]
        result = sanitize_for_ai(descriptions)
        assert result == ["First", "Second", "Third"]
