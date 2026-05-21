from pathlib import Path

from dks.search import SearchHit, search_wiki
from dks.store.wiki import WikiEntry, write_wiki_entry


def _seed_wiki(tmp_path: Path) -> Path:
    write_wiki_entry(
        tmp_path,
        WikiEntry(
            topic="PII handling rules",
            slug="pii-handling",
            source_refs=["claims.pdf#p14#3.2"],
            body="Customer personally identifiable information must be encrypted at rest.",
        ),
    )
    write_wiki_entry(
        tmp_path,
        WikiEntry(
            topic="Claims retention",
            slug="claims-retention",
            source_refs=["claims.pdf#p20#5.1"],
            body="Claims records must be retained for seven years from the date of closure.",
        ),
    )
    return tmp_path


def test_search_matches_topic(tmp_path):
    _seed_wiki(tmp_path)
    hits = search_wiki(wiki_dir=tmp_path, query="PII")
    assert len(hits) == 1
    assert hits[0].slug == "pii-handling"


def test_search_matches_body_terms(tmp_path):
    _seed_wiki(tmp_path)
    hits = search_wiki(wiki_dir=tmp_path, query="seven years")
    assert len(hits) == 1
    assert hits[0].slug == "claims-retention"


def test_search_is_case_insensitive(tmp_path):
    _seed_wiki(tmp_path)
    hits = search_wiki(wiki_dir=tmp_path, query="ENCRYPTED")
    assert len(hits) == 1
    assert hits[0].slug == "pii-handling"


def test_search_no_match_returns_empty(tmp_path):
    _seed_wiki(tmp_path)
    assert search_wiki(wiki_dir=tmp_path, query="quantum mechanics") == []


def test_search_returns_source_refs(tmp_path):
    _seed_wiki(tmp_path)
    [hit] = search_wiki(wiki_dir=tmp_path, query="PII")
    assert isinstance(hit, SearchHit)
    assert hit.source_refs == ["claims.pdf#p14#3.2"]
    assert hit.topic == "PII handling rules"
