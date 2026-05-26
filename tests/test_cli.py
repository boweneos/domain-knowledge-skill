import json

import pytest
from typer.testing import CliRunner

from dks.cli import app

runner = CliRunner()


def _invoke(args: list[str], stdin: str | None = None, env: dict | None = None):
    return runner.invoke(app, args, input=stdin, env=env)


def _presidio_installed() -> bool:
    try:
        import presidio_analyzer  # noqa: F401
        import presidio_anonymizer  # noqa: F401
        return True
    except ImportError:
        return False


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
    assert payload.get("shadows") == []


def test_blocks_get_warns_on_divergent_shadow(tmp_path):
    # Set up project and global with same block_id but different content
    project = tmp_path / "proj"
    global_base = tmp_path / "glob"
    project.mkdir()
    global_base.mkdir()
    # Quick way: use ingest with --write-global, then with default project
    src = tmp_path / "raw" / "notes.md"
    src.parent.mkdir()
    src.write_text("original content\n")
    _invoke(
        ["--project", str(project), "--global", str(global_base),
         "ingest", str(src), "--root", str(src.parent), "--write-global"],
    )
    # Overwrite source with different content and ingest into project
    src.write_text("project override content\n")
    _invoke(
        ["--project", str(project), "--global", str(global_base),
         "ingest", str(src), "--root", str(src.parent)],
    )
    res = _invoke(
        ["--project", str(project), "--global", str(global_base),
         "blocks", "get", "notes.md#L1-1"],
    )
    assert res.exit_code == 0, res.output
    # Expect a stderr-style WARN line embedded in res.output (CliRunner combines stdout+stderr)
    assert "WARN" in res.output
    assert "shadows" in res.output.lower()


def test_blocks_get_no_warning_when_no_divergence(tmp_path):
    # Same content in both layers → no WARN
    project = tmp_path / "proj"
    global_base = tmp_path / "glob"
    project.mkdir()
    global_base.mkdir()
    src = tmp_path / "raw" / "notes.md"
    src.parent.mkdir()
    src.write_text("identical content\n")
    common = ["--project", str(project), "--global", str(global_base)]
    _invoke(common + ["ingest", str(src), "--root", str(src.parent), "--write-global"])
    _invoke(common + ["ingest", str(src), "--root", str(src.parent)])
    res = _invoke(common + ["blocks", "get", "notes.md#L1-1"])
    assert res.exit_code == 0, res.output
    assert "WARN" not in res.output


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


# --- layers ---------------------------------------------------------------

def test_layers_list_project_explicit(tmp_path):
    project = tmp_path / "proj"
    global_base = tmp_path / "glob"
    project.mkdir()
    global_base.mkdir()
    res = _invoke(["--project", str(project), "--global", str(global_base), "layers", "list"])
    assert res.exit_code == 0, res.output
    rows = json.loads(res.output)
    by_name = {r["name"]: r for r in rows}
    assert by_name["project"]["source"] == "explicit"
    assert by_name["project"]["base"] == str(project.resolve())
    assert by_name["project"]["exists"] is True
    assert by_name["global"]["source"] == "explicit"


def test_layers_list_no_global_hides_global(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    res = _invoke(["--project", str(project), "--no-global", "layers", "list"])
    assert res.exit_code == 0, res.output
    rows = json.loads(res.output)
    assert [r["name"] for r in rows] == ["project"]


def test_layers_list_marks_missing_base(tmp_path):
    project = tmp_path / "proj"  # NOT created
    res = _invoke(["--project", str(project), "--no-global", "layers", "list"])
    assert res.exit_code == 0, res.output
    [row] = json.loads(res.output)
    assert row["exists"] is False


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


# --- classification ----------------------------------------------------

def test_ingest_with_classification_persists_field(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    source = tmp_path / "raw" / "audit.md"
    source.parent.mkdir()
    source.write_text("Sensitive line.\n")

    res = _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(source), "--root", str(source.parent),
         "--classification", "confidential"],
    )
    assert res.exit_code == 0, res.output

    # Read back the block and verify classification field
    get_res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "get", "audit.md#L1-1"],
    )
    assert get_res.exit_code == 0, get_res.output
    # The JSON object starts after any WARN line(s) on stderr+stdout. CliRunner combines them.
    json_start = get_res.output.find("{")
    payload = json.loads(get_res.output[json_start:])
    assert payload["block"]["classification"] == "confidential"


def test_ingest_with_classification_default_is_internal(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    source = tmp_path / "raw" / "policy.md"
    source.parent.mkdir()
    source.write_text("Regular policy.\n")

    res = _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(source), "--root", str(source.parent)],
    )
    assert res.exit_code == 0, res.output

    get_res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "get", "policy.md#L1-1"],
    )
    payload = json.loads(get_res.output[get_res.output.find("{"):])
    assert payload["block"]["classification"] == "internal"


def test_ingest_confidential_to_global_is_rejected(tmp_path):
    global_base = tmp_path / "glob"
    global_base.mkdir()
    source = tmp_path / "raw" / "audit.md"
    source.parent.mkdir()
    source.write_text("Sensitive.\n")

    res = _invoke(
        ["--global", str(global_base),
         "ingest", str(source), "--root", str(source.parent),
         "--classification", "confidential", "--write-global"],
    )
    assert res.exit_code == 2
    assert "confidential" in res.output.lower() or "global" in res.output.lower()


def test_ingest_restricted_to_global_is_rejected(tmp_path):
    global_base = tmp_path / "glob"
    global_base.mkdir()
    source = tmp_path / "raw" / "claim.md"
    source.parent.mkdir()
    source.write_text("PII content.\n")

    res = _invoke(
        ["--global", str(global_base),
         "ingest", str(source), "--root", str(source.parent),
         "--classification", "restricted", "--write-global"],
    )
    assert res.exit_code == 2


def test_ingest_internal_to_global_is_allowed(tmp_path):
    # Sanity: internal/public classifications can still go to global.
    global_base = tmp_path / "glob"
    global_base.mkdir()
    source = tmp_path / "raw" / "policy.md"
    source.parent.mkdir()
    source.write_text("Generic policy.\n")

    res = _invoke(
        ["--global", str(global_base),
         "ingest", str(source), "--root", str(source.parent),
         "--classification", "internal", "--write-global"],
    )
    assert res.exit_code == 0, res.output


def test_blocks_get_emits_warn_for_confidential(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    source = tmp_path / "raw" / "audit.md"
    source.parent.mkdir()
    source.write_text("Sensitive.\n")
    _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(source), "--root", str(source.parent),
         "--classification", "confidential"],
    )
    res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "get", "audit.md#L1-1"],
    )
    assert res.exit_code == 0, res.output
    assert "WARN" in res.output
    assert "confidential" in res.output.lower()


def test_blocks_get_no_warn_for_internal(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    source = tmp_path / "raw" / "policy.md"
    source.parent.mkdir()
    source.write_text("Regular.\n")
    _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(source), "--root", str(source.parent)],
    )
    res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "get", "policy.md#L1-1"],
    )
    assert res.exit_code == 0
    # No classification WARN (a divergence WARN could still appear if shadows exist —
    # this test has no shadows, so any WARN would be wrong.)
    assert "classification" not in res.output.lower() or "WARN" not in res.output


def test_wiki_write_with_classification_persists_field(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    payload = {
        "topic": "Sensitive topic",
        "source_refs": ["a.md#L1-1"],
        "body": "details",
    }
    res = _invoke(
        ["--project", str(project), "--no-global",
         "wiki", "write", "sensitive", "--classification", "confidential"],
        stdin=json.dumps(payload),
    )
    assert res.exit_code == 0, res.output
    read_res = _invoke(
        ["--project", str(project), "--no-global",
         "wiki", "read", "sensitive"],
    )
    parsed = json.loads(read_res.output)
    assert parsed["entry"]["classification"] == "confidential"


def test_wiki_write_confidential_to_global_is_rejected(tmp_path):
    global_base = tmp_path / "glob"
    global_base.mkdir()
    payload = {
        "topic": "Sensitive",
        "source_refs": ["a.md#L1-1"],
        "body": "details",
    }
    res = _invoke(
        ["--global", str(global_base),
         "wiki", "write", "sensitive",
         "--classification", "confidential", "--write-global"],
        stdin=json.dumps(payload),
    )
    assert res.exit_code == 2


def test_blocks_list_with_content_includes_full_block(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    source = tmp_path / "raw" / "notes.md"
    source.parent.mkdir()
    source.write_text("First line.\n\nSecond paragraph here.\n")
    _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(source), "--root", str(source.parent)],
    )
    res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "list", "notes.md", "--with-content"],
    )
    assert res.exit_code == 0, res.output
    rows = json.loads(res.output)
    assert len(rows) == 2
    for row in rows:
        assert "block_id" in row
        assert "layer" in row
        assert "block" in row
        # The block object should have all NormalizedBlock fields
        assert "content" in row["block"]
        assert "locator" in row["block"]
        assert "classification" in row["block"]
        assert "redacted" in row["block"]


def test_blocks_list_without_with_content_is_unchanged(tmp_path):
    # Existing schema must be preserved when --with-content not passed
    project = tmp_path / "proj"
    project.mkdir()
    source = tmp_path / "raw" / "notes.md"
    source.parent.mkdir()
    source.write_text("hi\n")
    _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(source), "--root", str(source.parent)],
    )
    res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "list", "notes.md"],
    )
    rows = json.loads(res.output)
    assert len(rows) == 1
    assert set(rows[0].keys()) == {"block_id", "layer"}  # exactly these two


def test_wiki_list_with_content_includes_full_entry(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    payload = {
        "topic": "Test topic",
        "source_refs": ["a.md#L1-1"],
        "body": "Body text here.",
    }
    _invoke(
        ["--project", str(project), "--no-global",
         "wiki", "write", "test-slug"],
        stdin=json.dumps(payload),
    )
    res = _invoke(
        ["--project", str(project), "--no-global",
         "wiki", "list", "--with-content"],
    )
    assert res.exit_code == 0, res.output
    rows = json.loads(res.output)
    assert len(rows) == 1
    row = rows[0]
    assert row["slug"] == "test-slug"
    assert row["layer"] == "project"
    assert "entry" in row
    assert row["entry"]["topic"] == "Test topic"
    assert row["entry"]["body"] == "Body text here."
    assert row["entry"]["classification"] == "internal"


def test_wiki_list_without_with_content_is_unchanged(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    payload = {
        "topic": "T", "source_refs": ["a.md#L1-1"], "body": "b",
    }
    _invoke(
        ["--project", str(project), "--no-global",
         "wiki", "write", "x"],
        stdin=json.dumps(payload),
    )
    res = _invoke(
        ["--project", str(project), "--no-global", "wiki", "list"],
    )
    rows = json.loads(res.output)
    assert len(rows) == 1
    assert set(rows[0].keys()) == {"slug", "layer"}


# --- scan ---

def test_scan_command_no_findings(tmp_path):
    src = tmp_path / "clean.md"
    src.write_text("Just a plain policy document with no PII.")
    res = _invoke(["--no-global", "--project", str(tmp_path), "scan", str(src)])
    assert res.exit_code == 0
    assert "no PII-like patterns detected" in res.output


def test_scan_command_reports_findings(tmp_path):
    src = tmp_path / "audit.md"
    src.write_text("Customer alice@example.com phoned on 0412 345 678 about claim.")
    res = _invoke(["--no-global", "--project", str(tmp_path), "scan", str(src)])
    assert res.exit_code == 0
    assert "EMAIL" in res.output
    assert "AU_PHONE" in res.output
    assert "Consider --classification" in res.output


def test_scan_command_missing_file_exits_nonzero(tmp_path):
    res = _invoke(["--no-global", "--project", str(tmp_path), "scan", str(tmp_path / "nope.md")])
    assert res.exit_code != 0


def test_ingest_auto_scan_warns_when_patterns_found(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    source = tmp_path / "raw" / "audit.md"
    source.parent.mkdir()
    source.write_text("Customer alice@example.com phoned about claim.")
    res = _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(source), "--root", str(source.parent)],
    )
    assert res.exit_code == 0, res.output
    assert "WARN" in res.output
    assert "EMAIL" in res.output


def test_ingest_no_warn_when_clean(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    source = tmp_path / "raw" / "clean.md"
    source.parent.mkdir()
    source.write_text("Plain policy text. No identifiers.")
    res = _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(source), "--root", str(source.parent)],
    )
    assert res.exit_code == 0, res.output
    # No PII WARN. (Classification WARN only fires for confidential/restricted.)
    # Allow other unrelated WARN lines but specifically no "PII-like patterns".
    assert "PII-like patterns" not in res.output


# --- redact-pii ---

def test_ingest_redact_pii_without_presidio_errors(tmp_path, monkeypatch):
    # Force ImportError by stubbing out presidio modules so dks.redact raises ImportError
    import sys
    monkeypatch.setitem(sys.modules, "presidio_analyzer", None)
    monkeypatch.setitem(sys.modules, "presidio_anonymizer", None)
    # Also remove dks.redact from sys.modules so its lazy import is re-triggered
    monkeypatch.delitem(sys.modules, "dks.redact", raising=False)
    project = tmp_path / "proj"
    project.mkdir()
    src = tmp_path / "raw" / "x.md"
    src.parent.mkdir()
    src.write_text("Hello.")
    res = _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(src), "--root", str(src.parent), "--redact-pii"],
    )
    assert res.exit_code != 0
    assert "redact" in res.output.lower() or "presidio" in res.output.lower()


@pytest.mark.skipif(
    not _presidio_installed(),
    reason="presidio not installed; --redact-entities flag skipped",
)
def test_ingest_redact_entities_all_includes_date_time(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    src = tmp_path / "raw" / "doc.md"
    src.parent.mkdir()
    src.write_text("Customer with DOB 1985-03-14")
    res = _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(src), "--root", str(src.parent),
         "--redact-pii", "--redact-entities", "all"],
    )
    assert res.exit_code == 0, res.output
    get_res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "get", "doc.md#L1-1"],
    )
    payload = json.loads(get_res.output[get_res.output.find("{"):])
    # With --redact-entities all, the DATE_TIME-shaped string IS redacted
    assert "1985-03-14" not in payload["block"]["content"]
    assert "[REDACTED:" in payload["block"]["content"]


@pytest.mark.skipif(
    not _presidio_installed(),
    reason="presidio not installed; --redact-entities flag skipped",
)
def test_ingest_redact_default_leaves_dates_alone(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    src = tmp_path / "raw" / "policy.md"
    src.parent.mkdir()
    src.write_text("Waiting period is 12 months and DOB is 1985-03-14.")
    res = _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(src), "--root", str(src.parent),
         "--redact-pii"],
    )
    assert res.exit_code == 0, res.output
    get_res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "get", "policy.md#L1-1"],
    )
    payload = json.loads(get_res.output[get_res.output.find("{"):])
    content = payload["block"]["content"]
    # With default tuned list, "12 months" stays (no DATE_TIME redaction)
    assert "12 months" in content
    # 1985-03-14 also stays (DATE_TIME not in default)
    assert "1985-03-14" in content


@pytest.mark.skipif(
    not _presidio_installed(),
    reason="presidio not installed; --redact-pii path skipped",
)
def test_ingest_with_redact_pii_writes_redacted_blocks(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    src = tmp_path / "raw" / "audit.md"
    src.parent.mkdir()
    src.write_text("Customer John Smith emailed alice@example.com about claim.")

    res = _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(src), "--root", str(src.parent), "--redact-pii"],
    )
    assert res.exit_code == 0, res.output

    get_res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "get", "audit.md#L1-1"],
    )
    payload = json.loads(get_res.output[get_res.output.find("{"):])
    assert payload["block"]["redacted"] is True
    content = payload["block"]["content"]
    assert "John Smith" not in content
    assert "alice@example.com" not in content
    assert "[REDACTED:" in content
