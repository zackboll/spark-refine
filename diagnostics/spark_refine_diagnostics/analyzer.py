"""Entry points combining the diagnostic rules (see rules.RULES).

Every rule reads only structural data: rule ids, check status (derived from
SARIF kind / suppressions), logical entity names, source locations, owning
unit (.spark) and unit dependencies (.ali). Message text is display only.
"""

from __future__ import annotations

from pathlib import Path

from . import srd001, srd002, srd003
from .ali import AliDeps, load_ali_deps
from .loader import load_run, resolve_input
from .model import Diagnostic, ProofRun, Report

SRD002_SKIPPED = ("SRD002 not evaluated: client dependency information "
                  "unavailable")


def run_notes(run: ProofRun) -> list[str]:
    notes = []
    if run.unit_attribution == "entity":
        notes.append("no .spark files: units attributed from entity names; "
                     "stop_reason and pragma Assume unknown")
    notes += [f"consistency: {i}" for i in run.consistency_issues]
    notes += [f"unit {u.name}: analysis stopped early ({u.stop_reason}); "
              "results are partial" for u in run.units if not u.complete]
    pa = sum(u.pragma_assume for u in run.units)
    if pa:
        notes.append(f"{pa} pragma Assume analysed: proved results may "
                     "depend on unchecked assumptions")
    return notes


def analyze_run_report(run: ProofRun, ali: AliDeps | None = None,
                       client_units: list[str] | None = None) -> Report:
    """Single-run rules (SRD001, SRD002) with analysis metadata.

    SRD001 needs only SARIF (+ .spark). SRD002 additionally needs unit
    dependencies; when they are unavailable it is skipped (never guessed)
    and the report says so. An ALI problem is never a proof failure and
    never an input error."""
    notes = run_notes(run)
    graph = srd002.build_unit_graph(run, ali, client_units)
    srd002_meta: dict = {"evaluated": graph.source != "none",
                         "dependency_source": graph.source}
    if ali is not None:
        srd002_meta["ali_status"] = ali.status
        srd002_meta["ali_versions"] = sorted(ali.versions)
        if ali.unsupported_versions:
            srd002_meta["ali_unsupported_versions"] = sorted(
                ali.unsupported_versions)
    if graph.source == "none":
        srd002_meta["reason"] = graph.reason
        notes.append(f"{SRD002_SKIPPED} ({graph.reason})")
    srd002_diags, srd002_notes = srd002.evaluate(run, graph)
    notes += srd002_notes
    diags = sorted(srd001.check(run) + srd002_diags,
                   key=Diagnostic.sort_key)
    analysis = {"rules": {"SRD001": {"evaluated": True},
                          "SRD002": srd002_meta}}
    return Report([run], diags, notes, analysis)


def analyze_run(run: ProofRun, ali: AliDeps | None = None,
                client_units: list[str] | None = None
                ) -> tuple[list[Diagnostic], list[str]]:
    """Single-run rules. Returns (diagnostics, notes)."""
    rep = analyze_run_report(run, ali, client_units)
    return rep.diagnostics, rep.notes


def analyze_path_report(path: Path, name: str | None = None,
                        client_units: list[str] | None = None) -> Report:
    run = load_run(path, name)
    _sarif, directory = resolve_input(path)
    ali = load_ali_deps(directory, run.unit_names())
    return analyze_run_report(run, ali, client_units)


def analyze_path(path: Path, name: str | None = None,
                 client_units: list[str] | None = None
                 ) -> tuple[ProofRun, list[Diagnostic], list[str]]:
    rep = analyze_path_report(path, name, client_units)
    return rep.runs[0], rep.diagnostics, rep.notes


def compare_provers_report(runs: list[ProofRun],
                           reference: ProofRun | None = None) -> Report:
    """Multi-run rule (SRD003) with matching metadata."""
    notes = []
    for r in runs + ([reference] if reference else []):
        notes += [f"{r.name}: {n}" for n in run_notes(r)]
    versions = {r.tool_version for r in runs}
    if len(versions) > 1:
        notes.append(f"runs come from different GNATprove versions: "
                     f"{sorted(versions)}")
    diags, result = srd003.evaluate(runs, reference)
    analysis: dict = {"rules": {"SRD003": {"evaluated": result is not None}}}
    if result is not None:
        analysis["srd003_matching"] = result.to_dict()
        hidden = [u for u in result.unresolved if u.outcomes_differ()]
        if hidden:
            notes.append(
                f"SRD003: {len(hidden)} check identit"
                f"{'y' if len(hidden) == 1 else 'ies'} with differing "
                "outcomes could not be matched confidently and were not "
                "reported (see analysis.srd003_matching.unresolved)")
    all_runs = runs + ([reference] if reference else [])
    return Report(all_runs, sorted(diags, key=Diagnostic.sort_key), notes,
                  analysis)


def compare_provers(runs: list[ProofRun], reference: ProofRun | None = None
                    ) -> tuple[list[Diagnostic], list[str]]:
    """Multi-run rule (SRD003). Returns (diagnostics, notes)."""
    rep = compare_provers_report(runs, reference)
    return rep.diagnostics, rep.notes
