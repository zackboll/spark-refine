"""Task 010: report-level SRD002 semantic triage groups (backend-neutral).

Pure data over diagnostics SRD002 already emitted and their Task 009
`semantic` blocks. This module never imports Libadalang, never creates,
removes, merges or mutates a Diagnostic, never reads check messages and
never evaluates or normalises an expression.

A GROUP collects unproved VC_PRECONDITION client failures whose Task 009
enrichment is `exact` and which call the SAME resolved declaration with
the SAME extracted public Pre. It is consolidation for triage, not
diagnosis: members are not claimed to share a cause, the Pre is not
claimed to be wrong or incomplete, and no failed conjunct is identified
(GNATprove does not report one). A group has no confidence of its own;
each occurrence keeps the confidence of the diagnostic it came from.

Group identity: the complete Task 009 `callee` object (fully-qualified
name, kind, declaration span) and the complete `precondition` object
(explicit flag, exact source text, source span, conjuncts, attribution),
compared as canonical JSON. Two overloads sharing a name, or the same
name with a different declaration span, Pre text or Pre span, therefore
never collapse, and differing Pre metadata for one declaration splits
into separate groups instead of one being chosen. Text is compared
verbatim: no simplification, reordering, renaming or logical equivalence.

Coverage invariant (coverage_problems): every SRD002 client failure
appears EXACTLY ONCE, either as a group occurrence or in `ungrouped`.
Checks that cannot be grouped carry a stable machine reason (REASONS).

Occurrence identity: (client unit, entity, rule, file, line, column).
Two related client failures with the same identity are indistinguishable
in the report; they are kept as ONE occurrence carrying `duplicate_count`
(present only when > 1). All counts are counts of distinct occurrences.
"""

from __future__ import annotations

import json

PRECONDITION = "VC_PRECONDITION"
ASSERTION = "VC_ASSERT"
CLIENT_FAILURE = "client failure"

# Stable machine-readable reasons for `ungrouped` entries.
REASONS = (
    "assertion_has_no_callee",  # VC_ASSERT: no called operation, ever
    "rule_not_groupable",       # any other client rule (none today)
    "semantic_ambiguous",       # Task 009 resolution of a precondition
    "semantic_unresolved",
    "semantic_unavailable",
    "semantic_incomplete",      # exact, but required grouping data missing
)
_BY_RESOLUTION = {"ambiguous": "semantic_ambiguous",
                  "unresolved": "semantic_unresolved",
                  "unavailable": "semantic_unavailable"}


def _copy(v):
    return json.loads(json.dumps(v))


def _loc(loc) -> dict:
    return {"file": loc.file, "line": loc.line, "column": loc.column}


def _num(v) -> int:
    return v if isinstance(v, int) else -1


def occurrence_id(client_unit, entity, rule, location: dict) -> tuple:
    return (client_unit, entity, rule, location.get("file"),
            location.get("line"), location.get("column"))


def _occ_key(o: dict) -> tuple:
    loc = o["location"]
    return (o["client_unit"] or "", o["entity"] or "", loc["file"] or "",
            _num(loc["line"]), _num(loc["column"]), o["rule"])


def _span_ok(s) -> bool:
    return (isinstance(s, dict) and isinstance(s.get("file"), str)
            and isinstance(s.get("start_line"), int)
            and isinstance(s.get("start_column"), int))


def _complete(c: dict) -> bool:
    """An exact precondition entry has everything its identity needs."""
    call, callee, pre = c.get("call"), c.get("callee"), c.get("precondition")
    if not (isinstance(call, dict) and isinstance(callee, dict)
            and isinstance(pre, dict)):
        return False
    if not (isinstance(callee.get("name"), str) and callee["name"]
            and isinstance(callee.get("kind"), str)
            and _span_ok(callee.get("declaration"))):
        return False
    if pre.get("explicit") is True:
        return (isinstance(pre.get("text"), str)
                and _span_ok(pre.get("location")))
    return pre.get("explicit") is False


def _group_sort_key(g: dict) -> tuple:
    callee, pre = g["callee"], g["precondition"]
    d = callee["declaration"]
    pl = pre.get("location") or {}
    return (callee["name"], d["file"], d["start_line"], d["start_column"],
            _num(d.get("end_line")), _num(d.get("end_column")),
            callee["kind"], pre["explicit"], pre.get("text") or "",
            pl.get("file") or "", _num(pl.get("start_line")),
            _num(pl.get("start_column")), g["_identity"])


def _pairs(d):
    """(related client failure, its Task 009 semantic check or None),
    paired by (rule, file, line, column). The related checks of the
    diagnostic are authoritative: every one is visited exactly once."""
    pool: dict[tuple, list] = {}
    for c in (d.semantic or {}).get("checks") or []:
        loc = c.get("location") or {}
        key = (c.get("rule"), loc.get("file"), loc.get("line"),
               loc.get("column"))
        pool.setdefault(key, []).append(c)
    for r in d.related:
        if r.role != CLIENT_FAILURE:
            continue
        key = (r.rule, r.location.file, r.location.line, r.location.column)
        found = pool.get(key)
        yield r, (found.pop(0) if found else None)


def _classify(rule: str, c: dict | None) -> tuple[str | None, str | None]:
    """(ungrouped reason, optional detail); reason None = groupable."""
    if rule == ASSERTION:
        return "assertion_has_no_callee", None
    if rule != PRECONDITION:
        return "rule_not_groupable", None
    if c is None:
        return "semantic_incomplete", "no semantic entry for this check"
    res = c.get("resolution")
    if res in _BY_RESOLUTION:
        return _BY_RESOLUTION[res], c.get("reason")
    if res != "exact":
        return "semantic_incomplete", f"unknown resolution {res!r}"
    if not _complete(c):
        return ("semantic_incomplete",
                "exact entry lacks call/callee/precondition data")
    return None, None


def build_srd002_groups(diagnostics) -> dict:
    """Group the SRD002 client failures of `diagnostics` (never mutated;
    all output is copied). Deterministic plain data, independent of input
    order."""
    groups: dict[str, dict] = {}
    ungrouped: list[dict] = []
    placed: dict[tuple, dict] = {}   # occurrence id -> occurrence dict
    for d in diagnostics:
        if d.code != "SRD002":
            continue
        client = dict(d.data).get("client_unit")
        for r, c in _pairs(d):
            loc = _loc(r.location)
            oid = occurrence_id(client, d.entity, r.rule, loc)
            if oid in placed:
                placed[oid]["duplicate_count"] = (
                    placed[oid].get("duplicate_count", 1) + 1)
                continue
            base = {"client_unit": client, "entity": d.entity,
                    "diagnostic_confidence": d.confidence.value,
                    "rule": r.rule, "location": loc}
            reason, detail = _classify(r.rule, c)
            if reason is not None:
                item = {**base, "resolution": (c or {}).get("resolution"),
                        "reason": reason,
                        **({"detail": detail} if detail else {})}
                ungrouped.append(item)
                placed[oid] = item
                continue
            callee, pre = _copy(c["callee"]), _copy(c["precondition"])
            identity = json.dumps({"callee": callee, "precondition": pre},
                                  sort_keys=True)
            g = groups.setdefault(identity, {
                "callee": callee, "precondition": pre, "occurrences": [],
                "_identity": identity})
            occ = {**base, "call": _copy(c["call"])}
            g["occurrences"].append(occ)
            placed[oid] = occ
    out_groups = []
    for g in sorted(groups.values(), key=_group_sort_key):
        occs = sorted(g["occurrences"], key=_occ_key)
        out_groups.append({
            "callee": g["callee"],
            "precondition": g["precondition"],
            "check_count": len(occs),
            "diagnostic_confidences": sorted(
                {o["diagnostic_confidence"] for o in occs}),
            "occurrences": occs})
    ungrouped.sort(key=_occ_key)
    grouped_n = sum(g["check_count"] for g in out_groups)
    return {"client_failure_count": grouped_n + len(ungrouped),
            "group_count": len(out_groups),
            "grouped_check_count": grouped_n,
            "ungrouped_check_count": len(ungrouped),
            "groups": out_groups,
            "ungrouped": ungrouped}


# ---------------------------------------------------------------------
# Coverage invariant (used by tests and by the E2E-F/E2E-G checkers)
# ---------------------------------------------------------------------

def occurrence_ids(diagnostics) -> set[tuple]:
    """Distinct occurrence identities of the SRD002 client failures of
    Diagnostic objects: exactly what a groups document must cover."""
    return {occurrence_id(dict(d.data).get("client_unit"), d.entity,
                          r.rule, _loc(r.location))
            for d in diagnostics if d.code == "SRD002"
            for r in d.related if r.role == CLIENT_FAILURE}


def report_occurrence_ids(report: dict) -> set[tuple]:
    """The same identities, from a JSON report."""
    return {occurrence_id((d.get("data") or {}).get("client_unit"),
                          d.get("entity"), r.get("rule"),
                          r.get("location") or {})
            for d in report.get("diagnostics", [])
            if d.get("code") == "SRD002"
            for r in d.get("related", [])
            if r.get("role") == CLIENT_FAILURE}


def coverage_problems(doc: dict, expected: set[tuple]) -> list[str]:
    """Structural invariants of a groups document against the expected
    occurrence identities; [] = OK. Every expected occurrence exactly once
    (group occurrence XOR ungrouped), counts consistent, only preconditions
    grouped, no group-level confidence, no failed-conjunct claim."""
    problems: list[str] = []
    groups = doc.get("groups", [])
    ungrouped = doc.get("ungrouped", [])
    for g in groups:
        name = (g.get("callee") or {}).get("name")
        occs = g.get("occurrences", [])
        if g.get("check_count") != len(occs):
            problems.append(f"group {name}: check_count "
                            f"{g.get('check_count')!r} != {len(occs)} "
                            "occurrences")
        if "confidence" in g:
            problems.append(f"group {name}: group-level confidence")
        if (g.get("precondition") or {}).get("failed_conjunct") is not None:
            problems.append(f"group {name}: failed conjunct claimed")
        for o in occs:
            if o.get("rule") != PRECONDITION:
                problems.append(f"group {name}: {o.get('rule')} grouped")
    for u in ungrouped:
        if u.get("reason") not in REASONS:
            problems.append(f"unknown ungrouped reason {u.get('reason')!r}")
    seen: dict[tuple, int] = {}
    for o in [o for g in groups for o in g.get("occurrences", [])]\
            + ungrouped:
        oid = occurrence_id(o.get("client_unit"), o.get("entity"),
                            o.get("rule"), o.get("location") or {})
        seen[oid] = seen.get(oid, 0) + 1
    for oid, n in sorted(seen.items(), key=repr):
        if n > 1:
            problems.append(f"occurrence listed {n} times: {oid}")
        if oid not in expected:
            problems.append(f"not an SRD002 client failure: {oid}")
    for oid in sorted(expected - set(seen), key=repr):
        problems.append(f"SRD002 client failure missing: {oid}")
    grouped_n = sum(len(g.get("occurrences", [])) for g in groups)
    for key, want in (("group_count", len(groups)),
                      ("grouped_check_count", grouped_n),
                      ("ungrouped_check_count", len(ungrouped)),
                      ("client_failure_count", len(expected))):
        if doc.get(key) != want:
            problems.append(f"{key} {doc.get(key)!r} != {want}")
    total = [doc.get("grouped_check_count"), doc.get("ungrouped_check_count")]
    if not all(isinstance(n, int) for n in total) \
            or sum(total) != len(expected):
        problems.append(f"grouped + ungrouped {total} != {len(expected)} "
                        "SRD002 client failures")
    return problems
