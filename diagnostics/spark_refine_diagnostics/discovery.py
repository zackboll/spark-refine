"""Conservative discovery of a GNATprove result set (Task 006).

Used only when `spark-refine explain` is given no explicit path. The rule
is deliberately simple and never guesses:

  * A *result set* is a directory that directly contains `gnatprove.sarif`
    and at least one `*.spark` file (what `gnatprove -P ...` writes to
    `<Object_Dir>/gnatprove/`, e.g. `obj/gnatprove` or
    `obj/<variant>/gnatprove`).
  * The search walks the current directory recursively, in sorted order,
    without following symbolic links. It skips hidden directories
    (`.git`, `.alire`, ...) and Alire's dependency cache `alire/`, which
    holds builds of *dependencies*, not of the project.
  * Exactly one result set: it is used.
    Zero or several: DiscoveryError (the CLI exits 2). Several candidates
    are listed in sorted order; the tool never picks the newest, largest
    or first-found one. The caller must pass the path explicitly.

Discovery only locates `gnatprove.sarif` + `*.spark`. `.ali` handling is
unchanged: the analyzer reads the `.ali` files next to the chosen SARIF
exactly as for an explicit path, and SRD002 is skipped when they are
missing or unsupported. Discovery never searches elsewhere for `.ali`.

Discovery says nothing about freshness: it finds results on disk, which
correspond to the current sources only if GNATprove was just run.
"""

from __future__ import annotations

import os
from pathlib import Path

SARIF_NAME = "gnatprove.sarif"
SKIPPED_DIR_NAMES = frozenset({"alire", "__pycache__", "node_modules"})

NONE_FOUND = ("No GNATprove result set found.\n"
              "Run GNATprove first or pass the result path explicitly.")


class DiscoveryError(Exception):
    """No unique result set. `candidates` is sorted (possibly empty)."""

    def __init__(self, message: str, candidates: list[Path]):
        super().__init__(message)
        self.candidates = candidates


def is_result_set(directory: Path) -> bool:
    if not (directory / SARIF_NAME).is_file():
        return False
    return any(p.is_file() for p in directory.glob("*.spark"))


def _skip(name: str) -> bool:
    return name.startswith(".") or name in SKIPPED_DIR_NAMES


def _find(root: Path, valid_only: bool) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not _skip(d))
        if SARIF_NAME in filenames and (not valid_only or
                                        is_result_set(Path(dirpath))):
            found.append(Path(dirpath).relative_to(root))
    return sorted(found, key=lambda p: p.as_posix())


def find_result_sets(root: Path) -> list[Path]:
    """All result-set directories under `root` (inclusive), as paths
    relative to `root`, sorted by their POSIX form."""
    return _find(root, valid_only=True)


def find_sarif_dirs(root: Path) -> list[Path]:
    """Every directory under `root` directly holding gnatprove.sarif
    (result set or not), same walk and order as find_result_sets. Used by
    `prove`'s conservative pre-run snapshot (orchestration.py)."""
    return _find(root, valid_only=False)


def discover(root: Path) -> Path:
    """The unique result set under `root`, relative to `root`."""
    candidates = find_result_sets(root)
    if not candidates:
        raise DiscoveryError(NONE_FOUND, [])
    if len(candidates) > 1:
        listing = "\n".join(f"  {c.as_posix()}" for c in candidates)
        raise DiscoveryError(
            f"Multiple GNATprove result sets found ({len(candidates)}); "
            "refusing to guess:\n"
            f"{listing}\n"
            "Pass one explicitly, e.g.: spark-refine explain "
            f"{candidates[0].as_posix()}", candidates)
    return candidates[0]
