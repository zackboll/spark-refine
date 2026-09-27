"""Text and JSON rendering of diagnostics. Output is deterministic:
diagnostics are sorted by (code, entity, location), and neither format
contains timestamps or absolute paths added by the tool."""

from __future__ import annotations

import json
import shlex

from .model import Diagnostic, ProofRun
from .model import Confidence
from .rules import RULES

JSON_FORMAT_VERSION = 1


def wrap(text: str, indent: str, width: int = 76) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(indent) + len(cur) + 1 + len(w) > width:
            lines.append(indent + cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(indent + cur)
    return lines


def diagnostic_to_text(d: Diagnostic) -> str:
    info = RULES[d.code]
    out = [f"{d.code}: {d.title}",
           f"  severity: {d.severity.value}   confidence: "
           f"{d.confidence.value}",
           f"  category: {info.category}   action: {info.action}",
           f"  entity:   {d.entity or '-'}"]
    if d.primary_location:
        out.append(f"  location: {d.primary_location}")
    if d.match_quality:
        out.append(f"  match:    {d.match_quality}")
    roles: dict[str, list] = {}
    for r in d.related:
        roles.setdefault(r.role, []).append(r)
    for role, items in roles.items():
        out.append(f"  {role}:")
        for r in items:
            run = f" ({r.run})" if r.run else ""
            out.append(f"    {r.location} {r.rule} [{r.status}]{run}")
            if r.message:
                out += wrap(r.message, "        ")
    out.append("  evidence:")
    out += [f"    - {e}" for e in d.evidence]
    out.append("  explanation:")
    out += wrap(d.explanation, "    ")
    out.append("  recommendation:")
    out += wrap(d.recommendation, "    ")
    return "\n".join(out)


def run_header(run: ProofRun) -> str:
    s = run.summary()
    return (f"run {run.name}: GNATprove {run.tool_version or '?'}; "
            f"{s['checks']} checks: {s['proved']} proved, "
            f"{s['unproved']} unproved, {s['justified']} justified; "
            f"units: {', '.join(run.unit_names()) or '-'}")


def _matching_text(m: dict) -> list[str]:
    c = m["counts"]
    out = [f"srd003 matching: exact={c['exact']} "
           f"fingerprint={c['fingerprint']} "
           f"unique_entity={c['unique_entity']} "
           f"duplicate_identity={c['duplicate_identity']} "
           f"ambiguous_candidates={c['ambiguous_candidates']} "
           f"unmatched={c['unmatched']} (fingerprints "
           f"{m['fingerprint_support']})"]
    for u in m["unresolved"]:
        if not u["outcomes_differ"]:
            continue
        out.append(f"  not paired ({u['reason']}): {u['rule']} "
                   f"{u['entity']} {u['file']}")
        for run, cands in u["candidates"].items():
            for c in cands:
                out.append(f"    {run}: candidate {c['candidate']} at "
                           f"{c['line']}:{c['column']} [{c['status']}]")
    return out


def orchestration_text(o: dict) -> list[str]:
    """`prove` provenance (analysis.orchestration), shown first."""
    return [f"proof command: {shlex.join(o['command'])}",
            f"GNATprove exit: {o['gnatprove_exit_code']}",
            f"fresh results: {o['result_path']}",
            f"selection: {o['result_selection']}"]


def orchestration_plan_text(plan: dict) -> str:
    """`prove --dry-run` text output."""
    return "\n".join([
        f"proof command: {shlex.join(plan['command'])}",
        "dry run: GNATprove not executed; no result set inspected",
        f"selection: {plan['result_selection']}",
        *([f"results: {plan['result_path']}"] if plan["result_path"]
          else [])]) + "\n"


def to_text(runs: list[ProofRun], diags: list[Diagnostic],
            notes: list[str], analysis: dict | None = None) -> str:
    out = []
    if analysis and "orchestration" in analysis:
        out += orchestration_text(analysis["orchestration"])
    source = (analysis or {}).get("input")
    if source and source.get("discovered"):
        out.append(f"results: {source['path']} (auto-discovered; "
                   "analyses the results on disk, which match the current "
                   "sources only if GNATprove was just run)")
    out += [run_header(r) for r in runs]
    for n in notes:
        out.append(f"note: {n}")
    if analysis and "srd003_matching" in analysis:
        out += _matching_text(analysis["srd003_matching"])
    out.append("")
    if not diags:
        out.append("no SRD diagnostics")
    for d in diags:
        out.append(diagnostic_to_text(d))
        out.append("")
    counts: dict[str, int] = {}
    for d in diags:
        counts[d.code] = counts.get(d.code, 0) + 1
    out.append("summary: " + (", ".join(f"{c}={n}"
                                        for c, n in sorted(counts.items()))
                              or "0 diagnostics"))
    return "\n".join(out).rstrip() + "\n"


def diagnostic_to_dict(d: Diagnostic) -> dict:
    def loc(l):
        return None if l is None else {"file": l.file, "line": l.line,
                                       "column": l.column}
    info = RULES[d.code]
    return {
        "code": d.code,
        "category": info.category,
        "action": info.action,
        "severity": d.severity.value,
        "confidence": d.confidence.value,
        "title": d.title,
        "entity": d.entity,
        "primary_location": loc(d.primary_location),
        "related": [{"role": r.role, "rule": r.rule, "status": r.status,
                     "entity": r.entity, "location": loc(r.location),
                     "message": r.message,
                     **({"run": r.run} if r.run else {})}
                    for r in d.related],
        "evidence": list(d.evidence),
        "explanation": d.explanation,
        "recommendation": d.recommendation,
        "data": {k: _plain(v) for k, v in d.data},
        **({"match_quality": d.match_quality} if d.match_quality else {}),
    }


def _plain(v):
    if isinstance(v, tuple):
        return [_plain(x) for x in v]
    return v


def rules_to_dict() -> dict:
    return {c: {"title": r.title, "confidence": r.confidence_label,
                **({"confidence_policy": r.confidence_policy}
                   if r.confidence_policy else {}),
                "scope": r.scope,
                "category": r.category,
                "action": r.action,
                "action_description": r.action_description}
            for c, r in RULES.items()}


def summary_to_dict(diags: list[Diagnostic]) -> dict:
    """Deterministic counts derived only from `diags` (never maintained
    separately). Every known code / confidence / category / action is
    present, with 0 when absent, so consumers need no key checks."""
    def count(keys, values) -> dict:
        out = {k: 0 for k in keys}
        for v in values:
            out[v] = out.get(v, 0) + 1
        return out
    infos = [RULES[d.code] for d in diags]
    return {
        "diagnostic_count": len(diags),
        "by_code": count(RULES, (d.code for d in diags)),
        "by_confidence": count((c.value for c in Confidence),
                               (d.confidence.value for d in diags)),
        "by_category": count((r.category for r in RULES.values()),
                             (i.category for i in infos)),
        "by_action": count((r.action for r in RULES.values()),
                           (i.action for i in infos)),
    }


def to_json(runs: list[ProofRun], diags: list[Diagnostic],
            notes: list[str], analysis: dict | None = None) -> str:
    doc = {
        "format_version": JSON_FORMAT_VERSION,
        "tool": "spark_refine_diagnostics",
        "rules": rules_to_dict(),
        "runs": [{"name": r.name, "gnatprove": r.tool_version,
                  "command_line": r.command_line,
                  "unit_attribution": r.unit_attribution,
                  "units": r.unit_names(), **r.summary()} for r in runs],
        "notes": notes,
        "analysis": analysis or {},
        "summary": summary_to_dict(diags),
        "diagnostics": [diagnostic_to_dict(d) for d in diags],
    }
    return json.dumps(doc, indent=2) + "\n"
