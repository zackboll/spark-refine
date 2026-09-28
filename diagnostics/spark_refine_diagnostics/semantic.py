"""Task 009: optional semantic enrichment of SRD002 (backend-neutral part).

Policy lives here; all Libadalang calls live in semantic_lal.py.

Semantic enrichment is ADDITIVE and DESCRIPTIVE. It runs only on SRD002
diagnostics the base rule already produced, never creates or removes a
diagnostic, and never changes code, title, confidence, evidence,
explanation or recommendation. Any failure (backend missing, project not
loadable, source/result mismatch, ambiguous location, ...) is recorded as
a structured state; the base report and the CLI exit status are unchanged.

Provenance gate (hard requirement): a source file is used only if it
matches GNAT's .ali source identity metadata, i.e. its GNAT source
checksum AND its modification time (at the one-second resolution GNAT
records) equal a `D` record of the analysed result set's .ali files.
Otherwise the check's enrichment is `unavailable`.

Limitation (stated, not worked around): the GNAT checksum ignores layout
and comments and the D timestamp has one-second resolution, so a
layout/comment-only change made within the same timestamp second cannot
be distinguished from the proof-time source by the available GNATprove
16.1.0 artifacts (.spark records no stronger content digest). The gate is
therefore NOT a proof of byte-identical source; `analysis.semantic.
provenance` says so machine-readably (PROVENANCE, `layout_exact: false`).

`resolution: "exact"` is a statement about semantic lookup only: exactly
one call/assertion was found at the GNATprove-reported location and name
resolution succeeded. It does not strengthen the provenance above.

Failed-conjunct attribution: GNATprove 16.1.0 reports one precondition
check per call; its SARIF and .spark output carry no structural mapping
from that check to a conjunct of the callee's Pre (Task 009 experiment,
docs/tasks/009-libadalang-srd002-enrichment.md). `failed_conjunct` is
therefore always null with attribution "not_provided_by_gnatprove". No
message text is parsed and no conjunct is chosen heuristically.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from .ali import load_ali_sources
from .model import Diagnostic, Report
from .semantic_groups import build_srd002_groups

BACKEND = "libadalang"
ATTRIBUTION = "not_provided_by_gnatprove"
RESOLUTIONS = ("exact", "ambiguous", "unresolved", "unavailable")

# What the source/result provenance gate establishes. Constant, so the
# output stays deterministic; describes the gate, not the current run.
PROVENANCE = {
    "basis": "gnat_ali_checksum_and_timestamp",
    "checksum": "gnat_source_checksum",   # ignores layout and comments
    "timestamp_resolution": "seconds",
    "layout_exact": False,   # same-second layout/comment edits undetectable
    "byte_exact": False,     # no proof-time content digest is available
}


@dataclass
class SemanticRequest:
    project: str | None
    scenario: dict[str, str] = field(default_factory=dict)


def _default_factory(project, scenario, records):
    from .semantic_lal import open_backend
    return open_backend(project, scenario, records)


def _unavailable_errors():
    from .semantic_lal import BackendUnavailable
    return BackendUnavailable


def enrich_report(report: Report, result_dir: Path,
                  request: SemanticRequest, factory=None) -> Report:
    """Add analysis.semantic and per-SRD002 `semantic` blocks in place."""
    meta: dict = {"requested": True, "evaluated": False,
                  "backend": BACKEND, "provenance": dict(PROVENANCE)}
    if request.project is not None:
        meta["project"] = Path(request.project).as_posix()
    if request.scenario:
        meta["scenario"] = dict(sorted(request.scenario.items()))
    report.analysis["semantic"] = meta
    targets = [d for d in report.diagnostics if d.code == "SRD002"]
    backend = None
    if request.project is None:
        meta["reason"] = "no project supplied (-P PROJECT)"
    elif not targets:
        meta["reason"] = "no SRD002 diagnostic to enrich"
    else:
        ali = load_ali_sources(result_dir)
        if not ali.ok:
            meta["reason"] = ("source provenance unavailable: "
                              + "; ".join(ali.problems[:3]))
        else:
            try:
                backend = (factory or _default_factory)(
                    request.project, request.scenario, ali.records)
            except _unavailable_errors() as exc:
                meta["reason"] = str(exc)
            except Exception as exc:  # never fatal
                meta["reason"] = (f"semantic backend failed "
                                  f"({type(exc).__name__}: {exc})")
    if backend is None:
        return report
    meta.update(evaluated=True, version=backend.version)
    counts = {r: 0 for r in RESOLUTIONS}
    out = []
    for d in report.diagnostics:
        if d.code == "SRD002":
            sem = _enrich_one(backend, d)
            for c in sem["checks"]:
                counts[c["resolution"]] += 1
            d = replace(d, semantic=sem)
        out.append(d)
    meta["resolutions"] = counts
    report.diagnostics[:] = out
    # Task 010: report-level triage view over the enriched diagnostics
    # (descriptive grouping only; see semantic_groups.py). Added last so
    # every Task 009 field keeps its position and value.
    meta["srd002_groups"] = build_srd002_groups(report.diagnostics)
    return report


def _enrich_one(backend, d: Diagnostic) -> dict:
    checks = []
    for r in d.related:
        if r.role != "client failure":
            continue
        loc = r.location
        entry = {"rule": r.rule,
                 "location": {"file": loc.file, "line": loc.line,
                              "column": loc.column}}
        if loc.line is None or loc.column is None:
            res = {"resolution": "unavailable",
                   "reason": "check has no line/column"}
        else:
            try:
                if r.rule == "VC_PRECONDITION":
                    res = backend.resolve_precondition(loc.file, loc.line,
                                                       loc.column)
                else:
                    res = backend.resolve_assertion(loc.file, loc.line,
                                                    loc.column)
            except Exception as exc:  # never fatal
                res = {"resolution": "unavailable",
                       "reason": f"semantic backend error "
                                 f"({type(exc).__name__}: {exc})"}
        if res.get("resolution") == "exact" and "precondition" in res:
            res["precondition"] = {**res["precondition"],
                                   "failed_conjunct": None,
                                   "attribution": ATTRIBUTION}
        checks.append({**entry, **res})
    return {"backend": BACKEND, "checks": checks}
