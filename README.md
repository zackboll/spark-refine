# spark-refine

**Reusable proof patterns and proof-aware diagnostics for SPARK.**

`spark-refine` is an open-source proof-engineering toolkit for SPARK. It
combines reusable, GNATprove-verified proof patterns with proof-aware
diagnostics for humans and AI agents. GNATprove remains the proof
authority.

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

Task 019 closed with **`DO_NOT_ADOPT_BITMAP_PATTERN`**: manual P=54,
minimized library-backed R=56, library L=124. The 32-bit bitmap candidate
reached complete local proofs, but failed the economic criteria; broader
validation and falsification were not completed. Its source is retained as
unsupported research, not a second supported pattern. Prefix_Sets remains
the one established reusable pattern. See [closeout](docs/tasks/019-bitmap-set-proof-pattern.md#observations-append-only-after-preregistration-commit).

A deterministic analyzer over GNATprove's machine-readable output
(`gnatprove.sarif`, `*.spark`, `*.ali`). It turns low-level check
outcomes into proof-engineering diagnostics. It serves humans directly
and serves AI agents, CI and editors as stable JSON:

| Code | Category | Meaning | Command |
|---|---|---|---|
| SRD001 | `proof_context` | a failed invariant may mask downstream proved postconditions (a masking *risk*, never a causality or falsity claim) | `prove` / `explain` |
| SRD002 | `abstraction_boundary` | client-only proof gap; the public abstraction *may* be insufficient (medium / low confidence) | `prove` / `explain` |
| SRD003 | `prover_portfolio` | a proof depends on the prover portfolio (confidently matched checks only) | `compare-provers` |

## Quick start

Install the diagnostics CLI (Python ≥ 3.11, no runtime dependencies):

```bash
python3 -m pip install ./diagnostics        # from a checkout
python3 -m pip install -e ./diagnostics     # or: editable, for development
spark-refine rules
```

Preferred workflow, from your SPARK project's directory:

```bash
spark-refine prove -P my_project.gpr                 # run GNATprove, then explain ITS results
spark-refine prove -P my_project.gpr --format json   # the same, for agents / CI
spark-refine prove -P my_project.gpr -- --level=2 --prover=z3   # extra GNATprove args
```

What `spark-refine prove` does (Task 008):

* it prints the exact GNATprove command to stderr, then runs it (argv,
  never a shell). GNATprove's console output goes to **stderr**, so
  stdout carries only the spark-refine report;
* it analyzes **only the result set that this GNATprove run created or
  changed**. Unchanged (stale) result sets are ignored. If there are zero
  or several fresh result sets, it refuses instead of guessing. With
  `--results PATH`, that location must have been freshly written;
* if GNATprove fails but wrote fresh results, you still get SRD001/SRD002,
  and `prove` exits with **GNATprove's exit code**;
* it proves nothing itself. It is exactly "run GNATprove, then `explain`",
  plus a guarantee that the analyzed results come from that run.
  `--dry-run` shows the command without running it.

For an Alire crate: `alr exec -- spark-refine prove -P my_project.gpr`.

**Opt-in raw unproved worklist (Task 020):** add `--show-unproved` to
`explain`, `analyze`, or `prove`, in text or JSON:

```bash
spark-refine explain RESULT_DIR --show-unproved
spark-refine analyze RESULT_DIR --show-unproved --format json
alr exec -- spark-refine prove -P my_project.gpr --show-unproved --format json -- --checks-as-errors=on
```

This lists every loaded normalized unproved check, independently of SRD
diagnostics. **11 unproved checks + 0 SRD diagnostics still means proof work
remains.** JSON adds optional `analysis.unproved_checks` (`scope`, `count`,
`by_rule`, `items`), retaining `format_version: 1`. Duplicate occurrences
remain separate; missing metadata stays unknown; disputed unproved checks
are marked. Proved and justified checks are excluded. The worklist is not a
complete proof certificate: inspect justifications, warnings, consistency
and incomplete-analysis notes alongside it. No source access or Libadalang
is required; it works with `--semantic` too. Without the flag reports are
unchanged. The flag is reporting-only, not an exit gate; use GNATprove's
`--checks-as-errors=on` after `prove`'s first `--` if desired. Dry-run still
only shows the plan. See [details](diagnostics/README.md#unproved-worklist-task-020)
and [human/agent workflow](docs/AGENT_INTEGRATION.md#the-loop-preferred).

**Experimental, opt-in (Task 009):** add `--semantic` (with `-P`, plus
`-X NAME=VALUE` scenario values where the project needs them) to
`prove`/`explain` when Libadalang is installed
(`diagnostics/scripts/setup_libadalang.sh`; it is not on PyPI). Each
SRD002 precondition failure then shows the exact call, the resolved
callee and its explicit public `Pre`. It never names a "failed conjunct"
(GNATprove does not report one), and without Libadalang the report is
unchanged. See `docs/INTEGRATION.md`. When enrichment runs, the report
also starts with an **SRD002 semantic triage** section (Task 010). It
groups precondition failures that call the same resolved declaration with
the same explicit `Pre`, for example three `Push` calls under one
`Ring_Buffer.Push` / `not Is_Full (B)` group. Everything else is listed as
ungrouped with a reason. Groups are descriptive: they do not claim a shared
cause or a contract defect.

Manual two-step workflow (still fully supported):

```bash
gnatprove -P my_project.gpr     # 1. GNATprove proves (the proof authority)
spark-refine explain            # 2. spark-refine interprets those results
```

What `spark-refine explain` does:

* it analyzes **one existing** GNATprove result set and runs **SRD001**
  and **SRD002** on it;
* it does **not** run GNATprove. Results it discovers may be **stale** if
  you changed sources since the last GNATprove run;
* it does **not** produce SRD003, which needs several single-prover runs
  and comes from `spark-refine compare-provers` (below).

Without a path, `explain` looks under the current directory for exactly
one GNATprove result set: `gnatprove.sarif` + `*.spark`, e.g. in
`obj/gnatprove/` or `obj/<variant>/gnatprove/`. If it finds none or
several, it exits 2 and lists the candidates. It never guesses. When
discovery is ambiguous, pass the results path explicitly:

```bash
spark-refine explain obj/<variant>/gnatprove
spark-refine explain obj/<variant>/gnatprove/gnatprove.sarif
```

JSON for an agent or CI. The format is `format_version` 1. Every
diagnostic carries `code`, `category`, `action` and `confidence`, and the
report has a `summary` derived from the diagnostics:

```bash
spark-refine explain --format json > spark-refine.json
spark-refine explain --format json --fail-on SRD001   # exit 1 if emitted
```

Prover-portfolio comparison over single-prover runs. This is the only
command that produces **SRD003**. Run GNATprove once per prover first,
e.g. `--prover=cvc5`, each into its own object directory:

```bash
spark-refine compare-provers \
  --run cvc5=obj/cvc5/gnatprove \
  --run z3=obj/z3/gnatprove \
  --run altergo=obj/altergo/gnatprove
```

> **Freshness.** `prove` guarantees that the analyzed result was freshly
> changed by the GNATprove command it just launched. `explain` analyzes an
> existing result set, and the caller is responsible for freshness: those
> results describe your current sources only if you have just run
> GNATprove. Neither command produces SRD003.

`analyze` remains a compatibility alias of `explain` (path required), and
`python3 -m spark_refine_diagnostics ...` still works. Full reference:
[`diagnostics/README.md`](diagnostics/README.md). Agent loop and trust
boundary: [`docs/AGENT_INTEGRATION.md`](docs/AGENT_INTEGRATION.md).

## Trust boundary

```text
GNATprove        determines proof status (the proof authority)
spark-refine     orchestration (`prove`: runs GNATprove, fresh-result
                 provenance) + interpretation of proof-result patterns
                 (read-only, deterministic)
you / an agent   decide what to change; authoritative Pre/Post/model
                 changes deserve explicit human review
```

`spark-refine prove` does not prove anything itself. Its authority is the
same as "run GNATprove, then run `explain` on the result". The only
extra property it adds is fresh-result provenance.

Neither `spark-refine` nor an AI agent consuming its output is a proof
authority. `spark-refine` never edits sources, repairs proofs, changes
contracts or emits unchecked assumptions. See
[`docs/TRUST_MODEL.md`](docs/TRUST_MODEL.md).

The project distinguishes three kinds of source. The distinction is a
recommended policy and is not mechanically enforced:

| Kind | Examples | Policy |
|---|---|---|
| Production implementation | operation bodies, concrete representation | normal engineering changes |
| Authoritative specification | public `Pre`/`Post`, abstract model semantics, requirements | high sensitivity; do not weaken it just to get a green proof |
| Mechanical proof support | representation invariants, model adapters, lemmas, loop invariants, proof-pattern instantiation | may change to make the proof architecture work; still checked by GNATprove |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §3.

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

The decision is recorded in
[ADR 0005](docs/adr/0005-library-and-diagnostics-first.md). Source
generation is **deferred pending new evidence**, not ruled out.

The original generator design is preserved as history:

* the original README, unchanged, in [`docs/history/ORIGINAL_README.md`](docs/history/ORIGINAL_README.md);
* [`docs/SPEC.md`](docs/SPEC.md) and [`docs/MANIFEST.md`](docs/MANIFEST.md), with a historical/deferred banner;
* Part II of [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), the historical
  sections of [`docs/VISION.md`](docs/VISION.md),
  [`docs/MVP.md`](docs/MVP.md) and [`docs/ROADMAP.md`](docs/ROADMAP.md);
* ADRs [0003](docs/adr/0003-manifest-first.md) and
  [0004](docs/adr/0004-annotations-later.md), marked
  superseded/deferred.

The current direction is in [`docs/VISION.md`](docs/VISION.md),
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/ROADMAP.md`](docs/ROADMAP.md). Each task's full record is in
[`docs/tasks/`](docs/tasks/).

## Two executables, two names

| Name | What | Status |
|---|---|---|
| `spark-refine` (hyphen) | the Python diagnostics CLI, installed from `diagnostics/` | **current** developer-facing tool |
| `spark_refine` (underscore) | the Ada bootstrap executable built from the root `alire.toml` | legacy/bootstrap; implements no commands and points to `spark-refine` |

The generator commands once sketched for the Ada executable (`validate`,
`generate`, `check`) are historical, deprioritized research. They are not
planned commands.

## Where to start: documentation hierarchy

Read the current-direction documents in this order. When documents
disagree, the higher one wins:

```text
README.md                  what spark-refine is, how to use it
  ↓
docs/VISION.md             mission, developer loop, maturity levels
  ↓
docs/ARCHITECTURE.md       current components, trust boundary, three kinds of source
  ↓
docs/ROADMAP.md            completed / near term / later / deferred
```

| Status | Documents |
|---|---|
| **Current, specialized** | [`docs/AGENT_INTEGRATION.md`](docs/AGENT_INTEGRATION.md), [`diagnostics/README.md`](diagnostics/README.md), [`docs/PROOF_PATTERNS.md`](docs/PROOF_PATTERNS.md), [`docs/TRUST_MODEL.md`](docs/TRUST_MODEL.md), [`docs/INTEGRATION.md`](docs/INTEGRATION.md), [`docs/METRICS.md`](docs/METRICS.md), [ADR 0005](docs/adr/0005-library-and-diagnostics-first.md) |
| **Historical / deferred** | [`docs/SPEC.md`](docs/SPEC.md), [`docs/MANIFEST.md`](docs/MANIFEST.md), [`docs/history/`](docs/history/), ADRs [0003](docs/adr/0003-manifest-first.md) and [0004](docs/adr/0004-annotations-later.md), task records [`docs/tasks/001`–`007`](docs/tasks/), benchmark experiment records (`examples/*/*METRICS*.md`) |

Some current documents, such as `docs/MVP.md`, `docs/ROADMAP.md` and
`docs/ARCHITECTURE.md`, also contain clearly labelled historical
sections. Anything under a "Historical" or "Deferred" heading describes
the generator hypothesis explored before the pivot. It is not the
current product.

## Repository map

```text
README.md                        this overview
diagnostics/                     spark-refine CLI (Python package, SRD001-SRD003)
  pyproject.toml                 installable package, console script spark-refine
  tests/                         fixture-based suite (49 real GNATprove runs)
proof_patterns/                  reusable SPARK proof-pattern library
examples/ring_buffer/            Tasks 001-002 benchmark (two representations)
examples/fixed_pool/             Tasks 003-004 benchmark (manual + library-backed)
docs/VISION.md                   current vision and maturity levels
docs/ARCHITECTURE.md             current architecture (Part II: deferred generator design)
docs/MVP.md                      current MVP: implemented / validated / future
docs/ROADMAP.md                  evidence-gated roadmap
docs/AGENT_INTEGRATION.md        safe agent loop over spark-refine JSON
docs/TRUST_MODEL.md              soundness and trust boundary
docs/INTEGRATION.md              GNATprove SARIF/.spark/.ali, SPARKlib, Libadalang (optional), Alire
docs/MOTIVATION.md, LANDSCAPE.md, RESEARCH.md, FAQ.md
docs/BENCHMARKS.md, METRICS.md   validation experiments and metrics
docs/PROOF_PATTERNS.md           pattern notes (circular sequence design + fixed pool)
docs/tasks/                      task records 001-008
docs/adr/                        architecture decision records (0005: current direction)
docs/history/ORIGINAL_README.md  original generator-centred README (history)
docs/SPEC.md, MANIFEST.md        original generator design (historical/deferred)
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
