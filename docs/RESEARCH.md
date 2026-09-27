# Research Notes and References

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
