"""Optional PII redaction via Microsoft Presidio.

This module is the integration point for `dks ingest --redact-pii`. It lazily
imports Presidio so that dks core works without the optional dependency
installed.

Install the optional extra:
    uv tool install --with presidio-analyzer --with presidio-anonymizer dks
And download the spaCy model (once):
    python -m spacy download en_core_web_lg

If Presidio isn't installed, calling redact_text() raises ImportError with
a clear message; callers (CLI) should catch and re-message appropriately.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any


def _missing_dep_message() -> str:
    return (
        "presidio is not installed. To enable --redact-pii:\n"
        "  uv tool install --with presidio-analyzer --with presidio-anonymizer dks\n"
        "  python -m spacy download en_core_web_lg\n"
        "Then re-run with --redact-pii."
    )


@lru_cache(maxsize=1)
def _get_analyzer() -> Any:
    """Lazy-load Presidio analyzer. Cached so the spaCy model loads once per process."""
    try:
        from presidio_analyzer import AnalyzerEngine
    except ImportError as e:
        raise ImportError(_missing_dep_message()) from e
    return AnalyzerEngine()


@lru_cache(maxsize=1)
def _get_anonymizer() -> Any:
    try:
        from presidio_anonymizer import AnonymizerEngine
    except ImportError as e:
        raise ImportError(_missing_dep_message()) from e
    return AnonymizerEngine()  # type: ignore[no-untyped-call]


def redact_text(text: str, *, entities: list[str] | None = None) -> str:
    """Return `text` with detected PII entities replaced by `[REDACTED:<TYPE>]`.

    `entities`: optional list of Presidio entity types to redact (e.g.
    ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"]). Default: all entities
    Presidio detects for English (plus Australian patterns Presidio supports
    natively: AU_TFN, AU_MEDICARE, AU_ABN).

    Raises ImportError with install hint if Presidio isn't available.
    """
    if not text:
        return text

    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()

    try:
        from presidio_anonymizer.entities import OperatorConfig
    except ImportError as e:
        raise ImportError(_missing_dep_message()) from e

    results = analyzer.analyze(text=text, entities=entities, language="en")
    if not results:
        return text

    # Default operator: replace with [REDACTED:<TYPE>]
    operators: dict[str, Any] = {
        "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED:DEFAULT]"}),
    }
    # Per-entity replacements (override the default for known entity types)
    for entity_type in {r.entity_type for r in results}:
        operators[entity_type] = OperatorConfig(
            "replace", {"new_value": f"[REDACTED:{entity_type}]"}
        )

    anonymized = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
    result: str = anonymized.text
    return result
