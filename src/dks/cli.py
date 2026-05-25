"""Typer CLI: `dks ingest`, `dks blocks`, `dks pageindex`, `dks wiki`.

All commands operate against the two-layer KB (project + global). Layer flags
are global (declared on the top-level callback); per-command flags concern
behaviour specific to that command.
"""

import json
import sys
from pathlib import Path
from typing import Any

import typer

from dks.layers import KbLayer, KbLayers, resolve_layers
from dks.normalizer import normalize
from dks.parsers import get_parser
from dks.search import search_wiki
from dks.store.blocks import get_block, list_blocks
from dks.store.pageindex import read_pageindex, write_pageindex
from dks.store.wiki import WikiEntry, list_wiki_entries, read_wiki_entry, write_wiki_entry
from dks.writer import write_blocks

app = typer.Typer(no_args_is_help=True)


@app.callback()
def root(
    ctx: typer.Context,
    project: Path | None = typer.Option(  # noqa: B008
        None,
        "--project",
        "-p",
        help="Explicit project layer base directory. Overrides auto-discovery.",
    ),
    global_base: Path | None = typer.Option(  # noqa: B008
        None,
        "--global",
        help="Explicit global layer base directory. Overrides DKS_GLOBAL env / ~/.dks default.",
    ),
    no_global: bool = typer.Option(
        False,
        "--no-global",
        help="Suppress the global layer entirely (project-only mode).",
    ),
) -> None:
    layers = resolve_layers(
        project=project,
        global_base=global_base,
        include_global=not no_global,
    )
    ctx.obj = layers


def _layers(ctx: typer.Context) -> KbLayers:
    return ctx.obj  # type: ignore[no-any-return]


def _resolve_write_layer(layers: KbLayers, write_global: bool) -> KbLayer:
    if write_global:
        if layers.global_layer is None:
            typer.echo("error: --write-global requested but global layer is suppressed", err=True)
            raise typer.Exit(code=2)
        return layers.global_layer
    return layers.for_write()


# --- ingest ---------------------------------------------------------------

@app.command()
def ingest(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Source file to ingest."),  # noqa: B008
    root_dir: Path = typer.Option(  # noqa: B008
        Path("raw"),
        "--root",
        "-r",
        help="Directory the source path is relative to (for computing source_file).",
    ),
    write_global: bool = typer.Option(
        False,
        "--write-global",
        help="Force the write target to the global layer.",
    ),
) -> None:
    """Parse, normalize, and persist a source document into the active write layer."""
    if not path.exists() or not path.is_file():
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(code=2)

    layers = _layers(ctx)
    write_layer = _resolve_write_layer(layers, write_global)

    try:
        source_file = str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        source_file = path.name

    try:
        parser = get_parser(path)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e

    items = parser(path)
    blocks = normalize(source_file=source_file, items=items)
    written = write_blocks(blocks, write_layer)
    typer.echo(f"wrote {len(written)} blocks to {write_layer.normalized_dir}/{source_file}/")


# --- blocks ---------------------------------------------------------------

blocks_app = typer.Typer(no_args_is_help=True, help="Inspect normalized blocks.")
app.add_typer(blocks_app, name="blocks")


@blocks_app.command("list")
def blocks_list(ctx: typer.Context, source_file: str = typer.Argument(...)) -> None:  # noqa: B008
    """List BlockHits ({block_id, layer}) for a source file across active layers (JSON)."""
    layers = _layers(ctx)
    hits = list_blocks(layers, source_file=source_file)
    out = [{"block_id": h.block_id, "layer": h.layer} for h in hits]
    typer.echo(json.dumps(out, indent=2))


@blocks_app.command("get")
def blocks_get(ctx: typer.Context, block_id: str = typer.Argument(...)) -> None:  # noqa: B008
    """Fetch a NormalizedBlock + the layer that served it (JSON)."""
    layers = _layers(ctx)
    try:
        block, layer_name = get_block(layers, block_id=block_id)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e
    payload = {"block": block.model_dump(), "layer": layer_name}
    typer.echo(json.dumps(payload, indent=2, default=str))


# --- pageindex ------------------------------------------------------------

pageindex_app = typer.Typer(no_args_is_help=True, help="Manage PageIndex trees.")
app.add_typer(pageindex_app, name="pageindex")


@pageindex_app.command("write")
def pageindex_write(
    ctx: typer.Context,
    source_file: str = typer.Argument(...),  # noqa: B008
    write_global: bool = typer.Option(
        False,
        "--write-global",
        help="Force write to the global layer.",
    ),
) -> None:
    """Read a JSON tree from stdin and persist it to the active write layer."""
    layers = _layers(ctx)
    write_layer = _resolve_write_layer(layers, write_global)
    tree: dict[str, Any] = json.loads(sys.stdin.read())
    target = write_pageindex(write_layer, source_file=source_file, tree=tree)
    typer.echo(f"wrote {target}")


@pageindex_app.command("read")
def pageindex_read(ctx: typer.Context, source_file: str = typer.Argument(...)) -> None:  # noqa: B008
    """Print PageIndex tree + the layer that served it (JSON)."""
    layers = _layers(ctx)
    try:
        tree, layer_name = read_pageindex(layers, source_file=source_file)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e
    typer.echo(json.dumps({"tree": tree, "layer": layer_name}, indent=2))


# --- wiki -----------------------------------------------------------------

wiki_app = typer.Typer(no_args_is_help=True, help="Manage compiled wiki entries.")
app.add_typer(wiki_app, name="wiki")


@wiki_app.command("write")
def wiki_write(
    ctx: typer.Context,
    slug: str = typer.Argument(...),  # noqa: B008
    write_global: bool = typer.Option(
        False,
        "--write-global",
        help="Force write to the global layer.",
    ),
) -> None:
    """Read JSON {topic, source_refs, body} from stdin and persist."""
    layers = _layers(ctx)
    write_layer = _resolve_write_layer(layers, write_global)
    data = json.loads(sys.stdin.read())
    data["slug"] = slug
    entry = WikiEntry.model_validate(data)
    target = write_wiki_entry(write_layer, entry)
    typer.echo(f"wrote {target}")


@wiki_app.command("read")
def wiki_read(ctx: typer.Context, slug: str = typer.Argument(...)) -> None:  # noqa: B008
    """Print a wiki entry + the layer that served it (JSON)."""
    layers = _layers(ctx)
    try:
        entry, layer_name = read_wiki_entry(layers, slug)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e
    typer.echo(json.dumps({"entry": entry.model_dump(), "layer": layer_name}, indent=2))


@wiki_app.command("list")
def wiki_list(ctx: typer.Context) -> None:
    """List wiki slugs across layers (JSON, deduped — project shadows global)."""
    layers = _layers(ctx)
    hits = list_wiki_entries(layers)
    out = [{"slug": h.slug, "layer": h.layer} for h in hits]
    typer.echo(json.dumps(out, indent=2))


@wiki_app.command("search")
def wiki_search(ctx: typer.Context, query: str = typer.Argument(...)) -> None:  # noqa: B008
    """Search wiki entries by keyword across layers (JSON)."""
    layers = _layers(ctx)
    hits = search_wiki(layers, query=query)
    typer.echo(json.dumps([h.model_dump() for h in hits], indent=2))


if __name__ == "__main__":
    app()
