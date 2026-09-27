#!/usr/bin/env python3
"""Capture the committed diagnostics fixtures from real GNATprove runs.

Provenance of every fixture: diagnostics/tests/fixtures/manifest.toml.
GNATprove is always invoked through the benchmarks' own code (gate
run_gnatprove, ablation run_case), so switches and toolchain are those of
Tasks 001-004 (pinned FSF GNATprove 16.1.0). Fixtures are sanitized copies
of real output; the hand-written expectations (tests/expectations.toml) are
never touched by this script.

A "case" fixture may list `extra_sources`: directories (relative to
diagnostics/) of fixture-only Ada units, e.g. the false-client-assertion
client. They are staged with src/ under examples/<ex>/obj/srd_extra_src/
(git-ignored); benchmark sources are never modified.

  python3 diagnostics/scripts/capture_fixtures.py produce [NAME ...]
  python3 diagnostics/scripts/capture_fixtures.py collect [NAME ...]

produce  runs GNATprove for producer = "case" / "gate" fixtures
         ("benchmark" fixtures come from the benchmark scripts; the
         commands are in tests/fixtures/README.md)
collect  copies examples/<ex>/obj/<obj>/gnatprove/{gnatprove.sarif,
         *.spark, *.ali} into tests/fixtures/<name>/, sanitized, and writes
         fixture.json (provenance)

Sanitization removes only content no diagnostic reads; results are kept:
  SARIF   drop tool.driver.rules (static catalogue) and invocation
          timestamps; every result kept verbatim, one per line
  .spark  keep stop_reason, pragma_assume, entity names and each proof/flow
          entry.s rule/severity/file/line/col/entity/stats
  .ali    keep only V/U/W/Z lines
"""

from __future__ import annotations

import importlib
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"
DIAGNOSTICS = REPO / "diagnostics"
FIXTURES = DIAGNOSTICS / "tests" / "fixtures"
MANIFEST = FIXTURES / "manifest.toml"
# .spark message text duplicates the SARIF message and is never read.
SPARK_KEEP = ("rule", "severity", "file", "line", "col", "entity", "stats")


def manifest() -> dict:
    return tomllib.loads(MANIFEST.read_text(encoding="utf-8"))


def _modules(example: str):
    scripts = str(EXAMPLES / example / "scripts")
    sys.path[:] = [p for p in sys.path if not p.startswith(str(EXAMPLES))]
    sys.path.insert(0, scripts)
    for m in ("check_proof_results", "ablate_proof_support"):
        sys.modules.pop(m, None)
    return (importlib.import_module("check_proof_results"),
            importlib.import_module("ablate_proof_support"))


def _edits(example: str, abl, spec: list[str]) -> list[tuple]:
    out = []
    for item in spec:
        kind, _, rest = item.partition(":")
        if kind == "fault":
            fault = tomllib.loads((EXAMPLES / example / rest / "fault.toml")
                                  .read_text(encoding="utf-8"))
            out += [(e["file"], e["find"], e["replace"])
                    for e in fault["edit"]]
        elif kind == "ablation":
            variant, case = rest.split(":", 1)
            cases = getattr(abl, "VARIANT_CASES", {}).get(variant, abl.CASES)
            out += list(cases[case])
        else:
            raise SystemExit(f"unknown edit source {item!r}")
    return out


def _staged_src(gate, name: str, extra_sources: list[str]) -> Path:
    """src/ plus fixture-only client units, copied under obj/ (ignored by
    git). The benchmark sources are never modified."""
    stage = gate.OBJ / "srd_extra_src" / name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for f in gate.SRC.glob("*.ad[sb]"):
        shutil.copy2(f, stage / f.name)
    for rel in extra_sources:
        for f in sorted((DIAGNOSTICS / rel).glob("*.ad[sb]")):
            if (stage / f.name).exists():
                raise SystemExit(f"{name}: {f.name} would shadow a "
                                 "benchmark source")
            shutil.copy2(f, stage / f.name)
    return stage


def produce(name: str, spec: dict) -> None:
    ex = spec["example"]
    if spec["producer"] not in ("gate", "case"):
        return
    gate, abl = _modules(ex)
    print(f"== produce {name}", flush=True)
    if spec["producer"] == "gate":
        var = gate.VARIANTS[spec["variant"]]
        gate.run_gnatprove(var["obj_name"], var["impl"])
        return
    edits = _edits(ex, abl, spec["edits"])
    case = spec["obj"].removeprefix("ablation_htc_").removeprefix(
        "ablation_")
    extra = spec.get("extra_sources", [])
    if extra and ex != "fixed_pool":
        raise SystemExit(f"{name}: extra_sources only supported for "
                         "fixed_pool")
    old_src = gate.SRC
    if extra:
        # the ablation module reads the source directory through its gate
        # module (`g.SRC`); point it at the staged copy for this case only
        gate.SRC = _staged_src(gate, name, extra)
    try:
        if ex == "ring_buffer":
            abl.run_case(case, edits, spec.get("switches", []),
                         spec["variant"])
        else:
            abl.run_case(case, edits, spec.get("switches", []))
    finally:
        gate.SRC = old_src
    if not (EXAMPLES / ex / "obj" / spec["obj"] / "gnatprove").is_dir():
        raise SystemExit(f"{name}: expected output in obj/{spec['obj']}")


def sanitize_paths(text: str) -> str:
    """Replace the capturing checkout's absolute path by a placeholder
    (appears only in invocation command lines, e.g. -XPROOF_PATTERNS_SRC)."""
    return text.replace(str(REPO), "<repo>")


def sanitize_sarif(text: str) -> str:
    data = json.loads(sanitize_paths(text))
    run = data["runs"][0]
    run["tool"]["driver"].pop("rules", None)
    for inv in run.get("invocations", []):
        inv.pop("startTimeUtc", None)
        inv.pop("endTimeUtc", None)
    results = run.pop("results")
    meta = {"tool": run.pop("tool"), "invocations": run.pop("invocations",
                                                             [])}
    meta.update(run)
    lines = ['{', f' "version": {json.dumps(data["version"])},',
             ' "runs": [{']
    for k, v in meta.items():
        lines.append(f'  {json.dumps(k)}: {json.dumps(v, sort_keys=True)},')
    lines.append('  "results": [')
    lines.append(",\n".join("   " + json.dumps(r, sort_keys=True)
                            for r in results))
    lines += ['  ]', ' }]', '}']
    return "\n".join(lines) + "\n"


def sanitize_spark(text: str) -> str:
    data = json.loads(text)
    out = {"stop_reason": data.get("stop_reason"),
           "pragma_assume": data.get("pragma_assume") or [],
           "entities": {k.strip(): {"name": (v or {}).get("name", "")}
                        for k, v in (data.get("entities") or {}).items()}}
    for kind in ("proof", "flow"):
        out[kind] = [{k: e[k] for k in SPARK_KEEP if k in e}
                     for e in data.get(kind) or []]
    # one entry per line: compact, but reviewable in diffs
    lines = ["{"]
    for i, k in enumerate(sorted(out)):
        sep = "," if i < len(out) - 1 else ""
        v = out[k]
        if isinstance(v, list) and v:
            lines.append(f"{json.dumps(k)}: [")
            lines.append(",\n".join(json.dumps(e, sort_keys=True)
                                    for e in v))
            lines.append(f"]{sep}")
        else:
            lines.append(f"{json.dumps(k)}: "
                         f"{json.dumps(v, sort_keys=True)}{sep}")
    return sanitize_paths("\n".join(lines) + "\n}\n")


def sanitize_ali(text: str) -> str:
    return "\n".join(l for l in text.splitlines()
                     if l[:2] in ("V ", "U ", "W ", "Z ")) + "\n"


def collect(name: str, spec: dict) -> None:
    src = EXAMPLES / spec["example"] / "obj" / spec["obj"] / "gnatprove"
    if not (src / "gnatprove.sarif").is_file():
        raise SystemExit(f"{name}: no output in {src} (run produce or the "
                         "benchmark scripts first)")
    dest = FIXTURES / name
    dest.mkdir(parents=True, exist_ok=True)
    for old in [*dest.glob("*.spark"), *dest.glob("*.ali")]:
        old.unlink()
    (dest / "gnatprove.sarif").write_text(
        sanitize_sarif((src / "gnatprove.sarif").read_text("utf-8")),
        encoding="utf-8")
    for p in sorted(src.glob("*.spark")):
        (dest / p.name).write_text(sanitize_spark(p.read_text("utf-8")),
                                   encoding="utf-8")
    for p in sorted(src.glob("*.ali")):
        (dest / p.name).write_text(
            sanitize_ali(p.read_text("utf-8", errors="replace")),
            encoding="utf-8")
    prov = {"name": name, **spec,
            "source": f"examples/{spec['example']}/obj/{spec['obj']}/"
                      "gnatprove",
            **provenance(src, spec)}
    (dest / "fixture.json").write_text(
        json.dumps(prov, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"collected {name} <- {prov['source']}")


def _case_label(spec: dict) -> str:
    """Human-readable benchmark/variant/case of a fixture."""
    if spec.get("edits"):
        return " + ".join(spec["edits"])
    if spec.get("extra_sources"):
        return "extra client: " + ", ".join(spec["extra_sources"])
    return spec["obj"]


def provenance(src: Path, spec: dict) -> dict:
    """Toolchain and configuration provenance, read from the raw output
    (SARIF driver version, invocation command line, .ali V header) and the
    example's pinned alire.toml. The .ali files are GNAT 16.1.0 output: the
    ALI adapter makes no claim about other compiler versions."""
    sarif = json.loads((src / "gnatprove.sarif").read_text("utf-8"))
    run = sarif["runs"][0]
    cmd = (run.get("invocations") or [{}])[0].get("commandLine", "")
    alire = tomllib.loads((EXAMPLES / spec["example"] / "alire.toml")
                          .read_text("utf-8"))
    pins = {}
    for dep in alire.get("depends-on", []):
        pins.update(dep)
    ali_headers = set()
    for p in src.glob("*.ali"):
        first = p.read_text("utf-8", errors="replace").split("\n", 1)[0]
        m = re.match(r'V "([^"]*)"', first)
        if m:
            ali_headers.add(m.group(1))
    provers = re.findall(r"--prover=(\S+)", cmd)
    return {"provenance": {
        "benchmark": spec["example"],
        "variant": _variant(spec),
        "case": _case_label(spec),
        "gnatprove_version": run["tool"]["driver"].get("version", ""),
        "gnat_version": pins.get("gnat_native", "").lstrip("="),
        "ali_producer": "GNAT " + pins.get("gnat_native", "").lstrip("="),
        "ali_version_header": sorted(ali_headers),
        "sparklib_version": pins.get("sparklib", "").lstrip("="),
        "prover_configuration": (
            f"--prover={','.join(provers)} (single prover)" if provers
            else "project Prove switches: --level=2 portfolio "
                 "(cvc5, z3, altergo)"),
        "command_line": sanitize_paths(cmd),
        "source_ref": _source_ref(spec["example"]),
    }}


def _variant(spec: dict) -> str:
    """Explicit `variant`, else the benchmark's obj/ naming convention
    (htc = ring buffer B, lib/library_backed = Task 004 pool)."""
    if "variant" in spec:
        return spec["variant"]
    obj = spec["obj"]
    if spec["example"] == "ring_buffer":
        return "head_tail_count" if "htc" in obj else "first_length"
    return "library_backed" if "lib" in obj else "baseline"


def _source_ref(example: str) -> str:
    """Commit the benchmark sources were captured from. The fixtures'
    GNATprove runs were made from sources identical to this commit (no
    benchmark source is modified by Task 005); fixture-only client units
    are committed under diagnostics/tests/fixture_sources/."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                              capture_output=True, text=True, check=True
                              ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--",
             f"examples/{example}", "proof_patterns"],
            cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown (git unavailable)"
    return head + (" + uncommitted benchmark changes" if dirty else "")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("produce", "collect"):
        print(__doc__)
        return 2
    specs = manifest()
    names = sys.argv[2:] or list(specs)
    unknown = [n for n in names if n not in specs]
    if unknown:
        raise SystemExit(f"unknown fixture(s): {unknown}")
    for n in names:
        (produce if sys.argv[1] == "produce" else collect)(n, specs[n])
    return 0


if __name__ == "__main__":
    sys.exit(main())
