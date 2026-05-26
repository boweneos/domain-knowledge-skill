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

# Tuned default entity list for AU regulated-insurance corpora (v0.3.5+).
#
# Deliberately EXCLUDED (over-fire on typical policy/rule documents):
#   DATE_TIME         — fires on durations ("12 months"), version dates ("May 2025")
#   LOCATION          — fires on internal acronyms (MLC, NEOS, URE)
#   US_DRIVER_LICENSE — fires on version numbers ("1.0", "2.0")
#   URL, IP_ADDRESS, NRP — not relevant for insurance rule docs
#   US_SSN, US_PASSPORT, etc. — US-specific, not relevant to AU corpus
#
# To revert to Presidio's full all-entities coverage (pre-0.3.5 behavior), pass
# use_all=True to redact_text(), or use --redact-entities all on the CLI.
DEFAULT_REDACT_ENTITIES: tuple[str, ...] = (
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "AU_TFN",
    "AU_MEDICARE",
    "AU_ABN",
    "CREDIT_CARD",
    "IBAN_CODE",
)


def _missing_dep_message() -> str:
    model_url = (
        "https://github.com/explosion/spacy-models/releases/download/"
        "en_core_web_lg-3.8.0/en_core_web_lg-3.8.0.tar.gz"
    )
    return (
        "presidio or its spaCy model is not installed. To enable --redact-pii:\n"
        "  uv tool install --reinstall \\\n"
        "    --with presidio-analyzer --with presidio-anonymizer \\\n"
        f'    --with "en-core-web-lg @ {model_url}" \\\n'
        "    dks\n"
        "(--reinstall is needed if dks is already installed without these extras.\n"
        "The spaCy model wheel URL must match the spacy version pinned in dks's deps;\n"
        "today that is 3.8.x. python -m spacy download does NOT work inside a uv tool\n"
        "venv because pip isn't available there.)"
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
    return AnonymizerEngine()


def redact_text(
    text: str,
    *,
    entities: list[str] | None = None,
    use_all: bool = False,
) -> str:
    """Return `text` with detected PII entities replaced by `[REDACTED:<TYPE>]`.

    Entity selection (v0.3.5+):
      - default (entities=None, use_all=False): redact only DEFAULT_REDACT_ENTITIES
        — a tuned AU-insurance-focused list that excludes over-firing categories
        (DATE_TIME on durations, LOCATION on internal acronyms, US_DRIVER_LICENSE
        on version numbers).
      - explicit list (entities=[...]): pass that list verbatim to Presidio.
      - use_all=True: pass entities=None to Presidio (full coverage, including the
        noisy categories — pre-0.3.5 behavior). Use --redact-entities all on the CLI.

    NOTE: operators who need broader coverage (e.g. real DATE_TIME PII like a
    customer's DOB written 1985-03-14) should pass use_all=True or an explicit
    entity list including DATE_TIME. The default is a deliberate trade-off —
    fewer false positives on rule documents, at the cost of missing some real PII
    outside the default list.

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

    # Resolve which entities to pass to Presidio.
    # use_all=True → entities=None (Presidio default = all)
    # entities=[...] → pass verbatim
    # entities=None (default) → tuned DEFAULT_REDACT_ENTITIES
    if use_all:
        presidio_entities: list[str] | None = None
    elif entities is not None:
        presidio_entities = entities
    else:
        presidio_entities = list(DEFAULT_REDACT_ENTITIES)

    results = analyzer.analyze(text=text, entities=presidio_entities, language="en")
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
