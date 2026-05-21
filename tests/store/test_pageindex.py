import pytest

from dks.store.pageindex import read_pageindex, write_pageindex


def test_write_and_read_roundtrip(tmp_path):
    tree = {
        "title": "Claims Handling",
        "block_ids": [],
        "children": [
            {
                "title": "Filing Window",
                "block_ids": ["claims.pdf#p1#1.1"],
                "children": [],
            }
        ],
    }
    target = write_pageindex(tmp_path, source_file="claims.pdf", tree=tree)
    assert target.exists()
    loaded = read_pageindex(tmp_path, source_file="claims.pdf")
    assert loaded == tree


def test_read_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_pageindex(tmp_path, source_file="absent.pdf")


def test_write_creates_index_dir_if_missing(tmp_path):
    nested = tmp_path / "index"
    assert not nested.exists()
    write_pageindex(
        nested, source_file="a.pdf", tree={"title": "x", "block_ids": [], "children": []}
    )
    assert nested.exists()
