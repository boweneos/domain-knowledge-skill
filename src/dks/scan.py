"""Regex-based PII pattern scanner — advisory only, no content modification.

The scanner detects high-confidence structured identifiers (TFN, Medicare,
ABN, email, AU phone, DOB-shaped dates). It does NOT detect names or
unstructured PII — for that, use the v0.3.2 redact path with Presidio.

Scan output is intended for the operator: a hint that a source may warrant
a stricter --classification at ingest. The scanner never changes
classification automatically; that decision belongs to the operator.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScanFinding:
    """A single pattern's match count in a scanned text."""

    pattern: str
    count: int


@dataclass(frozen=True)
class ScanResult:
    """Result of scanning a file (or text). path may be None for in-memory scans."""

    path: Path | None
    findings: list[ScanFinding]

    @property
    def total_matches(self) -> int:
        return sum(f.count for f in self.findings)


# Pattern names are short codes; order is preserved for stable output ordering.
_PATTERNS: dict[str, re.Pattern[str]] = {
    "TFN": re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\b"),
    "MEDICARE": re.compile(r"\b[2-6]\d{3}\s?\d{5}\s?\d\b"),
    "ABN": re.compile(r"\b\d{2}\s?\d{3}\s?\d{3}\s?\d{3}\b"),
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "AU_PHONE": re.compile(r"(?:\+?61[ -]?|\b0)4\d{2}[ -]?\d{3}[ -]?\d{3}\b"),
    "DOB_LIKE_DATE": re.compile(
        r"\b(19[2-9]\d|200\d|201[0-5])[/-](0[1-9]|1[0-2])[/-](0[1-9]|[12]\d|3[01])\b"
    ),
}


def scan_text(text: str) -> list[ScanFinding]:
    """Return a ScanFinding per pattern that matched at least once."""
    findings: list[ScanFinding] = []
    for name, pattern in _PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings.append(ScanFinding(pattern=name, count=len(matches)))
    return findings


def scan_file(path: Path) -> ScanResult:
    """Read a text file and scan its content. For binary formats, use a parser
    upstream and pass the extracted text via scan_text().
    """
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return ScanResult(path=path, findings=scan_text(text))
