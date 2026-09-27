# Design Principles

> **Status (Task 007).** These principles still hold. Where one was
> phrased in terms of the (now deferred) generator, it applies to
> proof-pattern libraries and diagnostics. The original wording is kept
> in parentheses. See [ADR 0005](adr/0005-library-and-diagnostics-first.md).

1. **Requirements are not boilerplate.** Never optimize away the user's statement of intended behavior.
2. **Models are not the enemy.** The target is the glue between models and implementations.
3. **GNATprove decides truth.** Proof-pattern libraries state obligations that GNATprove proves per instance, and diagnostics interpret its results. Neither certifies anything. (Originally: "The generator constructs obligations; it does not certify them.")
4. **No green-by-assumption.** A proof that succeeds because tooling inserted trust is not an automation success.
5. **Use existing mathematical libraries.** Prefer SPARKlib abstractions over parallel incompatible theories.
6. **Write boring proof code.** Predictable, simple SPARK is preferable to clever metaprogramming. (Originally: "Generate boring code.")
7. **Every library fact and every diagnostic has provenance.** A reviewer should know why a library lemma exists and which GNATprove results a diagnostic is based on. (Originally: "Every generated fact has provenance.")
8. **Every pattern earns stability through proof fixtures.** Documentation alone is insufficient.
9. **Measure maintenance, not just initial LOC.** Representation refactors are part of the benchmark.
10. **Semantic analysis beats text parsing.** Use Libadalang when source semantics matter.
11. **Start external, upstream evidence later.** Avoid a prover fork until the pattern is understood.
12. **AI is optional acceleration.** Deterministic proof engineering must remain useful without it.
13. **Fail loudly on ambiguity.** Do not guess entity resolution or representation meaning.
14. **Do not hide proof performance.** Library code that makes proving impractical is not a win. (Originally: "Generated code ...")
15. **Support escape hatches explicitly.** Application-specific lemmas will always exist; make them composable with library-provided structure. (Originally: "... with generated structure.")
16. **Interpret conservatively.** A diagnostic states a risk or gap, never more than its evidence supports. When evidence is missing, the rule is skipped and the report says so.
