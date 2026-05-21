import pytest

from dks.store.wiki import WikiEntry, list_wiki_entries, read_wiki_entry, write_wiki_entry


def _entry() -> WikiEntry:
    return WikiEntry(
        topic="PII handling rules",
        slug="pii-handling-rules",
        source_refs=["claims.pdf#p14#3.2"],
        body="When capturing customer details, fields A and B must be encrypted.",
    )


def test_write_read_roundtrip(tmp_path):
    target = write_wiki_entry(tmp_path, _entry())
    assert target.exists()
    loaded = read_wiki_entry(tmp_path, "pii-handling-rules")
    assert loaded.topic == "PII handling rules"
    assert loaded.source_refs == ["claims.pdf#p14#3.2"]
    assert "fields A and B" in loaded.body


def test_write_sets_compiled_at_if_missing(tmp_path):
    e = _entry()
    assert e.compiled_at is None
    write_wiki_entry(tmp_path, e)
    assert e.compiled_at is not None  # set as side effect


def test_list_returns_all_slugs(tmp_path):
    write_wiki_entry(tmp_path, _entry())
    other = _entry()
    other.slug = "data-retention"
    other.topic = "Data retention rules"
    write_wiki_entry(tmp_path, other)
    slugs = sorted(list_wiki_entries(tmp_path))
    assert slugs == ["data-retention", "pii-handling-rules"]


def test_read_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_wiki_entry(tmp_path, "absent")


def test_list_empty_dir(tmp_path):
    assert list_wiki_entries(tmp_path) == []
