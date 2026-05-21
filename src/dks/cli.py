"""Typer CLI: `dks ingest <path>`."""

from pathlib import Path

import typer

from dks.normalizer import normalize
from dks.parsers import get_parser
from dks.writer import write_blocks

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """dks — domain knowledge skill CLI."""


@app.command()
def ingest(
    path: Path = typer.Argument(..., help="Source file to ingest."),  # noqa: B008
    output_dir: Path = typer.Option(  # noqa: B008
        Path("normalized"), "--output-dir", "-o", help="Where to write normalized blocks."
    ),
    root: Path = typer.Option(  # noqa: B008
        Path("raw"),
        "--root",
        "-r",
        help="Root directory the source path is relative to; defaults to ./raw",
    ),
) -> None:
    """Parse, normalize, and persist a source document."""
    if not path.exists() or not path.is_file():
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(code=2)

    try:
        source_file = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        # path is not under root; fall back to basename
        source_file = path.name

    try:
        parser = get_parser(path)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e

    items = parser(path)
    blocks = normalize(source_file=source_file, items=items)
    written = write_blocks(blocks, output_dir=output_dir)
    typer.echo(f"wrote {len(written)} blocks to {output_dir}/{source_file}/")


if __name__ == "__main__":
    app()
