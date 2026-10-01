#!/usr/bin/env python3
"""Task 014: Ada call-binding conjunct re-proof EXPERIMENT (not a product).

  cd examples/ring_buffer
  PYTHONPATH=<lal bundle> alr -n exec -- \\
      python3 ../../diagnostics/scripts/call_binding_reproof_experiment.py

Pre-registration: docs/tasks/014-ada-call-binding-reproof.md.

For the committed corpus (tests/experiments/task014_call_binding):

  1. Libadalang resolves every pre-registered call anchor to its callee
     declaration and applicable explicit contract (Pre, or Pre'Class for
     the dispatching call), and the result must equal the frozen
     resolution_manifest.json BEFORE any proof run.
  2. The Task 013 planner produces cumulative SOURCE PREFIXES of each
     resolved contract (exact original bytes, operators preserved).
  3. One unmodified control runs, then one scratch copy per callee
     prefix. Only the resolved callee's contract suffix is blanked
     (newline-preserving); every caller stays byte-identical, so Ada /
     GNATprove performs the actual/formal binding. Nothing here parses
     association lists or substitutes actuals for formals.
  4. In every scratch copy every call anchor must still resolve to its
     frozen callee (semantic identity); every target VC_PRECONDITION is
     read structurally (exactly one match, SARIF status, .spark
     consistency); every other check is inventoried separately
     (conversion checks of A7/A8 are auxiliary obligations).
  5. Per-occurrence prefix transitions are classified, the frozen
     per-family and overall decision rules are applied, and
     evidence.json is written.

Scratch results are evidence about SCRATCH programs only. GNATprove stays
the proof authority; Libadalang only identifies calls and declarations.
No prover message text is read.

Exit status: 0 iff CALL_BINDING_METHOD_VALIDATED_ON_PREREGISTERED_
SUPPORTED_CASES; 1 for CALL_BINDING_METHOD_NOT_VALIDATED; 2 if a
precondition (corpus identity, manifest, extraction) stops the experiment.
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


def _load_task013():
    """The Task 013 experiment module, unchanged (it loads Task 012's).
    Only its pure planner / prefix transformation and Task 012's
    filesystem, overlay, inventory and trust helpers are used."""
    path = Path(__file__).resolve().parent / "guarded_reproof_experiment.py"
    spec = importlib.util.spec_from_file_location("task013_reproof", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T13 = _load_task013()
T12 = T13.T12
ExperimentStop = T12.ExperimentStop
ProbeRefused = T13.ProbeRefused

CORPUS = DIAGNOSTICS / "tests" / "experiments" / "task014_call_binding"
CORPUS_REL = "diagnostics/tests/experiments/task014_call_binding"
SCRATCH_ROOT = DIAGNOSTICS / "obj" / "task014-call-binding-reproof"
RB = REPO / "examples" / "ring_buffer"  # pinned toolchain crate (as 012/013)
PROJECT = "call_binding.gpr"
MANIFEST = "resolution_manifest.json"

EXPERIMENT = "task014_ada_call_binding_conjunct_reproof"
METHOD = "resolved_callee_contract_prefix_reproof"
SCOPE = "preregistered_call_binding_corpus"
GNATPROVE_VERSION = "FSF 16.1.0"
VALIDATED = "CALL_BINDING_METHOD_VALIDATED_ON_PREREGISTERED_SUPPORTED_CASES"
NOT_VALIDATED = "CALL_BINDING_METHOD_NOT_VALIDATED"
FAMILY_VALIDATED, FAMILY_NOT_VALIDATED, FAMILY_UNSUPPORTED = (
    "VALIDATED", "NOT_VALIDATED", "UNSUPPORTED")
PROVE_ARGS = ("-j0",)  # + the project's Proof_Switches (P8)
PROJECT_PROOF_SWITCHES = ("-U", "--mode=all", "--level=2",
                          "--report=statistics")

SOURCES = ("src/binding_client.adb", "src/binding_client.ads",
           "src/binding_generic.adb", "src/binding_generic.ads",
           "src/binding_int_ops.ads", "src/binding_ops.adb",
           "src/binding_ops.ads", "src/binding_shapes.adb",
           "src/binding_shapes.ads")
# copied into every scratch program; the manifest is NOT copied (P6)
COPIED_FILES = (PROJECT, *SOURCES)
CLIENT_BODY = "src/binding_client.adb"

# P3: committed corpus identity (manifest included)
CORPUS_SHA256 = {
    "call_binding.gpr":
        "eae698e45051e8471b61ce39c8c49ccb99c693fbb88b30159e81a981638cab94",
    "resolution_manifest.json":
        "e3c67f1a38b20ec32fd3c70ae8907f1235554a39793918e23fb6b7a2f57d3b90",
    "src/binding_client.adb":
        "9ff3f3cbf3c39969396d378bb91a2daa47643a2ab54e76bd270b752497556292",
    "src/binding_client.ads":
        "0cef4392124819daa5280e25634897473d7ca1dc9262d232e0974f4a858510a2",
    "src/binding_generic.adb":
        "55a198ec310788b4aa8c8d18e7e66805f6bf1c851dce7cf219a115037bda4302",
    "src/binding_generic.ads":
        "4f3f23d5de39c2c037a88de7fd83f4db39e995340a908b9f3ef0b0fdd9979db4",
    "src/binding_int_ops.ads":
        "ae94ebb225a95e166f794971cff2d21a1409b3a7cd07e0af573a55825a2475c1",
    "src/binding_ops.adb":
        "098d479b3ff93d09fa9c2fc924ad4e5a002c58f39359da34e8a23e5412e4ee4d",
    "src/binding_ops.ads":
        "924f0bbeca65b4884d254f0718c4d52c2dcd6be37c33f62b54c91b24d2653df0",
    "src/binding_shapes.adb":
        "9ecc62448438b1041578ef19979bd411c05b30859905b8ca46cd9c932ab00c5d",
    "src/binding_shapes.ads":
        "2a5f765b4d7cb7451b68f7cb57481df95aee1167e92316dd15fbcf8067fd4c90",
}


PROVED, UNPROVED, JUSTIFIED = "proved", "unproved", "justified"
PREFIX_PROVED, NEWLY_UNPROVED = "prefix_proved", "newly_unproved"
BLOCKED = "blocked_by_earlier_prefix"
AUX = "auxiliary_obligation_unproved"
INVALID = "invalid_probe"
# Frozen P11/P13 expectations, in manifest occurrence order.
SIGNATURES = (
    "PPP", "PUU", "PPU", "UUU", "PPP", "PPU", "PPU", "PPP",
    "PP", "PU", "UU", "PP", "PU", "UU", "PP", "PU", "UU",
    "PP", "PU", "UU", "PP", "PU", "UU", "PP", "PU", "UU")
BASELINE = ("P", "U", "U", "U", "P", "U", "U", "P",
            "P", "U", "U", "P", "U", "U", "P", "U", "U",
            "P", "U", "U", "P", "U", "U", "P", "U", "U")
SHORT = {"P": PROVED, "U": UNPROVED}
EXPECT_CLASS = {"P": PREFIX_PROVED, "N": NEWLY_UNPROVED,
                "B": BLOCKED, "A": AUX}
CLASS_SIGNATURES = (
    "PPP", "PNB", "PPN", "NBB", "PPP", "PPN", "PPN", "AAA",
    "PP", "PN", "NB", "PP", "PN", "NB", "PP", "PN", "NB",
    "PP", "PN", "NB", "PP", "PN", "NB", "PP", "PN", "NB")


def run_name(callee, index):
    return "baseline" if callee is None else f"{callee}_p{index}"


def span(node):
    r = node.sloc_range
    return {"file": "src/" + Path(node.unit.filename).name,
            "start_line": r.start.line, "start_column": r.start.column,
            "end_line": r.end.line, "end_column": r.end.column}


def resolve(base: Path, manifest: dict, mutated: str | None = None):
    """Resolve every call anew in its project; never bind actuals locally."""
    import libadalang as lal
    from spark_refine_diagnostics.semantic_lal import LalBackend

    ctx = lal.GPRProject(str(base / PROJECT), print_errors=False).create_context()
    units = [ctx.get_from_file(str(base / rel)) for rel in SOURCES]
    for unit in units:
        if unit.diagnostics:
            raise ExperimentStop(f"{Path(unit.filename).name}: {unit.diagnostics}")
    client = ctx.get_from_file(str(base / CLIENT_BODY))
    backend = LalBackend.__new__(LalBackend)
    backend.lal = lal
    calls = client.root.findall(lal.CallStmt)
    if len(calls) != len(manifest["occurrences"]):
        raise ExperimentStop(f"call count: {len(calls)}")
    observations = []
    for call, expected in zip(calls, manifest["occurrences"]):
        expr = call.f_call
        line, column = backend._anchor(expr.f_name)
        hits, err = backend.calls_at(client, line, column)
        if err or len(hits) != 1:
            raise ExperimentStop(f"{expected['case']}: call resolution {err}")
        decl = hits[0][1].p_referenced_decl()
        uninst = decl.p_get_uninstantiated_node
        inst = [span(n) for n in decl.p_generic_instantiations]
        overrides = [{"declaration": span(n),
                      "fully_qualified_name": n.p_fully_qualified_name,
                      "aspects": [a.f_id.text for a in n.findall(lal.AspectAssoc)]}
                     for n in decl.p_find_all_overrides(units)]
        relationship = {
            "uninstantiated_declaration": {
                "declaration": span(uninst),
                "fully_qualified_name": uninst.p_fully_qualified_name},
            "generic_instantiations": inst,
            "overriding_declarations": overrides,
            "other_precondition_aspect_present":
                decl.p_get_aspect("Pre" if expr.p_is_dispatching_call()
                                  else "Pre'Class").exists}
        cal = manifest["callees"][expected["callee"]]
        for key, value in relationship.items():
            if value != cal[key]:
                raise ExperimentStop(f"{expected['case']}: {key} changed")
        if decl.p_fully_qualified_name != cal["fully_qualified_name"]:
            raise ExperimentStop(f"{expected['case']}: callee name changed")
        aspect = "Pre'Class" if expr.p_is_dispatching_call() else "Pre"
        a = decl.p_get_aspect(aspect)
        if not a.exists or a.inherited or a.value is None:
            raise ExperimentStop(f"{expected['case']}: no explicit {aspect}")
        enc = call.parent
        while not isinstance(enc, lal.SubpBody):
            enc = enc.parent
        identity = {"case": expected["case"],
                    "call": {"file": "binding_client.adb", "line": line,
                             "column": column, "span": span(expr),
                             "text": expr.text},
                    "client_entity": enc.p_fully_qualified_name,
                    "callee": expected["callee"],
                    "unique_identifying_name": decl.p_unique_identifying_name,
                    "declaration": span(decl), "contract_aspect": aspect,
                    "dispatching_call": bool(expr.p_is_dispatching_call()),
                    "contract_span": span(a.value)}
        want = {"case": expected["case"], "call": expected["call"],
                "client_entity": expected["client_entity"],
                "callee": expected["callee"],
                "unique_identifying_name": cal["unique_identifying_name"],
                "declaration": cal["declaration"],
                "contract_aspect": cal["contract_aspect"],
                "dispatching_call": cal["dispatching_call"],
                "contract_span": cal["contract"]["span"]}
        if mutated == expected["callee"]:
            identity.pop("contract_span")
            want.pop("contract_span")
        if identity != want:
            raise ExperimentStop(f"{expected['case']}: resolution changed: "
                                 f"{identity!r} != {want!r}")
        observations.append(expected["case"])
    return observations


def extract(base: Path, manifest: dict, callee: str):
    import libadalang as lal
    frozen = manifest["callees"][callee]
    rel = frozen["mutable_file"]
    data = (base / rel).read_bytes()
    unit = lal.AnalysisContext().get_from_file(str(base / rel))
    if unit.diagnostics:
        raise ExperimentStop(f"{rel}: {unit.diagnostics}")
    candidates = [n for n in unit.root.findall(lal.BasicSubpDecl)
                  if span(n) == frozen["declaration"]]
    if len(candidates) != 1:
        raise ExperimentStop(f"{callee}: declaration not unique")
    a = candidates[0].p_get_aspect(frozen["contract_aspect"])
    if not a.exists or a.inherited or a.value is None:
        raise ExperimentStop(f"{callee}: missing explicit contract")
    expr = a.value
    nodes, ops = T13._top_level(lal, expr)
    if [n.text for n in nodes] != [n.text for n in T12._decomposer(lal).conjuncts(expr)]:
        raise ExperimentStop(f"{callee}: Task 009 decomposition differs")
    rng = T13._range(data, expr)
    if data[rng[0]:rng[1]].decode("ascii") != expr.text:
        raise ExperimentStop(f"{callee}: source does not match contract")
    return {"text": expr.text, "span": span(expr), "range": rng,
            "conjuncts": [{"text": n.text, "range": T13._range(data, n)}
                          for n in nodes], "operators": ops}


def preconditions():
    before = T12.tree_digest(CORPUS)
    if before != CORPUS_SHA256:
        raise ExperimentStop("committed corpus differs from frozen sha256")
    manifest = json.loads((CORPUS / MANIFEST).read_text("utf-8"))
    if manifest["resolver"] != "libadalang 26.0.0":
        raise ExperimentStop("resolver version differs")
    resolve(CORPUS, manifest)
    original = T12.read_tree(CORPUS, COPIED_FILES)
    for rel, data in original.items():
        T12.require_plain(rel, data)
    pres, plans = {}, {}
    for callee, frozen in manifest["callees"].items():
        p = extract(CORPUS, manifest, callee)
        if (p["text"] != frozen["contract"]["text"] or
                p["span"] != frozen["contract"]["span"] or
                [x["text"] for x in p["conjuncts"]] != frozen["conjuncts"] or
                p["operators"] != frozen["operators"]):
            raise ExperimentStop(f"{callee}: extraction differs from manifest")
        plan = T13.plan_prefixes(original[frozen["mutable_file"]], p["range"],
                                 p["conjuncts"], p["operators"])
        if [x["prefix_text"] for x in plan] != frozen["prefix_texts"]:
            raise ExperimentStop(f"{callee}: prefix differs from P5")
        pres[callee], plans[callee] = p, plan
    return before, manifest, original, pres, plans


def target(checks, occ):
    call = occ["call"]
    hits = [c for c in checks if c.rule == "VC_PRECONDITION"
            and c.entity == occ["client_entity"]
            and (c.location.file, c.location.line, c.location.column) ==
            (call["file"], call["line"], call["column"])]
    rec = {"case": occ["case"], "matches": len(hits), "status": None,
           "disputed": None, "problem": None}
    if len(hits) != 1:
        rec["problem"] = f"expected one structural target, got {len(hits)}"
    else:
        c = hits[0]
        rec["status"], rec["disputed"] = c.status.value, bool(c.disputed)
        if c.disputed or c.status.value == JUSTIFIED:
            rec["problem"] = "disputed or justified target"
    return rec


def inventory(checks, manifest):
    anchors = {(o["client_entity"], o["call"]["file"],
                o["call"]["line"], o["call"]["column"])
               for o in manifest["occurrences"]}
    result = {"conversion_A7": [], "conversion_A8": [], "other": []}
    entities = {o["case"]: o["client_entity"] for o in manifest["occurrences"]}
    for c in checks:
        loc = c.location
        if (c.rule == "VC_PRECONDITION" and
                (c.entity, loc.file, loc.line, loc.column) in anchors):
            continue
        rec = {"rule": c.rule, "entity": c.entity,
               "location": {"file": loc.file, "line": loc.line,
                            "column": loc.column}, "status": c.status.value,
               "disputed": bool(c.disputed)}
        key = "other"
        if (c.rule in ("VC_RANGE_CHECK", "VC_OVERFLOW_CHECK") and
                loc.file == "binding_client.adb" and
                20 <= (loc.column or 0) <= 30):
            for case, line in (("A7", 37), ("A8", 43)):
                if c.entity == entities[case] and loc.line == line:
                    key = "conversion_" + case
        result[key].append(rec)
    for records in result.values():
        records.sort(key=lambda r: (r["entity"] or "", r["rule"],
                                     r["location"]["file"] or "",
                                     r["location"]["line"] or 0,
                                     r["location"]["column"] or 0))
    return result


def inventory_problems(inv):
    problems = []
    for case in ("A7", "A8"):
        checks = inv["conversion_" + case]
        if not checks or any(r["disputed"] or r["status"] == JUSTIFIED
                             for r in checks):
            problems.append(f"{case}: conversion checks missing/disputed/justified")
        if case == "A7" and any(r["status"] != PROVED for r in checks):
            problems.append("A7: conversion not proved")
        if case == "A8" and not any(r["status"] == UNPROVED for r in checks):
            problems.append("A8: no unproved conversion")
    if any(r["status"] != PROVED or r["disputed"] for r in inv["other"]):
        problems.append("non-target check not proved or disputed")
    return problems


def classify(previous, current, auxiliary=False):
    def valid(r):
        return (r is not None and r.get("matches") == 1 and
                not r.get("problem") and not r.get("disputed") and
                r.get("status") in (PROVED, UNPROVED))
    if not valid(current) or (previous is not None and not valid(previous)):
        return INVALID
    if auxiliary:
        return AUX
    pred = PROVED if previous is None else previous["status"]
    if pred == UNPROVED:
        return BLOCKED if current["status"] == UNPROVED else INVALID
    return PREFIX_PROVED if current["status"] == PROVED else NEWLY_UNPROVED


def trust_scan(base):
    return T12.trust_hits(T12.trust_records(base / rel for rel in SOURCES))




def make_run(original, manifest, pres, plans, callee, index, original_hits):
    name = run_name(callee, index)
    d = T12.reset_dir(SCRATCH_ROOT / name, SCRATCH_ROOT)
    T12.copy_corpus(CORPUS, d, files=COPIED_FILES, root=SCRATCH_ROOT)
    allowed = {}
    rec = {"run": name, "callee": callee, "conjunct_index": index,
           "targets": []}
    if callee is not None:
        p, item = pres[callee], plans[callee][index]
        rel = manifest["callees"][callee]["mutable_file"]
        file = d / rel
        file.write_bytes(T13.prefix_source(file.read_bytes(), p["range"], item))
        if item["prefix_range"][1] != p["range"][1]:
            allowed[rel] = [(item["prefix_range"][1], p["range"][1])]
        rec.update(prefix_text=item["prefix_text"],
                   conjunct_text=item["conjunct_text"],
                   operators=item["operators"])
    inv = T12.mutation_inventory(original, T12.read_tree(d, COPIED_FILES), allowed)
    rec["mutation"] = inv
    rec["gate_problems"] = list(inv["problems"])
    expected = 0 if not allowed else 1
    if inv["changed_file_count"] != expected or inv["changed_range_count"] != expected:
        rec["gate_problems"].append("source isolation count differs")
    rec["reparse_problems"] = []
    if callee is not None:
        p2 = extract(d, manifest, callee)
        item = plans[callee][index]
        if (p2["text"] != item["prefix_text"] or
                [x["text"] for x in p2["conjuncts"]] !=
                [x["text"] for x in p["conjuncts"][:index + 1]] or
                p2["operators"] != item["operators"]):
            rec["reparse_problems"].append("scratch contract differs from plan")
        for other in manifest["callees"]:
            if other != callee and extract(d, manifest, other)["text"] != pres[other]["text"]:
                rec["reparse_problems"].append(f"{other}: crossed contract")
    try:
        rec["resolution"] = resolve(d, manifest, callee)
    except ExperimentStop as exc:
        rec["reparse_problems"].append(str(exc))
        rec["resolution"] = []
    rec["trust_hits_introduced"] = T12.introduced_hits(original_hits, trust_scan(d))
    return rec, d


def gnatprove(d):
    T12.reset_dir(d / "obj", SCRATCH_ROOT)
    prefix = shlex.split(os.environ.get("GNATPROVE_EXEC", "alr -n exec --"))
    cmd = [*prefix, "gnatprove", "-P", str(d / PROJECT), *PROVE_ARGS]
    print(f"$ (cd {RB.relative_to(REPO)} && {shlex.join(cmd)})", flush=True)
    start = time.monotonic()
    log = d / "gnatprove.log"
    with log.open("wb") as fh:
        subprocess.run(cmd, cwd=RB, stdout=fh, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - start
    out = d / "obj" / "gnatprove"
    if not (out / "gnatprove.sarif").is_file():
        raise ExperimentStop(f"{d.name}: no SARIF: " +
                             "\n".join(log.read_text(errors="replace").splitlines()[-20:]))
    run = load_run(out, name=d.name)
    if run.tool_version != GNATPROVE_VERSION:
        raise ExperimentStop(f"{d.name}: unexpected GNATprove {run.tool_version}")
    return run.checks, elapsed, len(run.consistency_issues), len(run.warnings)


def decide(ev):
    manifest = ev["manifest"]
    occurrences = manifest["occurrences"]
    runs = {r["run"]: r for r in ev["runs"]}
    reasons = []
    family_reasons = {f: [] for f in "ABCDEF"}

    def fail(family, message):
        reasons.append(message)
        family_reasons[family].append(message)

    expected_names = {"baseline"} | {
        run_name(c, i) for c, p in ev["plans"].items() for i in range(len(p))}
    if (set(runs) != expected_names or len(runs) != len(expected_names) or
            len(occurrences) != 26 or len(manifest["callees"]) != 7 or
            len(ev["plans"]) != 7 or
            [o["case"] for o in occurrences] !=
            [f"{f}{i}" for f, count in (("A", 8), ("B", 3), ("C", 3),
                                         ("D", 6), ("E", 3), ("F", 3))
             for i in range(1, count + 1)] or
            {c: len(p) for c, p in ev["plans"].items()} !=
            {c: m["prefix_count"] for c, m in manifest["callees"].items()}):
        for f in family_reasons:
            fail(f, "run set differs from frozen 16 programs")
    if (ev.get("trust_scan", {}).get("original_hits") or
            not ev.get("corpus_unchanged") or
            ev.get("corpus_sha256") != CORPUS_SHA256):
        for f in family_reasons:
            fail(f, "corpus identity or trust gate failed")
    expected_refusals = {(c, i) for c, plan in ev["plans"].items()
                         for i in range(1, len(plan))}
    if (any(not r.get("refused") or r.get("requested") != "selected_only"
            for r in ev.get("refusals", [])) or
            {(r.get("callee"), r.get("conjunct_index"))
             for r in ev.get("refusals", [])} != expected_refusals or
            len(ev.get("refusals", [])) != 8):
        for f in family_reasons:
            fail(f, "selected-only suffix not refused")
    for r in ev["runs"]:
        affected = "ABCDEF" if r["callee"] is None else manifest["callees"][r["callee"]]["family"]
        if (r.get("gate_problems") is None or
                r.get("reparse_problems") is None or
                r.get("trust_hits_introduced") is None or
                r.get("inventory_problems") is None or
                r.get("gate_problems") or r.get("reparse_problems") or
                r.get("trust_hits_introduced") or
                r.get("resolution") != [o["case"] for o in occurrences] or
                r.get("inventory_problems") or
                not r.get("inventory") or not r.get("mutation") or
                r.get("loader_consistency_issue_count") is None):
            for f in affected:
                fail(f, f"{r['run']}: source/resolution/auxiliary gate")
        if (len(r["targets"]) != 26 or
                [t["case"] for t in r["targets"]] !=
                [o["case"] for o in occurrences] or
                any(t["matches"] != 1 or t["problem"] or t["disputed"] or
                    t["status"] not in (PROVED, UNPROVED) for t in r["targets"])):
            for f in affected:
                fail(f, f"{r['run']}: invalid structural target records")
    for occ, base_char, sig, class_sig in zip(
            occurrences, BASELINE, SIGNATURES, CLASS_SIGNATURES):
        case, callee, family = occ["case"], occ["callee"], occ["family"]
        baseline_rec = next((t for t in runs.get("baseline", {}).get("targets", [])
                             if t["case"] == case), None)
        if baseline_rec is None or baseline_rec["status"] != SHORT[base_char] or baseline_rec["problem"]:
            fail(family, f"{case}: baseline mismatch")
        previous = None
        for i, (expected_status, expected_class) in enumerate(zip(sig, class_sig)):
            r = runs.get(run_name(callee, i), {})
            current = next((t for t in r.get("targets", []) if t["case"] == case), None)
            auxiliary = (case == "A8" and any(
                x["status"] != PROVED or x["disputed"] for x in
                r.get("inventory", {}).get("conversion_A8", [])))
            got = classify(previous, current, auxiliary) if current else INVALID
            if (current is None or current["status"] != SHORT[expected_status]
                    or current["problem"]):
                fail(family, f"{case} p{i}: status/structural target mismatch")
            if got != EXPECT_CLASS[expected_class]:
                fail(family, f"{case} p{i}: {got} != {EXPECT_CLASS[expected_class]}")
            previous = current
        if previous is None or baseline_rec is None or previous["status"] != baseline_rec["status"]:
            fail(family, f"{case}: final prefix != baseline")
        for r in ev["runs"]:
            if r["callee"] is None or r["callee"] == callee:
                continue
            t = next((t for t in r["targets"] if t["case"] == case), None)
            if t is None or baseline_rec is None or t["status"] != baseline_rec["status"] or t["problem"]:
                fail(family, f"{r['run']}: untouched {case} changed")
    families = {f: (FAMILY_VALIDATED if not errors else FAMILY_NOT_VALIDATED)
                for f, errors in family_reasons.items()}
    return {"verdict": VALIDATED if not reasons else NOT_VALIDATED,
            "families": families, "family_reasons": family_reasons,
            "reasons": reasons, "target_occurrence_count": len(occurrences),
            "naive_occurrence_prefix_runs": sum(len(s) for s in SIGNATURES),
            "unique_callee_prefix_runs": len(ev["runs"]) - 1,
            "per_occurrence_observations": sum(len(s) for s in SIGNATURES)}



def experiment():
    start = time.monotonic()
    before, manifest, original, pres, plans = preconditions()
    hits = trust_scan(CORPUS)
    if hits:
        raise ExperimentStop(f"original trust constructs: {hits}")
    refusals = [T13.refusal_record(plans[c], pres[c]["operators"], c, i)
                for c in manifest["callees"] for i in range(1, len(plans[c]))]
    ev = {"experiment": EXPERIMENT, "method": METHOD, "scope": SCOPE,
          "gnatprove": GNATPROVE_VERSION, "corpus": CORPUS_REL,
          "corpus_sha256": CORPUS_SHA256, "manifest": manifest,
          "extraction": {c: {"text": p["text"], "span": p["span"],
                             "conjuncts": [x["text"] for x in p["conjuncts"]],
                             "operators": p["operators"]} for c, p in pres.items()},
          "plans": {c: [{k: v for k, v in item.items() if k != "prefix_range"}
                        for item in plan] for c, plan in plans.items()},
          "refusals": refusals, "trust_scan": {"original_hits": hits}, "runs": []}
    timing = {}
    order = [(None, None)] + [(c, i) for c, plan in plans.items()
                              for i in range(len(plan))]
    for callee, index in order:
        r, d = make_run(original, manifest, pres, plans, callee, index, hits)
        if not (r["gate_problems"] or r["reparse_problems"] or r["trust_hits_introduced"]):
            checks, timing[r["run"]], issues, warnings = gnatprove(d)
            r["loader_consistency_issue_count"] = issues
            r["warning_count"] = warnings
            r["targets"] = [target(checks, o) for o in manifest["occurrences"]]
            r["inventory"] = inventory(checks, manifest)
            r["inventory_problems"] = inventory_problems(r["inventory"])
        else:
            r["inventory"] = {"conversion_A7": [], "conversion_A8": [], "other": []}
            r["inventory_problems"] = ["run not proved: gate failed"]
        ev["runs"].append(r)
    ev["corpus_unchanged"] = T12.tree_digest(CORPUS) == before
    ev["summary"] = decide(ev)
    timing["gnatprove_runs_total"] = sum(timing.values())
    timing["experiment_total"] = time.monotonic() - start
    return ev, {k: round(v, 1) for k, v in timing.items()}


def canonical(ev):
    return json.dumps(ev, sort_keys=True, indent=2) + "\n"


def main(argv):
    if argv:
        print(__doc__)
        return 2
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        evidence, timing = experiment()
    except ExperimentStop as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    (SCRATCH_ROOT / "evidence.json").write_text(canonical(evidence), encoding="utf-8")
    (SCRATCH_ROOT / "timing.json").write_text(
        json.dumps(timing, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence["summary"], indent=2, sort_keys=True))
    return 0 if evidence["summary"]["verdict"] == VALIDATED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
