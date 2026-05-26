from dataclasses import FrozenInstanceError

import pytest

from dks.scan import ScanFinding, scan_file, scan_text


def test_scan_text_empty_returns_no_findings():
    assert scan_text("") == []
    assert scan_text("just plain prose with no identifiers") == []


def test_scan_text_detects_tfn():
    findings = {f.pattern: f.count for f in scan_text("My TFN is 123 456 789 you should know")}
    assert findings.get("TFN") == 1


def test_scan_text_detects_email():
    findings = {f.pattern: f.count for f in scan_text("contact alice@example.com or bob@test.org")}
    assert findings.get("EMAIL") == 2


def test_scan_text_detects_au_phone():
    findings = {f.pattern: f.count for f in scan_text("Call 0412 345 678 or +61 412 345 678")}
    assert findings.get("AU_PHONE") == 2


def test_scan_text_detects_dob_like_date():
    findings = {f.pattern: f.count for f in scan_text("DOB: 1985-03-14 also 2010/05/22")}
    assert findings.get("DOB_LIKE_DATE") == 2


def test_scan_text_detects_medicare():
    findings = {f.pattern: f.count for f in scan_text("Medicare 2234 56789 0")}
    assert findings.get("MEDICARE") == 1


def test_scan_text_detects_abn():
    findings = {f.pattern: f.count for f in scan_text("ABN 12 345 678 901 trading as")}
    assert findings.get("ABN") == 1


def test_scan_text_multiple_pattern_kinds():
    text = "Email john@test.com, phone 0412345678, DOB 1985-03-14"
    findings = {f.pattern: f.count for f in scan_text(text)}
    assert findings.get("EMAIL") == 1
    assert findings.get("AU_PHONE") == 1
    assert findings.get("DOB_LIKE_DATE") == 1


def test_scan_text_does_not_match_non_pii():
    # Random numbers, prose, dates outside DOB range
    text = "Section 3.2.1 references item 12345 from page 99. Last update 2024-03-14."
    findings = {f.pattern: f.count for f in scan_text(text)}
    # 2024 is outside the DOB window (1920-2015); 12345 is too short for TFN
    assert findings == {}


def test_scan_file_reads_and_scans(tmp_path):
    p = tmp_path / "src.md"
    p.write_text("Contact alice@example.com today.")
    result = scan_file(p)
    assert result.path == p
    assert any(f.pattern == "EMAIL" for f in result.findings)


def test_scan_finding_is_frozen():
    f = ScanFinding(pattern="EMAIL", count=3)
    with pytest.raises(FrozenInstanceError):
        f.count = 5  # type: ignore[misc]
