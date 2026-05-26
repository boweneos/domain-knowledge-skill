"""Tests for the optional Presidio redaction. Skipped when Presidio isn't installed."""

import pytest

# Skip the whole module if Presidio isn't available
presidio_analyzer = pytest.importorskip("presidio_analyzer")
presidio_anonymizer = pytest.importorskip("presidio_anonymizer")

from dks.redact import redact_text  # noqa: E402


def test_redact_text_replaces_email():
    redacted = redact_text("Contact alice@example.com about claim.")
    assert "alice@example.com" not in redacted
    assert "[REDACTED:EMAIL_ADDRESS]" in redacted


def test_redact_text_replaces_person_name():
    redacted = redact_text("Customer John Smith reported the issue.")
    assert "John Smith" not in redacted
    assert "[REDACTED:PERSON]" in redacted


def test_redact_text_preserves_non_pii():
    # Use text with no detectable PII — no names, dates, numbers that look like identifiers
    text = "Policy section on retention obligations applies to all claims."
    redacted = redact_text(text)
    assert redacted == text


def test_redact_text_empty_returns_empty():
    assert redact_text("") == ""


def test_redact_text_no_pii_unchanged():
    text = "Policy section about retention periods."
    assert redact_text(text) == text


def test_redact_text_handles_multiple_entities():
    text = "Email alice@example.com phoned 0412 345 678"
    redacted = redact_text(text)
    assert "alice@example.com" not in redacted
    assert "0412 345 678" not in redacted
    assert "[REDACTED:EMAIL_ADDRESS]" in redacted
