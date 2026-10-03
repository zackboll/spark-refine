# Task 019 — Bitmap-set proof-pattern experiment (preregistered)

Base: `origin/main` at `440fe1d4ec7b23cfcc03c3b1dcaebaa80739c429`;
reviewed Task 018 head `967f73eb093df9eafe6ca89fadc2d2ea11b2c390`
is an ancestor. Branch: `feature/019-bitmap-set-proof-pattern`.
This section is frozen **before the first functional GNATprove run**. Do not
amend this commit. Record observations separately after this section.

## Question and immutable design

Does a packed bitmap allocator require enough reusable manual proof support
to warrant a second hand-written generic SPARK proof-pattern library? First
prove and minimize the manual implementation. Do not design the library from
anticipated rather than observed proof artifacts.

Main instance: `Interfaces.Unsigned_32`, `Object_Id` 0 .. 69 (70 identities),
three words indexed 0 .. 2. Ordinal offset is `Object_Id'Pos (Id) -
Object_Id'Pos (Object_Id'First)`; word number is offset / 32, bit number is
offset mod 32. Boundary IDs: 0, 31, 32, 63, 64, 69. Bits 6 .. 31 of word 2
are zero padding, not members. All unused storage bits are canonically zero.
The only mutable production fields are packed modular `Words` and redundant
`Count : 0 .. 70`; bit 1 means free. Production uses Ada modular bit operations
and scans for a free bit, clears it and decrements Count. Release sets its bit
and increments Count. Both variants retain the same production representation
and algorithm. No ghost library call in production.

Public API: `Initialize`, `Is_Free`, `Free_Count`, `Is_Exhausted`, `Allocate`,
`Release`, and ghost `Free_Model` returning the caller's `Functional.Sets` set
of `Object_Id`. Initialize makes all IDs free and Count 70; Is_Free equals
model Contains, Free_Count equals model Length, Is_Exhausted iff model Length
zero. Allocate requires nonexhaustion and returns a formerly free ID, with
new model = Remove (old model, returned ID); no lowest-ID promise. Release
requires ID absent from model and sets new model = Add (old model, ID).
These public requirements are authoritative specification, not mechanical
support. Redundant Count must be proved equal to model cardinality.

## Fixed proof and measurement policy

Alire 2.1.1; exact dependencies `gnat_native=16.1.0`,
`gnatprove=16.1.0`, `sparklib=16.1.0` (full), `gprbuild=26.0.1`.
GNATprove: `-U --mode=all --level=2 --no-loop-unrolling
--report=statistics --checks-as-errors=on --warnings=error -j0`.
No timeout, step or memory increases to obtain a green benchmark: record
the blocker before any proposed change. Run GNATprove sequentially from
clean outputs with invocation header, inspect SARIF and `.spark` per-unit
results, require all expected units, zero unproved/justified/flow errors,
and run deterministic boundary/exhaust/refill runtime tests with `-gnata`.
Only GNATprove is proof authority. Record proof application/library/SPARKlib
checks, rule distribution, maximum steps and three clean wall times. After
the final proofs, measure CVC5, Z3 and Alt-Ergo alone under level-2 limits;
the racing portfolio remains the gate. No speed claim without measurement.

Count nonblank, noncomment physical Ada lines, including configuration and
instantiation lines; document each classified span and run the inventory
twice. Three nonoverlapping classes: production implementation (fields,
runtime helpers and mutations), authoritative specification (public model
meaning and behavior contracts), mechanical proof support (invariants,
padding predicates, model construction/adapter, popcount facts, proof-only
mapping, Refined_Post, loop invariants, lemmas/calls, assertions and ghost
snapshots). Classify model implementation as mechanical even though the model
declaration/meaning is specification. Do not reclassify mechanical support
as production. `P` is minimized manual mechanical SLOC; `G` is genuinely
pattern-generic P/P (explain each policy-specific line). `R` is all residual
per-instance mechanical SLOC including configuration, adapter and any calls;
`L` is generic-library SLOC (excluded from R); `A` counts meaningful generic
actual concepts. Report each category, P-R and (P-R)/P. Ablate unneeded
artifacts before counting. Preserve public visible API and production code
between variants; check source/token equivalence or justify every diff.

## Falsification fixtures (both variants if library proceeds)

| ID | Mutation | Expected structural failure class |
|---|---|---|
| M1 | set padding bit in Initialize | canonical-padding/type-invariant failure |
| M2 | set incorrect Count | count/cardinality invariant or Free_Count postcondition |
| M3 | Allocate returns free ID without clearing bit | Allocate model Remove postcondition |
| M4 | Allocate clears one ID, returns another | Allocate old-membership or Remove postcondition |
| M5 | Release sets wrong bit | Release Add postcondition |
| M6 | mis-map boundary 31/32 | mapping bound, representation invariant, or model postcondition |
| M7 | let invalid final padding contribute to Count/model | padding/cardinality invariant or query postcondition |
| M8 | client double Release | public Release precondition at caller |

Require intended `(rule, entity, application-vs-generic location)` failures,
not merely nonzero exit. Do not preregister exact prover wording. For every
invariant-primary failure inspect whether it masks a functional postcondition;
do not change SRD001. Apply byte-identical production faults where possible
and report any generic-internal displacement.

## Decision (do not revise after measurement)

Only attempt `SPARK_Refine_Bitmap_Sets` if `P >= 15` and `G >= 50%`;
otherwise outcome `MANUAL_SUPPORT_TOO_SMALL`. The library is hand-written
SPARK, no generator, and should accept finite discrete IDs, modular word,
word index/storage array and the caller's Functional.Sets instance where
SPARK permits. Do not hardcode 70, 32, or zero origins. Document actual
representation restrictions. Prove three materially different independent
instances: nonzero-origin exact one-word, different word-origin multiword
partial-final/overcapacity, and enumeration crossing a word boundary;
exercise 8-bit and 16/32-bit words if supported. Library ablations: model
membership, cardinality, padding, mapping bound, set/Add and clear/Remove
relations if exported, and any construction-loop invariants. Residual
ablations: validity invariant/call, adapter, snapshots, lemma calls and
mapping adapter if present. Remove ornamental facts.

`ADOPT_BITMAP_PATTERN` iff P >= 15, R <= 15, reduction >= 50%, public API and
production semantics unchanged, zero unproved/justified, clean trust scan,
three proven independent instances, meaningful negative failures, no
production Ghost dependency or unchecked assumption/import/suppression.
`REVIEW_BITMAP_PATTERN` if soundness/reuse gates pass but reduction is 30%
through <50% or R is 16 .. 20. `DO_NOT_ADOPT_BITMAP_PATTERN` if reduction
<30%, R >20, any trust/soundness/reuse gate fails, production distortion or
unchecked proof shortcut. A racing-portfolio positive proof is required.

Trust scan covers no `pragma Assume`, axiom (`Annotate => Axiom` included),
false-positive/intentional justification, proof suppression, imported proof
oracle, bodyless ghost theorem or unchecked conversion establishing facts.
Keep the documented SPARKlib Big_Integers `Is_Valid` foundation warning
separate from user assumptions. GNATprove re-proves generic instances.
Canonical JSON has no absolute paths/timestamps/long prover prose and must
regenerate byte-identically twice. No diagnostics-rule or Task 015–018 edit;
no external positive-validation work.

## Observations (append only after preregistration commit)

### Adoption decision and scope

**ADOPTION DECISION: `DO_NOT_ADOPT_BITMAP_PATTERN`.** Task 019 is closed
economically for the candidate measured at
`ce13e839259e3e8b7c265678db4e119f8b4152ce`: the preserved packed allocator
and production interface, recorded proof architecture and tested bounded
minimization alternatives. This is not `MANUAL_SUPPORT_TOO_SMALL`: the manual
gate passed (P=54, 52 generic support lines).

| Measurement | Value |
|---|---:|
| Manual application support P | 54 |
| Unminimized library application support R_start | 110 |
| Minimized application support R | 56 |
| Reusable library L | 124 |
| Generic actual concepts A | 6 |
| Support saved P−R | −2 |
| Reduction 100(P−R)/P | −200/54 = −3.703704% |

Both independent frozen non-adoption predicates hold: **R=56 >20** and
**reduction=−3.703704% <30%**. The candidate reached complete local proofs;
rejection is economic, not a finding that its proved 32-bit instance is
incorrect. No supported second pattern, package release or adoption results
from this experiment. Prefix_Sets remains the established reusable pattern.

### Recorded evidence (not new hosted reproduction)

* [Manual metrics](../../examples/bitmap_allocator/BASELINE_METRICS.md),
  [inventory](../../examples/bitmap_allocator/evidence/manual_inventory.json)
  and [proof evidence](../../examples/bitmap_allocator/evidence/manual_proof.json):
  P=54, 52 generic lines; recorded clean proof 118/118; 45,792 runtime checks
  in each recorded build mode. Baseline checkpoint:
  `029f2907c7993da3854ed72583c166de4b79faa5`.
* [Library metrics](../../examples/bitmap_allocator/LIBRARY_METRICS.md),
  [minimization snapshot](../../examples/bitmap_allocator/evidence/library_minimization.json)
  and [timings](../../examples/bitmap_allocator/evidence/library_minimization_timings.json):
  R_start=110 explicitly unminimized, R=56 after bounded minimization, L=124,
  A=6. Three clean 174/174 proofs of identical source, zero unproved and
  justified results, recorded wall times 7.609, 7.269, 7.275 seconds.
  Public contracts and all 42 production lines preserved; runtime tests
  passed in both recorded modes (45,792 checks each). First-green checkpoint:
  `fee271fbeaf9fcd1077ede3a9e3a2f276e3ea907`.
* Standalone arbitrary-raw-storage padding equivalence: 25 Ada SLOC,
  recorded 104/104 result in the snapshot. This validates one specific
  representation relationship, **not three materially different generic
  validation instances**.
* Imported-unit assertion execution was not established by these runtime
  checks: the assertion-enabled claim covers allocator and runtime driver,
  not imported generic/SPARKlib units.
* The snapshot remains historical intermediate evidence, SHA-256
  `6655666c27ad24322dd1719d7b46e13e24005d6dd40dd9abae3842520da28cb6`.
  [Progress ledger](../../examples/bitmap_allocator/LIBRARY_EXPERIMENT_PROGRESS.md)
  preserves prior stages and ablations. Ignored local logs/snapshots are retained.

### Experimental execution and coverage

**Closed early after economic rejection; not every originally planned
validation campaign completed.** Review authorized stopping after observing
the economic result. This is a **post-measurement stopping decision**, not a
separately preregistered early-stopping plan.

| Campaign | Coverage at closeout |
|---|---|
| Independent generic-instance campaign | Not performed before economic closeout; no result claimed |
| Other word widths and identity kinds | Not performed before economic closeout; no result claimed |
| Invalid-configuration rejection tests | Not performed before economic closeout; no result claimed |
| Complete M1–M8 campaign, manual and library variants | Not performed before economic closeout; no result claimed |
| Masking experiments | Not performed before economic closeout; no result claimed |
| Complete single-prover comparison | Not performed before economic closeout; no result claimed |
| Final controlled performance comparison | Not performed before economic closeout; no result claimed |
| Dedicated hosted bitmap proof gate | Not performed before economic closeout; no result claimed |

Passing these checks would not change measured R or make this existing
candidate satisfy the frozen economic criteria. They were therefore not
pursued after review elected to close it. This does not make such checks
permanently unnecessary for any future candidate. No new bitmap proof CI job
was added; structural CI checks only closeout integrity and pure regressions.
No external validation, further bitmap redesign, or Task 020 was started.

### Technical findings and limits

**Direct measurement:** the mapping bridge (10 lines) and model
contract/forwarding body (21) account for 31 of the 56 residual support lines.
The checked local/generic model relationship removed substantial duplicated
reasoning but did not make this integration smaller than the manual proof.
The contaminated aggregate report (331 results, inherited manual outputs)
was rejected; isolated project-closure output reproduced the unchanged
first-green candidate at 213/213 before accepted minimized measurements.

**Engineering interpretation from this candidate:** generic proof content
does not guarantee cheap application integration. Physical padding
preservation is distinct from abstract set equality; valid-ID membership
does not describe unused physical bits. The standalone padding check and
retained physical-update premises address that distinction.

**Unresolved:** broader instances, configurations, complete falsification,
single-prover robustness and controlled performance remain unvalidated.
No global minimum, generic unsoundness, GNATprove defect or compiler theorem
is claimed. This does not show that no useful bitmap proof library or better
integration is possible, nor that library-first universally failed.

### Closeout artifact and retention

[Canonical closeout evidence](../evidence/task019-bitmap-set-proof-pattern.json)
is separate from the preserved minimization snapshot. The standard-library
[helper](../../examples/bitmap_allocator/scripts/closeout_bitmap_experiment.py)
binds reviewed inventory metadata to current source/configuration hashes,
derives the economic predicates and serializes documented coverage limits.
It does not parse Ada semantics, launch GNATprove, independently reproduce
proofs or verify the human stopping decision. `--check` is read-only and
requires no historical Git object, ignored logs, toolchain or network.

Candidate source remains at its measured paths for reproducibility, as an
unsupported research artifact, still covered by trust scanning. The manual
benchmark is not a production-ready supported container merely because its
positive proof passed. Task 019 is closed with incomplete planned validation;
the research branch is delivered for review, not automatic merge.