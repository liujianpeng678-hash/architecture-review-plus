# Audit Standard (canonical)

This is the fixed rubric. Every module audit must follow it verbatim so scores are
comparable across modules, runs, and projects. Do not improvise scoring.

## Scoring rubric (0–100) → grade

| Score | Grade | Meaning |
|------:|:-----:|---------|
| 90–100 | A | Clean, well-scoped, idiomatic. No material smells. |
| 75–89 | B | Minor issues: a documented shim, mild bloat, a localized cast. |
| 60–74 | C | Notable hacks/fallbacks, real bloat, or duplication that has a clear owner. |
| 40–59 | D | Significant legacy/stubs/duplication, or a dual-format/protocol violation. |
| 0–39 | F | Broken, fake output, or an unfinished feature wired in as if done. |

Be rigorous and evidence-based, not generous. A module with one HIGH finding rarely
scores above 60; with only LOW findings it usually scores 80+.

## Machine-enforced semantic invariants

`scripts/audit_contract.py` is the single executable owner of this rubric's hard
semantics. `apply_audit.py`, publish preflight and retained-history verification must call
that shared contract rather than reimplementing checks. At minimum it enforces:

- `score` is a real integer from 0 through 100 (a boolean is not a score), and `grade`
  exactly matches the table above;
- every tag exists in the effective standard; `clean` is exclusive, has no findings,
  and is incompatible with a materially low score;
- every negative tag has concrete finding evidence, and each finding has a valid
  severity, location and non-empty explanation;
- `auditedHash` identifies the exact current `contentHash` at publish time;
- a publishable audit has the complete module/dependency graph, exactly eight canonical
  dimensions, exactly four lenses, and the evidence required by this standard.

A project `standard.json` may add valid taxonomy tags and descriptions, but it cannot
remove these invariants. A semantic failure is a hard rejection: no partial mutation,
version allocation or retained promotion is allowed.

## Smell taxonomy (the `tags`)

Use these exact tag strings. `clean` is the only positive tag; the rest are negative
(the map colors them red and counts them in the report).

- `monkeypatch` — runtime mutation of another module / stdlib / vendor; `setattr` on
  foreign objects; `sys.modules` / `sys.meta_path` surgery; reassigning store actions.
- `fallback` — "try the real thing, then fake/degrade"; chained `a || b || c` /
  `a ?? b` defaults that hide which value is real.
- `silent-except` / `silent-catch` — `except: pass`, bare `except`, empty `catch {}`
  that swallow errors with no log/signal.
- `legacy` — deprecated/back-compat shims, retired vocabulary, dead-but-shipped code,
  parallel "old + new" code paths kept side by side.
- `dual-format` — accepting both snake_case and camelCase (or two payload shapes) for
  the same field; the classic `display_name || displayName` patch.
- `stub` / `placeholder` — `NotImplemented`, `TODO: implement`, dead buttons, demo
  scripts, hardcoded sample data presented as real.
- `fake-output` — returns random/canned/hardcoded results where real computation is implied.
- `duplication` — logic copy-pasted from a sibling or that an existing shared
  abstraction already covers.
- `bloat` / `god-component` — oversized file/function; many responsibilities in one unit.
- `glue` — thin, valueless pass-through / boilerplate forwarding: rows of one-line
  wrappers that only forward args to another layer (e.g. dozens of `send({type:...})`
  methods), an adapter that copies a payload field-for-field without transforming, a
  store/function that only re-exports or delegates to another. The indirection earns
  nothing. Distinct from `bloat` (size) and `duplication` (copy-paste): glue is about
  forwarding that adds no value.
- `any-escape` — `as any`, `@ts-ignore`, untyped boundaries used to bypass the type system.
- `over-fit` — hardcoded to one case where a small generalization was expected.
- `clean` — no material issues.

### The taxonomy is language-agnostic — recognize the per-language form

The tags name *behaviors*, not syntax. Map each to whatever the target language does:

| tag | Python | TS / JS | C# / .NET | Rust | C / C++ |
|---|---|---|---|---|---|
| `any-escape` | `# type: ignore`, `Any` | `as any`, `@ts-ignore`, `!` | `dynamic`, `object` casts, `#nullable disable` | `unsafe`, `transmute`, blanket `.unwrap()` | `void*`, `reinterpret_cast`, C-style casts |
| `silent-except` | `except: pass` | empty `catch {}` | `catch (Exception) {}` | `let _ = x;`, `.ok()`, `unwrap_or_default` to hide | empty `catch`, ignored return codes / `errno` |
| `monkeypatch` | `setattr`, `sys.modules` | prototype patching, global override | reflection / Harmony patching | macro / `static mut` hacks | `#define` overrides, weak-symbol swap |
| `dual-format` | `a or b` (snake/camel) | `a ?? b`, `a \|\| b` | nullable + alias props | `Option` chains for two shapes | overloads accepting two layouts |
| `fallback` | try real then stub | `try/catch` → canned data | `try/catch` fallback | `unwrap_or(fakeDefault)` | `#ifdef` to fake impl |

`legacy`, `stub`, `fake-output`, `bloat`, `god-component`, `duplication`, `glue`,
`over-fit` are the same idea in every language. Generated/vendor/build outputs are excluded from production scanning. Tests and build
configuration remain evidence for safeguards, scenarios and conclusion invalidation,
even where excluded from production LoC (`target/`, `bin/`, `obj/`, `node_modules/`,
`__pycache__/`, `dist/`, …).

Judgement rules:
- A *documented, bounded* compat shim that deliberately refuses to silently coerce is
  `legacy` at most LOW — do not over-penalize disciplined shims.
- A fallback that is a real security control or numeric guard (e.g. identity matrix on
  singular input, stripping untrusted shaders) is **not** a smell.
- Native-dependency gating that *raises or returns an error* when a lib is missing is
  correct; only `fake-output` if it silently returns fabricated data.
- A `*Placeholder` name is not automatically a stub — read it; it may be a finished
  read-only widget.
- A *single* thin delegator, or a genuine boundary normalizer that converts/validates
  once, is fine — not `glue`. Flag `glue` only when pass-through wrappers **proliferate**
  (many near-identical forwarders that should be collapsed, generated, or replaced by a
  generic dispatch) or an adapter forwards with no transformation. Usually MED when it
  proliferates, LOW for a one-off.

## Severity (each finding)

- `HIGH` — wrong/dangerous/fake, a protocol or security issue, or a god-file that is a
  genuine maintenance hazard.
- `MED` — a real smell a maintainer should fix: a live dual-format patch, an un-migrated
  duplicate, an unfinished-but-wired path.
- `LOW` — a documented shim, a cosmetic cast, benign bloat. Worth noting, not urgent.

Always cite `file:line` and quote/paraphrase the offending snippet. Never report a
grep hit as a problem without reading the surrounding code.

## Four-lens / eight-dimension architecture classification

Module quality scores and architecture-dimension results are related but not
interchangeable. A clean module can still participate in a bad dependency direction;
a low-scoring leaf need not create a system-wide boundary risk. Keep the existing
per-module scoring protocol unchanged, then synthesize these eight evidence-backed
architecture dimensions:

| Lens | Dimension | Judge this | Typical evidence |
|---|---|---|---|
| 分 | `responsibility` | one coherent reason to change; no God Object | responsibilities, public surface, file/class size, unrelated change reasons |
| 分 | `boundary` | UI, combat, persistence, and data do not write through each other | cross-layer writes, internal-state access, global-singleton calls |
| 连 | `contract` | stable interfaces, events, DTOs/snapshots, contract tests | typed APIs, signals/events, Dictionary/has_method/dynamic dispatch |
| 连 | `dependency` | no cycles, reversed layers, or uncontrolled blast radius | dependency edges, fan-in/out, cycles, lower-to-upper dependencies |
| 变 | `data_logic` | new content uses data through one stable extension point | catalog/resource coverage, hardcoded branches, registration sites |
| 变 | `composition_state` | complex behavior is composed and stateful, not condition sprawl | state machines, components, strategies, branch complexity, inheritance depth |
| 变 | `evolution` | old data upgrades through stable IDs and real migrations | schema version, migration steps, compatibility reads, transactions, rollback |
| 保 | `safeguards` | regressions can be detected, traced, and recovered | tests, Git, CI, docs, retained audits, snapshots, backups, rollback proof |

Dimension status is one of `good`, `warning`, `risk`, `unknown`:

- `good`: current evidence supports a healthy boundary.
- `warning`: localized coupling or evolution cost exists but is not yet systemic.
- `risk`: evidence shows cross-domain ownership, uncontrolled dependency, unsafe
  migration, or materially weak recovery.
- `unknown`: the dimension was not checked, evidence is insufficient, or tooling cannot
  decide. Unknown is never treated as good.

Do not create a dimension score from the number of findings. Leave `score: null` unless
the project's `standard.json` defines a repeatable dimension rubric. Every `warning` or
`risk` needs at least one current evidence item and a primary dimension. The same evidence
may be referenced elsewhere, but it must not be counted twice. A missing cycle, a tests
folder, a schema version, or a large file is not by itself proof of health or failure.

## Module review protocol

Follow MAINTAINABILITY.md for coverage, evidence, reviewer mode and acceptance. Each
scored module needs its own assessment and rationale. Prefer an independent subagent
when delegation is authorized and available; otherwise use a disclosed `single-reviewer`
pass. Sequential passes by the same reviewer do not establish independence. Small,
low-risk modules may share context, but never share scores or coverage records.
Honor the user's model settings and use sufficient capability for the evidence scope.
JSON validation checks record consistency, not the truth of a diagnosis.

### Auditor prompt template

> You are auditing ONE functional module for an architecture audit.
> Module: **{label}** (`{id}`). Files: {paths}. Project root: {root}.
> Maintenance scenario: {scenario}. Reviewer mode: {reviewer_mode}.
>
> Read reference/MAINTAINABILITY.md and the effective project standard. Trace relevant
> public interfaces, callers, state writers, failure paths and existing tests. Use search
> to locate evidence, then read enough surrounding code and dependencies to test the
> diagnosis. No marker hits, file size, or a few excerpts alone establish module health.
> Assess adapters and compatibility code by their actual boundary and maintenance value.
> Use the scoring rubric, taxonomy and severity rules below, including project tag
> overrides: {paste effective rubric, taxonomy, severity and judgment rules}.
>
> Declare coverage as triage, scenario-reviewed or full-module-reviewed; identify files
> and symbols read, exclusions, confidence, unanswered questions, and conclusion
> dependencies (contracts, tests, configuration, standard and source revision/hashes).
> Explain the grade and uncertainty. Each finding must contain the five evidence
> elements from MAINTAINABILITY.md: trigger/observation, cause/confidence, impact,
> smallest correction/tradeoffs, and verification/disconfirming result.
>
> Return review notes separately from the audit JSON. Notes must include coverage,
> reviewer mode, score rationale and conclusion dependencies. For triage or insufficient
> whole-module evidence, return notes only, leave the module unscored, and identify the
> missing review work. Do not fabricate a score to satisfy publication requirements.
> For sufficient coverage, also return this audit JSON:
> {"score": <0-100>, "grade": "<A|B|C|D|F>",
>  "tags": ["<from the effective taxonomy>", ...],
>  "findings": [{"sev":"HIGH|MED|LOW","loc":"file:line","text":"evidence and rationale"}, ...]}
> If clean, use tags ["clean"] and findings []. Clean still requires coverage evidence.

Pass only the audit JSON to `apply_audit.py`. Persist the separate notes in existing
`reportThemes` headline/body pairs as specified by MAINTAINABILITY.md; extra audit JSON
fields are not a storage channel. A structured result may carry notes and audit as
separate fields, but the orchestrator must extract the audit object before applying it.

## Test-author protocol (the `test` command + the baseline step of `fix`)

Use existing test facilities and public behavior. Separate the test-author from the
fixer when risk warrants and delegation is authorized; local fixes may use disclosed
self-review. Do not silently introduce a framework. Without a harness, use a scoped
reproducible check or propose a minimal harness within authorized work.

- Characterization checks record behavior to preserve, not a claim that all current
  behavior is correct. Do not lock a known bug as the desired behavior.
- Defect reproductions assert the intended behavior and may fail before repair. Record
  them as expected target failures and require them to pass after the fix.
- Capture exact baseline commands and outcomes: baseline-green checks, target failures,
  unrelated existing failures and environmental blockers. Bound regression risk before
  proceeding; an unrelated failure alone does not prohibit a scoped repair.
- Preserve meaningful tests. Test changes for intentional contract changes need explicit
  rationale; never delete, skip or weaken checks simply to obtain green results.
- Return framework/check commands, files, preserved behaviors, target reproductions,
  baseline outcomes and remaining gaps.

## Acceptance / regression gate (the gate in `fix`)

High-risk fixes to contracts, state/data ownership, persistence, permissions or
release/recovery require independent verification. If unavailable or unauthorized,
report implementation and self-check results with acceptance pending. Local low-risk
fixes may use disclosed self-review. A verifier assesses outcomes, not quality scores.

- Re-run baseline checks and the narrowest relevant build/type checks. Baseline-green
  required behavior must remain; unexplained failed, skipped, deleted or flaky checks
  prevent acceptance. Account explicitly for intentional contract changes.
- Require evidence that the original defect or structural violation is resolved and
  the representative maintenance scenario demonstrates the expected benefit. Green
  regression tests alone are insufficient.
- Run relevant new tests, including fixer-authored reproductions; assess their assertions
  rather than ignoring them because of authorship. Preserve unrelated baseline failures
  without worsening them, and disclose environmental limits.
- Check that complexity was not merely relocated; migration/recovery changes need scoped
  recovery evidence with disposable data.
- Return PASS, FAIL or PENDING with reviewer mode, commands/outcomes, defect resolution,
  regression evidence, scenario benefit, gaps and required independent verification.
- Failed or pending acceptance must not be promoted as an accepted score improvement.
  Keep work draft, correct the failure within scope, and never revert unrelated changes.

## Cross-cutting themes

Synthesize supported patterns and required scenario/coverage/dependency notes into
`reportThemes` headline/body pairs. Do not invent themes to satisfy a numeric quota.
These are main-thread synthesis; every module's assessment remains evidence-backed.
