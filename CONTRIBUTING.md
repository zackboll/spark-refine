# Contributing

`spark-refine` is pre-alpha. It is a proof-engineering toolkit for SPARK
with two pillars: reusable, GNATprove-verified proof patterns and
proof-aware diagnostics for humans and AI agents. GNATprove remains the
proof authority. See `README.md`, `docs/ARCHITECTURE.md` and
[ADR 0005](docs/adr/0005-library-and-diagnostics-first.md).

Contributions should strengthen what the evidence supports rather than
expand scope prematurely.

## Priorities

- **proof-pattern correctness and validation.** Libraries are proved per
  instance, have independent validation instances and negative fixtures,
  and contain no assumptions;
- **diagnostic conservatism.** A rule should skip or lower confidence
  rather than guess;
- **GNATprove result compatibility.** Keep SARIF / `.spark` / `.ali`
  reading faithful, and be explicit about the versions validated;
- **human-readable explanations** that state what a diagnostic does
  *not* claim;
- **stable agent-facing JSON.** `format_version` 1 changes must be
  additive. Breaking changes need a new format version;
- **benchmark and evidence quality**: real GNATprove results, provenance,
  ablation-based ground truth;
- **trust-boundary preservation.** Nothing may decide proof status, edit
  sources, or introduce unchecked assumptions.

Source generation, manifests and generation-oriented annotations are
deferred research (see `docs/ROADMAP.md`). Please open a discussion with
evidence before contributing in that direction.

## Development workflow

Use feature branches and pull requests. A change should normally include:

- tests for new behavior, fixture-based for diagnostics and GNATprove
  proof gates for patterns;
- documentation for public semantics, including JSON fields and exit
  codes;
- a note if trust assumptions change;
- benchmark/proof evidence for pattern changes;
- a CHANGELOG entry.

Useful local commands:

```bash
python3 scripts/check_repo.py
python3 -m unittest discover -s tests -v
(cd diagnostics && python3 -m unittest discover -s tests -t tests -v)
python3 diagnostics/scripts/packaging_smoke.py
```

The proof gates need the pinned Alire / GNAT / GNATprove 16.1.0
toolchain. See `.github/workflows/ci.yml`.

## Proof-pattern contributions

A pattern PR should explain:

- **mathematical meaning**: the abstract model and the relation to the
  representation;
- **supported representation family**, with explicit restrictions and
  unsupported variants;
- **GNATprove evidence**: application instance(s) and independent
  validation instances fully proved, and negative fixtures detected;
- **application configuration burden**: generic actuals, local invariant
  and adapter lines, and per-instance SLOC `R` against a manual
  baseline;
- **proof-time effect**: checks, wall time, max steps, and the
  single-prover matrix;
- **trust assumptions**: which SPARKlib contracts are relied on. There
  must be no `pragma Assume`, axioms, justifications, imports or
  suppressions (trust scan);
- whether the pattern's version must change, since library changes can
  affect proof behavior for every instance.

## Diagnostics contributions

A diagnostics PR, and especially a new or changed rule, should explain:

- the **exact structural rule**: which GNATprove facts must hold, in
  terms of rule ids, statuses, units and entities;
- the **evidence corpus**: the real GNATprove fixtures it was checked on,
  with provenance, and positive and negative controls;
- its **confidence** policy and the wording of its claim, i.e. what it
  does not assert;
- **known false or conservative warnings**, reported per case, not as an
  aggregate accuracy score;
- its **degradation behavior** when inputs are missing, malformed,
  inconsistent or from an unsupported version;
- JSON additions (`category`, `action`) and their agent guidance in
  `docs/AGENT_INTEGRATION.md`.

## Soundness review

Any change that introduces assumptions, imported proof-only declarations, disabled proof checks, or a new trusted foundation must be called out explicitly. The same applies to any change that could make a diagnostic appear to decide proof status, or that could encourage weakening an authoritative specification. See `SECURITY.md` and `docs/TRUST_MODEL.md`.

## Style

Favor clear Ada/SPARK over abstraction-heavy framework code. Proof-pattern libraries are part of the user experience and should be understandable to someone learning the proof pattern. Diagnostics code should stay small, deterministic and dependency-free at runtime.
