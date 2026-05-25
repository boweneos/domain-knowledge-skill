import json

from typer.testing import CliRunner

from dks.cli import app

runner = CliRunner()


def _invoke(args: list[str], stdin: str | None = None, env: dict | None = None):
    return runner.invoke(app, args, input=stdin, env=env)


# --- ingest ---------------------------------------------------------------

def test_ingest_writes_to_project_layer(tmp_path):
    project = tmp_path / "proj-dks"
    project.mkdir()
    source = tmp_path / "raw" / "notes.md"
    source.parent.mkdir()
    source.write_text("# Heading\n\nA paragraph.\n")

    res = _invoke(
        [
            "--project", str(project),
            "--no-global",
            "ingest", str(source),
            "--root", str(source.parent),
        ],
    )
    assert res.exit_code == 0, res.output
    assert "wrote 2 blocks" in res.output
    # files land under <project>/normalized/notes.md/
    files = list((project / "normalized" / "notes.md").glob("*.md"))
    assert len(files) == 2


def test_ingest_writes_to_global_when_write_global(tmp_path):
    global_base = tmp_path / "glob"
    global_base.mkdir()
    source = tmp_path / "raw" / "x.md"
    source.parent.mkdir()
    source.write_text("# H\n\np.\n")

    res = _invoke(
        [
            "--global", str(global_base),
            "ingest", str(source),
            "--root", str(source.parent),
            "--write-global",
        ],
    )
    assert res.exit_code == 0, res.output
    files = list((global_base / "normalized" / "x.md").glob("*.md"))
    assert len(files) == 2


def test_ingest_missing_file_exits_nonzero(tmp_path):
    res = _invoke(["--project", str(tmp_path), "--no-global", "ingest", str(tmp_path / "nope.md")])
    assert res.exit_code != 0


def test_ingest_unsupported_extension_exits_nonzero(tmp_path):
    src = tmp_path / "x.bin"
    src.write_bytes(b"\x00\x01")
    res = _invoke(["--project", str(tmp_path), "--no-global", "ingest", str(src)])
    assert res.exit_code != 0
    assert "no parser" in res.output.lower()


# --- blocks ---------------------------------------------------------------

def test_blocks_list_after_ingest(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    source = tmp_path / "raw" / "notes.md"
    source.parent.mkdir()
    source.write_text("First.\n\nSecond paragraph.\n")
    _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(source), "--root", str(source.parent)],
    )
    res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "list", "notes.md"],
    )
    assert res.exit_code == 0, res.output
    hits = json.loads(res.output)
    assert len(hits) == 2
    assert all(h["layer"] == "project" for h in hits)


def test_blocks_get_includes_layer(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    source = tmp_path / "raw" / "notes.md"
    source.parent.mkdir()
    source.write_text("First line.\n")
    _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(source), "--root", str(source.parent)],
    )
    res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "get", "notes.md#L1-1"],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["block"]["content"].startswith("First line")
    assert payload["layer"] == "project"


def test_blocks_get_missing_returns_nonzero(tmp_path):
    res = _invoke(
        ["--project", str(tmp_path), "--no-global", "blocks", "get", "absent.md#L1-1"],
    )
    assert res.exit_code != 0


# --- pageindex ------------------------------------------------------------

def test_pageindex_write_and_read_via_cli(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    tree = {"title": "Top", "block_ids": [], "children": []}
    w = _invoke(
        ["--project", str(project), "--no-global",
         "pageindex", "write", "x.pdf"],
        stdin=json.dumps(tree),
    )
    assert w.exit_code == 0, w.output
    r = _invoke(
        ["--project", str(project), "--no-global",
         "pageindex", "read", "x.pdf"],
    )
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["tree"] == tree
    assert payload["layer"] == "project"


def test_pageindex_read_missing_returns_nonzero(tmp_path):
    res = _invoke(
        ["--project", str(tmp_path), "--no-global", "pageindex", "read", "absent.pdf"],
    )
    assert res.exit_code != 0


# --- wiki -----------------------------------------------------------------

def _wiki_payload(topic: str, body: str, refs=None):
    return {
        "topic": topic,
        "source_refs": refs or ["a.md#L1-1"],
        "body": body,
    }


def test_wiki_write_read_list_via_cli(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    w = _invoke(
        ["--project", str(project), "--no-global",
         "wiki", "write", "pii-handling"],
        stdin=json.dumps(_wiki_payload("PII handling", "Encrypt PII at rest.")),
    )
    assert w.exit_code == 0, w.output

    lst = _invoke(["--project", str(project), "--no-global", "wiki", "list"])
    assert lst.exit_code == 0
    rows = json.loads(lst.output)
    assert any(r["slug"] == "pii-handling" and r["layer"] == "project" for r in rows)

    r = _invoke(["--project", str(project), "--no-global", "wiki", "read", "pii-handling"])
    assert r.exit_code == 0
    parsed = json.loads(r.output)
    assert parsed["entry"]["topic"] == "PII handling"
    assert parsed["layer"] == "project"


def test_wiki_read_missing_returns_nonzero(tmp_path):
    res = _invoke(["--project", str(tmp_path), "--no-global", "wiki", "read", "absent"])
    assert res.exit_code != 0


def test_wiki_search_returns_layer(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    _invoke(
        ["--project", str(project), "--no-global",
         "wiki", "write", "pii"],
        stdin=json.dumps(_wiki_payload("PII", "Encrypt PII at rest.")),
    )
    res = _invoke(
        ["--project", str(project), "--no-global",
         "wiki", "search", "PII"],
    )
    assert res.exit_code == 0, res.output
    hits = json.loads(res.output)
    assert len(hits) == 1
    assert hits[0]["slug"] == "pii"
    assert hits[0]["layer"] == "project"


def test_wiki_project_shadows_global_via_cli(tmp_path):
    project = tmp_path / "proj"
    global_base = tmp_path / "glob"
    project.mkdir()
    global_base.mkdir()
    common = ["--project", str(project), "--global", str(global_base)]
    _invoke(
        common + ["wiki", "write", "retention", "--write-global"],
        stdin=json.dumps(_wiki_payload("Retention", "retain seven years")),
    )
    _invoke(
        common + ["wiki", "write", "retention"],
        stdin=json.dumps(_wiki_payload("Retention", "retain ten years")),
    )
    r = _invoke(common + ["wiki", "read", "retention"])
    assert r.exit_code == 0
    parsed = json.loads(r.output)
    assert parsed["layer"] == "project"
    assert "ten years" in parsed["entry"]["body"]
