# Task 009 — Libadalang semantic enrichment of SRD002

Status: implemented (experimental, opt-in `--semantic`). Base: `origin/main`
`d3d8be13f520e4a3c8f7857920ff03de3c71efb5` (contains the reviewed Task 008 head
`336c8e5b`).

## Result in one paragraph

With `--semantic -P PROJECT [-X NAME=VALUE ...]`, each SRD002 client failure is
annotated by Libadalang. A `VC_PRECONDITION` gets the exact call, the resolved
callee (fully qualified name and declaration range), the callee's explicit
`Pre` (text and range), and its top-level `and` / `and then` conjuncts. A
`VC_ASSERT` gets the asserted expression and the subprogram that encloses it.
All 15 client failures (9 `VC_PRECONDITION`, 6 `VC_ASSERT`) of the five
SRD002 benchmark cases resolve `exact`.
The pre-registered experiment shows that FSF GNATprove 16.1.0 output is
**NOT ATTRIBUTABLE** to a Pre conjunct. `failed_conjunct` is therefore always
`null`, with attribution `not_provided_by_gnatprove`. SRD002's trigger,
confidence, title, causes and recommendation are unchanged. Without
`--semantic`, the output is byte-identical to Task 008. The core package
still has no runtime dependencies.

## 1. Evidence gate: Libadalang in this repository

| question | finding |
|---|---|
| PyPI | `libadalang` is **not published** (`pypi.org/pypi/libadalang` → 404) |
| apt | no package |
| Alire | crate `libadalang=26.0.0` (current release); source build |
| build | `alr get` + `alr build` with `LIBRARY_TYPE=relocatable`: 215–217 s wall (32 cores, cold, twice); Alire picks GNAT 15.3.1 (`gnat_native`) for it, separate from the proof toolchain (GNAT 16.1.0) |
| Python binding | `python/libadalang/__init__.py` loads `libadalang.so` from its own directory if present |
| bundle | 21 shared objects (Libadalang, Langkit, GNATcoll, GPR/GPR2, XML/Ada, VSS, AdaSAT, Prettier-Ada, GNAT 15 runtime) copied next to the binding with `DT_RPATH=$ORIGIN` → **166 MB**, relocatable, cacheable; works from `env -i` and inside `alr exec` of the GNAT 16 crates |
| version string | `libadalang.version` is `"undefined"` in Alire builds; the setup script records the crate version (`SPARK_REFINE_CRATE_VERSION`) |

Spike (all passed): `import libadalang`; `GPRProject("ring_buffer.gpr",
scenario_vars=...)` loads (SPARKlib `with` resolved under `alr exec`);
`create_context()` gives project-aware resolution; `ring_buffer_client_proof.adb`
has no parse diagnostics; `no_is_full_post` 9:7 → `Push (Q, A)` →
`p_referenced_decl()` = `Ring_Buffer.Push` in
`obj/ablation_src/no_is_full_post/ring_buffer.ads`.

Reproducibility: `diagnostics/scripts/setup_libadalang.sh` pins the whole
observed dependency solution (`alr pin`: adasat, gnatcoll*, gprconfig_kb,
langkit_support, libgpr, libgpr2, prettier_ada, xmlada = 26.0.0, vss_text =
26.2.0) and the build tools (`gnat_native=15.3.1`, `gprbuild=26.0.1`). It
bundles with `patchelf==0.17.2.1` from PyPI and smoke-tests the result.
Verified from scratch into a new directory: 215 s, identical solution.

Decision: **separately documented environment dependency**, not a pip extra.
There is no installable distribution, so a `[semantic]` extra would be
hypothetical. The wheel stays pure Python with `dependencies = []`.

## 2. Architecture

```
cli.py  --semantic, -P/--project, -X NAME=VALUE   (explain, analyze, prove)
  └─ semantic.py      policy, provenance gate, JSON shape, never fatal
       └─ semantic_lal.py   ONLY module importing libadalang (lazily):
                            GPRProject + AnalysisContext, unit lookup,
                            call discovery, p_referenced_decl, Pre aspect,
                            conjunct decomposition, assertion context
  ali.py              + load_ali_sources: .ali D records
  gnat_checksum.py    GNAT source checksum over Libadalang tokens
```

`semantic` is a new optional `Diagnostic` field (`compare=False`), rendered
only when set. `prove` reuses its own `-P`; `explain`/`analyze` take `-P` or
`--project`. No project is ever inferred: without `-P`, enrichment reports
`no project supplied`. `-X` values are handed to Libadalang's
`GPRProject(scenario_vars=...)` and are **not** passed to GNATprove. For
`prove`, GNATprove pass-through `-X` arguments are not reinterpreted, so the
user repeats them before `--`. The benchmarks need `RING_BUFFER_SRC` /
`FIXED_POOL_SRC` (and the `*_VARIANT` values) to select the ablated source
directory GNATprove analysed.

## 3. Call-site resolution rule

Observed for FSF GNATprove 16.1.0: a `VC_PRECONDITION` is reported at the
first column of the called name, or for a selected name `P.Op (...)` at the
`.` before the selector (`client.adb:7:10` for `Ops.Op (X, Y)` at column 7).
The adapter enumerates every Libadalang `Name` with `p_is_call` (outermost
name of each call) and computes that anchor from the tree and tokens. A
check is `exact` only if exactly one call is anchored at its line:column.
Otherwise it is `ambiguous` (>1) or `unresolved` (0, or `p_referenced_decl`
fails). Identifier text is never matched. `unavailable` covers the file not
being in the project, a parse diagnostic, or a failed provenance check.

For `VC_ASSERT`, the location must lie inside the expression argument of a
`pragma Assert` / `Assert_And_Cut` / `Loop_Invariant` / `Check`. The result
is the expression and the enclosing subprogram, with no callee and no Pre.

## 4. Source/result provenance

The ablation fixtures are proved from materialised copies under
`obj/ablation_src/<case>/`. A source file is used only if its **GNAT source
checksum AND modification time** equal a `D` record in the analysed result
set's `.ali` files. Those records are GNAT's own list of analysed sources:
`D ring_buffer.ads 20260927180831 baec7707`. The checksum is recomputed in
`gnat_checksum.py` from Libadalang's token stream, following GNAT's
documented algorithm (`sinput.ads`, "Checksum Handling", `scng.adb`):
CRC-32 without the final XOR, lower-cased identifiers and keywords each
followed by `Tok_Identifier`'s position (5), numeric literals by 0/1,
underscores dropped from decimal literals, and `[ ] { }` not accumulated.
Validated against GNAT: **28/28** source dependencies of the
`no_is_full_post` result set (client, spec, SPARKlib, GNAT runtime), and
all 19 committed snapshot sources. The checksum ignores layout, so the
mtime match is also required before a line/column is trusted.

Measured failure modes (tests):

| situation | result |
|---|---|
| positive `ring_buffer.ads` used for an ablation result (no `-X`) | callee `unavailable`: checksum differs |
| same tokens, one line inserted | `unavailable`: timestamp differs |
| Task 005 fixtures (sanitized .ali without D records) | `evaluated: false`, provenance unavailable |

## 5. Pre-registered failed-conjunct experiment — NOT ATTRIBUTABLE

`diagnostics/tests/semantic_fixtures/conjunct_experiment/` (4 Ada files,
real GNATprove 16.1.0, `--level=2`, cvc5/z3/altergo):

| line | call | ground truth |
|---|---|---|
| 7 | `Ops.Op (X, Y)`, `Pre => X > 0 and then Y > 0` | only conjunct 1 fails |
| 12 | same | only conjunct 0 fails |
| 17 | same | both fail |
| 22 | `Ops.Op3`, `X > 0 and Y > 0 and Z > 0` | only conjunct 1 fails |

Evidence (committed, `evidence.json`, tests `ConjunctExperiment`):

- SARIF: one `VC_PRECONDITION` result per call, keys exactly
  `kind, level, locations, message, ruleId`; one location, at the call
  anchor, whichever conjunct fails. The four results are structurally
  identical except for the line.
- `.spark`: entry keys `check_col, check_file, check_line, check_tree,
  cntexmp, cntexmp_value, col, entity, file, how_proved, line, message,
  msg_id, rule, severity, unproved_status`. None of them names a conjunct.
- `check_tree` (undocumented Why3 goal tree after `split_goal_wp_conj`):
  "first conjunct fails" (12) and "both fail" (17) have **identical** goal
  outcomes (`[{}, {CVC5/Z3/altergo: Unknown}]`), so no structural rule
  over it can distinguish them. It also counts Why3 goals, including
  parameter/range goals, not source conjuncts.
- The English message sometimes says "cannot prove X > 10". That is
  message parsing and is forbidden, and it is absent in all four cases
  above.

Therefore `failed_conjunct: null`, `attribution:
"not_provided_by_gnatprove"`, always. A test fails if the semantic modules
touch message text, call `eval`/`exec`/`re`, or evaluate expressions.

## 6. Benchmark cases (all `exact`)

| case | check | call | callee | explicit Pre |
|---|---|---|---|---|
| ring `no_is_full_post` | 9:7, 10:7, 25:7 | `Push (Q, A)` / `(Q, B)` / `(Q, X)` | `Ring_Buffer.Push` (`ring_buffer.ads:36`) | `not Is_Full (B)` |
| | 16:43 VC_ASSERT | — | — | assertion `not Is_Empty (Q) and not Is_Full (Q)` |
| ring `no_public_model_bound` | 25:7 | `Push (Q, X)` | `Ring_Buffer.Push` | `not Is_Full (B)` |
| ring `no_is_empty_post` | 11:7 | `Pop (Q, X)` | `Ring_Buffer.Pop` | `not Is_Empty (B)` |
| | 25:7 | `Push (Q, X)` | `Ring_Buffer.Push` | `not Is_Full (B)` |
| | ads 24:45, 25:45 | `Sequences.Remove (...)` / `Sequences.Get (...)` | `Ring_Buffer.Sequences.Remove` / `.Get` (SPARKlib instance) | `(SPARKlib_Defensive => Position in ...)` |
| | 7:22, 16:22 VC_ASSERT | — | — | assertions |
| pool `spec_no_count_posts` | 35:7 | `Allocate (P, X)` | `Fixed_Pool.Allocate` (`fixed_pool.ads:43`) | `Free_Count (P) > 0` |
| | 15:22, 20:22 VC_ASSERT | — | — | assertions |
| pool `false_client_assert` | 9:22 VC_ASSERT | — | **no callee, no Pre** | assertion `Free_Count (P) = 0` in `Fixed_Pool_False_Client.Initialize_Then_Claim_Empty`; SRD002 stays LOW |

None of this says which contract is missing. The ablations removed
`Is_Full`'s / `Free_Count`'s postconditions (benchmark ground truth); the
enrichment shows only the call and the Pre that GNATprove could not
establish.

Experiment corpus (lookup/extraction unit tests): statement-start call,
multi-line call, nested `F (F (X))`, three calls on one line, selected
name `Ops.Op`, use-clause `Op`, overloaded `Over (Integer)` /
`Over (Boolean)` resolved to different declarations, no Pre, multi-line
Pre, `and`, `and then`, `(A or else B) and then (C)`, and nested calls with a
parenthesised inner `and` kept whole.

## 7. JSON (format_version stays 1; additive, only with --semantic)

```json
"analysis": {"semantic": {"requested": true, "evaluated": true,
  "backend": "libadalang", "version": "26.0.0", "project": "ring_buffer.gpr",
  "scenario": {"RING_BUFFER_SRC": "..."},
  "resolutions": {"exact": 4, "ambiguous": 0, "unresolved": 0, "unavailable": 0}}}
"diagnostics": [{"code": "SRD002", ..., "semantic": {"backend": "libadalang",
  "checks": [{"rule": "VC_PRECONDITION",
    "location": {"file": "ring_buffer_client_proof.adb", "line": 9, "column": 7},
    "resolution": "exact",
    "call": {"text": "Push (Q, A)", "location": {SPAN}},
    "callee": {"name": "Ring_Buffer.Push", "kind": "procedure", "declaration": {SPAN}},
    "precondition": {"explicit": true, "text": "not Is_Full (B)", "location": {SPAN},
      "conjuncts": [{"index": 0, "text": "not Is_Full (B)", "location": {SPAN}}],
      "failed_conjunct": null, "attribution": "not_provided_by_gnatprove"}}]}}]
```

`SPAN` = `{file, start_line, start_column, end_line, end_column}`. `file` is
relative to the project directory, or the base name outside it (SPARKlib).
Non-exact entries carry `resolution` + `reason`. If enrichment is not
evaluated, `analysis.semantic` has `evaluated: false` + `reason` and no
diagnostic gets a `semantic` key. `analysis.rules.SRD002` is untouched:
"SRD002 evaluated" and "semantic evaluated" are independent. There are no
timestamps and no Libadalang object representations.

## 8. Degradation (never fatal; exit status unchanged)

| situation | outcome |
|---|---|
| no `--semantic` | byte-identical Task 008 output (202 comparisons: explain/analyze × 49 fixtures × text/json, compare-provers, rules, prove --dry-run) |
| libadalang not importable / native load error | `evaluated: false`, reason `libadalang not importable (...)` |
| no `-P` | `evaluated: false`, `no project supplied` |
| project load failure | `evaluated: false`, `project ... could not be loaded` |
| no SRD002 | `evaluated: false`, `no SRD002 diagnostic to enrich` (backend not opened) |
| no .ali D records | `evaluated: false`, provenance unavailable |
| file missing/not in project, parse diagnostics, provenance mismatch | per check `unavailable` |
| 0 / >1 anchored calls, resolution failure | per check `unresolved` / `ambiguous` |
| unexpected backend exception | per check `unavailable` |

## 9. Installation, size, CI

- Core: `pip install ./diagnostics`; wheel 56 426 → 66 529 bytes (three
  new pure-Python modules), `dependencies = []`, `libadalang` imported only
  lazily inside `semantic_lal.py` (test-enforced). The packaging smoke test
  checks `--semantic` without Libadalang in the installed wheel and in
  editable mode.
- Semantic: `diagnostics/scripts/setup_libadalang.sh [DIR]` (~3.6 min cold
  on 32 cores, 166 MB bundle; build tree ~1.4 GB of Alire cache), then
  `source DIR/env.sh`. The benchmark projects `with "sparklib"`, so run
  under `alr -n exec` of the example crate.
- CI: new isolated job `diagnostics-semantic`. It caches the bundle keyed on
  the setup script, runs the full suite under `alr exec` with **no skips
  allowed**, and runs E2E-F. Other jobs are unchanged and do not install
  Libadalang. Without Libadalang, the 12 Libadalang tests skip (structural
  job).
- Fixtures: `diagnostics/tests/semantic_fixtures/` = 6 cases, 432 KB
  (sanitized results keeping `D` records, 19 verified source files,
  snapshots with sha256 + D timestamp, restored by the tests). No benchmark
  tree is copied; SPARKlib comes from the Alire environment. Captured by
  `diagnostics/scripts/capture_semantic_fixtures.py`, which refuses any
  source whose checksum/mtime do not match the result set.

## 10. Tests

Existing diagnostics suite: 188 tests at Task 008 (189 with the new
Libadalang-isolation packaging test). New `test_semantic.py`: 38 tests (26
run without Libadalang, 12 need it). Total 227; with Libadalang, 0 skipped. E2E-F (fresh
`no_is_full_post` ablation + `explain --semantic`): PASS locally.

## 11. Recommendation for Task 010

Conjunct attribution cannot come from GNATprove 16.1.0 output. Candidates,
in order of evidence value:

1. Keep enrichment opt-in until the CI job has run on hosted runners, and
   measure the cold-build time there.
2. A separately named, pre-registered experiment that re-proves each
   top-level conjunct as its own check (e.g. a generated scratch client with
   one `pragma Assert` per conjunct, in `obj/` only). This would be *new
   proof evidence*, not an inference from existing output, and needs its own
   trust review.
3. Otherwise use the recovered callee/Pre to *group* SRD002 failures by
   callee, which is purely descriptive, before any new rule.

## 12. Non-goals honoured

There is no new SRD rule and no SRD001–003 change. Nothing rewrites source,
repairs proofs, changes contracts or generates source. There is no Ada
parser (all structure comes from Libadalang; the checksum only consumes
Libadalang tokens), no English message parsing, and no heuristic conjunct
choice. GNATprove remains the proof authority.
