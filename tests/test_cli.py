import json

from typer.testing import CliRunner

from dks.cli import app

runner = CliRunner()


def test_ingest_markdown_creates_normalized_files(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("# Heading\n\nA paragraph.\n")
    output = tmp_path / "out"

    result = runner.invoke(app, ["ingest", str(source), "--output-dir", str(output)])
    assert result.exit_code == 0, result.output
    assert "wrote 2 blocks" in result.output

    files = list((output / "notes.md").glob("*.md"))
    assert len(files) == 2


def test_ingest_missing_file_exits_nonzero(tmp_path):
    result = runner.invoke(app, ["ingest", str(tmp_path / "nope.md")])
    assert result.exit_code != 0


def test_ingest_unsupported_extension_exits_nonzero(tmp_path):
    source = tmp_path / "x.bin"
    source.write_bytes(b"\x00\x01")
    result = runner.invoke(app, ["ingest", str(source)])
    assert result.exit_code != 0
    assert "no parser" in result.output.lower()


def test_ingest_uses_path_relative_to_root(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    nested = root / "policies"
    nested.mkdir()
    source = nested / "claims.md"
    source.write_text("A claim rule.\n")
    output = tmp_path / "out"

    result = runner.invoke(
        app,
        ["ingest", str(source), "--output-dir", str(output), "--root", str(root)],
    )
    assert result.exit_code == 0, result.output
    # Output directory is named after the basename (writer.py's current behavior)
    files = list((output / "claims.md").glob("*.md"))
    assert len(files) == 1
    from dks.block import parse_markdown
    parsed = parse_markdown(files[0].read_text())
    assert parsed.source_file == "policies/claims.md"


def test_blocks_list_after_ingest(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("First line.\n\nSecond paragraph.\n")
    output = tmp_path / "out"
    runner.invoke(app, ["ingest", str(source), "--output-dir", str(output)])

    result = runner.invoke(app, ["blocks", "list", "notes.md", "--normalized-dir", str(output)])
    assert result.exit_code == 0, result.output
    ids = result.output.strip().splitlines()
    assert len(ids) == 2


def test_blocks_get_after_ingest(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("First line.\n")
    output = tmp_path / "out"
    runner.invoke(app, ["ingest", str(source), "--output-dir", str(output)])

    result = runner.invoke(app, ["blocks", "get", "notes.md#L1-1", "--normalized-dir", str(output)])
    assert result.exit_code == 0, result.output
    assert "First line." in result.output


def test_blocks_get_missing_returns_nonzero(tmp_path):
    result = runner.invoke(
        app, ["blocks", "get", "absent.md#L1-1", "--normalized-dir", str(tmp_path)]
    )
    assert result.exit_code != 0


def test_pageindex_write_and_read_via_cli(tmp_path):
    tree = {"title": "Top", "block_ids": [], "children": []}
    write_result = runner.invoke(
        app,
        ["pageindex", "write", "x.pdf", "--index-dir", str(tmp_path)],
        input=json.dumps(tree),
    )
    assert write_result.exit_code == 0, write_result.output

    read_result = runner.invoke(
        app, ["pageindex", "read", "x.pdf", "--index-dir", str(tmp_path)]
    )
    assert read_result.exit_code == 0, read_result.output
    assert json.loads(read_result.output) == tree


def test_pageindex_read_missing_returns_nonzero(tmp_path):
    result = runner.invoke(
        app, ["pageindex", "read", "absent.pdf", "--index-dir", str(tmp_path)]
    )
    assert result.exit_code != 0


def test_wiki_write_read_and_list_via_cli(tmp_path):
    payload = {
        "topic": "PII handling rules",
        "source_refs": ["claims.pdf#p14#3.2"],
        "body": "Fields A and B must be encrypted. [ref: claims.pdf#p14#3.2]",
    }
    write_result = runner.invoke(
        app,
        ["wiki", "write", "pii-handling-rules", "--wiki-dir", str(tmp_path)],
        input=json.dumps(payload),
    )
    assert write_result.exit_code == 0, write_result.output

    list_result = runner.invoke(app, ["wiki", "list", "--wiki-dir", str(tmp_path)])
    assert list_result.exit_code == 0
    assert "pii-handling-rules" in list_result.output

    read_result = runner.invoke(
        app, ["wiki", "read", "pii-handling-rules", "--wiki-dir", str(tmp_path)]
    )
    assert read_result.exit_code == 0
    parsed = json.loads(read_result.output)
    assert parsed["topic"] == "PII handling rules"
    assert parsed["source_refs"] == ["claims.pdf#p14#3.2"]


def test_wiki_read_missing_returns_nonzero(tmp_path):
    result = runner.invoke(
        app, ["wiki", "read", "absent", "--wiki-dir", str(tmp_path)]
    )
    assert result.exit_code != 0
