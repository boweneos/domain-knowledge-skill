"""KB layer resolution — global + project, project shadows global on reads."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KbLayer:
    """A single KB layer rooted at a directory with the standard subdirs."""

    name: str
    base: Path

    @property
    def normalized_dir(self) -> Path:
        return self.base / "normalized"

    @property
    def index_dir(self) -> Path:
        return self.base / "index"

    @property
    def wiki_dir(self) -> Path:
        return self.base / "wiki"

    @property
    def raw_dir(self) -> Path:
        return self.base / "raw"


@dataclass(frozen=True)
class KbLayers:
    """Resolved active layers. Project first (highest precedence), then global."""

    project: KbLayer | None
    global_layer: KbLayer | None

    def for_read(self) -> tuple[KbLayer, ...]:
        """Read order: project first, then global. Empty layers omitted."""
        return tuple(layer for layer in (self.project, self.global_layer) if layer is not None)

    def for_write(self) -> KbLayer:
        """Write target: project if present, else global."""
        if self.project is not None:
            return self.project
        if self.global_layer is not None:
            return self.global_layer
        raise RuntimeError("no writable layer (both project and global are None)")

    def by_name(self, name: str) -> KbLayer | None:
        for layer in self.for_read():
            if layer.name == name:
                return layer
        return None


def _auto_discover_project(cwd: Path, skip: Path | None = None) -> Path | None:
    """Walk up from cwd looking for a .dks/ directory. Return its path or None.

    `skip` is an optional resolved path that the walker treats as if it didn't
    exist — used to prevent the global layer's default location (e.g. ~/.dks)
    from being mistakenly auto-discovered as a project layer when walking up
    through $HOME.
    """
    current = cwd.resolve()
    skip_resolved = skip.resolve() if skip is not None else None
    while True:
        candidate = current / ".dks"
        if candidate.is_dir() and candidate.resolve() != skip_resolved:
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def resolve_layers(
    project: Path | None = None,
    global_base: Path | None = None,
    include_global: bool = True,
    cwd: Path | None = None,
) -> KbLayers:
    """Resolve which layers are active.

    Precedence for the project layer:
      1. Explicit `project` argument.
      2. `DKS_PROJECT` env var.
      3. Auto-discovery from `cwd` (default: real CWD), excluding the global
         layer's resolved location so the global path is never silently
         re-used as the project layer.
      4. None.

    Precedence for the global layer (suppressed if include_global=False):
      1. Explicit `global_base` argument.
      2. `DKS_GLOBAL` env var.
      3. ~/.dks.
    """
    if cwd is None:
        cwd = Path.cwd()

    # Resolve the global base FIRST so it can be passed as `skip` to auto-discovery,
    # avoiding the case where the walker climbs to the user's home dir and matches
    # the global layer's own location as a project layer.
    resolved_global_base: Path | None
    if include_global:
        if global_base is None:
            env_global = os.environ.get("DKS_GLOBAL")
            resolved_global_base = Path(env_global) if env_global else Path.home() / ".dks"
        else:
            resolved_global_base = global_base
    else:
        resolved_global_base = None

    if project is None:
        env_project = os.environ.get("DKS_PROJECT")
        if env_project:
            project = Path(env_project)
        else:
            project = _auto_discover_project(cwd, skip=resolved_global_base)

    project_layer = KbLayer(name="project", base=project) if project is not None else None

    global_layer: KbLayer | None = (
        KbLayer(name="global", base=resolved_global_base)
        if resolved_global_base is not None
        else None
    )

    return KbLayers(project=project_layer, global_layer=global_layer)
