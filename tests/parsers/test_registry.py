from pathlib import Path

import pytest

from dks.parsers import get_parser


def test_get_parser_for_markdown():
    parser = get_parser(Path("notes.md"))
    assert callable(parser)


def test_get_parser_for_uppercase_extension():
    parser = get_parser(Path("notes.MD"))
    assert callable(parser)


def test_get_parser_raises_on_unknown_extension():
    with pytest.raises(ValueError, match="no parser"):
        get_parser(Path("mystery.bin"))
