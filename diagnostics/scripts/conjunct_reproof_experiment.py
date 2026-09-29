#!/usr/bin/env python3
"""Task 012: per-conjunct GNATprove re-proof EXPERIMENT (not a product).

  cd examples/ring_buffer
  PYTHONPATH=<lal bundle> alr -n exec -- \\
      python3 ../../diagnostics/scripts/conjunct_reproof_experiment.py

Pre-registration: docs/tasks/012-per-conjunct-reproof-experiment.md.

For the unchanged Task 009 corpus
(tests/semantic_fixtures/conjunct_experiment) this script

  1. copies the project (real files only) to scratch directories below
     diagnostics/obj/task012-conjunct-reproof/ (gitignored);
  2. runs one UNMODIFIED control (byte-identical copy);
  3. for each selected top-level conjunct of Ops.Op / Ops.Op3 (Libadalang
     AST, Task 009's decomposition), replaces ONLY that callee's Pre
     expression source range in the scratch ops.ads with the conjunct
     (newline-preserving overlay) and re-runs GNATprove;
  4. reads VC_PRECONDITION at each pre-registered call structurally (the
     existing loader; exactly one match; SARIF status only);
  5. applies the frozen decision rule and writes evidence.json.

Scratch results are evidence about the SCRATCH programs only: they do not
prove the original program and no ordinary spark-refine report uses them.
GNATprove stays the proof authority. No prover message text is read.
Libadalang is imported lazily, only by the Libadalang layer below.

Exit status: 0 iff the verdict is VALIDATED_ON_CONTROLLED_CORPUS; 1 for
NOT_VALIDATED; 2 if a precondition stops the experiment before a verdict.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIAGNOSTICS = REPO / "diagnostics"
if str(DIAGNOSTICS) not in sys.path:
    sys.path.insert(0, str(DIAGNOSTICS))

from spark_refine_diagnostics.loader import load_run  # noqa: E402

CORPUS = DIAGNOSTICS / "tests" / "semantic_fixtures" / "conjunct_experiment"
SCRATCH_ROOT = DIAGNOSTICS / "obj" / "task012-conjunct-reproof"
RB = REPO / "examples" / "ring_buffer"  # pinned toolchain crate (as Task 009)

EXPERIMENT = "task012_per_conjunct_reproof"
METHOD = "scratch_callee_pre_replacement"
SCOPE = "preregistered_independent_total_conjuncts"
GNATPROVE_VERSION = "FSF 16.1.0"
VALIDATED = "VALIDATED_ON_CONTROLLED_CORPUS"
NOT_VALIDATED = "NOT_VALIDATED"
PROVE_ARGS = ("-j0",)  # + the project's Proof_Switches (P11)
PROJECT_PROOF_SWITCHES = ("-U", "--mode=all", "--level=2",
                          "--report=statistics")

# The complete project copied into every scratch directory (P7). The
# committed results/, evidence.json, snapshot.json and obj/ are NOT copied.
COPIED_FILES = ("experiment.gpr", "src/client.adb", "src/client.ads",
                "src/ops.adb", "src/ops.ads")
MUTABLE_FILE = "src/ops.ads"

# P3: committed source identity (snapshot.json of the Task 009 corpus)
CORPUS_SHA256 = {
    "src/client.adb":
        "6c033a9b019f70a1768fae0820e9555f9865448c9be02d3ead58fcfe2e33c51e",
    "src/client.ads":
        "738db3c34770fd711104e0602794890d4b20c56542e582d0d175dd53f1650656",
    "src/ops.adb":
        "4be7470978852f55a16a9a6512af9a77e4637e392873c91811e07ace475dd4b0",
    "src/ops.ads":
        "8ceb30a3a18e075ab308e0565c1f428b38424cd6e30901c2aff348ff0a69939a",
}

# P4: pre-registered extraction (never updated to make a run pass)
EXPECTED_CONJUNCTS = {
    "Ops.Op": ("X > 0", "Y > 0"),
    "Ops.Op3": ("X > 0", "Y > 0", "Z > 0"),
}

# Pre-registered call sites: (client entity, file, line, column, callee)
TARGETS = (
    ("Client.Second_Fails", "client.adb", 7, 10, "Ops.Op"),
    ("Client.First_Fails", "client.adb", 12, 10, "Ops.Op"),
    ("Client.Both_Fail", "client.adb", 17, 10, "Ops.Op"),
    ("Client.Middle_Fails", "client.adb", 22, 10, "Ops.Op3"),
)

PROVED, UNPROVED, JUSTIFIED = "proved", "unproved", "justified"

# P6: baseline control, entity -> required status
BASELINE_EXPECTED = {
    "Client.Second_Fails": UNPROVED,
    "Client.First_Fails": UNPROVED,
    "Client.Both_Fail": UNPROVED,
    "Client.Middle_Fails": UNPROVED,
}

# P5: ground truth, (callee, conjunct index, entity) -> expected status
GROUND_TRUTH = {
    ("Ops.Op", 0, "Client.Second_Fails"): PROVED,
    ("Ops.Op", 0, "Client.First_Fails"): UNPROVED,
    ("Ops.Op", 0, "Client.Both_Fail"): UNPROVED,
    ("Ops.Op", 1, "Client.Second_Fails"): UNPROVED,
    ("Ops.Op", 1, "Client.First_Fails"): PROVED,
    ("Ops.Op", 1, "Client.Both_Fail"): UNPROVED,
    ("Ops.Op3", 0, "Client.Middle_Fails"): PROVED,
    ("Ops.Op3", 1, "Client.Middle_Fails"): UNPROVED,
    ("Ops.Op3", 2, "Client.Middle_Fails"): PROVED,
}

# P13: critical discrimination pair, signatures over Ops.Op conjuncts [0, 1]
DISCRIMINATION = {
    "Client.First_Fails": [UNPROVED, PROVED],
    "Client.Both_Fail": [UNPROVED, UNPROVED],
}


class ExperimentStop(Exception):
    """A precondition failed; no verdict can be produced."""


# ===================================================== filesystem safety
def scratch_path(path: Path, root: Path | None = None) -> Path:
    """`path` resolved, if it lies STRICTLY below the resolved scratch
    root (default: SCRATCH_ROOT at call time); otherwise raise. Every
    destructive operation goes through it."""
    root = SCRATCH_ROOT if root is None else root
    root_r = Path(root).resolve()
    p = Path(path).resolve()
    if p == root_r or root_r not in p.parents:
        raise ExperimentStop(f"refusing to touch {path}: not below the "
                             f"scratch root {root}")
    return p


def reset_dir(path: Path, root: Path | None = None) -> Path:
    """Delete and recreate a directory below the scratch root only."""
    if Path(path).is_symlink():
        raise ExperimentStop(f"refusing to follow symlink {path}")
    p = scratch_path(path, root)
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)
    return p


def copy_corpus(src_root: Path, dest: Path, files=COPIED_FILES,
                root: Path | None = None) -> None:
    """Copy the listed files as REAL files (bytes only: no symlink is
    followed or created, no metadata copied) into a scratch directory."""
    dest = scratch_path(dest, root)
    for rel in files:
        s = Path(src_root) / rel
        if s.is_symlink() or not s.is_file():
            raise ExperimentStop(f"{rel}: not a regular file in the corpus")
        d = dest / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_bytes(s.read_bytes())


def read_tree(base: Path, files=COPIED_FILES) -> dict[str, bytes]:
    return {rel: (Path(base) / rel).read_bytes() for rel in files}


def tree_digest(base: Path, exclude_top=("obj",)) -> dict[str, str]:
    """sha256 of every regular file below `base` (relative posix path ->
    digest), skipping top-level generated directories."""
    base = Path(base)
    out = {}
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base)
        if rel.parts[0] in exclude_top or not p.is_file():
            continue
        out[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# ================================================= source transformation
def line_starts(data: bytes) -> list[int]:
    starts = [0]
    starts.extend(i + 1 for i, b in enumerate(data) if b == 0x0A)
    return starts


def require_plain(name: str, data: bytes) -> None:
    """Libadalang columns are characters; with ASCII, LF-only, tab-free
    source they equal byte columns. Anything else stops the experiment."""
    if not data.isascii() or b"\t" in data or b"\r" in data:
        raise ExperimentStop(f"{name}: not plain ASCII/LF without tabs; "
                             "line:column -> byte offset would be unsafe")


def sloc_to_offset(data: bytes, line: int, column: int) -> int:
    """Byte offset of a 1-based line:column (plain sources only)."""
    return line_starts(data)[line - 1] + column - 1


def overlay(data: bytes, start: int, end: int, text: str) -> bytes:
    """Replace data[start:end] by spaces, keeping every newline byte, then
    write `text` at `start`. Length, newline count and all later line
    numbers are preserved. Refuses if `text` would cover a newline."""
    if not (0 <= start < end <= len(data)):
        raise ExperimentStop(f"invalid replacement range {start}..{end}")
    t = text.encode("ascii")
    if b"\n" in t:
        raise ExperimentStop("selected conjunct text spans several lines")
    region = bytearray(0x0A if b == 0x0A else 0x20 for b in data[start:end])
    if len(t) > len(region) or b"\n" in bytes(region[:len(t)]):
        raise ExperimentStop(f"conjunct {text!r} does not fit on the first "
                             "line of the original Pre range")
    region[:len(t)] = t
    return data[:start] + bytes(region) + data[end:]

def mutation_inventory(original: dict[str, bytes], scratch: dict[str, bytes],
                       allowed: dict[str, list[tuple[int, int]]]) -> dict:
    """Byte-level comparison of two trees. `allowed` maps a file to the
    byte ranges that may differ. `changed_range_count` counts allowed
    ranges containing changed bytes; bytes outside them are problems."""
    problems: list[str] = []
    changed, ranges_hit = [], 0
    length_ok = newlines_ok = True
    for rel in sorted(set(original) | set(scratch)):
        a, b = original.get(rel), scratch.get(rel)
        if a is None or b is None:
            problems.append(f"{rel}: present in only one tree")
            changed.append(rel)
            continue
        if a == b:
            continue
        changed.append(rel)
        if len(a) != len(b):
            length_ok = False
            problems.append(f"{rel}: length changed {len(a)} -> {len(b)}")
            continue
        if line_starts(a) != line_starts(b):
            newlines_ok = False
            problems.append(f"{rel}: newline positions changed")
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        rngs = allowed.get(rel, [])
        outside = [i for i in diff if not any(s <= i < e for s, e in rngs)]
        if outside:
            problems.append(f"{rel}: {len(outside)} changed byte(s) outside "
                            "the allowed Pre expression range")
        ranges_hit += sum(1 for s, e in rngs if any(s <= i < e for i in diff))
    return {"changed_files": changed,
            "changed_file_count": len(changed),
            "changed_range_count": ranges_hit,
            "length_preserved": length_ok,
            "newlines_preserved": newlines_ok,
            "problems": problems}


def probe_isolation_problems(inv: dict) -> list[str]:
    """P9 gate for one probe variant."""
    out = list(inv["problems"])
    if inv["changed_files"] != [MUTABLE_FILE]:
        out.append(f"changed files {inv['changed_files']}, expected "
                   f"[{MUTABLE_FILE!r}]")
    if inv["changed_range_count"] != 1:
        out.append(f"changed_range_count {inv['changed_range_count']}, "
                   "expected 1")
    if not (inv["length_preserved"] and inv["newlines_preserved"]):
        out.append("file length or newline layout not preserved")
    return out


# ========================================================= trust scan
# The Libadalang layer turns each unit into structural records:
#   ("pragma", <pragma identifier>, [<argument expression texts>])
#   ("aspect", <aspect identifier>, [<aspect value text>] or [])
#   ("ghost_decl_without_body", <qualified name>, [])
# The classification below is over those records only (identifiers are
# compared case-insensitively, as Ada does); it never reads prover output.
_ANNOTATE_FORBIDDEN = {"false_positive", "intentional", "skip_proof",
                       "skip_flow_and_proof"}


def _words(texts) -> set[str]:
    out = set()
    for t in texts:
        for ch in "(),=>'\"":
            t = t.replace(ch, " ")
        out |= {w.lower() for w in t.split()}
    return out


def classify_trust(record: tuple) -> str | None:
    """Forbidden-trust category of one structural record, or None."""
    kind, name, args = record
    n, words = name.lower(), _words(args)
    if kind == "ghost_decl_without_body":
        return "bodyless_ghost_subprogram"
    if kind == "pragma":
        if n == "assume":
            return "pragma_assume"
        if n == "annotate" and _ANNOTATE_FORBIDDEN & words:
            return "annotate_justification_or_skip"
        if n in ("suppress", "suppress_all"):
            return "suppress"
        if n == "spark_mode" and "off" in words:
            return "spark_mode_off"
        if n in ("import", "interface", "axiom"):
            return "unchecked_axiom_mechanism"
    if kind == "aspect":
        if n == "spark_mode" and "off" in words:
            return "spark_mode_off"
        if n == "annotate" and _ANNOTATE_FORBIDDEN & words:
            return "annotate_justification_or_skip"
        if n in ("import", "axiom") and "false" not in words:
            return "unchecked_axiom_mechanism"
        if n == "suppress":
            return "suppress"
    return None


def trust_hits(records: list[tuple]) -> list[dict]:
    hits = []
    for r in records:
        cat = classify_trust(r)
        if cat:
            hits.append({"category": cat, "kind": r[0], "name": r[1]})
    return sorted(hits, key=lambda h: (h["category"], h["kind"], h["name"]))


def introduced_hits(original: list[dict], scratch: list[dict]) -> list[dict]:
    """Scratch hits not already present in the original (multiset)."""
    rest = list(original)
    out = []
    for h in scratch:
        if h in rest:
            rest.remove(h)
        else:
            out.append(h)
    return out


# =============================================== structural VC reading
def match_target(checks, entity: str, file: str, line: int,
                 column: int) -> dict:
    """Exactly one VC_PRECONDITION for (entity, file, line, column). The
    status is the loader's structural SARIF classification (Check.status:
    kind + in-source suppression); message text is never consulted."""
    hits = [c for c in checks
            if c.rule == "VC_PRECONDITION" and c.entity == entity
            and c.location.file == file and c.location.line == line
            and c.location.column == column]
    loc = {"file": file, "line": line, "column": column}
    if len(hits) != 1:
        return {"entity": entity, "location": loc, "status": None,
                "matches": len(hits),
                "problem": ("no matching VC_PRECONDITION" if not hits else
                            f"{len(hits)} matching VC_PRECONDITION checks")}
    c = hits[0]
    return {"entity": entity, "location": loc, "status": c.status.value,
            "matches": 1,
            "problem": ("SARIF and .spark disagree on this check"
                        if c.disputed else None)}


def read_outcomes(checks, callee: str | None = None) -> list[dict]:
    """Outcomes for every pre-registered call of `callee` (all if None),
    each occurrence keyed by its own client entity and location."""
    return [match_target(checks, ent, f, ln, col)
            for ent, f, ln, col, cal in TARGETS
            if callee is None or cal == callee]


def _target_order(entity: str) -> int:
    for i, t in enumerate(TARGETS):
        if t[0] == entity:
            return i
    return len(TARGETS)


def canonical(evidence: dict) -> str:
    """Deterministic serialisation: sorted keys, probes by (callee, index),
    outcomes in pre-registered target order."""
    ev = dict(evidence)
    ev["baseline"] = sorted(ev.get("baseline") or [],
                            key=lambda o: _target_order(o["entity"]))
    ev["probes"] = sorted(
        ({**p, "outcomes": sorted(p.get("outcomes") or [],
                                  key=lambda o: _target_order(o["entity"]))}
         for p in ev.get("probes") or []),
        key=lambda p: (p["callee"], p["conjunct_index"]))
    return json.dumps(ev, indent=2, sort_keys=True) + "\n"


# ============================================================ decision
def decide(evidence: dict) -> dict:
    """The frozen P14 decision rule over an evidence dict. Every missing
    field counts as a failure (fail closed)."""
    reasons: list[str] = list(evidence.get("stop_reasons") or [])

    by_ent: dict[str, list[dict]] = {}
    for o in evidence.get("baseline") or []:
        by_ent.setdefault(o.get("entity"), []).append(o)
    b_ok = 0
    for ent, want in BASELINE_EXPECTED.items():
        recs = by_ent.get(ent, [])
        if len(recs) != 1:
            reasons.append(f"baseline {ent}: {len(recs)} outcome records")
            continue
        o = recs[0]
        if o.get("matches") != 1 or o.get("problem"):
            reasons.append(f"baseline {ent}: {o.get('problem')}")
        elif o.get("status") != want:
            reasons.append(f"baseline {ent}: {o.get('status')}, "
                           f"required {want}")
        else:
            b_ok += 1
    if (evidence.get("baseline_isolation") or {}).get(
            "changed_file_count") != 0:
        reasons.append("baseline copy is not byte-identical to the corpus")

    observed: dict[tuple, str | None] = {}
    counts = {PROVED: 0, UNPROVED: 0, JUSTIFIED: 0}
    for p in evidence.get("probes") or []:
        cal, idx = p.get("callee"), p.get("conjunct_index")
        tag = f"{cal}[{idx}]"
        gate = (p.get("mutation") or {}).get("gate_problems", ["missing"])
        if gate:
            reasons.append(f"{tag} source isolation: {gate}")
        reparse = p.get("reparse_problems", ["missing"])
        if reparse:
            reasons.append(f"{tag} reparse: {reparse}")
        if p.get("trust_hits_introduced", ["missing"]):
            reasons.append(f"{tag} forbidden trust construct introduced")
        for o in p.get("outcomes") or []:
            key = (cal, idx, o.get("entity"))
            if key in observed:
                reasons.append(f"duplicate observation {key}")
            if o.get("matches") != 1 or o.get("problem"):
                reasons.append(f"{key}: {o.get('problem')}")
                observed[key] = None
                continue
            observed[key] = o.get("status")
            if o.get("status") in counts:
                counts[o["status"]] += 1
            else:
                reasons.append(f"{key}: unknown status {o.get('status')!r}")
    if counts[JUSTIFIED]:
        reasons.append(f"{counts[JUSTIFIED]} JUSTIFIED probe result(s)")

    matches = 0
    for key, want in GROUND_TRUTH.items():
        if key not in observed:
            reasons.append(f"{key}: observation missing")
        elif observed[key] == want:
            matches += 1
        else:
            reasons.append(f"{key}: observed {observed[key]}, "
                           f"pre-registered {want}")
    extra = sorted((k for k in observed if k not in GROUND_TRUTH), key=str)
    if extra:
        reasons.append(f"unexpected observations {extra}")

    if (evidence.get("trust_scan") or {}).get("original_hits", ["missing"]):
        reasons.append("committed corpus trust scan not clean")
    if evidence.get("corpus_unchanged") is not True:
        reasons.append("committed corpus changed or not verified")

    sig = {ent: [observed.get(("Ops.Op", i, ent)) for i in (0, 1)]
           for ent in DISCRIMINATION}
    distinguished = (sig == DISCRIMINATION and
                     sig["Client.First_Fails"] != sig["Client.Both_Fail"])
    return {"baseline_matches": b_ok,
            "probe_observations": len(observed),
            "proved": counts[PROVED],
            "unproved": counts[UNPROVED],
            "justified": counts[JUSTIFIED],
            "ground_truth_matches": matches,
            "discrimination": {"signatures": sig,
                               "distinguished": distinguished},
            "verdict": NOT_VALIDATED if reasons else VALIDATED,
            "reasons": reasons}



# ===================================================== Libadalang layer
# Everything below imports libadalang lazily; the pure helpers above (and
# their tests) work without it. Nothing parses Ada text with regexes.
def _lal():
    from spark_refine_diagnostics.semantic_lal import _import
    return _import()   # raises BackendUnavailable with a clear reason


def _decomposer(lal):
    """Task 009's own top-level `and`/`and then` decomposition
    (semantic_lal.LalBackend.conjuncts, the same function object)."""
    from spark_refine_diagnostics.semantic_lal import LalBackend

    class _D:
        conjuncts = LalBackend.conjuncts

        def __init__(self):
            self.lal = lal
    return _D()


def parse_unit(path: Path):
    lal = _lal()
    ctx = lal.AnalysisContext()
    return lal, ctx.get_from_file(str(path))


def extract_pre(path: Path, callee: str) -> dict:
    """The explicit Pre of the ONE subprogram declaration of `callee`
    (fully qualified) in `path`: its text, byte range and conjunct texts.
    Raises ExperimentStop on parse problems, overloads or a missing Pre."""
    data = Path(path).read_bytes()
    require_plain(Path(path).name, data)
    lal, unit = parse_unit(path)
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
    r = expr.sloc_range
    start = sloc_to_offset(data, r.start.line, r.start.column)
    end = sloc_to_offset(data, r.end.line, r.end.column)
    if data[start:end].decode("ascii") != expr.text:
        raise ExperimentStop(f"{callee}: Pre byte range does not match the "
                             "Libadalang node text")
    parts = _decomposer(lal).conjuncts(expr)
    return {"callee": callee, "text": expr.text,
            "range": [start, end],
            "span": {"start_line": r.start.line,
                     "start_column": r.start.column,
                     "end_line": r.end.line, "end_column": r.end.column},
            "conjuncts": [c.text for c in parts]}


def reparse_problems(path: Path, callee: str, conjunct: str) -> list[str]:
    """P8: the scratch file parses and the target Pre is exactly the
    selected conjunct (one top-level conjunct)."""
    try:
        pre = extract_pre(path, callee)
    except ExperimentStop as exc:
        return [str(exc)]
    out = []
    if pre["text"] != conjunct:
        out.append(f"{callee}: scratch Pre is {pre['text']!r}, expected "
                   f"{conjunct!r}")
    if pre["conjuncts"] != [conjunct]:
        out.append(f"{callee}: scratch Pre conjuncts {pre['conjuncts']}")
    return out


def trust_records(paths) -> list[tuple]:
    """Structural pragma/aspect records (see classify_trust) of every
    unit, plus ghost subprogram declarations without a body among the
    scanned units."""
    lal = _lal()
    ctx = lal.AnalysisContext()
    recs, ghost_decls, bodies = [], [], set()
    for path in sorted(Path(p) for p in paths):
        unit = ctx.get_from_file(str(path))
        if unit.diagnostics:
            raise ExperimentStop(f"{path.name}: parse diagnostics")
        for n in unit.root.findall(lal.PragmaNode):
            recs.append(("pragma", n.f_id.text,
                         [a.text for a in n.f_args]))
        for n in unit.root.findall(lal.AspectAssoc):
            recs.append(("aspect", n.f_id.text,
                         [n.f_expr.text] if n.f_expr is not None else []))
        for n in unit.root.findall(lal.BaseSubpBody):
            bodies.add(n.p_fully_qualified_name)
        for n in unit.root.findall(lal.SubpDecl):
            if n.p_get_aspect("Ghost").exists:
                ghost_decls.append(n.p_fully_qualified_name)
    recs += [("ghost_decl_without_body", g, [])
             for g in ghost_decls if g not in bodies]
    return recs


def trust_scan(base: Path) -> list[dict]:
    return trust_hits(trust_records(
        Path(base) / rel for rel in COPIED_FILES if rel.endswith(
            (".ads", ".adb"))))



# ========================================================= orchestration
def run_dir_name(callee: str | None, index: int | None) -> str:
    if callee is None:
        return "baseline"
    return f"{callee.lower().replace('.', '_')}_c{index}"


def gnatprove(run_dir: Path) -> tuple[list, float]:
    """One fresh GNATprove run of <run_dir>/experiment.gpr in the pinned
    Alire environment. Returns (checks, wall seconds). The exit code is
    NOT used for any outcome; only a missing SARIF stops the experiment."""
    reset_dir(run_dir / "obj")
    prefix = shlex.split(os.environ.get("GNATPROVE_EXEC", "alr -n exec --"))
    cmd = [*prefix, "gnatprove", "-P", str(run_dir / "experiment.gpr"),
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
    return run.checks, wall


def _preconditions() -> tuple[dict, dict, dict]:
    """Corpus identity (P3) and extraction (P4), before any proof run."""
    before = tree_digest(CORPUS)
    committed = {r: before.get(r) for r in CORPUS_SHA256}
    if committed != CORPUS_SHA256:
        raise ExperimentStop(f"committed corpus differs from the "
                             f"pre-registered sha256: {committed}")
    original = read_tree(CORPUS)
    for rel, data in original.items():
        require_plain(rel, data)
    pres = {c: extract_pre(CORPUS / MUTABLE_FILE, c)
            for c in EXPECTED_CONJUNCTS}
    for c, want in EXPECTED_CONJUNCTS.items():
        if tuple(pres[c]["conjuncts"]) != want:
            raise ExperimentStop(f"{c}: extracted {pres[c]['conjuncts']}, "
                                 f"pre-registered {list(want)}; STOP")
    return before, original, pres


def make_probe(original: dict, pres: dict, callee: str, idx: int,
               text: str, original_hits: list) -> tuple[dict, Path]:
    """Build one isolated scratch project and its gate evidence."""
    start, end = pres[callee]["range"]
    d = reset_dir(SCRATCH_ROOT / run_dir_name(callee, idx))
    copy_corpus(CORPUS, d)
    target = d / MUTABLE_FILE
    target.write_bytes(overlay(target.read_bytes(), start, end, text))
    inv = mutation_inventory(original, read_tree(d),
                             {MUTABLE_FILE: [(start, end)]})
    probe = {
        "callee": callee, "conjunct_index": idx, "conjunct_text": text,
        "mutation": {
            "changed_files": inv["changed_files"],
            "changed_file_count": inv["changed_file_count"],
            "changed_range_count": inv["changed_range_count"],
            "allowed_range": {"file": MUTABLE_FILE, **pres[callee]["span"]},
            "length_preserved": inv["length_preserved"],
            "newlines_preserved": inv["newlines_preserved"],
            "gate_problems": probe_isolation_problems(inv)},
        "reparse_problems": reparse_problems(target, callee, text),
        "trust_hits_introduced": introduced_hits(original_hits,
                                                 trust_scan(d)),
        "outcomes": [],
    }
    return probe, d


def experiment() -> tuple[dict, dict]:
    """Run the whole pre-registered experiment. Returns (evidence, timing);
    timing is measurement only and kept out of evidence.json."""
    timing: dict[str, float] = {}
    t0 = time.monotonic()
    before, original, pres = _preconditions()
    original_hits = trust_scan(CORPUS)
    evidence = {
        "experiment": EXPERIMENT, "method": METHOD, "scope": SCOPE,
        "gnatprove": GNATPROVE_VERSION,
        "gnatprove_switches": [*PROJECT_PROOF_SWITCHES, *PROVE_ARGS],
        "corpus": "diagnostics/tests/semantic_fixtures/conjunct_experiment",
        "copied_files": list(COPIED_FILES),
        "corpus_sha256": dict(sorted(CORPUS_SHA256.items())),
        "extraction": {c: {"text": p["text"], "span": p["span"],
                           "conjuncts": p["conjuncts"]}
                       for c, p in sorted(pres.items())},
        "trust_scan": {"original_hits": original_hits},
        "baseline": [], "probes": [],
    }

    # P6: fresh, unmodified control
    d = reset_dir(SCRATCH_ROOT / run_dir_name(None, None))
    copy_corpus(CORPUS, d)
    inv = mutation_inventory(original, read_tree(d), {})
    evidence["baseline_isolation"] = {
        "changed_file_count": inv["changed_file_count"],
        "problems": inv["problems"]}
    evidence["trust_scan"]["baseline_hits"] = trust_scan(d)
    checks, timing["baseline"] = gnatprove(d)
    evidence["baseline"] = read_outcomes(checks)

    # P7: one independent scratch project per selected conjunct
    for callee, conj in EXPECTED_CONJUNCTS.items():
        for idx, text in enumerate(conj):
            probe, d = make_probe(original, pres, callee, idx, text,
                                  original_hits)
            if not (probe["mutation"]["gate_problems"]
                    or probe["reparse_problems"]
                    or probe["trust_hits_introduced"]):
                # a scratch program that failed a gate is never proved
                checks, timing[d.name] = gnatprove(d)
                probe["outcomes"] = read_outcomes(checks, callee)
            evidence["probes"].append(probe)

    evidence["corpus_unchanged"] = tree_digest(CORPUS) == before
    evidence["summary"] = decide(evidence)
    timing["gnatprove_runs_total"] = sum(timing.values())
    timing["gnatprove_runs"] = len(timing) - 1
    timing["experiment_total"] = time.monotonic() - t0
    return evidence, {k: round(v, 1) for k, v in timing.items()}


def _print_matrix(ev: dict) -> None:
    print("baseline (unmodified scratch copy):")
    for o in ev["baseline"]:
        loc = o["location"]
        print(f"  {o['entity']:<22} {loc['file']}:{loc['line']}:"
              f"{loc['column']}  {str(o['status']).upper()}")
    print("selected-conjunct probes:")
    for p in ev["probes"]:
        for o in p["outcomes"]:
            print(f"  {p['callee']:<8} c{p['conjunct_index']} "
                  f"{p['conjunct_text']:<6} {o['entity']:<22} "
                  f"{str(o['status']).upper()}")
    s = ev["summary"]
    print(f"summary: baseline {s['baseline_matches']}/4, observations "
          f"{s['probe_observations']}, proved {s['proved']}, unproved "
          f"{s['unproved']}, justified {s['justified']}, ground truth "
          f"{s['ground_truth_matches']}/9")
    print(f"discrimination: {json.dumps(s['discrimination'])}")
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

