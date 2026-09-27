"""Fresh GNATprove orchestration for `spark-refine prove` (Task 008).

`prove` runs GNATprove, then analyses the result set THAT invocation
wrote, with the unchanged single-run analysis (SRD001 / SRD002). It is
orchestration only: GNATprove remains the proof authority; this module
never changes a proof status, never edits sources, never repairs proofs.

Responsibilities (CLI parsing and rendering stay in cli.py / render.py):

  command construction   [GNATPROVE, "-P", PROJECT, *PASSTHROUGH] as an
                         argv list, executed with shell=False; displayed
                         with shlex.join
  result snapshots       SarifStamp of every result set's gnatprove.sarif
  subprocess execution   GNATprove stdout+stderr relayed to OUR stderr, so
                         stdout stays reserved for the spark-refine report
  fresh-result selection explicit --results location, or exactly one
                         result set newly created / changed by the run
  exit-code policy       GNATprove's nonzero exit code is preserved

Freshness (the central invariant). A result set is the Task 006 notion
(discovery.is_result_set: a directory directly holding gnatprove.sarif
and >= 1 *.spark). Before GNATprove starts, the gnatprove.sarif of every
candidate is stamped; after it exits, a candidate is *fresh* only if it is
new or its stamp differs. Freshness is judged on gnatprove.sarif because
FSF GNATprove 16.1.0 rewrites it on every run, including a repeated run of
an unchanged project, whereas incremental runs leave the .spark files
untouched. Observed (docs/tasks/008-proof-run-orchestration.md): the
repeated-run SARIF keeps its inode and size, gets a later mtime/ctime, and
its content differs at most in the one-second `endTimeUtc`, so two runs
within the same second are byte-identical. Hence the stamp combines
metadata (device, inode, size, mtime_ns, ctime_ns) AND a content digest;
any difference counts as a change. This is conservative change detection,
not security. The only miss would be a rewrite with identical bytes
within one filesystem timestamp tick of the previous write; that fails
SAFE (the run is refused as "no fresh result"), never by analysing stale
output. The tool never picks the newest / first / largest candidate.
"""

from __future__ import annotations

import hashlib
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .discovery import (SARIF_NAME, find_result_sets, find_sarif_dirs,
                        is_result_set)

DEFAULT_GNATPROVE = "gnatprove"

EXPLICIT = "explicit"
FRESH_DISCOVERY = "fresh_discovery"

NOT_FRESH_EXPLICIT = ("GNATprove did not produce fresh results at the "
                      "requested location.")
NOT_VALID_EXPLICIT = ("GNATprove did not produce a valid result set at the "
                      "requested location.")
NONE_FRESH = ("GNATprove did not create or change any result set under the "
              "current directory; refusing to analyse stale results.")


class FreshnessError(Exception):
    """No usable fresh result set. `candidates` is sorted (maybe empty):
    for an ambiguous selection, the fresh candidates; otherwise empty."""

    def __init__(self, message: str, candidates: list[Path] | None = None):
        super().__init__(message)
        self.candidates = candidates or []


class LaunchError(Exception):
    """GNATprove could not be started (no process ran)."""


# --------------------------------------------------------------------------
# Command construction
# --------------------------------------------------------------------------

def build_command(project: str, passthrough: list[str] | None = None,
                  gnatprove: str = DEFAULT_GNATPROVE) -> list[str]:
    """The exact GNATprove argv: executable, -P PROJECT, then the
    pass-through arguments verbatim (never reinterpreted, never split)."""
    return [gnatprove, "-P", project, *(passthrough or [])]


def display_command(argv: list[str]) -> str:
    """Deterministic, shell-escaped display (copy-pastable into a POSIX
    shell). Display only: execution never goes through a shell."""
    return shlex.join(argv)


# --------------------------------------------------------------------------
# Result snapshots
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class SarifStamp:
    """State of one gnatprove.sarif. Equal stamps = unchanged file."""
    device: int
    inode: int
    size: int
    mtime_ns: int
    ctime_ns: int
    sha256: str


def stamp(sarif: Path) -> SarifStamp | None:
    """The file's stamp, or None if it does not exist / is not a file."""
    try:
        if not sarif.is_file():
            return None
        st = sarif.stat()
        digest = hashlib.sha256(sarif.read_bytes()).hexdigest()
    except OSError:
        return None
    return SarifStamp(st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns,
                      st.st_ctime_ns, digest)


def snapshot(root: Path, result_sets_only: bool = True
             ) -> dict[Path, SarifStamp]:
    """Stamp of the gnatprove.sarif of every result set under `root`
    (paths relative to root). With result_sets_only=False, of every
    directory holding a gnatprove.sarif, valid result set or not: the
    pre-run snapshot uses this, so a directory whose SARIF pre-dates the
    run can never count as "new" merely because it became valid."""
    dirs = (find_result_sets(root) if result_sets_only
            else find_sarif_dirs(root))
    out: dict[Path, SarifStamp] = {}
    for rel in dirs:
        s = stamp(root / rel / SARIF_NAME)
        if s is not None:
            out[rel] = s
    return out


def fresh_candidates(before: dict[Path, SarifStamp],
                     after: dict[Path, SarifStamp]) -> list[Path]:
    """Result sets new in `after` or whose SARIF stamp changed, sorted."""
    return sorted((p for p, s in after.items() if before.get(p) != s),
                  key=lambda p: p.as_posix())


def explicit_result_dir(path: Path) -> Path:
    """`--results` names a result-set directory (the one directly holding
    gnatprove.sarif) or that gnatprove.sarif file itself."""
    return path.parent if path.name == SARIF_NAME else path


@dataclass
class Selection:
    path: Path                     # result-set directory to analyse
    method: str                    # EXPLICIT | FRESH_DISCOVERY
    stale_ignored: list[Path] = field(default_factory=list)


class Freshness:
    """Pre-run snapshot + post-run selection for ONE GNATprove invocation.

    Construct BEFORE launching GNATprove; call select() after it exits.
    `results` (the --results PATH) is authoritative: only that location
    is considered, there is no fallback to discovery."""

    def __init__(self, root: Path, results: Path | None = None):
        self.root = root
        self.results = results
        self._before_one: SarifStamp | None = None
        self._before: dict[Path, SarifStamp] = {}
        if results is not None:
            self._before_one = stamp(self._sarif_of(results))
        else:
            self._before = snapshot(root, result_sets_only=False)

    def _abs(self, p: Path) -> Path:
        return p if p.is_absolute() else self.root / p

    def _sarif_of(self, results: Path) -> Path:
        return self._abs(explicit_result_dir(results)) / SARIF_NAME

    def select(self) -> Selection:
        if self.results is not None:
            return self._select_explicit()
        after = snapshot(self.root)
        fresh = fresh_candidates(self._before, after)
        stale = sorted((p for p in after if p not in fresh),
                       key=lambda p: p.as_posix())
        if not fresh:
            hint = ""
            if stale:
                hint = ("\nUnchanged (stale) result sets ignored:\n" +
                        "\n".join(f"  {p.as_posix()}" for p in stale))
            raise FreshnessError(
                NONE_FRESH + hint + "\nIf GNATprove writes its results "
                "outside the current directory, pass --results PATH.")
        if len(fresh) > 1:
            listing = "\n".join(f"  {p.as_posix()}" for p in fresh)
            raise FreshnessError(
                f"GNATprove created or changed {len(fresh)} result sets; "
                f"refusing to guess:\n{listing}\n"
                "Pass the one to analyse with --results PATH.", fresh)
        return Selection(fresh[0], FRESH_DISCOVERY, stale)

    def _select_explicit(self) -> Selection:
        assert self.results is not None
        directory = explicit_result_dir(self.results)
        where = self._abs(directory)
        if not is_result_set(where):
            raise FreshnessError(
                f"{NOT_VALID_EXPLICIT}\n  {directory.as_posix()}: expected "
                f"{SARIF_NAME} and at least one *.spark file")
        if stamp(where / SARIF_NAME) == self._before_one:
            raise FreshnessError(
                f"{NOT_FRESH_EXPLICIT}\n  {directory.as_posix()}/"
                f"{SARIF_NAME} is unchanged by this GNATprove invocation; "
                "refusing to analyse it as fresh.")
        return Selection(directory, EXPLICIT)


# --------------------------------------------------------------------------
# Subprocess execution and exit status
# --------------------------------------------------------------------------

def normalize_returncode(raw: int) -> int:
    """Shell-compatible exit status: a process killed by signal N has
    subprocess return code -N and is reported as 128 + N."""
    return 128 - raw if raw < 0 else raw


def run_gnatprove(argv: list[str], cwd: Path | None = None) -> int:
    """Run GNATprove (shell=False) and return its RAW return code.

    Its stdout and stderr are merged and relayed, as they arrive, to this
    process's sys.stderr; nothing is written to stdout, so the
    spark-refine report (text or JSON) on stdout cannot be corrupted.
    stdin is /dev/null: the run is non-interactive."""
    try:
        proc = subprocess.Popen(argv, cwd=cwd, shell=False,
                                stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    except OSError as exc:
        raise LaunchError(f"could not launch {argv[0]!r}: "
                          f"{exc.strerror or exc}") from exc
    assert proc.stdout is not None
    with proc.stdout:
        for line in iter(proc.stdout.readline, b""):
            sys.stderr.write(line.decode("utf-8", errors="replace"))
            sys.stderr.flush()
    return proc.wait()


def exit_status(gnatprove_exit: int, fail_on_matched: bool) -> int:
    """Task 008 precedence, after a successful analysis: GNATprove's
    nonzero exit code (normalized) wins; otherwise 1 if a --fail-on code
    was emitted; otherwise 0. Errors before a usable result are handled
    by the caller: 2, or GNATprove's nonzero code if it had already run."""
    if gnatprove_exit != 0:
        return gnatprove_exit
    return 1 if fail_on_matched else 0


def metadata(argv: list[str], raw_returncode: int,
             selection: Selection) -> dict:
    """Deterministic provenance for analysis.orchestration: no
    timestamps, no UUIDs, no absolute paths added by the tool (an
    absolute --results path given by the user is preserved as given)."""
    meta: dict = {
        "command": list(argv),
        "gnatprove_exit_code": normalize_returncode(raw_returncode),
        "result_path": selection.path.as_posix(),
        "result_selection": selection.method,
        "fresh": True,
    }
    if raw_returncode < 0:
        meta["gnatprove_raw_returncode"] = raw_returncode
    if selection.method == FRESH_DISCOVERY:
        meta["stale_result_sets_ignored"] = [
            p.as_posix() for p in selection.stale_ignored]
    return meta


def plan(argv: list[str], results: Path | None) -> dict:
    """The --dry-run orchestration plan (nothing executed or inspected)."""
    return {
        "command": list(argv),
        "dry_run": True,
        "result_selection": (EXPLICIT if results is not None
                             else FRESH_DISCOVERY),
        "result_path": (explicit_result_dir(results).as_posix()
                        if results is not None else None),
    }

