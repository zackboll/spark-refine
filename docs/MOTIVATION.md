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

> **What the benchmarks found (Tasks 001–004).** The opportunity is real,
> but smaller and differently shaped than first assumed:
>
> * for the two ring-buffer representations, GNATprove and SPARKlib
>   discharged the wraparound and index facts listed above
>   **automatically**. The manual support was only 19 and 21 SLOC, with
>   no lemmas;
> * the fixed pool needed more (36 SLOC, including a pigeonhole lemma),
>   but all of it was generic. A reusable SPARK library absorbed it,
>   leaving 10 SLOC per instance.

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
                abstract model
                       |
        reusable proof pattern + small adapter
                /             \
               /               \
       representation A   representation B
```

(The original diagram had "generated refinement" in the middle. Tasks
001–004 replaced it with a reviewed library plus a small
application-owned adapter.)

The evidence supports the localization claim:

* moving the ring buffer from `First + Length` to `Head + Tail + Count`
  changed 0 lines of the public spec and the client proof;
* moving the fixed pool onto the library left the public API (visible
  part, CI-checked equivalent) and the client proof unchanged.

The proof architecture then becomes an explicit software architecture rather than an informal convention scattered through ghost code.

## 5. Why a reusable pattern library is more valuable than code generation alone

The project initially suspected that repeated proof machinery should be
**generated** from a declaration. The experiments showed that, for at
least some patterns, a **reviewed SPARK generic library** is the better
abstraction.

Evidence from the fixed pool (Tasks 003–004):

| | Manual | Library-backed |
|---|---:|---:|
| Per-instance mechanical proof support | 36 SLOC | **10 SLOC** |
| Local lemmas | 1 (12 SLOC incl. call) | 0 |
| Local loop invariants | 5 SLOC | 0 |
| Reusable library (written once) | — | 98 SLOC |
| Public API / client proof changes | — | none |

The ten remaining lines are a generic instantiation, a representation
invariant and a one-call model adapter. That is roughly the size a
manifest declaration would have been. A generator would have added a
tool layer that users must review and trust, for little further saving.

Advantages of a library over generated source:

* it is ordinary SPARK that users read, instantiate and prove with stock
  tools;
* GNATprove re-proves it per instance, so it is not a trusted theorem
  oracle;
* hard, prover-sensitive VCs are tuned once, in library source, by the
  library author.

The cost is that generic bodies are re-proved per instance (fixed pool:
136 → 161 checks; gate wall time ≈ 1.9 s → 2.2 s).

The original argument below still holds, with "generated" read as "provided by the library":

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

## 6. Why proof support must stay visible

High-assurance developers need to understand why a proof works. Proof
support, whether library-provided or local, should therefore be
ordinary Ada/SPARK that can be inspected, versioned and passed directly
to GNATprove.

> **Update (Task 007).** This section was originally titled "Why not hide
> the generated proof code". The point now applies to proof-pattern
> libraries: they are plain, reviewed SPARK generics, and nothing is
> hidden or generated. The *teaching* role once expected of generated
> code falls to two things:
>
> * readable libraries with documented meaning and restrictions
>   (`proof_patterns/README.md`);
> * diagnostics that explain *what kind* of proof failure occurred.

Library code should optimize for:

- deterministic names;
- comments that identify the originating pattern rule;
- stable formatting;
- small helper functions;
- explicit dependencies;
- no mysterious solver-specific scripts where normal SPARK is sufficient.

Proof libraries should teach as well as automate.

A developer learning SPARK should be able to inspect `SPARK_Refine_Prefix_Sets.Model` and its contract, or a library lemma, and understand the pattern that would otherwise have been written by hand.

## 7. Why this helps AI-assisted development without depending on AI

Large language models can be useful for SPARK development, but unconstrained proof repair has a bad failure mode: an agent may make the proof easier by weakening the property.

Structure gives an agent something much safer to operate on:

```text
authoritative specification  -> user-owned (public Pre/Post, model semantics)
mechanical proof support     -> reviewed library + small local adapter/invariant
implementation               -> ordinary engineering changes
proof result                 -> GNATprove
interpretation               -> spark-refine explain --format json
```

An agent that receives `SRD001 / fix_invariant_then_reprove` knows to
repair the invariant or state transition first, and to distrust the
listed "proved" postconditions until it re-proves them. It does not
blindly edit a postcondition. An agent that receives
`SRD002 / validate_client_goal_then_review_public_contracts` knows to
check whether the client's goal is true before proposing any public
contract change. See `docs/AGENT_INTEGRATION.md`.

That interface now exists. The core project's value is still measurable
with no AI at all: the library and the diagnostics are useful to a human
alone.

## 8. What we hope to accomplish

At maturity, writing verified real-time SPARK should feel less like building a bespoke mini proof framework for every component.

A developer should spend most proof-design effort on:

- the requirement;
- the abstraction boundary;
- application-specific invariants;
- difficult domain properties.

Reusable proof libraries should shoulder more of:

- mechanical model construction;
- standard representation validity;
- routine refinement lemmas;
- predictable preservation conditions.

Proof-aware diagnostics should shoulder more of:

- recognizing which kind of proof-engineering failure occurred;
- flagging "proved" results that may rest on a failed invariant;
- separating program problems from prover-portfolio problems;
- giving humans and agents conservative, structured next steps.

(Generated proof-package structure and drift detection were on this list
originally. They are deferred together with generation.)

The ambition is not “push a button and formally verify arbitrary software.”

The ambition is much more practical:

> **Turn common proof-engineering patterns into reusable tooling, the same way ordinary software engineering turns common implementation patterns into libraries and frameworks.**
