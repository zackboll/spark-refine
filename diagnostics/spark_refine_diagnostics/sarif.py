"""Reading GNATprove's SARIF output (gnatprove.sarif, FSF GNATprove 16.1.0).

The pass/fail classification is identical to the benchmark gates
(examples/*/scripts/check_proof_results.py, function load_results) and is
purely structural:

  kind == "pass"                              -> proved
  allow-listed foundation warning             -> ToolWarning(allowed=True)
  suppression of kind "inSource"              -> justified
  level in ("warning", "note")                -> ToolWarning(allowed=False)
  anything else                               -> unproved

English message text never decides whether a check passed. It is only used
(a) for the documented allow-list of toolchain warnings, exactly as the
gates do, and (b) for display. tests/test_parity.py checks this module
against both gates on every committed fixture.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .model import Check, Location, Status, ToolWarning

# Toolchain warnings that belong to the documented external proof foundation
# (examples/*/BASELINE_METRICS.md, "Trust boundary"). Matched on SARIF rule
# id, file and message prefix. Kept identical to ALLOWED_WARNINGS in both
# benchmark gates: Ada.Numerics.Big_Numbers.Big_Integers.Is_Valid is an
# intrinsic that GNATprove assumes, reached through SPARKlib.
ALLOWED_FOUNDATION_WARNINGS: tuple[tuple[str, str, str], ...] = (
    ("error", "a-nbnbin.ads", "function Is_Valid is assumed to return True"),
)


class InputError(Exception):
    """Machine-readable GNATprove output is missing or malformed."""


def is_allowed_warning(rule: str, uri: str, text: str) -> bool:
    return any(rule == r and uri == f and text.startswith(m)
               for r, f, m in ALLOWED_FOUNDATION_WARNINGS)


@dataclass
class SarifRun:
    tool_version: str
    command_line: str
    exit_code: int | None
    checks: list[Check] = field(default_factory=list)
    warnings: list[ToolWarning] = field(default_factory=list)


def _first_location(res: dict) -> tuple[Location, str]:
    locs = res.get("locations") or []
    if not locs:
        return Location(""), ""
    loc = locs[0]
    phys = loc.get("physicalLocation") or {}
    uri = (phys.get("artifactLocation") or {}).get("uri", "")
    region = phys.get("region") or {}
    entity = (loc.get("logicalLocations") or [{}])[0].get("name", "")
    return (Location(uri, region.get("startLine"), region.get("startColumn")),
            entity)


def parse_sarif_data(data: dict, source: str = "<sarif>") -> SarifRun:
    try:
        runs = data["runs"]
        run = runs[0]
        results = run["results"]
    except (KeyError, IndexError, TypeError) as exc:
        raise InputError(f"{source}: not a GNATprove SARIF log "
                         f"(missing {exc})") from exc
    if len(runs) != 1:
        raise InputError(f"{source}: expected exactly one SARIF run, "
                         f"found {len(runs)}")
    driver = (run.get("tool") or {}).get("driver") or {}
    inv = (run.get("invocations") or [{}])[0]
    out = SarifRun(tool_version=driver.get("version", ""),
                   command_line=inv.get("commandLine", ""),
                   exit_code=inv.get("exitCode"))
    for res in results:
        try:
            rule = res["ruleId"]
            kind = res["kind"]
            message = res["message"]["text"]
        except (KeyError, TypeError) as exc:
            raise InputError(f"{source}: SARIF result without {exc}") from exc
        level = res.get("level", "")
        location, entity = _first_location(res)
        suppressions = tuple(s.get("kind", "")
                             for s in (res.get("suppressions") or []))
        if kind == "pass":
            status = Status.PROVED
        elif is_allowed_warning(rule, location.file, message):
            out.warnings.append(ToolWarning(rule, location, entity, message,
                                            allowed=True))
            continue
        elif "inSource" in suppressions:
            status = Status.JUSTIFIED
        elif level in ("warning", "note"):
            out.warnings.append(ToolWarning(rule, location, entity, message,
                                            allowed=False))
            continue
        else:
            status = Status.UNPROVED
        out.checks.append(Check(rule=rule, status=status, location=location,
                                entity=entity, message=message,
                                sarif_kind=kind, sarif_level=level,
                                suppressions=suppressions))
    return out


def parse_sarif(path: Path) -> SarifRun:
    if not path.is_file():
        raise InputError(f"missing SARIF output {path} "
                         "(compilation or analysis did not complete)")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON: {exc}") from exc
    return parse_sarif_data(data, str(path))
