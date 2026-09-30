#!/usr/bin/env python3
"""Task 013: guard-sensitive conjunct re-proof EXPERIMENT (not a product).

  cd examples/ring_buffer
  PYTHONPATH=<lal bundle> alr -n exec -- \\
      python3 ../../diagnostics/scripts/guarded_reproof_experiment.py

Pre-registration: docs/tasks/013-guard-sensitive-conjunct-reproof.md.

For the committed experimental corpus (tests/experiments/task013_guarded):

  1. Libadalang extracts each guarded callee's explicit Pre, its ordered
     top-level conjuncts with source ranges, and the original top-level
     operators (`and` / `and then`).
  2. A pure planner produces CUMULATIVE SOURCE PREFIXES only
     (P0 = C0, P1 = C0 and then C1, ...). It refuses to schedule a guarded
     later conjunct on its own (Task 012's selected-only method).
  3. One unmodified control runs, then one scratch copy per prefix. In a
     copy only the bytes of the target Pre AFTER the prefix are blanked
     (newline-preserving); the prefix stays the original source bytes.
  4. Every call VC_PRECONDITION is read structurally (exactly one match,
     SARIF status, .spark consistency). Nested-call, guard
     well-definedness and all other checks are recorded SEPARATELY.
  5. The per-occurrence prefix transition is classified, the frozen
     decision rule is applied, and evidence.json is written.

Scratch results are evidence about SCRATCH programs only. They do not
prove the original program, and no ordinary spark-refine report uses them.
GNATprove stays the proof authority. No prover message text is read.

Filesystem safety, the mutation inventory, the overlay and the
forbidden-trust scan are Task 012's helpers (conjunct_reproof_experiment.py),
reused unchanged and always called with THIS experiment's scratch root and
file list.

Exit status: 0 iff PREFIX_METHOD_VALIDATED_ON_GUARDED_CORPUS; 1 for
PREFIX_METHOD_NOT_VALIDATED; 2 if a precondition stops the experiment.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIAGNOSTICS = REPO / "diagnostics"
if str(DIAGNOSTICS) not in sys.path:
    sys.path.insert(0, str(DIAGNOSTICS))

from spark_refine_diagnostics.loader import load_run  # noqa: E402


def _load_task012():
    """The Task 012 experiment module, unchanged; only helpers are used."""
    path = Path(__file__).resolve().parent / "conjunct_reproof_experiment.py"
    spec = importlib.util.spec_from_file_location("task012_reproof", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T12 = _load_task012()
ExperimentStop = T12.ExperimentStop

CORPUS = DIAGNOSTICS / "tests" / "experiments" / "task013_guarded"
CORPUS_REL = "diagnostics/tests/experiments/task013_guarded"
SCRATCH_ROOT = DIAGNOSTICS / "obj" / "task013-guarded-reproof"
RB = REPO / "examples" / "ring_buffer"  # pinned toolchain crate (as 012)

EXPERIMENT = "task013_guard_sensitive_conjunct_reproof"
METHOD = "guard_preserving_prefix_reproof"
SCOPE = "preregistered_guarded_and_then_corpus"
GNATPROVE_VERSION = "FSF 16.1.0"
VALIDATED = "PREFIX_METHOD_VALIDATED_ON_GUARDED_CORPUS"
NOT_VALIDATED = "PREFIX_METHOD_NOT_VALIDATED"
PROVE_ARGS = ("-j0",)  # + the project's Proof_Switches (P8)
PROJECT_PROOF_SWITCHES = ("-U", "--mode=all", "--level=2",
                          "--report=statistics")

COPIED_FILES = ("guarded.gpr", "src/guarded_client.adb",
                "src/guarded_client.ads", "src/guarded_ops.adb",
                "src/guarded_ops.ads")
MUTABLE_FILE = "src/guarded_ops.ads"

# P3: committed source identity
CORPUS_SHA256 = {
    "guarded.gpr":
        "4fdddb9c2ce3c57c0b048561b76a1f85d3d1bc23ad90c3f8f06eb452cb11d01e",
    "src/guarded_client.adb":
        "4b6cc0c70ecf4decb15589f4013683225dedc1fb96005716f15549645d25772c",
    "src/guarded_client.ads":
        "146a235bbffae94e4e18b5ce8439de47f29184453e1cd0f5f98b998e94690186",
    "src/guarded_ops.adb":
        "8e1af7ef8a0bac18e11bc0815ad6984d22777a8377cb86f226752c0353548950",
    "src/guarded_ops.ads":
        "06b08015661d612623c10000143dd3a24717913164e2f30829255c228d1ddb76",
}

AND, AND_THEN = "and", "and then"

# P4: pre-registered extraction (never updated to make a run pass).
# span = (start_line, start_column, end_line, end_column), end exclusive.
EXPECTED_EXTRACTION = {
    "Guarded_Ops.Use_Access": {
        "conjuncts": ("P /= null", "P.all > 0"),
        "operators": (AND_THEN,), "span": (11, 19, 12, 37)},
    "Guarded_Ops.Use_Index": {
        "conjuncts": ("I in A'Range", "A (I) > 0"),
        "operators": (AND_THEN,), "span": (17, 19, 18, 37)},
    "Guarded_Ops.Use_Nested": {
        "conjuncts": ("X in 12 .. 999", "F (F (X)) > 20"),
        "operators": (AND_THEN,), "span": (28, 19, 29, 42)},
}
CALLEES = tuple(EXPECTED_EXTRACTION)

_IND = "\n" + " " * 18
# P5: pre-registered exact prefix texts
EXPECTED_PREFIXES = {
    ("Guarded_Ops.Use_Access", 0): "P /= null",
    ("Guarded_Ops.Use_Access", 1): "P /= null" + _IND + "and then P.all > 0",
    ("Guarded_Ops.Use_Index", 0): "I in A'Range",
    ("Guarded_Ops.Use_Index", 1): ("I in A'Range" + _IND
                                   + "and then A (I) > 0"),
    ("Guarded_Ops.Use_Nested", 0): "X in 12 .. 999",
    ("Guarded_Ops.Use_Nested", 1): ("X in 12 .. 999" + _IND
                                    + "and then F (F (X)) > 20"),
}

# P3: pre-registered call sites:
#   (case, client entity, file, line, column, callee)
TARGETS = (
    ("A1", "Guarded_Client.A1_Guard_And_Value", "guarded_client.adb", 7, 7,
     "Guarded_Ops.Use_Access"),
    ("A2", "Guarded_Client.A2_Guard_Only", "guarded_client.adb", 12, 7,
     "Guarded_Ops.Use_Access"),
    ("A3", "Guarded_Client.A3_No_Guard", "guarded_client.adb", 17, 7,
     "Guarded_Ops.Use_Access"),
    ("B1", "Guarded_Client.B1_Range_And_Value", "guarded_client.adb", 22, 7,
     "Guarded_Ops.Use_Index"),
    ("B2", "Guarded_Client.B2_Range_Only", "guarded_client.adb", 27, 7,
     "Guarded_Ops.Use_Index"),
    ("B3", "Guarded_Client.B3_No_Range", "guarded_client.adb", 32, 7,
     "Guarded_Ops.Use_Index"),
    ("C1", "Guarded_Client.C1_Guard_And_Value", "guarded_client.adb", 37, 7,
     "Guarded_Ops.Use_Nested"),
    ("C2", "Guarded_Client.C2_Guard_Only", "guarded_client.adb", 42, 7,
     "Guarded_Ops.Use_Nested"),
    ("C3", "Guarded_Client.C3_No_Guard", "guarded_client.adb", 47, 7,
     "Guarded_Ops.Use_Nested"),
)
CASES = tuple(t[0] for t in TARGETS)

PROVED, UNPROVED, JUSTIFIED = "proved", "unproved", "justified"

# P12: stable classification vocabulary
PREFIX_PROVED = "prefix_proved"
NEWLY_UNPROVED = "newly_unproved"
BLOCKED = "blocked_by_earlier_prefix"
NESTED_UNPROVED = "nested_precondition_unproved"
INVALID = "invalid_probe"
CLASSIFICATIONS = (PREFIX_PROVED, NEWLY_UNPROVED, BLOCKED, NESTED_UNPROVED,
                   INVALID)

# P11: baseline control, case -> required status
BASELINE_EXPECTED = {
    "A1": PROVED, "A2": UNPROVED, "A3": UNPROVED,
    "B1": PROVED, "B2": UNPROVED, "B3": UNPROVED,
    "C1": PROVED, "C2": UNPROVED, "C3": UNPROVED,
}

# P13: (case, conjunct index) -> (prefix status, classification)
MATRIX = {
    ("A1", 0): (PROVED, PREFIX_PROVED), ("A1", 1): (PROVED, PREFIX_PROVED),
    ("A2", 0): (PROVED, PREFIX_PROVED), ("A2", 1): (UNPROVED, NEWLY_UNPROVED),
    ("A3", 0): (UNPROVED, NEWLY_UNPROVED), ("A3", 1): (UNPROVED, BLOCKED),
    ("B1", 0): (PROVED, PREFIX_PROVED), ("B1", 1): (PROVED, PREFIX_PROVED),
    ("B2", 0): (PROVED, PREFIX_PROVED), ("B2", 1): (UNPROVED, NEWLY_UNPROVED),
    ("B3", 0): (UNPROVED, NEWLY_UNPROVED), ("B3", 1): (UNPROVED, BLOCKED),
    ("C1", 0): (PROVED, PREFIX_PROVED), ("C1", 1): (PROVED, PREFIX_PROVED),
    ("C2", 0): (PROVED, PREFIX_PROVED), ("C2", 1): (UNPROVED, NEWLY_UNPROVED),
    ("C3", 0): (UNPROVED, NEWLY_UNPROVED), ("C3", 1): (UNPROVED, BLOCKED),
}

# P10: nested F calls inside the Use_Nested Pre (outer F, inner F)
NESTED_CALLEE = "Guarded_Ops.Use_Nested"
NESTED_RULE = "VC_PRECONDITION"
NESTED_LOCATIONS = (("guarded_ops.ads", 29, 28), ("guarded_ops.ads", 29, 31))
# P10: guard well-definedness checks, callee entity -> rule
GUARD_RULES = {"Guarded_Ops.Use_Access": "VC_NULL_POINTER_DEREFERENCE",
               "Guarded_Ops.Use_Index": "VC_INDEX_CHECK"}


# ========================================================= prefix planner
class ProbeRefused(Exception):
    """The planner refuses a probe that is not a cumulative source prefix
    (Task 012's selected-only method on a guarded suffix)."""


def plan_prefixes(source: bytes, expr_range, conjuncts, operators
                  ) -> list[dict]:
    """Pure: the cumulative source-prefix plan of one Pre expression.

    `source` is the file's bytes, `expr_range` the [start, end) byte range
    of the Pre expression, `conjuncts` the ordered top-level conjuncts as
    {"text", "range": [start, end)} and `operators` the original top-level
    operators between them. Every prefix_text is the EXACT original source
    slice from the start of C0 through the end of Ci; nothing is rebuilt,
    normalised, reordered or converted between `and` and `and then`."""
    es, ee = expr_range
    if not conjuncts:
        raise ExperimentStop("planner: no conjuncts")
    if len(operators) != len(conjuncts) - 1:
        raise ExperimentStop(f"planner: {len(operators)} operators for "
                             f"{len(conjuncts)} conjuncts")
    if any(op not in (AND, AND_THEN) for op in operators):
        raise ExperimentStop(f"planner: unknown operator in {operators}")
    if conjuncts[0]["range"][0] != es or conjuncts[-1]["range"][1] != ee:
        raise ExperimentStop("planner: conjuncts do not span the Pre")
    prev_end = es
    for c in conjuncts:
        s, e = c["range"]
        if not (prev_end <= s < e <= ee):
            raise ExperimentStop("planner: conjuncts overlap or are not in "
                                 "source order")
        if source[s:e].decode("ascii") != c["text"]:
            raise ExperimentStop(f"planner: range of {c['text']!r} does not "
                                 "hold its text")
        prev_end = e
    c0 = conjuncts[0]["range"][0]
    plan = []
    for i, c in enumerate(conjuncts):
        plan.append({
            "conjunct_index": i,
            "conjunct_text": c["text"],
            "prefix_text": source[c0:c["range"][1]].decode("ascii"),
            "prefix_range": [c0, c["range"][1]],
            "operators": list(operators[:i]),
            "predecessor_index": i - 1 if i else None,
            "requires_predecessor": i > 0,
        })
    return plan


def request_probe(plan: list[dict], operators, kind: str, index: int
                  ) -> dict:
    """The ONLY way to schedule a probe. `kind` "prefix" returns the plan
    item. Any other kind (e.g. Task 012's "selected_only") is refused
    for every index > 0: a later conjunct is never evaluated outside the
    context of its preceding conjuncts."""
    if not (0 <= index < len(plan)):
        raise ProbeRefused(f"no conjunct {index}")
    if kind == "prefix":
        return plan[index]
    if index == 0:
        # C0 alone IS prefix 0; still scheduled only as the prefix item
        return plan[0]
    reason = ("guarded_and_then_suffix" if AND_THEN in operators[:index]
              else "not_a_prefix")
    raise ProbeRefused(f"{kind} probe of conjunct {index} refused: {reason}")


def refusal_record(plan: list[dict], operators, callee: str, index: int
                   ) -> dict:
    try:
        request_probe(plan, operators, "selected_only", index)
    except ProbeRefused as exc:
        return {"callee": callee, "conjunct_index": index,
                "requested": "selected_only", "refused": True,
                "reason": str(exc).rsplit(": ", 1)[-1]}
    return {"callee": callee, "conjunct_index": index,
            "requested": "selected_only", "refused": False, "reason": None}


def is_planned_prefix(text: str, plan: list[dict]) -> bool:
    return any(p["prefix_text"] == text for p in plan)


# ================================================ scratch transformation
def prefix_source(data: bytes, expr_range, item: dict) -> bytes:
    """Blank (newline-preserving) the bytes of the Pre expression AFTER
    the prefix; the prefix keeps its original bytes. The final prefix
    (the full Pre) leaves the file unchanged."""
    ps, pe = item["prefix_range"]
    es, ee = expr_range
    if ps != es or not (es < pe <= ee):
        raise ExperimentStop("prefix range is not a prefix of the Pre")
    if pe == ee:
        return data
    out = T12.overlay(data, pe, ee, "")
    if out[es:pe] != data[es:pe]:
        raise ExperimentStop("prefix bytes changed")
    return out


def isolation_problems(inv: dict, final_prefix: bool) -> list[str]:
    """P6 gate for one run (Task 012 inventory, this corpus's file)."""
    out = list(inv["problems"])
    if final_prefix:
        if inv["changed_file_count"] != 0:
            out.append(f"full-Pre run changed {inv['changed_files']}")
        return out
    if inv["changed_files"] != [MUTABLE_FILE]:
        out.append(f"changed files {inv['changed_files']}, expected "
                   f"[{MUTABLE_FILE!r}]")
    if inv["changed_range_count"] != 1:
        out.append(f"changed_range_count {inv['changed_range_count']}, "
                   "expected 1")
    if not (inv["length_preserved"] and inv["newlines_preserved"]):
        out.append("file length or newline layout not preserved")
    return out


# =============================================== structural VC reading
def _target(case: str) -> tuple:
    for t in TARGETS:
        if t[0] == case:
            return t
    raise KeyError(case)


def match_target(checks, case: str) -> dict:
    """Exactly one VC_PRECONDITION at the pre-registered call site of
    `case` (rule, client entity, file, line, column). Status is the
    loader's structural SARIF classification; `disputed` is its SARIF vs
    .spark consistency flag. Message text is never consulted."""
    _, ent, f, ln, col, _callee = _target(case)
    hits = [c for c in checks
            if c.rule == "VC_PRECONDITION" and c.entity == ent
            and c.location.file == f and c.location.line == ln
            and c.location.column == col]
    rec = {"case": case, "entity": ent,
           "location": {"file": f, "line": ln, "column": col},
           "matches": len(hits), "status": None, "disputed": None,
           "problem": None}
    if len(hits) != 1:
        rec["problem"] = ("no matching VC_PRECONDITION" if not hits else
                          f"{len(hits)} matching VC_PRECONDITION checks")
        return rec
    c = hits[0]
    rec["status"] = c.status.value
    rec["disputed"] = bool(c.disputed)
    if c.disputed:
        rec["problem"] = "SARIF and .spark disagree on this check"
    elif c.status.value == JUSTIFIED:
        rec["problem"] = "JUSTIFIED target"
    return rec


def _is_target(c) -> bool:
    return c.rule == "VC_PRECONDITION" and any(
        c.entity == ent and c.location.file == f and c.location.line == ln
        and c.location.column == col for _, ent, f, ln, col, _ in TARGETS)


def _check_rec(c) -> dict:
    return {"rule": c.rule, "entity": c.entity,
            "location": {"file": c.location.file, "line": c.location.line,
                         "column": c.location.column},
            "status": c.status.value, "disputed": bool(c.disputed)}


def _loc_key(r: dict) -> tuple:
    loc = r["location"]
    return (r["entity"], r["rule"], loc["file"] or "", loc["line"] or 0,
            loc["column"] or 0)


def check_inventory(checks) -> dict:
    """Every non-target check, recorded SEPARATELY from the targets:
    nested call preconditions inside a guarded callee's Pre (a
    VC_PRECONDITION whose entity is one of CALLEES), guard
    well-definedness checks, and everything else (leakage control)."""
    nested, guards, other = [], [], []
    for c in checks:
        if _is_target(c):
            continue
        r = _check_rec(c)
        if c.rule == NESTED_RULE and c.entity in CALLEES:
            nested.append(r)
        elif GUARD_RULES.get(c.entity) == c.rule:
            guards.append(r)
        else:
            other.append(r)
    return {"nested": sorted(nested, key=_loc_key),
            "guard": sorted(guards, key=_loc_key),
            "other": sorted(other, key=_loc_key)}


def nested_status(inv: dict, callee: str) -> str:
    """For the nested calls inside `callee`'s Pre in one run: proved |
    unproved (any unproved/justified/disputed) | absent."""
    mine = [r for r in inv["nested"] if r["entity"] == callee]
    if not mine:
        return "absent"
    if all(r["status"] == PROVED and not r["disputed"] for r in mine):
        return PROVED
    return UNPROVED


def inventory_problems(inv: dict, run: str) -> list[str]:
    """P10 expectations for one run (fail closed)."""
    out = []
    stray = [_loc_key(r) for r in inv["nested"]
             if r["entity"] != NESTED_CALLEE]
    if stray:
        out.append(f"{run}: unexpected nested call checks {stray}")
    nested_full = run != "use_nested_p0"
    locs = sorted((r["location"]["file"], r["location"]["line"],
                   r["location"]["column"]) for r in inv["nested"]
                  if r["entity"] == NESTED_CALLEE)
    if nested_full:
        if locs != sorted(NESTED_LOCATIONS):
            out.append(f"{run}: nested F checks at {locs}, pre-registered "
                       f"{list(NESTED_LOCATIONS)}")
    elif locs:
        out.append(f"{run}: nested F checks present in the C0-only run")
    for r in inv["nested"]:
        if r["status"] != PROVED or r["disputed"]:
            out.append(f"{run}: nested check {_loc_key(r)} {r['status']}")
    for ent, rule in GUARD_RULES.items():
        mine = [r for r in inv["guard"] if r["entity"] == ent]
        stem = ent.rsplit(".", 1)[1].lower()
        if run == f"{stem}_p0" and mine:
            out.append(f"{run}: {rule} present although the guarded "
                       "conjunct is absent")
        for r in mine:
            if r["status"] != PROVED or r["disputed"]:
                out.append(f"{run}: guard check {_loc_key(r)} {r['status']}")
    for r in inv["other"]:
        if r["status"] != PROVED or r["disputed"]:
            out.append(f"{run}: non-target check {_loc_key(r)} "
                       f"{r['status']}")
    return out


# ======================================================== classification
def classify(predecessor: dict | None, current: dict,
             nested: str = "absent") -> str:
    """P12. `predecessor` is None for conjunct 0 (conceptual TRUE)."""
    def valid(o):
        return (o is not None and o.get("matches") == 1
                and not o.get("problem") and not o.get("disputed")
                and o.get("status") in (PROVED, UNPROVED))
    if not valid(current):
        return INVALID
    if predecessor is None:
        pred = PROVED
    elif not valid(predecessor):
        return INVALID
    else:
        pred = predecessor["status"]
    if nested == UNPROVED:
        return NESTED_UNPROVED
    cur = current["status"]
    if pred == UNPROVED:
        return BLOCKED if cur == UNPROVED else INVALID
    return PREFIX_PROVED if cur == PROVED else NEWLY_UNPROVED


def run_name(callee: str | None, index: int | None) -> str:
    if callee is None:
        return "baseline"
    return f"{callee.rsplit('.', 1)[1].lower()}_p{index}"


RUN_NAMES = ("baseline", *(run_name(c, i) for c in CALLEES
                           for i in range(len(
                               EXPECTED_EXTRACTION[c]["conjuncts"]))))


def _find_case(targets, case):
    hits = [t for t in (targets or []) if t.get("case") == case]
    return hits[0] if len(hits) == 1 else None


def derive_probes(runs: list[dict]) -> list[dict]:
    """Per call occurrence x conjunct index, from the run records only.
    Each occurrence is read on its own (keyed by case / client entity /
    call location); its predecessor is the SAME occurrence's target in
    the run for prefix i-1."""
    by_run = {r.get("run"): r for r in runs}
    out = []
    for case, ent, f, ln, col, callee in TARGETS:
        n = len(EXPECTED_EXTRACTION[callee]["conjuncts"])
        for i in range(n):
            cur_run = by_run.get(run_name(callee, i)) or {}
            cur = _find_case(cur_run.get("targets"), case)
            prev = None
            if i:
                prev_run = by_run.get(run_name(callee, i - 1)) or {}
                prev = _find_case(prev_run.get("targets"), case) or {}
            inv = cur_run.get("inventory") or {}
            nested = [r for r in inv.get("nested") or []
                      if r.get("entity") == callee]
            ns = nested_status({"nested": nested}, callee)
            cls = classify(prev, cur or {}, ns)
            if cur_run.get("gate_problems", ["missing"]) or \
                    cur_run.get("reparse_problems", ["missing"]):
                cls = INVALID   # a run that failed a gate is never read
            out.append({
                "case": case, "entity": ent, "callee": callee,
                "location": {"file": f, "line": ln, "column": col},
                "conjunct_index": i,
                "conjunct_text": cur_run.get("conjunct_text"),
                "prefix_text": cur_run.get("prefix_text"),
                "run": run_name(callee, i),
                "predecessor_index": i - 1 if i else None,
                "predecessor_status": (PROVED if i == 0
                                       else (prev or {}).get("status")),
                "current_status": (cur or {}).get("status"),
                "classification": cls,
                "target_match_count": (cur or {}).get("matches", 0),
                "target_disputed": (cur or {}).get("disputed"),
                "nested_checks": nested,
                "nested_status": ns,
                "mutation": cur_run.get("mutation"),
            })
    return out


# ============================================================ decision
def _run_reasons(name: str, r: dict) -> tuple[list[str], int, int]:
    """Gates and target identity of one run: (reasons, justified,
    disputed)."""
    reasons, justified, disputed = [], 0, 0
    for key in ("gate_problems", "reparse_problems",
                "trust_hits_introduced", "inventory_problems"):
        v = r.get(key, ["missing"])
        if v:
            reasons.append(f"{name} {key}: {v}")
    for case in CASES:
        o = _find_case(r.get("targets"), case)
        if o is None:
            reasons.append(f"{name} {case}: no single outcome record")
            continue
        if o.get("status") == JUSTIFIED:
            justified += 1
        if o.get("disputed"):
            disputed += 1
        if o.get("matches") != 1 or o.get("problem"):
            reasons.append(f"{name} {case}: {o.get('problem')}")
    if name == "baseline":
        for case, want in BASELINE_EXPECTED.items():
            o = _find_case(r.get("targets"), case) or {}
            if o.get("status") != want:
                reasons.append(f"baseline {case}: {o.get('status')}, "
                               f"required {want}")
        return reasons, justified, disputed
    if r.get("scratch_pre_is_planned_prefix") is not True:
        reasons.append(f"{name}: scratch Pre is not a planned prefix")
    callee, idx = r.get("callee"), r.get("conjunct_index")
    if callee not in CALLEES or not isinstance(idx, int) or \
            run_name(callee, idx) != name:
        reasons.append(f"{name}: run identity {(callee, idx)}")
    want = EXPECTED_PREFIXES.get((callee, idx))
    if r.get("prefix_text") != want:
        reasons.append(f"{name}: prefix text {r.get('prefix_text')!r}, "
                       f"pre-registered {want!r}")
    for case, _e, _f, _l, _c, cal in TARGETS:
        if cal == callee:
            continue
        o = _find_case(r.get("targets"), case) or {}
        if o.get("status") != BASELINE_EXPECTED[case]:
            reasons.append(f"{name}: untouched target {case} is "
                           f"{o.get('status')}")
    return reasons, justified, disputed


def decide(evidence: dict) -> dict:
    """The frozen P14 decision rule. Probes are RE-DERIVED from the run
    records and must equal the recorded ones. Every missing field counts
    as a failure (fail closed)."""
    reasons: list[str] = list(evidence.get("stop_reasons") or [])
    runs = evidence.get("runs") or []
    by_run: dict = {}
    for r in runs:
        if r.get("run") in by_run:
            reasons.append(f"duplicate run {r.get('run')}")
        by_run[r.get("run")] = r
    missing = [n for n in RUN_NAMES if n not in by_run]
    if missing:
        reasons.append(f"missing runs {missing}")
    extra = sorted(str(n) for n in by_run if n not in RUN_NAMES)
    if extra:
        reasons.append(f"unexpected runs {extra}")

    justified = disputed = 0
    for name in RUN_NAMES:
        if name in by_run:
            rr, j, d = _run_reasons(name, by_run[name])
            reasons += rr
            justified += j
            disputed += d
    if justified:
        reasons.append(f"{justified} JUSTIFIED target result(s)")
    if disputed:
        reasons.append(f"{disputed} disputed target(s)")
    base = (by_run.get("baseline") or {}).get("targets")
    b_ok = 0
    for case, want in BASELINE_EXPECTED.items():
        o = _find_case(base, case) or {}
        if (o.get("status") == want and o.get("matches") == 1
                and not o.get("problem")):
            b_ok += 1

    probes = derive_probes(runs)
    if evidence.get("probes") != probes:
        reasons.append("recorded probes differ from the run records")
    status_ok = cls_ok = 0
    counts = {c: 0 for c in CLASSIFICATIONS}
    st_counts = {PROVED: 0, UNPROVED: 0, JUSTIFIED: 0}
    for p in probes:
        key = (p["case"], p["conjunct_index"])
        want_st, want_cls = MATRIX[key]
        counts[p["classification"]] += 1
        if p["current_status"] in st_counts:
            st_counts[p["current_status"]] += 1
        if p["current_status"] == want_st:
            status_ok += 1
        else:
            reasons.append(f"{key}: prefix status {p['current_status']}, "
                           f"pre-registered {want_st}")
        if p["classification"] == want_cls:
            cls_ok += 1
        else:
            reasons.append(f"{key}: classification {p['classification']}, "
                           f"pre-registered {want_cls}")

    refusals = evidence.get("refusals") or []
    for callee in CALLEES:
        for i in range(1, len(EXPECTED_EXTRACTION[callee]["conjuncts"])):
            rec = [x for x in refusals if x.get("callee") == callee
                   and x.get("conjunct_index") == i]
            if len(rec) != 1 or rec[0].get("refused") is not True:
                reasons.append(f"{callee}[{i}]: selected-only probe not "
                               "refused")

    if (evidence.get("trust_scan") or {}).get("original_hits", ["missing"]):
        reasons.append("committed corpus trust scan not clean")
    if evidence.get("corpus_unchanged") is not True:
        reasons.append("committed corpus changed or not verified")

    return {"baseline_matches": b_ok,
            "probe_observations": len(probes),
            "prefix_status_matches": status_ok,
            "classification_matches": cls_ok,
            "prefix_status_counts": st_counts,
            "classification_counts": counts,
            "justified": justified,
            "disputed": disputed,
            "gnatprove_runs": sum(1 for n in RUN_NAMES if n in by_run),
            "verdict": NOT_VALIDATED if reasons else VALIDATED,
            "reasons": reasons}


def canonical(evidence: dict) -> str:
    """Deterministic: sorted keys; runs in RUN_NAMES order; targets and
    probes in pre-registered TARGETS order."""
    ev = dict(evidence)
    order = {n: i for i, n in enumerate(RUN_NAMES)}
    corder = {c: i for i, c in enumerate(CASES)}

    def ckey(case):
        return corder.get(case, len(corder))
    ev["runs"] = sorted(
        ({**r, "targets": sorted(r.get("targets") or [],
                                 key=lambda o: ckey(o.get("case")))}
         for r in ev.get("runs") or []),
        key=lambda r: order.get(r.get("run"), len(order)))
    ev["probes"] = sorted(ev.get("probes") or [],
                          key=lambda p: (ckey(p.get("case")),
                                         p.get("conjunct_index", 0)))
    return json.dumps(ev, indent=2, sort_keys=True) + "\n"


# ===================================================== Libadalang layer
# Everything below imports libadalang lazily (through Task 012's layer);
# the pure helpers above and their tests work without it.
def _top_level(lal, expr) -> tuple[list, list[str]]:
    """Ordered top-level conjunct nodes and the ORIGINAL operators between
    them, from the BinOp tree (same traversal as Task 009's
    LalBackend.conjuncts)."""
    if (isinstance(expr, lal.BinOp)
            and isinstance(expr.f_op, (lal.OpAnd, lal.OpAndThen))):
        ln, lo = _top_level(lal, expr.f_left)
        rn, ro = _top_level(lal, expr.f_right)
        op = AND_THEN if isinstance(expr.f_op, lal.OpAndThen) else AND
        return ln + rn, lo + [op] + ro
    return [expr], []


def _range(data: bytes, node) -> list[int]:
    r = node.sloc_range
    return [T12.sloc_to_offset(data, r.start.line, r.start.column),
            T12.sloc_to_offset(data, r.end.line, r.end.column)]


def extract_pre(path: Path, callee: str) -> dict:
    """The explicit Pre of the ONE declaration of `callee` in `path`: its
    text, byte range, span, top-level conjuncts (text + byte range) and
    original operators. Raises ExperimentStop on any problem."""
    data = Path(path).read_bytes()
    T12.require_plain(Path(path).name, data)
    lal, unit = T12.parse_unit(path)
    if unit.diagnostics:
        raise ExperimentStop(f"{Path(path).name}: parse diagnostics "
                             f"{[str(d) for d in unit.diagnostics]}")
    decls = [d for d in unit.root.findall(lal.BasicSubpDecl)
             if d.p_fully_qualified_name == callee]
    if len(decls) != 1:
        raise ExperimentStop(f"{callee}: {len(decls)} declarations")
    aspect = decls[0].p_get_aspect("Pre")
    if not aspect.exists or aspect.value is None:
        raise ExperimentStop(f"{callee}: no explicit Pre")
    expr = aspect.value
    rng = _range(data, expr)
    if data[rng[0]:rng[1]].decode("ascii") != expr.text:
        raise ExperimentStop(f"{callee}: Pre byte range does not match the "
                             "Libadalang node text")
    nodes, ops = _top_level(lal, expr)
    task009 = [c.text for c in T12._decomposer(lal).conjuncts(expr)]
    if [n.text for n in nodes] != task009:
        raise ExperimentStop(f"{callee}: decomposition differs from "
                             "Task 009's")
    r = expr.sloc_range
    return {"callee": callee, "text": expr.text, "range": rng,
            "span": {"start_line": r.start.line,
                     "start_column": r.start.column,
                     "end_line": r.end.line, "end_column": r.end.column},
            "conjuncts": [{"text": n.text, "range": _range(data, n)}
                          for n in nodes],
            "operators": ops}


def reparse_problems(path: Path, callee: str, item: dict, plan: list,
                     others: dict) -> tuple[list[str], bool]:
    """P6 reparse gate. Returns (problems, scratch Pre is a planned
    prefix)."""
    try:
        pre = extract_pre(path, callee)
    except ExperimentStop as exc:
        return [str(exc)], False
    out = []
    planned = is_planned_prefix(pre["text"], plan)
    if pre["text"] != item["prefix_text"]:
        out.append(f"{callee}: scratch Pre {pre['text']!r}, expected "
                   f"{item['prefix_text']!r}")
    want = [c["conjunct_text"] for c in plan[:item["conjunct_index"] + 1]]
    if [c["text"] for c in pre["conjuncts"]] != want:
        out.append(f"{callee}: scratch conjuncts {pre['conjuncts']}")
    if pre["operators"] != item["operators"]:
        out.append(f"{callee}: scratch operators {pre['operators']}, "
                   f"expected {item['operators']}")
    for other, orig in others.items():
        try:
            o = extract_pre(path, other)
        except ExperimentStop as exc:
            out.append(str(exc))
            continue
        if (o["text"], o["span"]) != (orig["text"], orig["span"]):
            out.append(f"{other}: Pre changed in the scratch copy")
    return out, planned


def trust_scan(base: Path) -> list[dict]:
    """Task 012's structural forbidden-trust scan over THIS corpus."""
    return T12.trust_hits(T12.trust_records(
        Path(base) / rel for rel in COPIED_FILES
        if rel.endswith((".ads", ".adb"))))


# ========================================================= orchestration
def gnatprove(run_dir: Path) -> tuple[list, float, int]:
    """One fresh GNATprove run of <run_dir>/guarded.gpr in the pinned
    Alire environment. Returns (checks, wall seconds, loader consistency
    issue count). The exit code is
    NOT used for any outcome; only a missing SARIF stops the experiment."""
    T12.reset_dir(run_dir / "obj", SCRATCH_ROOT)
    prefix = shlex.split(os.environ.get("GNATPROVE_EXEC", "alr -n exec --"))
    cmd = [*prefix, "gnatprove", "-P", str(run_dir / "guarded.gpr"),
           *PROVE_ARGS]
    print(f"$ (cd {RB.relative_to(REPO)} && {shlex.join(cmd)})", flush=True)
    start = time.monotonic()
    log = run_dir / "gnatprove.log"
    with log.open("wb") as fh:
        subprocess.run(cmd, cwd=RB, stdout=fh, stderr=subprocess.STDOUT)
    wall = time.monotonic() - start
    out = run_dir / "obj" / "gnatprove"
    if not (out / "gnatprove.sarif").is_file():
        tail = log.read_text("utf-8", errors="replace").splitlines()[-30:]
        raise ExperimentStop(f"{run_dir.name}: GNATprove produced no SARIF\n"
                             + "\n".join(tail))
    run = load_run(out, name=run_dir.name)
    if run.tool_version != GNATPROVE_VERSION:
        raise ExperimentStop(f"{run_dir.name}: GNATprove "
                             f"{run.tool_version!r}, pinned "
                             f"{GNATPROVE_VERSION!r}")
    return run.checks, wall, len(run.consistency_issues)


def _preconditions() -> tuple[dict, dict, dict, dict]:
    """Corpus identity (P3), extraction (P4) and plans (P5), before any
    proof run."""
    before = T12.tree_digest(CORPUS)
    if before != CORPUS_SHA256:
        raise ExperimentStop(f"committed corpus differs from the "
                             f"pre-registered sha256: {before}")
    original = T12.read_tree(CORPUS, COPIED_FILES)
    for rel, data in original.items():
        T12.require_plain(rel, data)
    src = original[MUTABLE_FILE]
    pres, plans = {}, {}
    for callee, want in EXPECTED_EXTRACTION.items():
        p = extract_pre(CORPUS / MUTABLE_FILE, callee)
        got = {"conjuncts": tuple(c["text"] for c in p["conjuncts"]),
               "operators": tuple(p["operators"]),
               "span": tuple(p["span"][k] for k in (
                   "start_line", "start_column", "end_line",
                   "end_column"))}
        if got != want:
            raise ExperimentStop(f"{callee}: extracted {got}, "
                                 f"pre-registered {want}; STOP")
        pres[callee] = p
        plans[callee] = plan_prefixes(src, p["range"], p["conjuncts"],
                                      p["operators"])
        for item in plans[callee]:
            key = (callee, item["conjunct_index"])
            if item["prefix_text"] != EXPECTED_PREFIXES[key]:
                raise ExperimentStop(f"{key}: planned prefix "
                                     f"{item['prefix_text']!r}, "
                                     "pre-registered; STOP")
    return before, original, pres, plans


def _targets(checks) -> list[dict]:
    return [match_target(checks, case) for case in CASES]


def make_run(original: dict, pres: dict, plans: dict, callee: str | None,
             index: int | None, original_hits: list) -> tuple[dict, Path]:
    """Build one isolated scratch project and its gate evidence."""
    name = run_name(callee, index)
    d = T12.reset_dir(SCRATCH_ROOT / name, SCRATCH_ROOT)
    T12.copy_corpus(CORPUS, d, files=COPIED_FILES, root=SCRATCH_ROOT)
    rec: dict = {"run": name, "targets": []}
    if callee is None:
        inv = T12.mutation_inventory(original,
                                     T12.read_tree(d, COPIED_FILES), {})
        rec["gate_problems"] = (list(inv["problems"])
                                + ([] if inv["changed_file_count"] == 0
                                   else [f"baseline changed "
                                         f"{inv['changed_files']}"]))
        rec["reparse_problems"] = []
    else:
        item = plans[callee][index]
        es, ee = pres[callee]["range"]
        target = d / MUTABLE_FILE
        target.write_bytes(prefix_source(target.read_bytes(), (es, ee),
                                         item))
        final = item["prefix_range"][1] == ee
        allowed = {} if final else {MUTABLE_FILE: [(item["prefix_range"][1],
                                                    ee)]}
        inv = T12.mutation_inventory(original,
                                     T12.read_tree(d, COPIED_FILES), allowed)
        others = {c: pres[c] for c in CALLEES if c != callee}
        reparse, planned = reparse_problems(target, callee, item,
                                            plans[callee], others)
        rec.update({
            "callee": callee, "conjunct_index": index,
            "conjunct_text": item["conjunct_text"],
            "prefix_text": item["prefix_text"],
            "operators": item["operators"],
            "full_pre": final,
            "scratch_pre_is_planned_prefix": planned,
            "reparse_problems": reparse,
            "gate_problems": isolation_problems(inv, final),
        })
    rec["mutation"] = {
        "changed_files": inv["changed_files"],
        "changed_file_count": inv["changed_file_count"],
        "changed_range_count": inv["changed_range_count"],
        "length_preserved": inv["length_preserved"],
        "newlines_preserved": inv["newlines_preserved"]}
    rec["trust_hits_introduced"] = T12.introduced_hits(original_hits,
                                                       trust_scan(d))
    return rec, d


def experiment() -> tuple[dict, dict]:
    """Run the whole pre-registered experiment. Returns (evidence, timing);
    timing is measurement only and kept out of evidence.json."""
    timing: dict[str, float] = {}
    t0 = time.monotonic()
    before, original, pres, plans = _preconditions()
    original_hits = trust_scan(CORPUS)
    refusals = [refusal_record(plans[c], pres[c]["operators"], c, i)
                for c in CALLEES for i in range(1, len(plans[c]))]
    evidence = {
        "experiment": EXPERIMENT, "method": METHOD, "scope": SCOPE,
        "gnatprove": GNATPROVE_VERSION,
        "gnatprove_switches": [*PROJECT_PROOF_SWITCHES, *PROVE_ARGS],
        "corpus": CORPUS_REL,
        "copied_files": list(COPIED_FILES),
        "corpus_sha256": dict(sorted(CORPUS_SHA256.items())),
        "extraction": {c: {"text": p["text"], "span": p["span"],
                           "conjuncts": [x["text"] for x in p["conjuncts"]],
                           "operators": p["operators"]}
                       for c, p in sorted(pres.items())},
        "plans": {c: [{k: v for k, v in it.items() if k != "prefix_range"}
                      for it in plan]
                  for c, plan in sorted(plans.items())},
        "refusals": refusals,
        "trust_scan": {"original_hits": original_hits},
        "runs": [],
    }
    order = [(None, None)] + [(c, it["conjunct_index"])
                              for c in CALLEES for it in plans[c]]
    for callee, index in order:
        rec, d = make_run(original, pres, plans, callee, index,
                          original_hits)
        if not (rec["gate_problems"] or rec["reparse_problems"]
                or rec["trust_hits_introduced"]):
            # a scratch program that failed a gate is never proved
            checks, timing[rec["run"]], n_issues = gnatprove(d)
            # recorded only (P9: a disputed TARGET invalidates the probe)
            rec["loader_consistency_issue_count"] = n_issues
            rec["targets"] = _targets(checks)
            rec["inventory"] = check_inventory(checks)
            rec["inventory_problems"] = inventory_problems(
                rec["inventory"], rec["run"])
        else:
            rec["inventory"] = {"nested": [], "guard": [], "other": []}
            rec["inventory_problems"] = ["run not proved: gate failed"]
        evidence["runs"].append(rec)

    evidence["probes"] = derive_probes(evidence["runs"])
    evidence["nested_checks"] = [
        {"run": r["run"], **n} for r in evidence["runs"]
        for n in (r.get("inventory") or {}).get("nested", [])]
    evidence["corpus_unchanged"] = T12.tree_digest(CORPUS) == before
    evidence["summary"] = decide(evidence)
    timing["gnatprove_runs_total"] = sum(timing.values())
    timing["gnatprove_runs"] = len(timing) - 1
    timing["experiment_total"] = time.monotonic() - t0
    return evidence, {k: round(v, 1) for k, v in timing.items()}


def _print_matrix(ev: dict) -> None:
    base = next((r for r in ev["runs"] if r["run"] == "baseline"), {})
    print("baseline (unmodified scratch copy, full Pre):")
    for o in base.get("targets", []):
        loc = o["location"]
        print(f"  {o['case']}  {o['entity']:<36} {loc['file']}:"
              f"{loc['line']}:{loc['column']}  {str(o['status']).upper()}")
    print("prefix probes:")
    for p in ev["probes"]:
        print(f"  {p['case']} c{p['conjunct_index']}  pred "
              f"{str(p['predecessor_status']).upper():<8} cur "
              f"{str(p['current_status']).upper():<8} "
              f"{p['classification']}")
    print("nested-call checks:")
    for n in ev["nested_checks"]:
        loc = n["location"]
        print(f"  {n['run']:<14} {n['rule']} {n['entity']} {loc['file']}:"
              f"{loc['line']}:{loc['column']} {n['status'].upper()}")
    s = ev["summary"]
    print(f"summary: baseline {s['baseline_matches']}/9, observations "
          f"{s['probe_observations']}, status matches "
          f"{s['prefix_status_matches']}/18, classification matches "
          f"{s['classification_matches']}/18, justified {s['justified']}, "
          f"disputed {s['disputed']}")
    print(f"classifications: {json.dumps(s['classification_counts'])}")
    for r in s["reasons"]:
        print(f"  reason: {r}")
    print(f"verdict: {s['verdict']}")


def main(argv: list[str]) -> int:
    if argv:
        print(__doc__)
        return 2
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        evidence, timing = experiment()
    except ExperimentStop as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    (SCRATCH_ROOT / "evidence.json").write_text(canonical(evidence),
                                                encoding="utf-8")
    (SCRATCH_ROOT / "timing.json").write_text(
        json.dumps(timing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print_matrix(evidence)
    print(f"wall seconds: {json.dumps(timing, sort_keys=True)}")
    print(f"evidence: {(SCRATCH_ROOT / 'evidence.json').relative_to(REPO)}")
    return 0 if evidence["summary"]["verdict"] == VALIDATED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
