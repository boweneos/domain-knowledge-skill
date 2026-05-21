import pytest

from dks.blockref import decode_blockref, encode_blockref
from dks.locators import DocxLocator, ExcelLocator, MarkdownLocator, PdfLocator


def test_encode_pdf_minimal():
    assert encode_blockref("policies/claims.pdf", PdfLocator(page=14)) == "policies/claims.pdf#p14"


def test_encode_pdf_with_section():
    ref = encode_blockref("policies/claims.pdf", PdfLocator(page=14, section="3.2"))
    assert ref == "policies/claims.pdf#p14#3.2"


def test_encode_docx():
    ref = encode_blockref("specs/intro.docx", DocxLocator(section="Introduction", paragraph_idx=3))
    assert ref == "specs/intro.docx#§Introduction#p3"


def test_encode_excel():
    ref = encode_blockref(
        "models/assumptions.xlsx", ExcelLocator(sheet="Mortality", cells="A1:D40")
    )
    assert ref == "models/assumptions.xlsx#sMortality!A1:D40"


def test_encode_markdown():
    ref = encode_blockref(
        "notes/handling.md",
        MarkdownLocator(heading_path=["A", "B"], line_start=5, line_end=7),
    )
    assert ref == "notes/handling.md#L5-7"


def test_roundtrip_pdf():
    original = PdfLocator(page=14, section="3.2")
    ref = encode_blockref("policies/claims.pdf", original)
    src, loc = decode_blockref(ref)
    assert src == "policies/claims.pdf"
    assert loc == original


def test_roundtrip_markdown():
    original = MarkdownLocator(heading_path=[], line_start=5, line_end=7)
    ref = encode_blockref("a.md", original)
    src, loc = decode_blockref(ref)
    assert src == "a.md"
    # heading_path isn't in the encoded ref, so it's empty after decode
    assert loc.line_start == 5
    assert loc.line_end == 7


def test_decode_rejects_malformed():
    with pytest.raises(ValueError, match="malformed"):
        decode_blockref("no-hash-here")


def test_decode_rejects_unknown_locator_prefix():
    with pytest.raises(ValueError, match="unknown locator"):
        decode_blockref("file.xyz#qWhatever")


def test_encode_pdf_with_section_and_clause():
    ref = encode_blockref("policies/claims.pdf", PdfLocator(page=14, section="3.2", clause="3.2.1"))
    assert ref == "policies/claims.pdf#p14#3.2#3.2.1"


def test_roundtrip_pdf_with_clause():
    original = PdfLocator(page=14, section="3.2", clause="3.2.1")
    ref = encode_blockref("policies/claims.pdf", original)
    src, loc = decode_blockref(ref)
    assert src == "policies/claims.pdf"
    assert loc == original
