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
