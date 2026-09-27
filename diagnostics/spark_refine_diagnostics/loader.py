"""Build a normalized ProofRun from a GNATprove output directory or file.

Accepted inputs:

  <dir>/gnatprove.sarif (+ optional <dir>/*.spark)   a GNATprove output dir
                                                     (obj/<variant>/gnatprove)
  <file>.sarif                                       SARIF only; the .spark
                                                     files next to it, if any,
                                                     are used as well

SARIF is authoritative for check status. The .spark files add:

  * the owning unit of each check (a generic instance's VCs are located in
    the generic's source file but belong to the instantiating unit);
  * per-prover statistics;
  * stop_reason and pragma Assume counts.

They are matched to SARIF results by (rule, file, line, column, entity) as a
multiset. Any disagreement (a SARIF check without a .spark entry, or a
.spark entry whose unproved-ness differs from the SARIF status) is recorded
in ProofRun.consistency_issues rather than silently resolved. The affected
check is marked `disputed` and its unit is added to
ProofRun.disputed_units, so that no rule relies on the disputed status
with full confidence (SRD001 lowers its confidence, SRD002 is not emitted
for a client whose dependency closure contains a disputed unit).

Without .spark files, each check's unit is attributed from the first
component of its SARIF logical entity name (Pkg.Subp -> pkg), and
ProofRun.unit_attribution records that weaker evidence.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from .model import Check, ProofRun, Status
from .sarif import InputError, parse_sarif
from .spark_results import SparkEntry, load_spark_dir


def unit_from_entity(entity: str) -> str | None:
    """Fallback unit attribution: library-level package of an entity.
    GNAT file naming lowercases unit names; child units ('.') are not used
    by the benchmarks, so the first component is the unit."""
    if not entity:
        return None
    return entity.split(".", 1)[0].lower()


def resolve_input(path: Path) -> tuple[Path, Path]:
    """Return (sarif_file, directory_holding_spark_files)."""
    if path.is_dir():
        for candidate in (path / "gnatprove.sarif",
                          path / "gnatprove" / "gnatprove.sarif"):
            if candidate.is_file():
                return candidate, candidate.parent
        raise InputError(f"{path}: no gnatprove.sarif found "
                         "(expected <dir>/gnatprove.sarif or "
                         "<dir>/gnatprove/gnatprove.sarif)")
    if path.is_file():
        return path, path.parent
    raise InputError(f"{path}: no such file or directory")


def load_run(path: Path, name: str | None = None) -> ProofRun:
    sarif_path, spark_dir = resolve_input(path)
    sarif = parse_sarif(sarif_path)
    units = load_spark_dir(spark_dir)
    run = ProofRun(name=name or path.as_posix(),
                   source=sarif_path.as_posix(),
                   tool_version=sarif.tool_version,
                   command_line=sarif.command_line,
                   exit_code=sarif.exit_code,
                   warnings=sarif.warnings,
                   units=[u.result for u in units])
    if not units:
        run.unit_attribution = "entity"
        run.checks = [replace(c, unit=unit_from_entity(c.entity))
                      for c in sarif.checks]
        return run

    pool: dict[tuple, list[SparkEntry]] = defaultdict(list)
    for unit in units:
        for entry in unit.entries:
            pool[entry.key()].append(entry)

    checks: list[Check] = []
    for c in sarif.checks:
        key = (c.rule, c.location.file, c.location.line, c.location.column,
               c.entity)
        candidates = pool.get(key) or []
        if not candidates:
            run.consistency_issues.append(
                f"SARIF check without .spark entry: {c.rule} {c.entity} "
                f"{c.location}")
            unit = unit_from_entity(c.entity)
            if unit:
                run.disputed_units.add(unit)
            checks.append(replace(c, unit=unit, disputed=True))
            continue
        # Prefer an entry whose outcome agrees with SARIF; deterministic
        # (units are read in sorted order, entries in file order).
        want_unproved = c.status is not Status.PROVED
        idx = next((i for i, e in enumerate(candidates)
                    if e.unproved == want_unproved), 0)
        entry = candidates.pop(idx)
        disputed = entry.unproved != want_unproved
        if disputed:
            run.consistency_issues.append(
                f"status disagreement: SARIF {c.status.value} vs .spark "
                f"severity {entry.severity!r}: {c.rule} {c.entity} "
                f"{c.location}")
            run.disputed_units.add(entry.unit)
        checks.append(replace(c, unit=entry.unit,
                              spark_severity=entry.severity,
                              prover_stats=entry.stats,
                              disputed=disputed))
    for entries in pool.values():
        for e in entries:
            # .spark entries with no SARIF counterpart. Proved ones would be
            # harmless, but an unproved one would mean SARIF under-reports.
            if e.unproved:
                run.consistency_issues.append(
                    f".spark unproved entry without SARIF result: {e.rule} "
                    f"{e.entity} {e.file}:{e.line} ({e.unit})")
                run.disputed_units.add(e.unit)
    run.checks = checks
    return run
