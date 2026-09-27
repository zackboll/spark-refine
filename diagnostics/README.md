# spark_refine_diagnostics: GNATprove proof-engineering diagnostics (MVP)

This is a deterministic analyzer for GNATprove's machine-readable output
(`gnatprove.sarif`, `<unit>.spark`, `<unit>.ali`). It turns low-level check
outcomes into higher-level SPARK proof-engineering diagnostics. It targets
only problems **already observed in this repository** (Tasks 001–004).

It does not:

* run GNATprove;
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
gnatprove -P my_project.gpr
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
just run.

Exit status:

* 0: diagnostics are informational;
* 1: a `--fail-on` code was emitted;
* 2: input error, or no unique result set was discovered.

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

**Future refinement (not in this MVP).** A later version could use
Libadalang to identify:

* the failing call and its callee;
* the precondition conjunct that failed;
* the public query/model contract that is insufficient.

The MVP tests whether the coarse diagnostic is already useful.

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

**Fixture-based regression coverage (primary).** `tests/` holds 137
unit tests over the committed corpus of 49 sanitized, real GNATprove
16.1.0 runs (`tests/fixtures/README.md`). Of these:

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
unsanitized SARIF / `.spark` / `.ali`. Exactly three cases:

| Case | Fresh run | Machine-checked |
|---|---|---|
| E2E-A SRD001 | ring buffer B, fault B3 `head_advances_wrong` (`check_proof_results.py negative --variant head_tail_count --only head_advances_wrong`) | one SRD001 on `Ring_Buffer.Pop`; confidence `high` unless a SARIF/.spark disagreement is recorded; an unproved `VC_INVARIANT_CHECK` and ≥ 1 proved `VC_POSTCONDITION` listed as *potentially affected* |
| E2E-B SRD002 | ring buffer A, ablation `no_is_full_post` (`ablate_proof_support.py --only no_is_full_post`) | SRD002 on `Ring_Buffer_Client_Proof.Push_Push_Pop` (`VC_PRECONDITION` + `VC_ASSERT`) and `…Rotate` (`VC_PRECONDITION`); client unit `ring_buffer_client_proof`; implementation units `[ring_buffer]` with > 0 checks and 0 failures; `dependency_source = ali`, `ali_status = ok`, `ali_versions = ["GNAT Lib v16"]` |
| E2E-C SRD003 | library-backed fixed pool, `--prover=cvc5` / `z3` / `altergo` (`prover_matrix.py --variant library_backed`), then `compare-provers` | the known SRD003 `VC_POSTCONDITION` `Fixed_Pool.Free_Prefix.Model` at `spark_refine_prefix_sets.ads:93`, `match_quality` `exact` or `unique_entity`, Z3 `unproved`, Alt-Ergo `proved`. The total SRD003 count is **not** gated |

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
