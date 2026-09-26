# Contributing

`spark-refine` is pre-alpha. Contributions should strengthen the experiment rather than expand scope prematurely.

## Priorities

For the first implementation cycle, prioritize:

- the manual circular-buffer proof baseline;
- reproducible GNATprove fixtures;
- refinement IR design;
- deterministic generation;
- trust/soundness tests;
- benchmark measurement.

Please avoid adding unrelated convenience features before the first benchmark answers whether the core idea saves proof effort.

## Development workflow

Use feature branches and pull requests. A change should normally include:

- tests for new behavior;
- documentation for public semantics;
- a note if trust assumptions change;
- benchmark/proof evidence for pattern changes.

Generated code should not be hand-edited unless a test explicitly exercises drift detection.

## Pattern changes

A pattern PR should explain:

- mathematical meaning;
- representation roles;
- generated properties;
- what is proved by GNATprove;
- unsupported variants;
- benchmark effect;
- whether the pattern's semantic version must change.

## Soundness review

Any change that introduces assumptions, imported proof-only declarations, disabled proof checks, or a new trusted foundation must be called out explicitly. See `SECURITY.md` and `docs/TRUST_MODEL.md`.

## Style

Favor clear Ada/SPARK over abstraction-heavy framework code. Generated artifacts are part of the user experience and should be understandable to someone learning the proof pattern.
