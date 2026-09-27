"""spark_refine_diagnostics: deterministic GNATprove proof-engineering
diagnostics (Task 005 MVP). No AI, no source mutation, no proof repair.

Public API:

    load_run(path, name=None) -> ProofRun
    analyze_path(path, name=None, client_units=None)
        -> (ProofRun, [Diagnostic], [note])
    analyze_run(run, ali=None, client_units=None)
        -> ([Diagnostic], [note])          ali: ali.AliDeps
    compare_provers([ProofRun, ...], reference=None)
        -> ([Diagnostic], [note])
    analyze_path_report / analyze_run_report / compare_provers_report
        -> Report (runs, diagnostics, notes, analysis metadata)
    RULES: stable rule catalogue (SRD001, SRD002, SRD003)
"""

from .analyzer import (analyze_path, analyze_path_report, analyze_run,
                       analyze_run_report, compare_provers,
                       compare_provers_report)
from .loader import load_run
from .model import (Check, Confidence, Diagnostic, Location, ProofRun,
                    Report, Severity, Status)
from .rules import RULES

__all__ = ["RULES", "Check", "Confidence", "Diagnostic", "Location",
           "ProofRun", "Report", "Severity", "Status", "analyze_path",
           "analyze_path_report", "analyze_run", "analyze_run_report",
           "compare_provers", "compare_provers_report", "load_run"]
