# Quality gates for long-term maintainability

The architecture map and module scores are evidence, not permission to ship. A
retained audit may be published only after the configured quality gates have an
explicit `:pass` result. A gate result is a compact receipt; the report must still
contain the command, scope, outcome and limitations that justify it.

## Gate states

- `pass` — the gate's required evidence is present and the observed result meets the
  project's acceptance bar.
- `review` — evidence is incomplete or a risk remains. Keep the audit as a working
  draft; do not publish it as an accepted retained version.
- `fail` — a required check failed, a regression was introduced, or the evidence is
  contradictory. Fix, narrow the scope, or explicitly stop the delivery.

The command-line receipt uses `<gate>:<state>`, for example
`code-quality:pass`. Any `:fail` result is rejected by `version.py`; configured gates
that are missing or marked `review` also block publication.

## Default gate set

Projects created by `init` should enable these gates in `.codemap/config.json`:

```json
{
  "qualityGates": {
    "enforce": true,
    "required": [
      "scope",
      "architecture",
      "code-quality",
      "verification",
      "tooling",
      "security-performance",
      "change-safety"
    ]
  }
}
```

Existing projects without `qualityGates` remain compatible and may opt in by adding
the block above. Once enabled, do not remove a required gate merely to make a publish
pass; change the project policy deliberately and record why.

## Gate contract

### `scope`

Pass only when the audit names the maintenance scenario, reviewed modules, excluded
areas, accepted constraints and the consumers that could be affected. A triage-only
pass cannot claim a full-module or project-wide quality result.

### `architecture`

Pass only when the module/dependency graph is current, every scored module has its own
evidence-backed assessment, and all eight architecture dimensions have a supported
status. `unknown` is honest evidence of a gap; it is not a healthy result. A retained
review must not hide an unresolved high-risk boundary behind an average score.

### `code-quality`

Pass only after checking the changed or affected modules for correctness, intent,
simplicity, meaningful abstractions, explicit error semantics, duplication, dead code,
unbounded complexity and misleading compatibility/fallback paths. Use the fixed smell
taxonomy and cite `file:line` evidence. Style preferences alone are not findings;
project conventions should be enforced by tooling.

### `verification`

Pass only when relevant tests or reproducible checks have run, the baseline outcome is
recorded, the original defect or risk is addressed, required old behavior remains, and
remaining failures are classified as unrelated or environmental. High-risk contract,
state, persistence, permission and recovery changes require independent acceptance when
delegation is authorized; otherwise mark the gate `review`.

### `tooling`

Pass only when the project's applicable formatter, linter, type checker, build and
static-analysis commands are recorded and pass. If a project has no such command, state
that limitation and add the smallest authorized check; do not invent a green result.

### `security-performance`

Pass only after considering untrusted input, secrets, authorization, dependency/supply
chain exposure, resource bounds, hot paths and relevant performance evidence. Use
focused measurement for performance-sensitive changes. If a dimension is not applicable,
record the reason and the evidence scope; do not silently skip it.

### `change-safety`

Pass only when the change is scoped, reviewable and reversible: behavior changes are
separate from unrelated cleanup, the diff has a clear intent, the history records why,
and the rollback or recovery path is known. Large changes must be split or explicitly
accepted as one atomic change with a reason.

## Delivery rule

`version.py publish` is the final promotion gate. It must receive every configured gate
as `gate:pass`, then run semantic validation and `version.py verify`. A successful hash
or a green build alone cannot promote an audit whose architectural, code-quality or
change-safety evidence is missing.
