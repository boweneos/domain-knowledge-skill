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


# --- v0.3.5 tuned default entity list ---


def test_redact_text_default_excludes_date_time():
    """Default entity list (v0.3.5+) deliberately excludes DATE_TIME to avoid
    over-detection on durations ('12 months', '8 weeks') and version dates
    common in policy/rule documents.
    """
    redacted = redact_text("The waiting period is 12 months from policy start.")
    # DATE_TIME should NOT be redacted by default (it was over-firing before v0.3.5)
    assert "[REDACTED:DATE_TIME]" not in redacted
    # The duration phrase stays
    assert "12 months" in redacted


def test_redact_text_default_excludes_location():
    """Default deliberately excludes LOCATION to avoid over-detection on
    internal acronyms (MLC, NEOS, URE) in insurance corpora.
    """
    redacted = redact_text("Refer to MLC or NEOS for advice.")
    assert "[REDACTED:LOCATION]" not in redacted
    assert "MLC" in redacted and "NEOS" in redacted


def test_redact_text_default_redacts_person():
    """PERSON stays in the default list — it's the highest-value PII redaction."""
    redacted = redact_text("Document owner: John Smith.")
    assert "John Smith" not in redacted
    assert "[REDACTED:PERSON]" in redacted


def test_redact_text_use_all_reverts_to_full_coverage():
    """use_all=True passes entities=None to Presidio for full all-entities mode
    (the pre-0.3.5 behavior). DATE_TIME redacts then.
    """
    redacted = redact_text("DOB 1985-03-14", use_all=True)
    # With all entities active, DATE_TIME should redact this DOB-shaped string
    assert "[REDACTED:DATE_TIME]" in redacted
