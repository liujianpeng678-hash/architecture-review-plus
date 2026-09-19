# Maintenance scenario and feedback protocol

## Purpose and theory in practice

Judge the ability to make required changes, diagnose failures and recover, rather than
optimizing a score. A skill cannot guarantee lifetime maintainability.

- 矛盾论: identify the current structural tension and the aspect that most restricts
  the project's actual goal. Treat the principal contradiction as a revisable hypothesis;
  do not force unrelated risks into one cause or ignore hard constraints.
- 实践论: connect each material judgment to a traceable observation and a practical
  test that could disprove it. Correct the diagnosis when the test disagrees.
- 工程控制论: capture a baseline, observable outcome, adjustable intervention and
  feedback point. Avoid reacting to score noise or changing several unrelated factors
  before feedback arrives. Record confounders and measurement limits.

These are operational interpretations, not quotations or mandatory theory exposition.

## Scope and authority

Ordinary local changes use focused checks. Contract, ownership, persistence, permissions
and release/recovery changes warrant targeted architecture review. Explicit milestones
warrant a system review of representative critical scenarios. Do not repeatedly audit
the whole project after small changes. Review alone does not authorize product fixes.

Select usually two or three scenarios for a system review, or one for a narrow review,
from actual upcoming requirements, past faults and agreed evolution plans. Record project
stage, accepted constraints and the reason each scenario matters. Avoid speculative
extension points. Missing project-state documents are not proof of a new project.

Examples: add a monster without duplicating its state machine; change attack timing
without duplicate damage; migrate an old save and recover from an interrupted migration.

## Evidence and coverage

For each reviewed module trace the relevant public interface, callers, state writers,
failure paths and existing checks. Search markers are leads, not findings. Large files,
adapters, dynamic interfaces and compatibility paths require contextual justification.
Do not flag a deliberate boundary adapter solely because it delegates.

Declare `triage`, `scenario-reviewed`, or `full-module-reviewed` coverage, the files and
symbols actually examined, excluded areas, reviewer mode (`independent` or
`single-reviewer`), confidence with reasons, and unanswered questions. Triage has no
module score. A partial review must not become a whole-module clean bill. A retained
full audit requires sufficient module coverage; otherwise leave a draft, not fabricated
scores to satisfy publishing requirements.

Each actionable finding's text must state:

1. Trigger scenario and concrete observation, with file/symbol/line evidence.
2. Root-cause hypothesis, alternatives where plausible, and confidence.
3. Observable maintenance or runtime impact and affected consumers.
4. Smallest justified correction, costs and relevant tradeoffs.
5. Reproduction or verification method, expected result and disconfirming result.

Scores are ordinal estimates under the existing rubric. Explain grade selection and
uncertainty; do not invent exact point deductions. Compare scores only when scope,
standard and review depth are comparable. Module splits and reviewer changes must be
disclosed; average score improvement alone is not proof of improvement.

## Compatible storage and invalidation

No engine schema migration is introduced by this protocol. Keep findings in existing
`sev`, `loc`, `text` fields; put the five evidence elements in `text`. Additional JSON
fields would be discarded by the existing normalizer and must not carry essential data.

Store review records in existing `reportThemes` headline/body pairs. Use stable headings
such as `Maintenance scenario: <id>`, `Review coverage: <module-id>` and
`Conclusion dependencies: <id>`. Bodies contain the coverage, score rationale, baseline,
outcome and dependencies. They are included in retained state and rendered reports.
Do not create negative findings merely to carry review metadata for clean modules.

Record dependency paths and symbols, contract/schema assumptions, test commands and
results, source revision or hashes, effective standard and invalidation conditions.
During update manually compare these dependencies as well as scan/version status:

- Public-interface or state-owner changes invalidate related consumer conclusions.
- Test/configuration changes invalidate affected safeguards and scenario evidence,
  although tests remain excluded from production LoC.
- Standard or scenario changes invalidate affected judgments even without source edits.
- Negative evidence (for example, no alternate writer found) must state search scope.

Recheck invalidated conclusions or mark dimensions unknown and explain module limits.
Do not claim the engine automatically tracks this prose dependency record. If an affected
module cannot be adequately reviewed, leave the update draft; identical content hashes
do not prove that a context-dependent conclusion remains true.

## Fix acceptance and feedback

Before changing code, record the scenario, expected benefit and exact baseline checks.
Separate baseline-green checks, expected target failures, unrelated existing failures
and environment blockers. A target failing reproduction is useful evidence, not a reason
to prohibit its repair. If evidence cannot bound regression risk, report the gap.

After the fix require all applicable evidence:

- The original reproduction or structural violation is resolved.
- Baseline-green required behavior remains; unrelated failures have not worsened.
- The representative maintenance scenario works and its expected benefit is demonstrated.
- Added abstractions/dependencies do not simply relocate the problem.
- Migration/recovery changes have scoped recovery evidence using disposable data.

Intentional behavior changes may update tests with explicit rationale and review; never
weaken checks just for green output. Local low-risk fixes may use disclosed self-review.
High-risk fixes require independent verification, subject to available authorization;
without it, do useful implementation/verification but label acceptance pending.

Track a small set of relevant observations across reviews: modules changed and why,
fault reproduction/localization effort, recurring regressions, migration/recovery
outcomes, and aging material risks. Do not turn these into universal numeric quotas.
Check again at the next comparable change, repeated fault or agreed milestone. Continue
when evidence supports the intervention, revise on contradiction, and roll back only
within authorization when new regressions outweigh benefit. Keep useful compatibility
until its documented retirement condition is met.

## Meaning of validation

Separate four claims: record format/rule validity, traceable evidence, reviewed judgment,
and demonstrated outcome. `semanticValid` denotes AuditContract consistency; it cannot
prove the architectural diagnosis, evidence truth or long-term success. Historical
hashes preserve the record, not the correctness of the author. Report limitations.

## Behavioral review cases for future skill edits

Use these as concrete review cases, not heading/keyword tests. When authorized, evaluate
with minimal fixtures; otherwise inspect the workflow and disclose no independent run.

| Request/evidence | Required behavior |
|---|---|
| Fix a local label typo | Focused verification; no automatic full audit |
| Large file, one cohesive generated dispatch | Investigate context; no size-only defect |
| Adapter preserves a public API during migration | Assess boundary and retirement need; no delegation-only smell |
| No marker hits, ownership paths unread | Triage/unknown, not a high clean score |
| Failing duplicate-reward reproduction | Repair with before/after evidence, preserve other green behavior |
| Green tests but duplicate-reward bug still present | Reject fix acceptance |
| Unchanged consumer file, dependency contract changed | Recheck consumer conclusion |
| Tests removed, production hash unchanged | Recheck safeguards; no inherited healthy claim |
| Delegation forbidden, high-risk persistence fix | No agents; independent acceptance remains pending |
| Score improves after module split | Disclose incomparable scope; verify actual scenario benefit |

Changing this protocol must also update conflicting entrypoint and standards instructions.
