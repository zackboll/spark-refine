# Research Notes and References

## Task 019: economic non-adoption of the measured bitmap candidate

**`DO_NOT_ADOPT_BITMAP_PATTERN`**: manual P=54, minimized library-backed
R=56, reusable L=124, A=6; savings −2, reduction −3.703704%. The 32-bit
candidate reached complete local proofs, but both R>20 and reduction<30%
hold. Broader validation and falsification were not completed; review elected
a post-measurement closeout. No second supported bitmap pattern was adopted;
Prefix_Sets remains the established reusable pattern.

Direct measurement: mapping bridge plus model contract/forwarding body
consume 31/56 residual lines. Engineering interpretation: generic proof
content does not guarantee cheap integration; physical padding preservation
is distinct from abstract set equality. Better integrations and broader
instances remain unresolved, not disproved. The contaminated aggregate report
was rejected in favor of isolated project-closure measurements; no GNATprove
defect is inferred. [Evidence, scope and coverage](tasks/019-bitmap-set-proof-pattern.md#observations-append-only-after-preregistration-commit).

## Task 018: candidate qualification without proof-based selection

Surveyed SPARKTLS, memcp, flyology, SPARKling-MuJoCo and the previously
tested Ada_CRDT using upstream commits, issues/PRs and manifests. No committed
natural GNATprove-16 case with sufficient independent SRD001/SRD002 structural
evidence was found. memcp's documented caller failure is explicitly an
uncommitted spike, not a candidate. No functional external proof or
spark-refine candidate analysis occurred. Verdict:
**NO_NATURAL_POSITIVE_CANDIDATE_QUALIFIED**.
[Inventory and gate](tasks/018-external-positive-candidate.md).

## Task 017: natural external failure, outside diagnostic scope

Detached Ada_CRDT `5fa2c0c` reproduced 11 unproved VCs under the upstream-compatible GNATprove 16.1.0 procedure; direct child `aeb8094` reproduced zero. The unchanged product ingested both fresh result sets; SRD001 and SRD002 evaluated, with zero diagnostics each and supported ALI dependencies. Nine overflow checks, one postcondition and one aliasing check do not match either rule's masking-risk or client-only structure. No semantic grouping or external conjunct probe occurred. The child is structural context, not proof of a specific fix. [Protocol and results](tasks/017-positive-external-validation.md).

Research date: 2026-09-26.

> **Status (Task 007).** The survey predates the experiments. Its
> findings still stand. Three conclusions were refined by Tasks 001–006
> ([ADR 0005](adr/0005-library-and-diagnostics-first.md)):
>
> * Finding 5 said a diagnostics formatter is less compelling than
>   refinement-aware diagnostics. Proof-engineering diagnostics
>   (SRD001–SRD003) turned out to be feasible directly on GNATprove
>   output, with no generator;
> * findings 7–9 (`Annotate`, Libadalang, TOML) supported a generator
>   that is now deferred. Libadalang remains relevant for future
>   semantic diagnostics;
> * "What we did not find" concerns generation tools; the project no
>   longer depends on that gap.

> **Experimental finding (Tasks 009 and 012).** GNATprove 16.1.0 SARIF and
> `.spark` output does not say which top-level `Pre` conjunct failed
> (Task 009). New proof evidence can supply that information. In Task 012,
> scratch copies of a controlled corpus had a callee's `Pre` replaced by
> one conjunct, and GNATprove was re-run. On the pre-registered corpus of
> independent, total integer conjuncts, this matched the ground truth for
> all 9 occurrence/conjunct observations
> ([Task 012](tasks/012-per-conjunct-reproof-experiment.md)). The method
> does not in general preserve the short-circuit guards of `and then`, so
> the finding is not generalised. Scratch proofs cover only the scratch
> programs.
>
> Task 013 re-proved cumulative source **prefixes** (`C0`,
> `C0 and then C1`) instead of isolated conjuncts, so each later conjunct
> is proved only under the guards before it. On a controlled
> access/null, array-index and nested-call corpus the result was
> `PREFIX_METHOD_VALIDATED_ON_GUARDED_CORPUS`: 9/9 baseline controls,
> 18/18 pre-registered prefix statuses and classifications, and nested
> call checks kept separate from the target VC
> ([Task 013](tasks/013-guard-sensitive-conjunct-reproof.md)). After an
> unproved prefix the method says nothing about later conjuncts, and a
> `newly_unproved` transition is not a root cause. Ada call binding and
> realistic-project cost remained to be tested at that point.
>
> Task 014 tested call binding on a pre-registered controlled corpus:
> `CALL_BINDING_METHOD_VALIDATED_ON_PREREGISTERED_SUPPORTED_CASES` for 26
> call occurrences, 7 resolved callee contracts and 60 per-occurrence
> observations from a baseline plus 15 callee-prefix programs
> ([Task 014](tasks/014-ada-call-binding-reproof.md)). Libadalang identifies
> the actual resolved declaration and contract source; GNATprove performs
> Ada actual/formal binding on unchanged callers. `spark-refine` does not
> implement an argument-substitution engine. Overloads, one generic
> instance (template `Pre`) and the preregistered dispatching case (root
> `Pre'Class`) were handled on this corpus, not arbitrary Ada generics or
> dispatch. A8's unproved conversion VC was auxiliary, not clean
> conjunct evidence. Scratch evidence is not proof of the original
> program; realistic/external validation and cost remain open.

> **Task 015 external pilot.** At pinned sml-ada commit
> `3ccd0e4bf51685ebd832383c12166e795473a037`, GNATprove 16.1.0
> proved 356/356 checks. Current core explain ingested fresh artifacts;
> SRD001 evaluated with zero diagnostics, while SRD002 was not evaluated
> because `sml.ali` was missing from the result directory. Nineteen SARIF
> checks had no matching `.spark` entry. No naturally unproved check was
> available for semantic or grouping evaluation; no external probes ran.
> This is evidence of ingestion, not validation of diagnostic correctness.
> See [Task 015](tasks/015-external-validation-pilot.md).

> **Task 016 compatibility finding.** The `sml.ali` request came from a
> disputed SARIF-only termination check's entity fallback, not an analysed
> `.spark` unit. All 12 analysed units have valid supported ALIs. The product
> now selects dependency units from `.spark` UnitResults when available;
> 19 unmatched SARIF checks remain conservatively disputed because their
> expected absence is not established structurally. SRD002 evaluates with
> zero diagnostics on the fully proved external run, not a positive external
> validation. See [Task 016](tasks/016-external-artifact-compatibility.md).

This repository was bootstrapped after surveying current SPARK/AdaCore documentation and adjacent tooling to avoid building a project that merely duplicates an existing feature.

## Key findings

### 1. Model functions and functional containers are established SPARK practice

SPARK documentation describes model functions as ghost functions that expose a simpler mathematical view of a data structure. Functional/formal container libraries provide sequence, map, set, vector, tree, and related abstractions intended for specification/proof use.

References:

- https://docs.adacore.com/spark2014-docs/html/ug/en/source/spark_libraries.html
- https://docs.adacore.com/spark2014-docs/html/ug/en/source/specification_features.html

### 2. Proof by refinement currently requires explicit model layers

Claire Dross's 2025 paper, *Containers for specification in SPARK*, discusses functional containers and model functions, uses a ring buffer as an example, and explains that proof by refinement can be achieved using multiple model layers. The paper notes that proof by refinement is not natively supported in SPARK as a dedicated mechanism.

Reference:

- https://www.adacore.com/uploads/papers/256080-adacore-spark-paper-cover-v6-1.pdf

This is the strongest direct evidence for the project's core gap.

### 3. Current AdaCore work demonstrates several model layers in practice

AdaCore's 2026 article *Multiple Levels of Models and Refinement* describes a verified hashed-set implementation with four abstraction levels: implementation, two intermediate models, and a top-level model. The refinement links between layers are an explicit part of the proof engineering.

Reference:

- https://www.adacore.com/blog/formally-verified-hashed-sets-in-ada-spark-2

This suggests the issue is not limited to beginner examples. Layered refinement is useful in sophisticated proofs and can create substantial support structure.

### 4. GNATprove already automates some loop frame information

GNATprove can generate certain loop frame conditions automatically, so a project whose pitch is merely “generate loop invariants” would overlap existing functionality. Documentation also describes limitations of the heuristic, leaving room for pattern-derived invariant work later.

Reference:

- https://docs.adacore.com/spark2014-docs/html/ug/en/source/how_to_write_loop_invariants.html

### 5. Proof diagnostics and machine-readable results already exist

GNATprove supports counterexamples in relevant cases, proof strategies/replay facilities, and machine-readable proof artifacts. Current tooling also supports SARIF output/integration paths.

References:

- https://docs.adacore.com/spark2014-docs/html/ug/en/source/how_to_run_gnatprove.html
- https://docs.adacore.com/spark2014-docs/html/ug/en/source/gnatprove.html

This makes a standalone diagnostics formatter less compelling than refinement-aware diagnostics built on top of existing output.

### 6. State refinement exists, but it is not a general model-refinement automation framework

SPARK provides `Refined_State` and `Refined_Post` to relate abstract package state/views to refined implementation state/contracts. This is important foundation and terminology for the project, but it does not remove the broader need to build model mappings and proof layers for complex data structures.

Reference:

- https://docs.adacore.com/spark2014-docs/html/lrm/packages.html

### 7. Ada provides a standard external-tool annotation mechanism

GNAT's `pragma Annotate` is designed to attach information for external tools, and `Annotate` is permitted in SPARK. This provides a plausible future source-level interface without requiring a new language dialect.

References:

- https://docs.adacore.com/gnat_rm-docs/html/gnat_rm/gnat_rm/implementation_defined_pragmas.html
- https://docs.adacore.com/spark2014-docs/html/lrm/implementation_defined_pragmas.html

### 8. Libadalang is available for semantic Ada analysis

The Ada ecosystem already has a semantic source-analysis library. `spark-refine` should use it rather than implementing an Ada parser.

Reference:

- https://alire.ada.dev/crates/libadalang

### 9. TOML tooling exists in Alire

An Ada TOML parser is available, making TOML a reasonable MVP manifest format without custom parsing.

Reference:

- https://alire.ada.dev/crates/ada_toml

### 10. WCET remains an important but separate opportunity

Bound-T is an open-source WCET/static-analysis project with Ada heritage. Its public status information indicates it is not an actively expanding modern general-purpose solution across current targets. WCET remains a significant real-time-tooling opportunity, but modern static timing analysis requires architecture/compiler-specific work well beyond this project's initial proof-engineering scope.

References:

- https://www.bound-t.com/
- https://www.bound-t.com/status.html

## What we did not find

The survey did **not** identify a general-purpose open-source tool whose primary purpose is to declare a concrete-to-abstract SPARK data-structure refinement and generate the recurring model/invariant/lemma/refined-contract scaffolding while leaving GNATprove as proof authority.

This is a search result, not proof of nonexistence. Before a public launch, repeat searches across:

- AdaCore GitHub organization;
- Alire crate index;
- Ada/SPARK conference papers;
- Why3/SPARK research repositories;
- recent AdaCore blog/release notes.

## Relevant upstream repository

- https://github.com/AdaCore/spark2014

The preferred strategy is to build externally first. If repeated patterns expose a small language/tool feature that belongs in GNATprove/SPARK itself, write an upstream proposal backed by benchmark data rather than starting with a compiler/prover fork.
