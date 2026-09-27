# spark-refine

**Reusable proof patterns and proof-aware diagnostics for SPARK.**

`spark-refine` is an open-source proof-engineering toolkit for SPARK.
It provides reusable proof patterns and proof-aware diagnostics while
keeping GNATprove as the proof authority.

> Status: pre-alpha. Both pillars below are real, tested and exercised by
> CI on the pinned FSF GNAT / GNATprove / SPARKlib 16.1.0 toolchain.
> Neither modifies your sources, and neither decides whether anything is
> proved: GNATprove does.

## The two pillars

**1. Reusable proof-pattern library**, in [`proof_patterns/`](proof_patterns/)

Hand-written, independently validated SPARK generics that carry the
generic part of a proof, so each instance does not have to. The first
pattern, `SPARK_Refine_Prefix_Sets`, reduced the per-instance proof
support of the fixed-pool benchmark from 36 to 10 SLOC
([`examples/fixed_pool/LIBRARY_METRICS.md`](examples/fixed_pool/LIBRARY_METRICS.md)).

**2. Proof-aware diagnostics**, in [`diagnostics/`](diagnostics/), command
`spark-refine`

A deterministic analyzer over GNATprove's machine-readable output
(`gnatprove.sarif`, `*.spark`, `*.ali`). It turns low-level check
outcomes into proof-engineering diagnostics. It serves humans directly
and serves AI agents, CI and editors as stable JSON:

| Code | Category | Meaning |
|---|---|---|
| SRD001 | `proof_context` | a failed invariant may mask downstream proved postconditions (a masking *risk*, never a causality or falsity claim) |
| SRD002 | `abstraction_boundary` | client-only proof gap; the public abstraction *may* be insufficient (medium / low confidence) |
| SRD003 | `prover_portfolio` | a proof depends on the prover portfolio (confidently matched checks only) |

## Quick start

Install the diagnostics CLI (Python ≥ 3.11, no runtime dependencies):

```bash
python3 -m pip install ./diagnostics        # from a checkout
python3 -m pip install -e ./diagnostics     # or: editable, for development
spark-refine rules
```

Human workflow, from your SPARK project's directory:

```bash
gnatprove -P my_project.gpr

spark-refine explain
```

Without a path, `explain` looks under the current directory for exactly
one GNATprove result set: `gnatprove.sarif` + `*.spark`, e.g. in
`obj/gnatprove/` or `obj/<variant>/gnatprove/`. If it finds none or
several, it exits 2 and lists the candidates. It never guesses. Pass the
location explicitly when needed:

```bash
spark-refine explain obj/proof/gnatprove
spark-refine explain obj/proof/gnatprove/gnatprove.sarif
```

JSON for an agent or CI. The format is `format_version` 1. Every
diagnostic carries `code`, `category`, `action` and `confidence`, and the
report has a `summary` derived from the diagnostics:

```bash
spark-refine explain --format json > spark-refine.json
spark-refine explain --format json --fail-on SRD001   # exit 1 if emitted
```

Prover-portfolio comparison over single-prover runs:

```bash
spark-refine compare-provers \
  --run cvc5=obj/cvc5/gnatprove \
  --run z3=obj/z3/gnatprove \
  --run altergo=obj/altergo/gnatprove
```

> **Freshness.** `spark-refine explain` analyzes the proof results you
> point it at. They describe your current sources only if you have just
> run GNATprove. `spark-refine` does not run GNATprove itself.

`analyze` remains a compatibility alias of `explain` (path required), and
`python3 -m spark_refine_diagnostics ...` still works. Full reference:
[`diagnostics/README.md`](diagnostics/README.md). Agent loop and trust
boundary: [`docs/AGENT_INTEGRATION.md`](docs/AGENT_INTEGRATION.md).

## Trust boundary

```text
GNATprove        determines proof status (the proof authority)
spark-refine     interprets proof-result patterns (read-only, deterministic)
you / an agent   decide what to change; authoritative Pre/Post/model
                 changes deserve explicit human review
```

Neither `spark-refine` nor an AI agent consuming its output is a proof
authority. `spark-refine` never edits sources, repairs proofs, changes
contracts or emits unchecked assumptions. See
[`docs/TRUST_MODEL.md`](docs/TRUST_MODEL.md).

## How the project got here

The project began as a hypothesis: *generate* the refinement proof
scaffolding (ghost models, representation predicates, lemmas) from a
manifest. Tasks 001–004 measured that hypothesis on real, fully proved
benchmarks. After them, source generation was **deliberately
deprioritized**:

| Task | Finding |
|---|---|
| 001–002 | ring buffers (two representations): generation had little value for these proofs |
| 003 | fixed pool: more proof support (36 SLOC), but all of it generic |
| 004 | a reusable SPARK *library* cut per-instance support to 10 SLOC → **PIVOT** to libraries |
| 005 | deterministic diagnostics work on real GNATprove output (SRD001–SRD003) |
| 006 | diagnostics packaged as the installable `spark-refine explain` CLI |

The original design documents are preserved unchanged as history:

* the original README, in [`docs/history/ORIGINAL_README.md`](docs/history/ORIGINAL_README.md);
* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md);
* [`docs/SPEC.md`](docs/SPEC.md);
* [`docs/MANIFEST.md`](docs/MANIFEST.md);
* the ADRs in [`docs/adr/`](docs/adr/).

The current direction is in [`docs/ROADMAP.md`](docs/ROADMAP.md). Each
task's full record is in [`docs/tasks/`](docs/tasks/).

## Two executables, two names

| Name | What | Status |
|---|---|---|
| `spark-refine` (hyphen) | the Python diagnostics CLI, installed from `diagnostics/` | **current** developer-facing tool |
| `spark_refine` (underscore) | the Ada bootstrap executable built from the root `alire.toml` | legacy/bootstrap; implements no commands and points to `spark-refine` |

The generator commands once sketched for the Ada executable (`validate`,
`generate`, `check`) are historical, deprioritized research. They are not
planned commands.

## Repository map

```text
README.md                        this overview
diagnostics/                     spark-refine CLI (Python package, SRD001-SRD003)
  pyproject.toml                 installable package, console script spark-refine
  tests/                         fixture-based suite (49 real GNATprove runs)
proof_patterns/                  reusable SPARK proof-pattern library
examples/ring_buffer/            Tasks 001-002 benchmark (two representations)
examples/fixed_pool/             Tasks 003-004 benchmark (manual + library-backed)
docs/AGENT_INTEGRATION.md        safe agent loop over spark-refine JSON
docs/TRUST_MODEL.md              soundness and trust boundary
docs/ROADMAP.md                  evidence-gated roadmap
docs/tasks/                      task records 001-006
docs/history/ORIGINAL_README.md  original generator-centred README (history)
docs/ARCHITECTURE.md, SPEC.md,   original generator design (history)
  MANIFEST.md, PROOF_PATTERNS.md
docs/MOTIVATION.md, LANDSCAPE.md, RESEARCH.md, VISION.md, FAQ.md
docs/BENCHMARKS.md, METRICS.md   validation experiments and metrics
docs/INTEGRATION.md              GNATprove/SPARKlib/Libadalang/Alire notes
docs/adr/                        architecture decision records
src/                             legacy Ada bootstrap executable spark_refine
```

## Design principles

- **Proof authority stays with GNATprove.**
- **No hidden axioms.** Library claims are proved; diagnostics never emit
  assumptions.
- **Read-only diagnostics.** No source rewriting, automatic proof repair
  or contract change.
- **Deterministic output.** Same inputs give byte-stable reports, with no
  timestamps.
- **Conservative inference.** When evidence is unavailable, a rule is
  skipped and the report says so. It never guesses.
- **Measure proof effort.** Each direction has to earn its place with
  evidence.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
