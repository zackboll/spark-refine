# Design Principles

1. **Requirements are not boilerplate.** Never optimize away the user's statement of intended behavior.
2. **Models are not the enemy.** The target is the glue between models and implementations.
3. **GNATprove decides truth.** The generator constructs obligations; it does not certify them.
4. **No green-by-assumption.** A proof that succeeds because tooling inserted trust is not an automation success.
5. **Use existing mathematical libraries.** Prefer SPARKlib abstractions over parallel incompatible theories.
6. **Generate boring code.** Predictable, simple SPARK is preferable to clever metaprogramming.
7. **Every generated fact has provenance.** A reviewer should know why it exists.
8. **Every pattern earns stability through proof fixtures.** Documentation alone is insufficient.
9. **Measure maintenance, not just initial LOC.** Representation refactors are part of the benchmark.
10. **Semantic analysis beats text parsing.** Use Libadalang when source semantics matter.
11. **Start external, upstream evidence later.** Avoid a prover fork until the pattern is understood.
12. **AI is optional acceleration.** Deterministic proof engineering must remain useful without it.
13. **Fail loudly on ambiguity.** Do not guess entity resolution or representation meaning.
14. **Do not hide proof performance.** Generated code that makes proving impractical is not a win.
15. **Support escape hatches explicitly.** Application-specific lemmas will always exist; make them composable with generated structure.
