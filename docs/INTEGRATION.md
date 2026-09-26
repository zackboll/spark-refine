# Ecosystem Integration

## GNATprove

GNATprove remains the verification authority.

`spark-refine` should generate normal SPARK and invoke or integrate with GNATprove only as an orchestrator. Users must be able to run GNATprove independently.

Future diagnostics can consume GNATprove's machine-readable outputs rather than scraping terminal text.

## SPARK functional/formal containers

Use existing SPARK mathematical container abstractions rather than inventing incompatible sequence/set/map theories when practical.

Functional containers are particularly appropriate for ghost models because they provide high-level mathematical operations even if their executable performance would not be suitable for production code.

The project should investigate each pattern against current SPARKlib capabilities and prefer library models where they produce stable proofs.

## Libadalang

Production source analysis should use Libadalang.

Why:

- Ada parsing is complex;
- name resolution matters;
- source locations matter;
- semantic type compatibility matters;
- a home-grown parser would become a maintenance liability.

The first generator can bootstrap with explicit manifest names, but semantic integration should happen early.

## `pragma Annotate` / `aspect Annotate`

Ada's implementation-defined `Annotate` mechanism is intended for information consumed by external tools and is allowed in SPARK. This is a promising long-term way to place refinement metadata near the code it describes without introducing a custom language extension.

Example concept only:

```ada
pragma Annotate
  (SPARK_Refine,
   Role,
   Queue_Contents,
   Storage,
   Content);
```

Do not freeze this syntax before the manifest MVP.

## Alire

Publish the CLI as an Alire crate once the project performs real generation.

Likely dependencies after bootstrap include:

- `ada_toml` for TOML parsing;
- `libadalang` for semantic analysis.

Exact versions should be selected and tested when implementation starts rather than hard-coded in this design bootstrap.

## GPR projects

The tool should accept a GPR project as the source of compilation context. It should not attempt to duplicate project-source discovery rules.

## Ada Language Server / editors

Editor integration should consume structured output from `spark-refine`.

Desired features later:

- go from a generated lemma to its manifest/source role;
- show refinement-layer errors inline;
- command to regenerate/check drift;
- visualize model layers;
- preview generated proof changes.

These should fit existing Ada tooling rather than fork it.

## GNATtest/GNATfuzz

GNATprove counterexamples can already participate in test workflows. A future `spark-refine` diagnostic layer could preserve provenance when a failed proof/counterexample originates from a generated refinement property.

## CI

A mature CI workflow should contain separate gates:

```text
format/lint
unit tests
generator determinism
manifest/source semantic validation
forbidden-trust scan
GNAT build
GNATprove proof fixtures
negative proof fixtures
```

Separating these makes a failure understandable.
