"""Reading GNATprove's per-unit .spark JSON files (FSF GNATprove 16.1.0).

Observed structure (one file per analysed unit, <unit>.spark):

  stop_reason     "STOP_REASON_NONE" when analysis of the unit completed
  pragma_assume   list of analysed pragma Assume
  entities        {" <n>": {"name": "Pkg.Subp", "sloc": [...]}}; proof/flow
                  entries refer to their entity by this integer index
  proof, flow     check entries: rule, severity, file, line, col, entity,
                  message, stats ({prover: {count, max_steps, max_time}})
  warn_error      warnings (e.g. the Is_Valid foundation warning)

A proof/flow entry is unproved when its severity is one of low, medium,
high or error (same criterion as the benchmark gates). "info" is proved.

check_tree and assumptions are not needed by any diagnostic and are ignored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .model import ProverStat, UnitResult
from .sarif import InputError

UNPROVED_SEVERITIES = frozenset({"low", "medium", "high", "error"})


@dataclass(frozen=True)
class SparkEntry:
    unit: str
    kind: str  # "proof" | "flow"
    rule: str
    severity: str
    file: str
    line: int | None
    col: int | None
    entity: str
    message: str
    stats: tuple[ProverStat, ...]

    @property
    def unproved(self) -> bool:
        return self.severity in UNPROVED_SEVERITIES

    def key(self) -> tuple:
        return (self.rule, self.file, self.line, self.col, self.entity)


@dataclass
class SparkUnit:
    result: UnitResult
    entries: list[SparkEntry] = field(default_factory=list)


def _stats(raw: dict | None) -> tuple[ProverStat, ...]:
    out = []
    for prover, st in sorted((raw or {}).items()):
        out.append(ProverStat(prover=prover,
                              count=int(st.get("count", 0)),
                              max_steps=int(st.get("max_steps", 0)),
                              max_time=float(st.get("max_time", 0.0))))
    return tuple(out)


def parse_spark_data(data: dict, unit: str) -> SparkUnit:
    if not isinstance(data, dict) or "stop_reason" not in data:
        raise InputError(f"{unit}.spark: not a GNATprove .spark file")
    entities = {str(k).strip(): (v or {}).get("name", "")
                for k, v in (data.get("entities") or {}).items()}
    entries: list[SparkEntry] = []
    counts = {"proof": 0, "flow": 0}
    for kind in ("proof", "flow"):
        for e in data.get(kind) or []:
            counts[kind] += 1
            ent = e.get("entity")
            msg = e.get("message")
            entries.append(SparkEntry(
                unit=unit, kind=kind, rule=e.get("rule", ""),
                severity=e.get("severity", ""), file=e.get("file", ""),
                line=e.get("line"), col=e.get("col"),
                entity=entities.get(str(ent), "") if ent is not None else "",
                message=(msg or {}).get("text", "") if isinstance(msg, dict)
                else str(msg or ""),
                stats=_stats(e.get("stats"))))
    result = UnitResult(
        name=unit,
        stop_reason=data.get("stop_reason", ""),
        pragma_assume=len(data.get("pragma_assume") or []),
        proof_entries=counts["proof"],
        flow_entries=counts["flow"],
        unproved_entries=sum(e.unproved for e in entries))
    return SparkUnit(result=result, entries=entries)


def parse_spark(path: Path) -> SparkUnit:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON: {exc}") from exc
    return parse_spark_data(data, path.name[:-len(".spark")])


def load_spark_dir(directory: Path) -> list[SparkUnit]:
    """All <unit>.spark files in a GNATprove output directory, sorted."""
    return [parse_spark(p) for p in sorted(directory.glob("*.spark"))]
