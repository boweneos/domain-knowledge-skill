"""Unit tests for the MSG parser.

Uses mocks because extract-msg cannot construct MSG files (read-only) and the
real corpus .msg files contain PII that shouldn't ship as fixtures.
"""

from unittest.mock import patch

from dks.locators import DocxLocator
from dks.parsers.msg import parse_msg_file


class _FakeMsg:
    """Minimal stand-in for extract_msg's Message object."""

    def __init__(
        self,
        subject="Test Subject",
        sender="alice@example.com",
        to="bob@example.com",
        cc=None,
        date="Mon, 1 Jan 2026 09:00:00 +1100",
        body="First paragraph.\n\nSecond paragraph.\n\nThird paragraph.",
    ):
        self.subject = subject
        self.sender = sender
        self.to = to
        self.cc = cc
        self.date = date
        self.body = body

    def close(self):
        pass


def test_parse_msg_yields_heading_and_body_items():
    with patch("dks.parsers.msg.extract_msg.openMsg", return_value=_FakeMsg()):
        items = parse_msg_file("/fake/path.msg")
    headings = [i for i in items if i.block_type == "heading"]
    bodies = [i for i in items if i.block_type == "text"]
    assert len(headings) == 1
    assert headings[0].content == "Test Subject"
    assert len(bodies) == 4  # headers block + 3 body paragraphs


def test_parse_msg_locator_uses_subject_as_section():
    with patch("dks.parsers.msg.extract_msg.openMsg", return_value=_FakeMsg()):
        items = parse_msg_file("/fake/path.msg")
    for item in items:
        assert isinstance(item.locator, DocxLocator)
        assert item.locator.section == "Test Subject"
    # Paragraph indices are sequential and unique
    indices = [item.locator.paragraph_idx for item in items]
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices)


def test_parse_msg_includes_headers_block():
    fake = _FakeMsg(sender="from@x.com", to="to@y.com", cc="cc@z.com")
    with patch("dks.parsers.msg.extract_msg.openMsg", return_value=fake):
        items = parse_msg_file("/fake/path.msg")
    headers_item = items[1]
    assert "From: from@x.com" in headers_item.content
    assert "To: to@y.com" in headers_item.content
    assert "Cc: cc@z.com" in headers_item.content


def test_parse_msg_skips_headers_block_when_all_empty():
    fake = _FakeMsg(sender=None, to=None, cc=None, date=None)
    with patch("dks.parsers.msg.extract_msg.openMsg", return_value=fake):
        items = parse_msg_file("/fake/path.msg")
    # heading + 3 body paragraphs, no headers item
    assert len(items) == 4
    assert all(item.block_type == "heading" or "From:" not in item.content for item in items)


def test_parse_msg_defaults_subject_when_missing():
    fake = _FakeMsg(subject=None)
    with patch("dks.parsers.msg.extract_msg.openMsg", return_value=fake):
        items = parse_msg_file("/fake/path.msg")
    assert items[0].content == "(no subject)"


def test_parse_msg_empty_body_returns_just_heading_and_headers():
    fake = _FakeMsg(body="")
    with patch("dks.parsers.msg.extract_msg.openMsg", return_value=fake):
        items = parse_msg_file("/fake/path.msg")
    # heading + headers — no body paragraphs
    assert len(items) == 2
    assert items[0].block_type == "heading"
    assert items[1].block_type == "text"
    assert "From:" in items[1].content
