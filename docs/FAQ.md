# FAQ

## Isn't the abstract model itself duplicate code?

It is duplicate *state meaning*, but usually intentional. The model is optimized for specification and proof; the implementation is optimized for execution. `spark-refine` focuses on reducing the mechanical code that establishes correspondence between them.

## Why not generate the entire model automatically from the implementation?

Because the implementation does not uniquely determine the intended abstraction. The same data can have many valid meanings. The developer must own the semantic choice.

The tool can generate a model adapter once the developer says “this is a circular sequence whose storage/first/length are these entities.”

## Why not just improve GNATprove?

Some improvements may ultimately belong upstream. An external tool is a better experiment because it can iterate rapidly, preserve GNATprove as the trusted verifier, and gather evidence about useful abstractions before proposing language/prover changes.

## Doesn't `Refined_State` already solve this?

It solves an important state-abstraction problem at package boundaries. It does not automatically provide the model functions, intermediate abstractions, data-structure lemmas, or representation-preservation proof architecture that this project targets.

## Doesn't SPARKlib already provide models?

Yes, and `spark-refine` should reuse them. SPARKlib helps define the **abstract side**. This project focuses on connecting common concrete representations to those abstractions with less manual work.

## Why is the first pattern a circular buffer?

It is small enough to understand but contains genuine proof complexity: bounded storage, wraparound indexing, empty/full conditions, prefix/suffix preservation, and a clear abstract sequence meaning. It is also common in real-time systems.

## Why not start with an SPSC lock-free queue?

Memory ordering and concurrency would make it difficult to separate failures in the refinement architecture from failures in the concurrency model. SPSC is an excellent later target after the sequential circular-sequence pattern is sound.

## Could generated ghost code hurt runtime performance?

Proper ghost code should not contribute to production behavior. The project must still verify how generated artifacts interact with compilation profiles and ensure no proof-only structure leaks into executable semantics.

## Could generated proof code hurt proof performance?

Absolutely. This is why GNATprove wall time, VC count, and solver behavior are explicit metrics. More lemmas are not always better.

## What if the generator has a bug?

Under the intended trust model, a wrong generated theorem should fail GNATprove. The project forbids closing gaps by silently generating assumptions.

A generator bug could still create misleading diagnostics, omit desired properties, or alter configuration, so review and negative tests remain important.

## Could the tool accidentally prove the wrong requirement?

A prover proves the assertions it is given. `spark-refine` cannot determine human intent. That is why public behavioral contracts remain user-owned and authoritative. The tool should not silently edit them.

## Will this make SPARK easy for beginners?

It can remove repetitive work and expose common patterns, but formal specification still requires skill. A useful side effect is educational: generated proof code can show canonical ways to connect an implementation to a model.

## Is AI required?

No. The deterministic generator must justify the project by itself. AI can later use the refinement IR and proof provenance for safer suggestions.

## Why not make the manifest the permanent DSL?

It may remain useful, but representation metadata belongs close to source in many projects. The plan is to prototype semantics in TOML, then add `Annotate`-based source declarations after the vocabulary stabilizes.

## Can this help certification?

Potentially. Stable proof identifiers, provenance, trust reports, and deterministic generation are good inputs to assurance evidence. Certification is not an MVP claim and depends on the applicable standard/tool qualification strategy.

## What would make us abandon this idea?

If benchmarks show that generic pattern information is insufficient, generated proofs are harder to maintain than hand-written proofs, or configuration duplicates as much work as it saves, the project should pivot. The initial benchmark is explicitly designed to make that decision possible.
