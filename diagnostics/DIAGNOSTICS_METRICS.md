# Diagnostics metrics (Task 005)

All numbers are measured on the committed corpus: 49 sanitized, real FSF
GNATprove 16.1.0 runs (`tests/fixtures/`). Each number is asserted by a
unit test, listed per section. Run the suite with:

```bash
cd diagnostics && python3 -m unittest discover -s tests -t tests -v
```

Two kinds of coverage are reported separately:

| Layer | What | Size | Toolchain | CI |
|---|---|---|---|---|
| **Fixture-based regression** (primary; every number below) | committed, sanitized GNATprove 16.1.0 output | 49 runs, 110 tests | none | `structural` job |
| **Fresh end-to-end integration** (smoke test) | GNATprove run now, output analysed unsanitized by the CLI | 3 cases | pinned Alire 2.1.1 / GNATprove 16.1.0 | `diagnostics-e2e` job |

The fresh gate is described at the end of this document. It does not
reproduce the corpus and it produces no metric; it confirms that the
analyzer still gives the known answer on real, current compiler and
prover output for one representative case per rule.

Terminology used throughout:

* A **positive** is the pattern a rule promises to detect. It is **not**
  an underlying functional defect in the program unless a section says
  so explicitly.
* **Confidence** qualifies the diagnostic's own claim, which is always
  stated in the rule's wording. It never qualifies a stronger claim.

## SRD001: failed invariant may mask downstream postconditions

**The claim.** For one entity:

* a `VC_INVARIANT_CHECK` is unproved;
* a `VC_POSTCONDITION` is proved;
* GNATprove checks a type invariant and then *assumes* it.

Together these give a **masking risk**. There is no proof-dependency
graph, so SRD001 never claims any of the following:

* that the postcondition depends on the failed invariant;
* that the postcondition is false;
* that GNATprove proved the wrong theorem.

Ground truth comes from invariant-removal ablations (`expectations.toml`,
`tests/fixtures/README.md`).

| Category | Result | Fixtures |
|---|---:|---|
| Structural masking-risk cases | **9 / 9 detected** | B1, B2, B3, B4, B6, P1, P5, L1, L5 |
| Known cases where invariant ablation exposes a secondary functional failure | **6 / 6 detected** | B3, B4, P1, P5, L1, L5 |
| Conservative masking-risk warnings where the related functional postcondition is actually true | **3** | B1, B2, B6 |
| Missed known masking cases | **0** | |
| Controls: failed invariant, no proved postcondition to mask | 2 / 2 silent | P4, L4 |

The three conservative warnings are **not errors** under SRD001's
semantics. In B1, B2 and B6:

* the invariant really fails;
* the proved postcondition really rests on an inconsistent assumption;
* the fault breaks only the representation relation, so the abstract
  postcondition happens to be true.

"0 false positives" holds only if a positive means the structural pattern.
Counted against actual hidden functional defects, SRD001's precision is
6/9.

Tests: `test_srd001.py` and `test_srd001_ground_truth.py`
(`test_metrics_categories`, `test_secondary_failure_labels_match_ablation`).

### Side finding: CVC5-only runs

With **correct** source code, the CVC5-only runs (`pool_prover_cvc5`,
`pool_lib_prover_cvc5`) report two things for `Fixed_Pool.Release`: the
invariant is unproved, and the postcondition is proved. SRD001 fires on
those prover-specific results, and the same masking-risk interpretation
applies: *that prover's* postcondition result may rest on an assumption
that the same prover could not establish.

This does **not** mean:

* that CVC5 found a bug;
* that the program is incorrect.

The configured portfolio proof (`--level=2`, run `pool_positive` /
`pool_lib_positive`) proves every check and remains authoritative. SRD001
therefore shows that the risk can arise even with correct source code
(`test_cvc5_side_finding_is_prover_specific_risk_only`).

## SRD002: client-only proof gap; public abstraction may be insufficient

**The claim.** For a client unit, every implementation unit in its `.ali`
dependency closure is fully proved (0 unproved, 0 justified, analysis
complete, no SARIF/.spark disagreement). The client still cannot prove a
`VC_PRECONDITION` or a `VC_ASSERT`. That is a **client-only proof gap**.
Possible causes:

* the public contracts may expose insufficient abstraction information;
* the client property may be too strong or false;
* an intermediate client assertion may be missing;
* the client may need a stronger precondition.

The MVP has no semantic evidence that can tell these causes apart. No
SRD002 hit is therefore a confirmed contract defect.

**Confidence policy** (`rules.SRD002_CONFIDENCE`):

| Failing client rule(s) in the diagnostic | Confidence |
|---|---|
| `VC_PRECONDITION` only | medium |
| `VC_ASSERT` only | low |
| both | low (the lowest applicable) |

### Known abstraction-gap examples (Task 001 / 003 ablations)

In these examples, removing a public contract is *known* to cause the gap.
SRD002 detects all of them. Following the rule, the diagnostic does not
name the removed contract.

| Fixture | Client entity | Rules | Confidence |
|---|---|---|---|
| ring `no_public_model_bound` | `Rotate` | PRE | medium |
| ring `no_is_empty_post` | `Push_Push_Pop` | ASSERT + PRE | low |
| | `Rotate` | PRE | medium |
| ring `no_is_full_post` | `Push_Push_Pop` | ASSERT + PRE | low |
| | `Rotate` | PRE | medium |
| pool `spec_no_count_posts` | `Release_Then_Allocate` | PRE | medium |
| | `Two_Allocations_Then_Release` | ASSERT | low |

Across the 4 fixtures there are 7 diagnostics: 4 medium, 3 low.

### False-client-assertion example

This fixture is `pool_false_client_assert`, a real GNATprove 16.1.0 run.
It contains the unchanged Task 003 pool plus the fixture-only client in
`tests/fixture_sources/fixed_pool_false_client`:

```ada
Initialize (P);
pragma Assert (Free_Count (P) = 0);   -- false: Post gives Max_Objects
```

| | Result |
|---|---|
| implementation `fixed_pool` | 108 checks, 0 unproved |
| client | 1 unproved `VC_ASSERT` |
| SRD002 | fires, **confidence low** |
| wording | lists "too strong or false" among the causes; never claims contract insufficiency |

This is **not** a false positive under the corrected SRD002 definition,
which is a client-only proof gap. It is the reason SRD002 no longer
claims a contract deficiency.

### Implementation-failing controls (SRD002 must stay silent)

| Fixture | Implementation failure | Client failure | SRD002 |
|---|---|---|---|
| N1 `ring_n1` | postcondition | — | silent |
| N2 `ring_n2` | range check | — | silent |
| B1 `ring_b1` | representation invariant | — | silent |
| `ring_ctl_post_and_client` | postcondition | yes | silent |
| `ring_ctl_range_and_client` | range check | yes | silent |
| `ring_ctl_invariant_and_client` | representation invariant | yes | silent |

The rule: if any analysed unit in the client's transitive `.ali`
dependency closure has an unproved or justified check, SRD002 is not
emitted for that client. A unit with a SARIF/.spark disagreement also
blocks it, with a note.

### Cases where SRD002 is skipped

SRD002 is skipped when dependency information is unavailable: the `.ali`
file is missing, empty, truncated, or malformed; it has no version header
or no unit record; its version header is not the validated
`GNAT Lib v16` (status `unsupported_version`, e.g. `GNAT Lib v17` or an
arbitrary string); or an analysed unit has no `.ali`. The report then
says:

```text
SRD002 not evaluated: client dependency information unavailable (...)
```

SRD001 still runs, SRD003 is unaffected, and the CLI exits 0. For an
unsupported version, `analysis.rules.SRD002.ali_unsupported_versions`
lists the observed header(s) and the reason includes
`supported ALI version is GNAT Lib v16`. On the committed corpus this
happens 0 times, because every fixture has GNAT 16.1.0 `.ali` files.

| ALI input | Result | Test |
|---|---|---|
| `V "GNAT Lib v16"` | `ok` | `test_parsing.AliTests.test_supported_version_v16` |
| `V "GNAT Lib v17"` | `unsupported_version`, no dependencies read | `test_unsupported_version_v17` |
| `V "something else"`, `""`, `GNAT Lib v16.1`, `gnat lib v16`, `GNAT Lib v15` | `unsupported_version` | `test_unsupported_arbitrary_version` |
| one unsupported file in a directory | whole set `unavailable` | `test_unsupported_version_makes_directory_unavailable` |
| v17 / arbitrary on an SRD002-positive and an SRD001-positive fixture | SRD002 skipped, SRD001 still reported, CLI exit 0 with `--fail-on SRD002` | `test_srd002.Srd002AliDegradation.test_unsupported_ali_version` |

Other degradation is tested in `test_srd002.Srd002AliDegradation` and
`test_parsing.AliTests`.

Tests: `test_srd002.py`.

## SRD003: proof depends on prover portfolio

**The claim.** A **confidently matched** check is proved by at least one
single-prover run and unproved by at least one other. This is robustness
information, not unsoundness.

### Matching hierarchy

| Level | `match_quality` | Identity | Used |
|---|---|---|---|
| 1 | `exact` | `(rule, file, line, column, entity)`, exactly once in every run | yes |
| 2 | `fingerprint` | SARIF `fingerprints` / `partialFingerprints` / `guid` | **not available** |
| 3 | `unique_entity` | `(rule, file, entity)` has exactly one check in every run (all checks counted) | yes |
| — | none (metadata only) | duplicate identity, ambiguous candidates, unmatched | never paired, never SRD003 |

Why level 2 is not used: all 58 raw GNATprove 16.1.0 SARIF logs of Tasks
001–005 were inspected. Their results carry only `kind`, `level`,
`locations`, `message` and `ruleId`, so no stable fingerprint exists.
None is synthesised from message text.

Why level 3 exists: GNATprove reports a proved postcondition at the
aspect (`fixed_pool.ads:39:17`) but an unproved one at the failing
conjunct (`41:24`). If the entity has only that one check of that rule in
that file in every run, nothing else could be confused with it.

The old "ordered fallback" is **removed**. It paired leftovers by source
order. Source order now appears only as context ("candidate 1 of 2") in
`analysis.srd003_matching.unresolved`.

### Results

| Run set (cvc5 / z3 / altergo) | Solver-sensitive checks (SRD003) | exact | fingerprint | unique_entity | Ambiguous / unmatched identities |
|---|---:|---:|---:|---:|---|
| fixed pool, manual (Task 003) | **6** (4 exact, 2 unique_entity) | 130 | 0 | 2 | 1 duplicate identity (`VC_CONTAINER_AGGR_CHECK`, 4× per run, identical outcomes) |
| fixed pool, library-backed (Task 004) | **5** (3 exact, 2 unique_entity) | 155 | 0 | 2 | 1 duplicate identity (same) |
| ring buffer A | **0** | 112 | 0 | 0 | 1 duplicate identity (same) |

In the committed runs, no identity with *differing* outcomes was left
unmatched, so hardening the matching lost no real finding. The 11 SRD003
diagnostics are the same checks as before; 4 of them are now explicitly
marked `unique_entity` instead of "ordered".

### Robustness tests

| Test | Result |
|---|---|
| Case A: duplicate identity, different outcomes and order across runs | no pairing, no SRD003, reported in metadata with a note |
| Ambiguous leftovers at shifted lines (the old fallback would pair them) | not paired |
| Case B: unique normal check | SRD003 with `match_quality = exact` |
| Case C: SARIF `results` (and `.spark` entries) shuffled with two seeds | byte-identical JSON output |
| Run list reversed | same findings |
| JSON | every SRD003 has `match_quality` in {`exact`, `unique_entity`}; never `ambiguous` |

Tests: `test_srd003.py`.

## Parser parity

On every fixture, the parser produces the same proved, unproved and
justified checks as the `load_results()` of **both** historical gates
(`examples/ring_buffer/scripts/check_proof_results.py` and
`examples/fixed_pool/scripts/check_proof_results.py`). It also agrees on
allowed warnings, other warnings, `pragma Assume` and `.spark`-unproved
counts. Message text never decides a status (`test_loader.py`,
`test_parsing.py`).

## Fresh end-to-end GNATprove integration (not fixture-based)

`scripts/e2e_fresh.py`, CI job `diagnostics-e2e`. Three cases, each run
fresh with the pinned toolchain through the benchmarks' own scripts and
analysed, unsanitized, by the CLI (`--format json`). Only structural JSON
fields are checked; prose never is.

| Case | Fresh GNATprove run | Required | Local result (pinned 16.1.0) |
|---|---|---|---|
| E2E-A SRD001 | ring buffer B3 `head_advances_wrong` | SRD001 on `Ring_Buffer.Pop`, confidence `high` (unless a recorded SARIF/.spark disagreement), ≥ 1 proved `VC_POSTCONDITION` *potentially affected* | pass: `high`, invariant `ring_buffer.ads:41:14` unproved, 1 proved postcondition affected, no consistency notes |
| E2E-B SRD002 | ring buffer `no_is_full_post` | SRD002 on `…Push_Push_Pop` (`VC_PRECONDITION`, `VC_ASSERT`) and `…Rotate` (`VC_PRECONDITION`); implementation `[ring_buffer]` green; `dependency_source = ali`; ALI `GNAT Lib v16` | pass: both SRD002 (low / medium), `ring_buffer` 92 checks 0 failures, `dependency_source = ali`, `ali_status = ok` |
| E2E-C SRD003 | library-backed pool, `--prover=` cvc5, z3, altergo | the known `VC_POSTCONDITION` `Fixed_Pool.Free_Prefix.Model` (`spark_refine_prefix_sets.ads:93`), `match_quality` `exact` or `unique_entity`, Z3 `unproved`, Alt-Ergo `proved` | pass: `unique_entity`, cvc5 ✗ / z3 ✗ / altergo ✓ |

The total number of SRD003 findings (5 in the local fresh run, as in the
fixture) is reported but not gated. Wall time: ≈ 30 s of GNATprove.
The pass criteria are themselves unit-tested on the matching fixtures,
with negative controls (`tests/test_e2e_checks.py`, 10 tests).
