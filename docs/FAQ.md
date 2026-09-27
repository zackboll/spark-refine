# FAQ

> **Status.** Updated in Task 007 for the current product: reusable proof
> patterns plus proof-aware diagnostics
> ([ADR 0005](adr/0005-library-and-diagnostics-first.md)). Answers
> written for the original generator plan have been reframed. Where
> useful, the original answer is kept as a short historical note.

## About the current product

### Does spark-refine prove my program?

No. **GNATprove does.** `spark-refine` has two parts:

* reusable proof-pattern libraries, which GNATprove proves in your
  project at each instantiation;
* diagnostics that *interpret* GNATprove's results.

A clean `spark-refine` report is not a proof, and a diagnostic is not a
verdict that something is false.

### Does spark-refine edit my source?

No. The current diagnostics are read-only. They never rewrite sources,
repair proofs, change contracts or emit assumptions.

### Does `spark-refine explain` run GNATprove?

No. It analyzes one existing result set (`gnatprove.sarif`, `*.spark`,
`*.ali`) and runs SRD001 and SRD002. Those results describe your current
sources only if you have just run GNATprove, so auto-discovered results
may be stale. Run GNATprove first, and again after every change:

```bash
gnatprove -P my_project.gpr
spark-refine explain                          # or: spark-refine explain obj/<variant>/gnatprove
```

There is no `spark-refine prove` command. Proof-run orchestration is only
a possible future direction.

### Which command produces SRD003?

`spark-refine compare-provers`, over two or more single-prover GNATprove
runs. `explain` never produces SRD003.

### Can an AI agent consume the output?

Yes. `spark-refine explain --format json` produces deterministic
`format_version` 1 JSON. Every diagnostic carries `code`, `category`,
`action` and `confidence`, and the report has a derived `summary`. See
`docs/AGENT_INTEGRATION.md` for the recommended loop and guardrails.

### Will it weaken contracts automatically?

No. `spark-refine` changes nothing. The recommended policy for agents is
that authoritative specifications (public `Pre`/`Post`, model
semantics, requirements) are not weakened just to get a green proof, and
that changes to them get explicit human review. That policy is not
mechanically enforced today.

### What do SRD001, SRD002 and SRD003 mean?

* **SRD001, invariant masking risk.** A type invariant check failed in an
  entity whose postconditions are reported proved. Those postconditions
  may rest on the failed invariant. Fix the invariant or state
  transition first, then re-prove.
* **SRD002, client-only proof gap.** The implementation is fully proved,
  but a client cannot prove a precondition or assertion. Check that the
  client's goal is actually true before reviewing public contracts.
* **SRD003, prover-portfolio dependency.** Some single provers prove a
  check and others do not. This is robustness information, not
  unsoundness. Do not rewrite a valid proof merely because one solver
  fails.

### Which toolchains are supported?

It is validated on FSF GNAT / GNATprove / SPARKlib 16.1.0. `.ali`
support is limited to `GNAT Lib v16`. With other versions, SRD002 is
skipped and the report says so.

### Why keep the old generator docs?

They record the experimental hypothesis the project started from and the
evidence that led away from it. They may become useful again if future
evidence supports generation. They are labelled historical/deferred
(`docs/SPEC.md`, `docs/MANIFEST.md`, Part II of `docs/ARCHITECTURE.md`,
`docs/history/ORIGINAL_README.md`).

## About proof patterns and the approach

### Isn't the abstract model itself duplicate code?

It is duplicate *state meaning*, but usually intentional. The model is optimized for specification and proof; the implementation is optimized for execution. `spark-refine` focuses on reducing the mechanical code that establishes correspondence between them.

### Why not generate the model (or the proof support) automatically?

There are two reasons.

1. The implementation does not uniquely determine the intended
   abstraction. The same data can have many valid meanings, so the
   developer must own that semantic choice. The abstract model's meaning
   is authoritative specification.
2. The *mechanical* correspondence, i.e. the model adapter, invariants
   and lemmas, turned out to be better captured by a reviewed SPARK
   generic library than by a generator. On the fixed pool, a library cut
   local support from 36 to 10 SLOC, and what remains is about as small
   as a generator's input would be.

The developer instantiates the library and writes a one-call adapter.
Generation is deferred unless new evidence justifies it.

*Historical:* the original answer said the tool would generate a model
adapter from a declaration such as "this is a circular sequence whose
storage/first/length are these entities".

### Why not just improve GNATprove?

Some improvements may ultimately belong upstream. An external tool is a better experiment because it can iterate rapidly, preserve GNATprove as the trusted verifier, and gather evidence about useful abstractions before proposing language/prover changes.

### Doesn't `Refined_State` already solve this?

It solves an important state-abstraction problem at package boundaries. It does not automatically provide the model functions, intermediate abstractions, data-structure lemmas, or representation-preservation proof architecture that this project targets.

### Doesn't SPARKlib already provide models?

Yes, and `spark-refine` reuses them: `SPARK_Refine_Prefix_Sets` models
its prefix as a SPARKlib `Functional.Sets` set. SPARKlib helps define
the **abstract side**. This project focuses on connecting common
concrete representations to those abstractions with less manual work.

### Why were the first benchmarks a circular buffer and a fixed pool?

The circular buffer is small enough to understand but contains genuine
proof complexity: bounded storage, wraparound indexing, empty/full
conditions, prefix/suffix preservation, and a clear abstract sequence
meaning. It is also common in real-time systems. The fixed pool added a
set-based model and a genuinely hard fact, the pigeonhole bound. That
contrast drove the library decision: the ring buffers needed little
support, and the pool needed more, all of it generic.

### Why not start with an SPSC lock-free queue?

Memory ordering and concurrency would make it difficult to separate failures in the refinement architecture from failures in the concurrency model. SPSC is an excellent later target once the sequential patterns are well understood.

### Could proof-pattern ghost code hurt runtime performance?

Proper ghost code should not contribute to production behavior.
`SPARK_Refine_Prefix_Sets` is entirely ghost. The fixed-pool runtime
tests run in a normal production build, and also with `-gnata`, where
the library's ghost model is executed. Projects should still check how
ghost code interacts with their own compilation profiles.

*Historical:* this question was originally asked about *generated*
ghost code.

### Could proof-pattern libraries hurt proof performance?

Yes, and that is why proof time, VC count and prover behavior are
explicit metrics. GNATprove re-proves a generic body **per instance**.
On the fixed pool the library-backed variant has 161 checks instead of
136, and the gate takes ≈ 2.2 s instead of ≈ 1.9 s. Its hardest VC,
however, dropped from 7 553 to 294 prover steps. More lemmas are not
always better, and every new pattern must report its proof-time effect.

### What if a proof-pattern library has a bug?

A wrong library claim should fail GNATprove, because the library is
proved at every instantiation and contains no assumptions, axioms,
justifications or suppressions (enforced by a CI trust scan). The
library is not a trusted theorem oracle.

A library can still be *useless or misleading* without being unsound.
Its contract can be too weak to help clients, or it can cover a
narrower representation family than documented. That is why patterns
ship with independent validation instances and negative fixtures.

### What if the diagnostics have a bug?

The diagnostics never decide proof status, so a diagnostic bug cannot
make an unproved program proved. It can mislead, though: for example, a
missed SRD001 or an overconfident SRD002 might steer a human or agent to
the wrong layer. The rules are therefore conservative. They skip when
evidence is missing and report consistency problems rather than resolve
them. A bug that could lead someone to weaken a requirement is treated
as soundness-sensitive (`SECURITY.md`).

*Historical:* the original question was "What if the generator has a
bug?".

### Could the tool accidentally prove the wrong requirement?

A prover proves the assertions it is given. `spark-refine` cannot
determine human intent. That is why public behavioral contracts remain
user-owned and authoritative. `spark-refine` never edits them.

### Will this make SPARK easy for beginners?

It can remove repetitive work and expose common patterns, but formal
specification still requires skill. Two side effects are educational:

* readable proof-pattern libraries show canonical ways to connect an
  implementation to a model;
* diagnostics name the kind of proof-engineering problem, e.g. masking
  or an abstraction gap, rather than only the failed check.

### Is AI required?

No. Both pillars are deterministic and useful to a human alone. AI
agents can *consume* `spark-refine explain --format json`, but they are
optional and are never a proof authority.

*Historical:* the original answer referred to "the deterministic
generator" and "the refinement IR".

### Why use a manifest?

Today there is no manifest. Nothing in the product reads
`spark-refine.toml`. The TOML manifest (ADR 0003) and later source
annotations (ADR 0004) were designed to drive a generator. With
generation deferred, a library's configuration is its **generic
instantiation**, which is ordinary Ada checked by the compiler.
`examples/ring_buffer/spark-refine.toml` remains as a historical,
illustrative fixture.

### Can this help certification?

Potentially. Deterministic diagnostics, stable rule identifiers,
assumption-free libraries and trust scans are good inputs to assurance
evidence. Certification is not a current claim and depends on the
applicable standard and tool-qualification strategy.

### What would make us change direction again?

The project already changed direction once on evidence: the generator
hypothesis was weakened by Tasks 001–003 and rejected as the primary
architecture in Task 004. The same discipline applies now.

* **Libraries.** If new patterns show that per-instance support stays
  large even with a library, or that libraries are harder to use than
  local proof code, reconsider thin generation or other approaches.
* **Diagnostics.** If they fail to help humans or agents pick the right
  layer on real projects, or their conservative warnings become noise,
  revise or retire rules.

Each direction has to keep earning its place.

*Historical:* the original question was "What would make us abandon this
idea?". Its answer ("if generic pattern information is insufficient,
generated proofs are harder to maintain, or configuration duplicates as
much work as it saves, the project should pivot") is what actually
happened to the generator.
