from pathlib import Path

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
