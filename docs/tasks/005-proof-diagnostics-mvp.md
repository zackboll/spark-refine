# Task 005 — GNATprove Diagnostic Analyzer MVP

**Status:** executed.

**Base:** `origin/main` = `d761a99edc4f23a2d36c162449784701e7a0d042`,
the PR #4 merge. The ancestor check against the reviewed PR #4 head
`e92b4b3e12c3d90b22df9701e703ecca02121ed9` succeeded.

**Branch:** `feature/005-proof-diagnostics-mvp`.

**Implementation:** `diagnostics/` (see `diagnostics/README.md`).

## Question

Tasks 001–004 found three things:

* source generation is not justified;
* reusable proof libraries are valuable;
* the remaining pain is *understanding* proof failures.

Can a deterministic analyzer help with that last problem? It would read
only GNATprove's machine-readable output and turn low-level outcomes into
useful proof-engineering diagnostics for the problems already observed
here.

## What was built

* `diagnostics/spark_refine_diagnostics`, a Python standard-library
  package with a CLI (`analyze`, `compare-provers`, `rules`). It contains:
  * a normalized model (`ProofRun`, `Check`, `Diagnostic`, `Report`);
  * SARIF and `.spark` readers, and a narrow `.ali` adapter that never
    raises;
  * a SARIF/.spark merge that marks disagreements;
  * the rules SRD001–SRD003;
  * text and JSON output with an `analysis` metadata section.
* Result reading uses the benchmark gates' classification unchanged. A
  parity test compares it with **both** gates' `load_results` on every
  fixture.
* **49 real GNATprove 16.1.0 fixtures**, captured through the benchmarks'
  own gate and ablation code (`diagnostics/scripts/capture_fixtures.py`)
  and sanitized. Provenance is in `tests/fixtures/manifest.toml` and in
  each `fixture.json`, which records the GNAT/GNATprove versions, the
  `.ali` producer, the prover configuration and the source commit.
* 95 unit tests. They need no toolchain and run in CI.
* Measured results: `diagnostics/DIAGNOSTICS_METRICS.md`.

### Corrective review

The first version made claims that went beyond its evidence. A corrective
pass fixed four things:

* **SRD002** was reframed from "likely abstraction/contract gap" to
  *client-only proof gap; public abstraction may be insufficient*. It now
  has per-rule confidence and a real false-client-assertion control.
* **SRD003** matching no longer pairs checks by source order.
* **`.ali` reading** was isolated in an adapter that degrades gracefully.
* **SRD001 metrics** are now reported in precise categories.

The corpus previously counted 48 fixtures, although the docs claimed 49.
The false-client fixture brings it to 49.

## SRD001: failed invariant may mask downstream postconditions

| Fixture | Normal run | SRD001 | Masked post? (ground truth) |
|---|---|---|---|
| B1, B2 | `INVARIANT@Push` | yes | no |
| **B3** | `INVARIANT@Pop` | yes | **yes** (`Pop`) |
| **B4** | `INVARIANT@Push` | yes | **yes** (`Push`) |
| B6 | `INVARIANT@Clear` | yes | no |
| **P1** / **L1** | `INVARIANT@Initialize` | yes | **yes** (`Initialize`) |
| P4 / L4 | `INVARIANT` + `POST@Release` | no (post already unproved) | no |
| **P5** / **L5** | `INVARIANT@Release` | yes | **yes** (`Release`) |

* Structural masking-risk cases: **9 / 9 detected**.
* Known cases where invariant ablation exposes a secondary functional
  failure: **6 / 6 detected**.
* Conservative masking-risk warnings where the related functional
  postcondition is actually true: **3** (B1, B2, B6).
* Missed known masking cases: **0**.

The three conservative warnings are not errors under SRD001's semantics:
the invariant fails, and the proof rests on an inconsistent state. There
is no proof-dependency graph, so the claim is exactly this:

* same entity;
* a failed invariant;
* a proved postcondition;
* GNATprove's invariant semantics.

Together that is a masking risk. SRD001 never claims:

* that the postcondition depends on the invariant;
* that the postcondition is false;
* that GNATprove proved the wrong theorem.

How the ground truth was established:

* **B3/B4 (differential).** Removing B's invariant alone breaks `Push`
  even without a fault, so every Push fault would look confirmed. The
  differential therefore uses the repository's control case
  `control_push_ignores_tail_no_invariant` (116/116 proved) as baseline.
  With it, B3 and B4 confirm and B1, B2 and B6 do not, matching
  `REFACTOR_METRICS.md`.
* **L5 (equivalence).** The library-backed invariant-removal baseline
  already fails `Release` without a fault. L5 is therefore labelled by
  its byte-identical edit to P5, which the tests verify.

**CVC5 side finding.** With correct source code, the CVC5-only runs fail
the `Release` invariant while proving its postcondition, and SRD001
fires. SRD001 can therefore be useful even when the source is correct:
the same masking-risk interpretation applies to that prover-specific
result. This does not mean that CVC5 found a bug or that the program is
incorrect. The configured portfolio proof proves every check and remains
authoritative.

## SRD002: client-only proof gap; public abstraction may be insufficient

When the implementation units are proved and the client cannot prove a
precondition or an assertion, that alone does not show that the public
abstraction is too weak. Possible causes:

* insufficient public contracts;
* a client property that is too strong or false;
* a missing intermediate assertion;
* a client precondition that is too weak.

SRD002 therefore reports a *client-only proof gap* and never claims a
contract deficiency.

| Fixture | SRD002 client entities (confidence) |
|---|---|
| ring `no_public_model_bound` | `Rotate` (medium) |
| ring `no_is_empty_post` / `no_is_full_post` | `Push_Push_Pop` (low), `Rotate` (medium) |
| pool `spec_no_count_posts` | `Release_Then_Allocate` (medium), `Two_Allocations_Then_Release` (low) |
| **pool `false_client_assert`** (the assertion is false; no contract problem) | `Initialize_Then_Claim_Empty` (low) |

Confidence policy:

* `VC_PRECONDITION` only: medium;
* any `VC_ASSERT`: low;
* both: the lowest applicable.

The false-client fixture is a real GNATprove 16.1.0 run. It is the
unchanged pool plus a fixture-only client
(`diagnostics/tests/fixture_sources/`). SRD002 firing on it is correct
under the corrected definition.

**Negative controls.** No SRD002 for any of:

* N1 (implementation postcondition);
* N2 (production range check);
* B1 (representation invariant);
* each of these three failure kinds combined with a real client failure
  in one run (`ring_ctl_*`).

The implementation is the transitive `.ali` dependency closure of the
client. Any unproved or justified check there blocks SRD002.

**ALI degradation.** `.ali` is read only by `ali.py`, which is observed
only for GNAT 16.1.0 and never raises. If the `.ali` data is missing,
empty, truncated or malformed, SRD002 is **skipped** with the note
`SRD002 not evaluated: client dependency information unavailable`. In
that case:

* SRD001 and SRD003 still work;
* the CLI exits 0;
* dependencies are never guessed from file names.

## SRD003: prover-portfolio dependency

| Run set | SRD003 | Notable |
|---|---:|---|
| fixed pool (manual), CVC5 / Z3 / Alt-Ergo | 6 | lemma `VC_ASSERT` (`fixed_pool.adb:45`): CVC5 ✗, Z3 ✗, Alt-Ergo ✓ |
| fixed pool (library-backed) | 5 | library `Model` post (`spark_refine_prefix_sets.ads:93`): CVC5 ✗, Z3 ✗, Alt-Ergo ✓ |
| ring buffer A | 0 | every prover alone proves all |

These counts reproduce the Task 003/004 prover matrices exactly.

Cross-run matching prefers *unmatched* over *incorrectly correlated*:

1. `exact`: `(rule, file, line, column, entity)` unique in every run.
   Counts: 130 / 155 / 112.
2. `fingerprint`: **not usable**. GNATprove 16.1.0 SARIF has no
   `fingerprints`, `partialFingerprints` or `guid`.
3. `unique_entity`: `(rule, file, entity)` has exactly one check in every
   run. Counts: 2 / 2 / 0. These are postconditions reported at the
   aspect when proved and at the failing conjunct when unproved.

Duplicate, ambiguous and unmatched identities are never paired. They
appear in `analysis.srd003_matching`, where source order is context only.
Each run set has one duplicate identity (a container aggregate check
reported 4×, with identical outcomes). Other properties:

* every SRD003 carries `match_quality` (`exact` or `unique_entity`);
* shuffling the SARIF results yields byte-identical output.

## Limitations (deliberate)

* SRD001 has no proof-dependency graph, because GNATprove output does not
  expose one.
* SRD002 cannot tell a contract gap from a false or too-strong client
  property, and it stays silent when the implementation also fails. A
  later version could use Libadalang to find the failing call, the callee
  and the failed conjunct. It is not used here.
* There are no automatic invariant-removal re-runs. The Task 004 proposal
  suggested them, but source mutation is out of scope, so ablation
  evidence is test metadata only.
* Only FSF GNATprove 16.1.0 output and GNAT 16.1.0 `.ali` files have been
  observed.

Out of scope and not done:

* source generation;
* manifest parsing;
* invariant synthesis;
* contract rewriting;
* proof repair;
* AI;
* Libadalang;
* changes to the root Ada CLI.

No proof requirement, benchmark source, fault fixture, gate script or CI
proof job was changed. The false-client control's Ada unit lives under
`diagnostics/tests/fixture_sources/`. It is staged into the git-ignored
`obj/` only while its fixture is captured.
