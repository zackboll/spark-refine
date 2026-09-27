"""Command-line interface.

  python3 -m spark_refine_diagnostics analyze PATH [--client-unit U ...]
                                              [--format text|json]
                                              [--fail-on SRD00x ...]
  python3 -m spark_refine_diagnostics compare-provers
                                              --run NAME=PATH --run ...
                                              [--reference NAME=PATH]
  python3 -m spark_refine_diagnostics rules

PATH is a GNATprove output directory (obj/<variant>/gnatprove, or its
parent) or a gnatprove.sarif file. Exit status: 0 on success (diagnostics
are informational), 1 if a --fail-on code was emitted, 2 on input errors
(missing/malformed SARIF or .spark). Missing or malformed .ali files are NOT
input errors: SRD002 is then skipped and the report says so.
The tool never runs GNATprove and never modifies sources.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyzer import analyze_path_report, compare_provers_report
from .loader import load_run
from .render import wrap, to_json, to_text
from .rules import RULES
from .sarif import InputError


def _named(spec: str) -> tuple[str, Path]:
    name, sep, path = spec.partition("=")
    if not sep or not name or not path:
        raise argparse.ArgumentTypeError(
            f"expected NAME=PATH, got {spec!r}")
    return name, Path(path)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python3 -m spark_refine_diagnostics",
        description="Deterministic proof-engineering diagnostics over "
                    "GNATprove SARIF/.spark results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="single-run rules (SRD001, SRD002)")
    a.add_argument("path", type=Path)
    a.add_argument("--name", help="run name shown in the report")
    a.add_argument("--client-unit", action="append", default=[],
                   help="treat this unit as a client of all other analysed "
                        "units (overrides .ali dependency discovery)")

    c = sub.add_parser("compare-provers",
                       help="multi-run rule (SRD003)")
    c.add_argument("--run", action="append", type=_named, required=True,
                   metavar="NAME=PATH",
                   help="a single-prover run (at least two)")
    c.add_argument("--reference", type=_named, metavar="NAME=PATH",
                   help="optional portfolio run, shown for context")

    for s in (a, c):
        s.add_argument("--format", choices=("text", "json"),
                       default="text")
        s.add_argument("--fail-on", action="append", default=[],
                       choices=sorted(RULES), metavar="CODE",
                       help="exit 1 if this diagnostic code is emitted")

    sub.add_parser("rules", help="list the diagnostic rules")
    return p


def print_rules() -> None:
    for code, r in RULES.items():
        print(f"{code}  [confidence {r.confidence_label}, {r.scope}]  "
              f"{r.title}")
        for line in wrap(r.summary, "        "):
            print(line)
        if r.confidence_policy:
            print(f"        confidence policy: {r.confidence_policy}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "rules":
        print_rules()
        return 0
    try:
        if args.command == "analyze":
            report = analyze_path_report(args.path, args.name,
                                         args.client_unit)
        else:
            if len(args.run) < 2:
                print("compare-provers needs at least two --run",
                      file=sys.stderr)
                return 2
            runs = [load_run(path, name) for name, path in args.run]
            ref = (load_run(args.reference[1], args.reference[0])
                   if args.reference else None)
            report = compare_provers_report(runs, ref)
    except (InputError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    render = to_json if args.format == "json" else to_text
    sys.stdout.write(render(report.runs, report.diagnostics, report.notes,
                            report.analysis))
    return 1 if any(d.code in args.fail_on
                    for d in report.diagnostics) else 0
