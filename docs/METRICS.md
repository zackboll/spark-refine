# Success Metrics

## North-star metric

**Developer-authored proof-support effort removed without weakening assurance.**

Because effort is hard to measure directly, the project should use several proxies rather than one vanity metric.

## 1. Proof-support LOC reduction

Define proof-support LOC as user-authored code whose primary purpose is connecting concrete representation to abstract proof semantics:

- ghost model adapters;
- representation predicates;
- generic representation lemmas;
- refinement helper contracts;
- pattern-specific loop invariants.

Do not count the public behavioral contract as waste. The contract is the requirement and should remain user-owned.

Initial target:

```text
>= 50% reduction for circular-buffer benchmark
```

This is a hypothesis, not a promised result.

## 2. Manual artifact count

Track counts of:

```text
model helper functions
representation predicates
lemmas
loop invariants
refined contracts
proof-only update statements
```

The goal is to reduce the number a developer must design and maintain.

## 3. Proof completeness

For a stable pattern fixture:

```text
unproved expected VCs = 0
```

No metric matters if the generated proof is incomplete.

## 4. Trust debt

Track:

```text
generated assumptions
external axioms
suppressed checks relevant to proof
trusted pattern facts
```

Default target:

```text
generated assumptions = 0
```

## 5. Representation-refactor locality

Measure what a representation change touches.

Desired behavior:

- public model contracts: unchanged;
- client proofs: unchanged;
- representation mapping: changed;
- generated proof layer: regenerated;
- small number of application-specific proof facts: potentially changed.

A useful normalized metric is:

```text
user-owned proof lines changed / total proof lines changed
```

Lower is better when the behavioral requirement is unchanged.

## 6. Time to green proof

On controlled development tasks, measure elapsed expert work from implementation to complete proof. This is noisy but ultimately more meaningful than LOC.

Use repeated tasks/patterns before drawing conclusions.

## 7. Proof performance

Record GNATprove:

- wall time;
- VC count;
- timeout count;
- solver steps when available;
- peak memory when practical.

Automation that saves authoring time but multiplies proof runtime by an order of magnitude may not be acceptable.

## 8. Generated-code readability

Use code-review questions rather than a fake numeric score initially:

- Can a SPARK developer identify why each generated helper exists?
- Can a failed obligation be traced to a pattern rule?
- Are names stable and descriptive?
- Is generated control flow simple?
- Does the code use standard SPARK idioms?

## 9. Diagnostic usefulness

Once `explain` exists, measure whether a developer can identify the failing abstraction boundary without reading generated internals.

## 10. Adoption metric

Do not optimize early for downloads/stars. More useful early adoption evidence is:

- independent projects using a pattern;
- external representation variants added without rewriting the core;
- external bug reports that identify real proof-pattern limitations;
- upstream interest from SPARK/Ada tooling contributors.
