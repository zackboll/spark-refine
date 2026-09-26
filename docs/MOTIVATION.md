# Motivation

## 1. SPARK's strength creates a proof-engineering problem

SPARK lets developers state requirements close to the program and ask GNATprove to establish data-flow properties, run-time safety, contracts, and other assertions. The hard part of a large proof is frequently not the final theorem but choosing the right abstractions so automated provers can see it.

For ordinary software, a programmer may freely choose a representation that is easy to reason about. For embedded and real-time code, the representation is constrained by execution and integration requirements. Examples include fixed-size arrays, circular indices, statically allocated pools, packed protocol fields, DMA descriptor ownership bits, memory-mapped registers, and bounded state machines.

These concrete structures are excellent engineering representations and poor requirement languages.

A queue requirement is naturally expressed as a sequence. A pool is naturally expressed as a set of free and allocated identities. A bitmap allocator is naturally expressed as a set. A state-machine implementation might be packed fields and counters, while the requirement talks about allowed transitions.

SPARK therefore encourages a useful separation between concrete state and ghost/model state.

## 2. Why the model is not the duplication we should remove

It is tempting to describe the problem as “SPARK makes me maintain two implementations.” That is only partly accurate.

The mathematical model has a different purpose from the executable implementation. It intentionally sacrifices implementation constraints to expose behavior. A sequence model for a circular buffer is not redundant in the same way two production implementations would be redundant; it is an executable or logical statement of meaning.

The duplication worth reducing is the repeated **refinement machinery**:

```text
Concrete state
   |
   | logical-to-physical mapping
   | representation invariant
   | preservation facts
   | lemmas
   | refined postconditions
   v
Abstract model
```

A significant portion of this machinery is determined by the representation pattern, not by the application's unique requirement.

For example, every conventional circular sequence proof needs some form of the following facts:

- every logical element maps to a valid storage index;
- wraparound preserves logical order;
- the logical length is bounded by capacity;
- an append preserves all old logical elements and adds one final element;
- removing the first element shifts the logical view by one;
- empty/full predicates agree between concrete and abstract views.

Re-proving and re-encoding those facts in every project is an opportunity for tooling.

## 3. Why real-time code benefits disproportionately

The more implementation constraints a component has, the greater the distance between its physical and logical representations can become.

A dynamic language can model a queue using a dynamic list and test it directly. A high-assurance real-time component may instead require:

- static capacity known at compile time;
- no heap allocation;
- bounded operation count;
- explicit rollover behavior;
- safe concurrency rules;
- hardware-owned and software-owned slots;
- exact representation clauses;
- deterministic failure when full.

Proof becomes easier if the public contract ignores those details and speaks in terms of a sequence. That creates exactly the refinement layer this project wants to automate.

## 4. Maintenance cost matters as much as initial proof cost

Proof-support code creates a second maintenance surface.

Suppose a circular buffer begins with:

```text
Content + First + Length
```

and later becomes:

```text
Content + Head + Tail + Count
```

because of integration or performance constraints.

Its externally visible mathematical behavior may be unchanged. Ideally client proofs should not care. In practice, model functions, helper lemmas, invariants, and operation proofs can all need surgery.

`spark-refine` aims to localize that change:

```text
              stable public contract
                       |
                abstract sequence
                       |
             generated refinement
                /             \
               /               \
       representation A   representation B
```

The proof architecture then becomes an explicit software architecture rather than an informal convention scattered through ghost code.

## 5. Why a reusable pattern library is more valuable than code generation alone

A code generator that prints boilerplate is useful but shallow. The deeper asset is a reviewed library of **refinement patterns**.

A pattern contains domain knowledge about proving a representation:

```text
circular_sequence
  - abstract model kind
  - concrete roles: storage, first/head, length/count
  - index mapping
  - validity properties
  - standard preservation lemmas
  - operation proof schemas
  - common failure diagnostics
```

Over time, this becomes shared proof-engineering infrastructure.

A team should not need five different engineers to rediscover five slightly different versions of the same wraparound lemma. A community should not need every SPARK codebase to invent its own proof conventions for a fixed pool.

## 6. Why not hide the generated proof code

High-assurance developers need to understand why a proof works. The generated source therefore should be ordinary Ada/SPARK that can be inspected, versioned if desired, and passed directly to GNATprove.

The tool should optimize for:

- deterministic names;
- comments that identify the originating pattern rule;
- stable formatting;
- small helper functions;
- explicit dependencies;
- no mysterious solver-specific scripts where normal SPARK is sufficient.

Generated code should teach as well as automate.

A developer learning SPARK should be able to inspect a generated `Logical_To_Physical` function or preservation lemma and understand the pattern that would otherwise have been written by hand.

## 7. Why this helps AI-assisted development without depending on AI

Large language models can be useful for SPARK development, but unconstrained proof repair has a bad failure mode: an agent may make the proof easier by weakening the property.

A structured refinement description gives an agent something much safer to operate on:

```text
public requirement        -> user-owned
representation mapping    -> explicit metadata
pattern lemmas            -> reviewed library
proof result               -> GNATprove
```

An agent can explain “the wraparound preservation obligation failed after `First` changed” instead of blindly editing a postcondition.

This should be a later integration. The core project's value must be measurable with no AI at all.

## 8. What we hope to accomplish

At maturity, writing verified real-time SPARK should feel less like building a bespoke mini proof framework for every component.

A developer should spend most proof-design effort on:

- the requirement;
- the abstraction boundary;
- application-specific invariants;
- difficult domain properties.

The tool should shoulder more of:

- mechanical model construction;
- standard representation validity;
- routine refinement lemmas;
- predictable preservation conditions;
- generated proof-package structure;
- drift detection;
- diagnostics that identify which refinement layer failed.

The ambition is not “push a button and formally verify arbitrary software.”

The ambition is much more practical:

> **Turn common proof-engineering patterns into reusable tooling, the same way ordinary software engineering turns common implementation patterns into libraries and frameworks.**
