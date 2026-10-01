# spark_refine_diagnostics: GNATprove proof-engineering diagnostics (MVP)

This is a deterministic analyzer for GNATprove's machine-readable output
(`gnatprove.sarif`, `<unit>.spark`, `<unit>.ali`). It turns low-level check
outcomes into higher-level SPARK proof-engineering diagnostics. It targets
only problems **already observed in this repository** (Tasks 001–004).

It does not:

* treat disputed SARIF entity-fallback attribution as an authoritative
  analysed unit for ALI completeness when `.spark` UnitResults are available;

* decide proof status. Only `spark-refine prove` runs GNATprove, and
  only as orchestration (see below);
* modify, repair or generate source;
* synthesize invariants;
* use AI;
* weaken any proof requirement.

Like the benchmark scripts, it uses only the Python 3.11+ standard library
at runtime.

## Installation (Task 006)

The package installs a console command, `spark-refine` (with a hyphen).
Do not confuse it with the legacy Ada bootstrap executable `spark_refine`
(with an underscore) at the repository root.

```bash
python3 -m pip install ./diagnostics       # from the repository root
python3 -m pip install -e ./diagnostics    # editable, for development
spark-refine --version
spark-refine rules                          # works from any directory
```

* Packaging is `pyproject.toml` (setuptools, build-time only). There are
  no runtime dependencies.
* The wheel contains only the `spark_refine_diagnostics` package, README
  and LICENSE. The fixture corpus (`tests/fixtures/`, about 5.5 MB),
  `tests/`, `scripts/` and `obj/` are **not** packaged.
* This is checked by `scripts/packaging_smoke.py` (CI job
  `diagnostics-packaging`). The script builds and inspects the wheel,
  installs it into an isolated venv, and runs the installed command from
  a temporary directory outside the repository. It also runs for an
  editable install.
* Publishing to PyPI is out of scope for now.

## Usage

```bash
spark-refine prove -P my_project.gpr        # preferred: run GNATprove + explain ITS result
spark-refine prove -P my_project.gpr --format json -- --level=2 -j0
spark-refine prove -P my_project.gpr --results obj/proof/gnatprove
spark-refine prove -P my_project.gpr --dry-run   # show the command only

gnatprove -P my_project.gpr                 # manual two-step workflow
spark-refine explain                        # discover the single result set
spark-refine explain obj/proof/gnatprove    # or name it explicitly
spark-refine explain obj/proof/gnatprove/gnatprove.sarif
spark-refine explain --format json > spark-refine.json
spark-refine explain PATH --format json --fail-on SRD001
spark-refine compare-provers \
    --run cvc5=obj/cvc5/gnatprove \
    --run z3=obj/z3/gnatprove \
    --run altergo=obj/altergo/gnatprove \
    [--reference portfolio=obj/baseline/gnatprove]
spark-refine rules [--format json]
```

The Task 005 invocations still work unchanged. `analyze` is a
compatibility alias of `explain`, identical for an explicit `PATH`, and
`PATH` stays required for it:

```bash
cd diagnostics
python3 -m spark_refine_diagnostics analyze ../examples/fixed_pool/obj/negative_p5_release_duplicate/gnatprove
python3 -m spark_refine_diagnostics compare-provers --run ... --run ...
python3 -m spark_refine_diagnostics rules
python3 -m unittest discover -s tests -t tests -v   # no toolchain needed
python3 scripts/e2e_fresh.py                        # pinned toolchain needed
python3 scripts/packaging_smoke.py [--editable]     # build + install check
```

`PATH` is either a GNATprove output directory (`obj/<variant>/gnatprove`
or its parent) or a `gnatprove.sarif` file. An explicit `PATH` is
authoritative, and no discovery is performed.

**Discovery (`explain` without `PATH`).** A *result set* is a directory
that directly contains `gnatprove.sarif` and at least one `*.spark` file.
The current directory is searched recursively and deterministically:
symbolic links are not followed, and hidden directories and Alire's
`alire/` dependency cache are skipped.

* **Exactly one result set:** it is analyzed. The text report starts with
  `results: <path> (auto-discovered; ...)`, and the JSON has
  `analysis.input = {"path": ..., "discovered": true}`.
* **None:** exit 2 with `No GNATprove result set found. Run GNATprove
  first or pass the result path explicitly.`
* **Several:** exit 2, with every candidate listed in sorted order.

The tool never picks the newest, largest or first-found result set.
Discovery does not change `.ali` handling: only the `.ali` files next to
the chosen SARIF are read, and SRD002 is skipped when they are missing or
unsupported.

**Freshness.** `spark-refine explain` analyzes the proof results you
point it at. They correspond to the current sources only if GNATprove was
just run. `spark-refine prove` guarantees that the analyzed result was
freshly changed by the GNATprove command it just launched.

Exit status of `explain` / `analyze` / `compare-provers`:

* 0: diagnostics are informational;
* 1: a `--fail-on` code was emitted;
* 2: input error, or no unique result set was discovered.

### `prove`: fresh GNATprove orchestration (Task 008)

```text
spark-refine prove -P PROJECT [--gnatprove PATH] [--results PATH] [--dry-run]
                   [--name N] [--client-unit U ...] [--format text|json]
                   [--fail-on CODE ...] [-- GNATPROVE_ARGS...]
```

* **Command.** The argv `[GNATPROVE, "-P", PROJECT, *GNATPROVE_ARGS]` is
  executed with `shell=False`. Everything after the first `--` is passed
  verbatim. `GNATPROVE` defaults to `gnatprove` on `PATH`. The command
  is printed to stderr (`shlex.join`) *before* it runs. `--dry-run`
  prints it and exits 0 without running anything or inspecting any
  results. With `--format json`, the dry run prints a small plan
  document.
* **Output streams.** GNATprove's stdout and stderr are relayed to
  spark-refine's **stderr**. stdout carries only the report, so
  `--format json` output is always valid JSON or empty.
* **Freshness.** Before GNATprove starts, the `gnatprove.sarif` of every
  candidate under the current directory is stamped: device, inode, size,
  mtime_ns, ctime_ns and sha256. Afterwards, only result sets that are
  new or whose stamp changed are eligible. This works because GNATprove
  16.1.0 rewrites `gnatprove.sarif` on every run, even an incremental
  re-run, as observed in `docs/tasks/008-proof-run-orchestration.md`.
  * exactly one fresh result set: analyzed (`selection: fresh_discovery`);
  * none: refused, with no report, even if an old valid result set
    exists;
  * several: refused, with the candidates listed in sorted order.
  * `--results PATH` is authoritative: that location must be a valid
    result set **and** freshly written, otherwise the error is
    "GNATprove did not produce fresh results at the requested
    location." There is no fallback.
* **Analysis.** The unchanged `analyze_path_report` (SRD001, SRD002)
  runs in-process. The report gains `analysis.orchestration`: `command`,
  `gnatprove_exit_code`, `result_path`, `result_selection`, `fresh`, and
  `stale_result_sets_ignored` for fresh discovery. There are no
  timestamps, and `format_version` stays 1. The text report starts with
  `proof command:`, `GNATprove exit:`, `fresh results:` and `selection:`
  lines.
* **Exit status.** GNATprove's nonzero exit code, if it returned one;
  the report is still emitted when a fresh result exists. Otherwise 1 if
  `--fail-on` matched, otherwise 0. Exit 2 means an error before a usable
  result: launch failure, or no unique fresh result while GNATprove
  exited 0. If GNATprove failed *and* left no fresh result, its code is
  returned and no report is fabricated. A signal kill of N is reported
  as 128 + N, and the raw code is recorded.
* **No new proof policy.** If GNATprove exits 0 with unproved checks, a
  note reports it, and the exit code is *not* overridden.
* **Scope.** One GNATprove run, so SRD001/SRD002 only; SRD003 needs
  `compare-provers`. GNATprove runs in the current directory, and GPR
  files are not parsed. For Alire, use
  `alr exec -- spark-refine prove -P project.gpr`.

AI agents and CI should read [`../docs/AGENT_INTEGRATION.md`](../docs/AGENT_INTEGRATION.md).

## Rules

IDs are stable. They never derive from line numbers or message text.

| ID | Title | Confidence | Input |
|---|---|---|---|
| **SRD001** | failed invariant may mask downstream postconditions | high (for the structural *risk*) | 1 run |
| **SRD002** | Client-only proof gap; public abstraction may be insufficient | medium for `VC_PRECONDITION`, low for `VC_ASSERT` (lowest applies) | 1 run + `.ali` |
| **SRD003** | proof depends on prover portfolio | high, for confidently matched checks only | ≥ 2 single-prover runs |

Measured results are in [`DIAGNOSTICS_METRICS.md`](DIAGNOSTICS_METRICS.md).

### SRD001: invariant masking risk

GNATprove checks a type invariant and then **assumes** it. If the check
fails, a postcondition that is really false can be reported *proved* under
the contradictory assumption. This was observed in:

* B3/B4 (ring buffer B);
* P1/P5 (fixed pool);
* L1/L5 (library-backed pool).

```text
for each logical entity E:
    some VC_INVARIANT_CHECK of E is unproved
    and some VC_POSTCONDITION of E is proved
    => SRD001(E)
```

The report lists:

* the failed invariant check(s);
* every proved postcondition of `E`, as *potentially affected*;
* already-unproved postconditions, as context.

A failed invariant with no proved postcondition stays ordinary GNATprove
output (P4, L4). Justified invariant checks do not trigger the rule.

> **Masking *risk* ≠ actual secondary failure.** SRD001 promises only the
> first. Without a proof-dependency graph, which GNATprove's SARIF/.spark
> output does not expose, the evidence is exactly this:
>
> * same entity;
> * a failed invariant;
> * a proved postcondition;
> * GNATprove's invariant semantics (checked, then assumed).
>
> Together that is a **masking risk**. SRD001 never claims:
>
> * that the postcondition definitely depends on the failed invariant;
> * that the postcondition is false;
> * that GNATprove proved the wrong theorem.

Measured on the committed corpus (`tests/test_srd001_ground_truth.py`):

| Category | Result |
|---|---|
| Structural masking-risk cases | 9 / 9 detected (B1–B4, B6, P1, P5, L1, L5) |
| Known cases where invariant ablation exposes a secondary functional failure | 6 / 6 detected (B3, B4, P1, P5, L1, L5) |
| Conservative masking-risk warnings where the related functional postcondition is actually true | 3 (B1, B2, B6) |

The three conservative warnings are correct SRD001 output, not errors. In
each, the invariant really fails, but the fault breaks only the
representation relation, so the abstract postcondition happens to be
true. How the ground truth was established is described in
`tests/fixtures/README.md`.

If SARIF and `.spark` disagree on a cited check's status, SRD001 is still
reported, at **medium** confidence, and the evidence says why.

### SRD002: client-only proof gap; public abstraction may be insufficient

The implementation units are proved, but the client cannot establish an
operation precondition or an assertion. That is a **client-only proof
gap**. It does **not**, by itself, prove that the public abstraction is
too weak. Possible causes:

* the public contracts may expose insufficient abstraction information;
* the client property may simply be too strong or false;
* an intermediate client assertion may be missing;
* the client may need a stronger precondition.

This was observed with a known contract cause in:

* the Task 001 ablations `no_public_model_bound`, `no_is_empty_post` and
  `no_is_full_post`;
* the Task 003 ablation `spec_no_count_posts`.

It was observed with a **false client assertion** as the cause (and no
contract problem) in `pool_false_client_assert`:

```ada
Initialize (P);
pragma Assert (Free_Count (P) = 0);
```

```text
for each client unit C:
    D = transitive closure of C's GNAT .ali W/Z dependencies (or
        --client-unit), restricted to analysed units that have >= 1 check
    D not empty
    and C has >= 1 unproved VC_PRECONDITION / VC_ASSERT
    and every unit in D: 0 unproved, 0 justified, analysis complete,
        no SARIF/.spark disagreement
    => SRD002 for each client entity with such failures

confidence: VC_PRECONDITION only -> medium
            any VC_ASSERT        -> low   (lowest applicable)
```

No Ada semantics are used. The report names the client entity and the
failed check(s) with their locations. It does **not** name the callee or
any contract, and it never says that a public contract *is* insufficient.
Message text is displayed but never required
(`test_message_text_is_not_required`). Other unproved checks of the
client, such as its own postconditions, are listed as context.

**Negative controls.** SRD002 is not emitted for:

* an implementation postcondition failure (N1);
* a production range check (N2);
* a representation invariant failure (B1).

It is also not emitted when each of these is combined with a real client
failure in the same run (`ring_ctl_*`). The rule is specifically
*client-only proof inability, with the implementation otherwise green*.

**Unit ownership.** Each check's owning unit comes from the `.spark` file
that reports it. Generic-instance VCs sit in the generic's source file
(`spark_refine_prefix_sets.ad?`) but belong to the instantiating unit.

**ALI adapter (`ali.py`).** ALI is compiler-internal and version-sensitive.
Only GNAT 16.1.0 ALI (`V "GNAT Lib v16"`) has been observed, and no other
compiler version is claimed. The adapter accepts exactly the header
`GNAT Lib v16`, because that is what the pinned GNAT 16.1.0 writes; this
is not a claim about other GNAT 16 releases. The adapter is the only
reader of `.ali` files, and it **never raises**:

| Input | Result |
|---|---|
| valid GNAT 16.1.0 ALI (`V "GNAT Lib v16"`) | `ok`, dependencies from `W`/`Z` records |
| any other version header (`V "GNAT Lib v17"`, `V "something else"`, …) | `unsupported_version`, with the observed `version` and `detail = "supported ALI version is GNAT Lib v16"`; no record is read |
| unknown record kinds | ignored (harmless) |
| missing file / empty file | `missing` / `empty` |
| no `V "..."` header (truncated head, not an ALI) | `no_version` |
| truncated or malformed `W`/`Z` record, no `U` record | `malformed` |

An unsupported version is reported in the problem list
(`<unit>.ali: unsupported_version (version 'GNAT Lib v17'; supported ALI
version is GNAT Lib v16)`) and in
`analysis.rules.SRD002.ali_unsupported_versions`.

If any analysed unit lacks a valid `.ali`:

* SRD002 is **skipped**. The report says `SRD002 not evaluated: client
  dependency information unavailable (...)`, and
  `analysis.rules.SRD002.evaluated` is `false`.
* SRD001 and SRD003 are unaffected, and the CLI still exits 0.
* Dependencies are never guessed from file names.
* An ALI problem is never treated as a proof failure.

`--client-unit U` supplies the dependency information explicitly instead.

**Optional semantic context (Task 009).** `--semantic -P PROJECT
[-X NAME=VALUE ...]` adds a `semantic` block per SRD002 when Libadalang is
importable (`scripts/setup_libadalang.sh`). For each client failure it
gives a `resolution` (`exact` / `ambiguous` / `unresolved` /
`unavailable`). For an `exact` `VC_PRECONDITION` it adds the call text and
range, the callee (qualified name, declaration range) and its explicit
`Pre` with top-level conjuncts. For a `VC_ASSERT`, it adds only the
asserted expression. `failed_conjunct` is always `null` (`attribution:
"not_provided_by_gnatprove"`). It still does not say which public contract
is insufficient. The trigger, confidence and text of SRD002 are identical
with or without it. Sources are used only if they match the result set's
`.ali` `D` records (GNAT checksum + second-resolution mtime). That is GNAT's
source identity metadata, not byte identity: a layout/comment-only edit
within the same second is undetectable, and `analysis.semantic.provenance`
reports `layout_exact: false`. `resolution: "exact"` means one call was
found at the reported location and resolved. It is not a source-identity
claim. The committed semantic snapshots (`tests/semantic_fixtures`) contain
the project-local source needed for regression. External library sources
such as SPARKlib are not copied; they are resolved from the active project
environment. Their archived proof-time `D` timestamps may therefore differ
from a fresh dependency checkout. When that happens, the gate correctly
degrades those external callee declarations to `unavailable`, and the
archived tests accept only that or `exact`. The fresh E2E-G run below is the
authoritative test of external-dependency enrichment. Any failure only sets
`analysis.semantic.evaluated = false` or a per-check `unavailable`.
Degradation is non-fatal through rendering too (Task 011): an internally
incomplete `exact` entry is shown as `semantic entry: incomplete` in text
(no call/callee/Pre/assertion facts claimed; same structural contract as
Task 010 grouping, `semantic_shape.py`) and is serialised unchanged in
JSON. See
`docs/tasks/009-libadalang-srd002-enrichment.md`.

**Semantic triage groups (Task 010).** Whenever enrichment is evaluated,
`analysis.semantic.srd002_groups` (module `semantic_groups.py`,
backend-neutral) summarises the SRD002 client failures of the report. It
is also rendered as an `SRD002 semantic triage` text section before the
individual diagnostics, which are unchanged:

* a **group** contains only `exact` `VC_PRECONDITION` failures that share
  an identical callee (qualified name, kind, declaration span) and an
  identical extracted `Pre` (explicit flag, verbatim source text, span,
  conjuncts). Two overloads with one name never merge, and neither do
  logically equivalent but textually different `Pre`s;
* every other client failure is listed in `ungrouped` with a stable
  `reason`: `assertion_has_no_callee`, `semantic_ambiguous`,
  `semantic_unresolved`, `semantic_unavailable`, `semantic_incomplete`
  (or `rule_not_groupable`). Task 009's own reason is kept as `detail`;
* every client failure appears **exactly once**, either in a group or in
  `ungrouped`, so `grouped_check_count + ungrouped_check_count ==
  client_failure_count`. `coverage_problems()` checks this;
* a group has **no confidence**. Each occurrence keeps its
  `diagnostic_confidence`, and `diagnostic_confidences` only lists them;
* groups are descriptive. Sharing a callee and `Pre` does not establish a
  shared cause, does not identify a failed conjunct, and does not show that
  a public contract must change.

No diagnostic is created, removed, merged or modified, and the SRD002
count is unchanged. Without `--semantic`, or when enrichment is not
evaluated, there is no `srd002_groups` and no triage section. See
`docs/tasks/010-srd002-semantic-groups.md`.

### SRD003: prover-portfolio dependency

```text
over >= 2 named single-prover runs of the same sources:
    check K CONFIDENTLY matched across all runs
    and K proved in >= 1 run and unproved in >= 1 other
    => SRD003(K), with match_quality
```

Results on the committed prover-matrix fixtures:

| Run set | SRD003 diagnostics | Example |
|---|---:|---|
| fixed pool, manual (Task 003) | 6 (4 `exact`, 2 `unique_entity`) | lemma `VC_ASSERT` at `fixed_pool.adb:45`: CVC5 and Z3 unproved, Alt-Ergo proved |
| fixed pool, library-backed (Task 004) | 5 (3 `exact`, 2 `unique_entity`) | |
| ring buffer A (every prover proves all) | 0 | |

An optional `--reference` portfolio run is shown for context only. This
is robustness information, not unsoundness.

**Check identity across runs.** The analyzer prefers *unmatched* over
*incorrectly correlated*. The order of SARIF results never matters.

| Level | `match_quality` | Identity |
|---|---|---|
| 1 | `exact` | `(rule, file, line, column, entity)` occurs exactly once in every run |
| 2 | `fingerprint` | not available: GNATprove 16.1.0 SARIF results carry no `fingerprints`, `partialFingerprints` or `guid`. Nothing is derived from message text. |
| 3 | `unique_entity` | for identities not matched at level 1: `(rule, file, entity)` has exactly one check in every run. GNATprove reports a proved postcondition at the aspect and an unproved one at the failing conjunct, so line and column legitimately differ. |

Everything else is **not paired** and never yields SRD003:

* a duplicate identity, i.e. the same exact key several times in a run;
* ambiguous candidates;
* unmatched checks.

These are listed in the JSON under `analysis.srd003_matching`, with
counts and per-run candidates such as "candidate 1 of 2". The text report
lists them too when their outcomes differ. Source order is context only;
the former source-order fallback has been removed. Runs from different
GNATprove versions produce a note.

## Result reading: the benchmark gates' semantics

Pass/fail is structural and identical to `load_results` in
`examples/*/scripts/check_proof_results.py`:

| SARIF result | Classification |
|---|---|
| `kind == "pass"` | proved |
| documented foundation warning (`Is_Valid`: rule + file + prefix) | allowed warning |
| `inSource` suppression | justified |
| `level` warning/note | warning |
| anything else | unproved |

The `.spark` files add four things:

* the owning unit of each check;
* per-prover statistics;
* `stop_reason`;
* `pragma_assume`.

A `.spark` severity of `low`, `medium`, `high` or `error` means unproved.
SARIF and `.spark` are matched as a multiset on
`(rule, file, line, column, entity)`.

Disagreements are reported as notes and never silently resolved. SARIF
stays authoritative for the status, but the affected check is marked
`disputed` so that no diagnostic overclaims:

* SRD001 and SRD003 drop to medium confidence and say why;
* SRD002 is not emitted for a client whose closure contains a disputed
  unit, and a note explains this.

`tests/test_loader.py` asserts **parity with both gates** on all 49
fixtures. English message text never decides a status.

## JSON output

`--format json` produces `format_version` 1. The `analysis` object and
the SRD003 `match_quality` field are additive.

Task 006 added more fields, also additive, so the version is unchanged:

* per diagnostic, `category` and `action`;
* per rule in the `rules` catalogue, `category`, `action` and
  `action_description`;
* a top-level `summary` with `diagnostic_count`, `by_code`,
  `by_confidence`, `by_category` and `by_action`. It is computed from
  `diagnostics`, every known key is present (0 if absent), and it has no
  timestamps;
* `analysis.input`, only when the result set was auto-discovered.

| Code | `category` | `action` |
|---|---|---|
| SRD001 | `proof_context` | `fix_invariant_then_reprove` |
| SRD002 | `abstraction_boundary` | `validate_client_goal_then_review_public_contracts` |
| SRD003 | `prover_portfolio` | `preserve_portfolio_or_strengthen_proof` |

Actions are workflow-level and never prescribe a source edit (see
`docs/AGENT_INTEGRATION.md`). Diagnostics are sorted by
`(code, entity, location)`, and the output has no timestamps. An SRD002
diagnostic, abridged:

```json
{
  "code": "SRD002",
  "severity": "warning",
  "confidence": "low",
  "title": "Client-only proof gap; public abstraction may be insufficient",
  "entity": "Fixed_Pool_False_Client.Initialize_Then_Claim_Empty",
  "data": {
    "client_unit": "fixed_pool_false_client",
    "client_rules": ["VC_ASSERT"],
    "implementation_units": ["fixed_pool"],
    "implementation_checks": 108,
    "implementation_failures": 0,
    "dependency_source": "ali"
  }
}
```

An SRD003 diagnostic, abridged. `match_quality` is `exact` or
`unique_entity`, never `ambiguous`:

```json
{
  "code": "SRD003",
  "severity": "note",
  "confidence": "high",
  "entity": "Fixed_Pool.Lemma_Universe_Bound",
  "data": {"rule": "VC_ASSERT",
           "results": [["cvc5", "unproved"], ["z3", "unproved"],
                       ["altergo", "proved"]]},
  "match_quality": "exact"
}
```

The top-level `analysis` object, abridged:

```json
{
  "rules": {"SRD002": {"evaluated": true, "dependency_source": "ali",
                       "ali_status": "ok", "ali_versions": ["GNAT Lib v16"]}},
  "srd003_matching": {"policy": ["exact", "fingerprint", "unique_entity"],
                      "counts": {"exact": 130, "fingerprint": 0,
                                 "unique_entity": 2, "duplicate_identity": 1,
                                 "ambiguous_candidates": 0, "unmatched": 0},
                      "unresolved": ["..."]}
}
```

In the JSON `rules` catalogue, SRD002 has `"confidence": "dynamic"` and a
`confidence_policy`.

## Layout

```text
spark_refine_diagnostics/
  model.py          ProofRun / Check / Diagnostic data model
  sarif.py          SARIF reading and structural classification
  spark_results.py  .spark reading (entity table, severity, stats)
  ali.py            narrow ALI adapter (never raises; structured status)
  loader.py         SARIF + .spark merge -> ProofRun
  rules.py          stable rule catalogue
  srd001.py, srd002.py, srd003.py
  analyzer.py       entry points
  render.py         text / JSON output (deterministic; summary)
  discovery.py      conservative result-set discovery for `explain`
  orchestration.py  `prove`: argv, SARIF snapshots, fresh selection,
                    subprocess relay, exit policy, provenance metadata
  cli.py, __main__.py
pyproject.toml, MANIFEST.in   packaging (console script spark-refine)
scripts/capture_fixtures.py   reproduces the fixture corpus
scripts/e2e_fresh.py          fresh end-to-end gate (pinned toolchain)
scripts/packaging_smoke.py    build/inspect/install; run outside the repo
tests/                        unittest suite, fixtures/, expectations.toml
tests/fixture_sources/        fixture-only Ada client units (not benchmarks)
DIAGNOSTICS_METRICS.md        measured results per rule
```

## Test coverage: fixtures and fresh end-to-end runs

There are three complementary layers.

**Fixture-based regression coverage (primary).** `tests/` holds 188
unit tests. 137 of them run over the committed corpus of 49 sanitized,
real GNATprove 16.1.0 runs (`tests/fixtures/README.md`). Task 008 adds
51 orchestration tests: 45 in `test_prove.py`, which use a fake
GNATprove script and no toolchain, and 6 E2E-D/E checker tests in
`test_e2e_checks.py`. The 137 break down as follows:

* 110 are the Task 005 tests. They are unchanged, and so are their
  expected diagnostics.
* 27 were added in Task 006:
  * `test_explain.py` covers discovery, `explain`/`analyze` equivalence
    on all 49 fixtures, `category`/`action`/`summary`, and ALI
    conservatism under discovery;
  * `test_packaging.py` covers the packaging configuration, stdlib-only
    runtime imports and the wheel allow-list.

The suite is deterministic and needs no toolchain. It checks every
fixture's expected diagnostics, the SRD001 ground truth, parser parity
with both benchmark gates, ALI degradation and SRD003 matching in
detail. No test depends on `obj/`. CI: job `structural`, step
*Proof-diagnostics tests (SRD001-SRD003)*.

**Installed-package coverage (Task 006).**
`scripts/packaging_smoke.py` builds the wheel, inspects its contents,
installs it into an isolated venv and runs the installed `spark-refine`
command from a temporary directory outside the repository, on absolute
fixture paths. It repeats this for an editable install. CI: job
`diagnostics-packaging`, no Ada toolchain.

**Fresh end-to-end GNATprove integration coverage (smoke test).**
`scripts/e2e_fresh.py` runs the pinned toolchain (Alire 2.1.1, FSF
GNATprove 16.1.0, GNAT 16.1.0) *now*, through the benchmarks' own
unchanged scripts, and runs the CLI (`--format json`) on the fresh,
unsanitized SARIF / `.spark` / `.ali`. Three per-rule cases, plus two
`spark-refine prove` cases (Task 008):

| Case | Fresh run | Machine-checked |
|---|---|---|
| E2E-A SRD001 | ring buffer B, fault B3 `head_advances_wrong` (`check_proof_results.py negative --variant head_tail_count --only head_advances_wrong`) | one SRD001 on `Ring_Buffer.Pop`; confidence `high` unless a SARIF/.spark disagreement is recorded; an unproved `VC_INVARIANT_CHECK` and ≥ 1 proved `VC_POSTCONDITION` listed as *potentially affected* |
| E2E-B SRD002 | ring buffer A, ablation `no_is_full_post` (`ablate_proof_support.py --only no_is_full_post`) | SRD002 on `Ring_Buffer_Client_Proof.Push_Push_Pop` (`VC_PRECONDITION` + `VC_ASSERT`) and `…Rotate` (`VC_PRECONDITION`); client unit `ring_buffer_client_proof`; implementation units `[ring_buffer]` with > 0 checks and 0 failures; `dependency_source = ali`, `ali_status = ok`, `ali_versions = ["GNAT Lib v16"]` |
| E2E-C SRD003 | library-backed fixed pool, `--prover=cvc5` / `z3` / `altergo` (`prover_matrix.py --variant library_backed`), then `compare-provers` | the known SRD003 `VC_POSTCONDITION` `Fixed_Pool.Free_Prefix.Model` at `spark_refine_prefix_sets.ads:93`, `match_quality` `exact` or `unique_entity`, Z3 `unproved`, Alt-Ergo `proved`. The total SRD003 count is **not** gated |
| E2E-F semantic (Task 009, opt-in: `e2e_fresh.py semantic`, CI job `diagnostics-semantic`) | ring buffer A, ablation `no_is_full_post`, then `explain --semantic -P ring_buffer.gpr -XRING_BUFFER_SRC=obj/ablation_src/no_is_full_post ...` under `alr exec`, with Libadalang | E2E-B criteria, plus `analysis.semantic.evaluated`, backend `libadalang`; the three Push failures (9:7, 10:7, 25:7) `exact`, call text, callee `Ring_Buffer.Push` declared at `obj/ablation_src/no_is_full_post/ring_buffer.ads:36`, Pre `not Is_Full (B)` at line 37, `failed_conjunct` null with `attribution` `not_provided_by_gnatprove`; the VC_ASSERT at 16:43 has assertion context and no callee/Pre. Task 010: `analysis.semantic.srd002_groups` passes the coverage invariant with exactly 1 group (`Ring_Buffer.Push`, Pre `not Is_Full (B)`, 3 occurrences at 9:7, 10:7, 25:7), 3 grouped and 1 ungrouped (the VC_ASSERT at 16:43, `assertion_has_no_callee`), no group-level confidence and no failed conjunct |
| E2E-G semantic, external dependency (Task 009, opt-in: `e2e_fresh.py semantic_external`, CI job `diagnostics-semantic`) | ring buffer A, ablation `no_is_empty_post`, then `explain --semantic -P ring_buffer.gpr -XRING_BUFFER_SRC=obj/ablation_src/no_is_empty_post ...` under the same `alr exec` (same SPARKlib checkout GNATprove used), with Libadalang | E2E-B criteria, plus semantic evaluated with backend `libadalang`; `ring_buffer_client_proof.adb` 11:7 `exact`, callee `Ring_Buffer.Pop`, Pre `not Is_Empty (B)`; `ring_buffer_client_proof.ads` 24:45 `exact` → `Ring_Buffer.Sequences.Remove` and 25:45 `exact` → `Ring_Buffer.Sequences.Get`, both declared in SPARKlib `spark-containers-functional-vectors.ads`; no `failed_conjunct`; `layout_exact` / `byte_exact` false. This is the authoritative external-dependency test: the archived snapshots may legitimately degrade these two calls to `unavailable`. Task 010: coverage invariant holds, with exactly 4 groups (`Ring_Buffer.Pop`, `Ring_Buffer.Push`, `Ring_Buffer.Sequences.Remove`, `Ring_Buffer.Sequences.Get`, one occurrence each) and the 2 assertions ungrouped |
| E2E-D prove | ring buffer A baseline via `spark-refine prove -P ring_buffer.gpr --format json -- -j0` (no `--results`), after E2E-A/B and with a stale decoy result set placed | `analysis.orchestration`: command exact, `gnatprove_exit_code` 0, `fresh` true, `result_selection` `fresh_discovery`, `result_path` `obj/baseline/gnatprove`, decoy listed as ignored; 0 unproved / 0 justified / 0 pragma Assume; no diagnostics |
| E2E-E prove | ring buffer B3 (materialized by the benchmark's `apply_fault`) via `prove ... -- -j0 -XRING_BUFFER_SRC=... -XRING_BUFFER_VARIANT=e2e_prove_b3` | GNATprove exit 1 preserved as `prove`'s exit; fresh `obj/e2e_prove_b3/gnatprove` selected; the E2E-A SRD001 criteria |

Every case also requires GNATprove `FSF 16.1.0` and `.spark`-based unit
attribution. Diagnostic prose is never checked. E2E-B is the only test
that exercises *fresh compiler-written* `.ali` → `ali.py` → transitive
dependency graph → SRD002. The checkers themselves are unit-tested on the
matching fixtures, including negative controls (`tests/test_e2e_checks.py`).
CI: job `diagnostics-e2e` (≈ 30 s of GNATprove). Reports are written to
`obj/e2e/` (git-ignored) and uploaded as an artifact.

## Limitations

* SRD001 reports risk, not causality or falsity.
* SRD002 reports a client-only proof gap. It cannot tell an insufficient
  public contract from a false or too-strong client property. It does not
  identify the callee or any contract, and it stays silent when the
  implementation also has failures.
* SRD003 assumes single-prover runs of identical sources. Checks that
  cannot be matched by a unique machine-readable identity are left
  unpaired and reported as metadata.
* Only GNATprove FSF 16.1.0 output and GNAT 16.1.0 ALI have been
  observed. Any ALI version header other than `GNAT Lib v16` is rejected
  (`unsupported_version`) and SRD002 is skipped.
* Without `.spark` files, units are attributed from the entity's first
  name component, and the report says so.

### Research note: per-conjunct re-proof (Task 012, not a feature)

`scripts/conjunct_reproof_experiment.py` is a pre-registered research
experiment. It is not part of the installed package and not a CLI
command. On scratch copies of the Task 009 corpus, it replaces one
callee's `Pre` with a single top-level conjunct and re-runs GNATprove.
On that controlled corpus of independent total conjuncts it reproduced
the expected per-call evidence (`VALIDATED_ON_CONTROLLED_CORPUS`, see
`docs/tasks/012-per-conjunct-reproof-experiment.md`).

Normal reports do not use this evidence. They still show
`failed_conjunct: null` and `attribution: not_provided_by_gnatprove`.
Scratch proofs cover only the scratch programs.

### Research note: guard-sensitive prefix re-proof (Task 013, not a feature)

`scripts/guarded_reproof_experiment.py` is a second pre-registered
experiment. It is not installed and not a CLI command. For `and then`
contracts whose later conjunct depends on an earlier guard (null check,
index range, or a nested call with its own `Pre`), it never probes the
guarded conjunct alone. It re-proves cumulative source prefixes
(`C0`, `C0 and then C1`, ...) on scratch copies of
`tests/experiments/task013_guarded/` and reads the per-call transition:
`prefix_proved`, `newly_unproved` or `blocked_by_earlier_prefix`.
Nested-call checks are kept separate. On that controlled corpus it
produced the pre-registered evidence
(`PREFIX_METHOD_VALIDATED_ON_GUARDED_CORPUS`, see
`docs/tasks/013-guard-sensitive-conjunct-reproof.md`). A `newly_unproved`
transition is not a root cause. Normal reports are unchanged.

### Research note: Ada call-binding prefix re-proof (Task 014, not a feature)

`scripts/call_binding_reproof_experiment.py` re-proves resolved callee
contract prefixes on scratch copies of a controlled Ada corpus. Libadalang
locates the called declaration and its contract; GNATprove binds actuals to
formals. No argument-substitution engine or user CLI is added. The
pre-registered call-binding verdict was
`CALL_BINDING_METHOD_VALIDATED_ON_PREREGISTERED_SUPPORTED_CASES` (see
`docs/tasks/014-ada-call-binding-reproof.md`). A8's unproved conversion
check remains auxiliary rather than clean call-prefix evidence. Scratch
evidence proves only scratch programs, not the original program. Normal
reports still have `failed_conjunct: null` and
`attribution: not_provided_by_gnatprove`.

### Research note: external validation pilot (Task 015)

The research-only `scripts/external_validation.py` hashes and normalizes a
pinned local external proof run; it is not installed, does not invoke GNATprove
or mutate external source, and is not part of CI proof gates. On pinned
sml-ada, GNATprove proved 356/356 checks and the unchanged core explain
ingested the fresh output. SRD002 did not evaluate because `sml.ali` was
missing; this is **not** zero SRD002 findings under a complete rule. See
`../docs/tasks/015-external-validation-pilot.md` for scope and limitations.

### Research note: natural external failures (Task 017)

Task 017 independently reproduced a naturally failing Ada_CRDT revision:
11 unproved VCs (nine overflow, one postcondition, one aliasing); its direct
child had zero. Both SRD001 and SRD002 evaluated using supported GNAT Lib v16
ALI, and neither emitted a diagnostic: these checks do not meet the rules'
specific structural conditions. Semantic grouping was not evaluated; no
conjunct probe or source patch was run. This is not positive validation of
either rule. See `../docs/tasks/017-positive-external-validation.md` and the
research-only `scripts/positive_external_validation.py`.
