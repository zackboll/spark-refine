"""Reporting-only projection of one loaded run's normalized unproved checks.

No new classification, attribution, deduplication or cross-run identity.
Messages are data; they participate only in deterministic tie-breaking.
"""

from __future__ import annotations

from collections import Counter
import json

from .model import ProofRun

SCOPE = "normalized_checks_in_loaded_result_set"
SCOPE_TEXT = (
    "Scope: loaded normalized checks only, not a complete proof certificate. "
    "Justifications, warnings, consistency issues and incomplete-analysis "
    "notes remain separate; these raw checks are not specialized SRD diagnostics."
)


def _known(value) -> tuple:
    """Missing values sort first, explicitly distinct from empty/zero."""
    return (value is not None, value if value is not None else "")


def _sort_key(item: dict) -> tuple:
    loc = item["location"]
    return (*(_known(value) for value in (
        item["unit"], item["entity"], loc["file"], loc["line"],
        loc["column"], item["rule"])),
        json.dumps(item, sort_keys=True, ensure_ascii=True))


def unproved_checks(run: ProofRun) -> dict:
    """Every raw occurrence, using the existing normalized status selector."""
    items = [{
        "rule": c.rule,
        "status": c.status.value,
        "entity": c.entity,
        "unit": c.unit,
        "location": {"file": c.location.file, "line": c.location.line,
                     "column": c.location.column},
        "disputed": c.disputed,
        "sarif_kind": c.sarif_kind,
        "sarif_level": c.sarif_level,
        "spark_severity": c.spark_severity,
        "message": c.message,
    } for c in run.unproved]
    items.sort(key=_sort_key)
    counts = Counter(item["rule"] for item in items)
    return {"scope": SCOPE, "count": len(items),
            "by_rule": dict(sorted(counts.items())), "items": items}


def inventory_text(inventory: dict) -> list[str]:
    """A clearly separated raw worklist, without diagnosis or repair advice."""
    out = [f"Reported unproved checks: {inventory['count']}"]
    out += [f"  {rule}: {count}"
            for rule, count in inventory["by_rule"].items()]
    out.append(f"  {SCOPE_TEXT}")
    if not inventory["items"]:
        out.append("  No unproved checks in the loaded normalized result set.")
    for item in inventory["items"]:
        loc = item["location"]
        line = loc["line"] if loc["line"] is not None else "-"
        column = loc["column"] if loc["column"] is not None else "-"
        unit = f"; unit: {item['unit']}" if item["unit"] is not None else ""
        disputed = " [disputed]" if item["disputed"] else ""
        out.append(f"  {loc['file']}:{line}:{column} {item['rule']} "
                   f"[unproved]{disputed}")
        out.append(f"    entity: {item['entity'] or '-'}{unit}")
        out += [f"    {line}" for line in item["message"].splitlines()]
    return out