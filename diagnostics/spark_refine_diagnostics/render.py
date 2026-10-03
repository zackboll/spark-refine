"""Text and JSON rendering of diagnostics. Output is deterministic:
diagnostics are sorted by (code, entity, location), and neither format
contains timestamps or absolute paths added by the tool."""

from __future__ import annotations

import json
import shlex

from .check_inventory import inventory_text
from .model import Diagnostic, ProofRun
from .model import Confidence
from .rules import RULES
from .semantic_shape import (exact_assertion_complete,
                             exact_precondition_complete)

JSON_FORMAT_VERSION = 1
PRECONDITION = "VC_PRECONDITION"


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
    if d.semantic is not None:
        out += semantic_text(d.semantic)
    out.append("  evidence:")
    out += [f"    - {e}" for e in d.evidence]
    out.append("  explanation:")
    out += wrap(d.explanation, "    ")
    out.append("  recommendation:")
    out += wrap(d.recommendation, "    ")
    return "\n".join(out)


def _span(s: dict) -> str:
    return f"{s['file']}:{s['start_line']}:{s['start_column']}"


def _one_line(text: str) -> str:
    return " ".join(text.split())


# Task 011: text rendering of semantic enrichment never raises on a
# malformed or incomplete internal semantic object. Exact entries are
# rendered only if they satisfy the SAME structural contract Task 010
# grouping uses (semantic_shape.py); otherwise the entry is shown as
# incomplete and none of its call/callee/Pre/conjunct/assertion facts are
# claimed. JSON rendering is unaffected: diagnostic_to_dict() serialises
# the semantic value exactly as provided.
INCOMPLETE_PRECONDITION = ("exact semantic entry lacks complete "
                           "call/callee/Pre data")
INCOMPLETE_ASSERTION = "exact semantic entry lacks complete assertion data"


def _incomplete(reason: str, indent: str) -> list[str]:
    return [f"{indent}semantic entry: incomplete",
            *wrap(f"reason: {reason}", indent)]


def _check_header(c: dict) -> str:
    loc = c.get("location")
    where = (f"{loc.get('file', '-')}:{loc.get('line', '-')}:"
             f"{loc.get('column', '-')}" if isinstance(loc, dict)
             else "(no location)")
    return f"    {where} {c.get('rule', '-')}: {c.get('resolution', '-')}"


def _precondition_lines(c: dict) -> list[str]:
    """Caller guarantees exact_precondition_complete(c)."""
    pre = c["precondition"]
    out = [f"      call: {_one_line(c['call']['text'])}",
           f"      callee: {c['callee']['name']} "
           f"({_span(c['callee']['declaration'])})"]
    if not pre["explicit"]:
        out.append("      public Pre: none (no explicit Pre aspect)")
        return out
    out += wrap(f"public Pre: {_one_line(pre['text'])}", "      ")
    if len(pre["conjuncts"]) > 1:
        for cj in pre["conjuncts"]:
            out += wrap(f"[{cj['index']}] {_one_line(cj['text'])}",
                        "        ")
    out.append("      failed conjunct: unknown (GNATprove "
               "result does not identify a specific conjunct)")
    return out


def _assertion_lines(c: dict) -> list[str]:
    """Caller guarantees exact_assertion_complete(c)."""
    a = c["assertion"]
    out = wrap(f"assertion: {_one_line(a['text'])} "
               f"({_span(a['location'])})", "      ")
    if c.get("enclosing_subprogram"):
        out.append(f"      in: {c['enclosing_subprogram']}")
    return out


def semantic_text(sem) -> list[str]:
    """Task 009: concise per-check semantic block (--semantic only).
    Task 011: fail-safe on malformed input (see INCOMPLETE_*)."""
    if not isinstance(sem, dict):
        return ["  semantic:", *_incomplete("semantic block is not an "
                                            "object", "    ")]
    out = [f"  semantic ({sem.get('backend', '-')}):"]
    checks = sem.get("checks")
    if not isinstance(checks, list):
        return out + _incomplete("semantic block has no list of checks",
                                 "    ")
    for c in checks:
        if not isinstance(c, dict):
            out += _incomplete("semantic check entry is not an object",
                               "    ")
            continue
        out.append(_check_header(c))
        if c.get("resolution") != "exact":
            out += wrap(f"reason: {c.get('reason', '-')}", "      ")
            continue
        # Dispatch on the rule, exactly as semantic.py dispatches to the
        # backend (VC_PRECONDITION -> call context, anything else ->
        # assertion context); never on which keys happen to be present.
        if c.get("rule") == PRECONDITION:
            out += (_precondition_lines(c) if exact_precondition_complete(c)
                    else _incomplete(INCOMPLETE_PRECONDITION, "      "))
        else:
            out += (_assertion_lines(c) if exact_assertion_complete(c)
                    else _incomplete(INCOMPLETE_ASSERTION, "      "))
    return out


def semantic_meta_text(m: dict) -> str:
    if not m.get("evaluated"):
        return (f"semantic enrichment: not evaluated "
                f"({m.get('reason', '-')})")
    res = m.get("resolutions")
    counts = (", ".join(f"{k}={v}" for k, v in res.items())
              if isinstance(res, dict) else "-")
    line = (f"semantic enrichment: {m.get('backend', '-')} "
            f"{m.get('version', '-')}, "
            f"project {m.get('project', '-')}; checks: {counts}")
    prov = m.get("provenance")
    if isinstance(prov, dict) and prov.get("layout_exact") is False:
        line += ("\n  source match: GNAT checksum + second-resolution .ali "
                 "timestamp (not byte-exact)")
    return line


GROUPS_DISCLAIMER = ("Groups are descriptive: sharing a callee and Pre does "
                     "not establish a shared cause, does not identify a "
                     "failed conjunct and does not show that a public "
                     "contract must change. GNATprove remains the proof "
                     "authority.")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _loc_text(loc: dict) -> str:
    return f"{loc['file']}:{loc['line']}:{loc['column']}"


def semantic_groups_text(g: dict) -> list[str]:
    """Task 010: report-level SRD002 semantic triage section (summary;
    the per-diagnostic detail follows unchanged)."""
    grouped = _plural(g["grouped_check_count"], "grouped precondition check")
    out = ["SRD002 semantic triage:",
           f"  {grouped} -> "
           f"{_plural(g['group_count'], 'callee/contract group')}",
           f"  {_plural(g['ungrouped_check_count'], 'ungrouped check')}"]
    for grp in g["groups"]:
        c, pre = grp["callee"], grp["precondition"]
        out.append("")
        out.append(f"  {c['name']} ({c['kind']}, "
                   f"{_span(c['declaration'])})")
        if pre["explicit"]:
            out += wrap(f"public Pre: {_one_line(pre['text'])}", "    ")
        else:
            out.append("    public Pre: none (no explicit Pre aspect)")
        out.append(f"    calls: {grp['check_count']}")
        width = max(len(_loc_text(o["location"]))
                    for o in grp["occurrences"])
        for o in grp["occurrences"]:
            dup = (f" (reported {o['duplicate_count']} times)"
                   if o.get("duplicate_count") else "")
            out.append(f"      {_loc_text(o['location']).ljust(width)} "
                       f"{_one_line(o['call']['text'])}{dup}")
    if g["ungrouped"]:
        out.append("")
        out.append("  ungrouped:")
        for u in g["ungrouped"]:
            out.append(f"    {_loc_text(u['location'])} {u['rule']}")
            out.append(f"      {u['reason']}")
    out.append("")
    out += wrap(GROUPS_DISCLAIMER, "  ")
    return out


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
    if analysis and "semantic" in analysis:
        out.append(semantic_meta_text(analysis["semantic"]))
    if analysis and "srd003_matching" in analysis:
        out += _matching_text(analysis["srd003_matching"])
    groups = ((analysis or {}).get("semantic") or {}).get("srd002_groups")
    if groups is not None:
        out.append("")
        out += semantic_groups_text(groups)
    if analysis and "unproved_checks" in analysis:
        out.append("")
        out += inventory_text(analysis["unproved_checks"])
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
        **({"semantic": d.semantic} if d.semantic is not None else {}),
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
