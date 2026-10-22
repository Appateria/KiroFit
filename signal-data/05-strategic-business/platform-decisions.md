---
document_id: STRAT-ADR-INDEX-2026
signal_class: strategic
owner: eng_lead_dana
last_reviewed: 2026-08-25
themes: [dependency_currency, offline_mode, native_mobile_apps, genai_charter, exercise_plan_generation, progress_reports_periodic, unit_system_imperial, billing_missing, observability_gap, deployability]
---

# Platform & dependency decisions (ADR index)

Directional engineering commitments that constrain how signals may be resolved. These are
*inputs* to prioritisation, not backlog items.

## ADR-001 — One AppSync API, one combined schema (accepted, 2026-01-20)

Replaces the former Merged API plus per-app source APIs. Consequence for the PSR: every
schema-shaped signal (the unit-preference field, the plan and planned-session types, the
report/aggregate types, range queries, erasure) lands in the **same file and the same
review**. Batching them is cheaper than sequencing them, but it also means one contentious
change can block five features.

Standing decision: schema changes are reviewed in a weekly batch, not per-PR.

## ADR-002 — Runtime `config.json` over build-time environment (accepted, 2026-01-20)

Enables the single-`cdk deploy` property. Consequence: the AppSync API key is served
publicly next to the bundle, which is the mechanism behind pen-test finding F-01/F-02.
Any remediation must preserve single-deploy (see ADR-006), so the fix is to narrow what
the API key can read, not to remove `config.json`.

## ADR-003 — Vendored UI libraries instead of a private registry (accepted, 2026-01-20)

`ui/src/lib/auth` and `ui/src/lib/preferences` are source, not packages. Consequence:
auth changes (SSO, tier claims) are local edits with no release cycle — cheap. Also means
no upstream security patches arrive automatically.

## ADR-004 — Web-first distribution; Capacitor retained but unused (accepted, 2026-02-10)

Native shells are configured (`capacitor.config.ts`, Capacitor 8 deps) but no store builds
exist. Consequence: HealthKit/Health Connect and reliable push are structurally
unavailable. Web push covers reminders at ~34% opt-in on iOS web versus ~71% on Android
web (EXP-2026-031). Revisit gate: two corporate accounts requesting wearable sync, or
reminder experiment retention lift holding past 60 days.

## ADR-005 — Store metric, present in the user's unit system (proposed, 2026-07-28)

Canonical storage stays SI (`heightCm`, `weightKg`) so no historical value is rewritten and
no aggregate needs a unit-aware code path. A `unitSystem` preference on the profile drives
conversion at the edges — on entry and on display — and never in the store.

Rejected alternative: infer units from locale. CLDR measurement-system defaults are wrong
for enough of the population (TSW-2026-16) that guessing produces a worse failure than
asking, and the guess cannot be corrected by the user.

Consequence: conversion is a display concern, which keeps it a ~2-day change rather than a
data migration. Any feature that renders a body metric must go through the same helper.

## ADR-006 — Preserve one-command deployability (accepted, 2026-01-15, reaffirmed 2026-08-25)

Workshop commitment PC-010. Consequence: no feature may introduce a manual deploy step, a
private registry, a Docker image push, or an out-of-band schema merge. This is why the
Bedrock AgentCore service stayed descoped, and it is the binding constraint on how AI
capabilities may be delivered (see ADR-010): a managed model invoked from an existing
Lambda or resolver satisfies it; a containerised agent service does not.

## ADR-007 — Local draft/outbox before offline-first (proposed, 2026-08-14)

Rejects a general offline-first rewrite. Scope: persist the compose-form draft and queue
the single pending mutation, with idempotency keys. This unblocks EXP-2026-007 (54.5%
sign-up lift) and removes the guest-sync loss mechanism without adopting a sync engine.

## ADR-008 — Toolchain currency policy (proposed, 2026-07-21)

Adopt a rule: no dependency more than one major behind, no EOL runtime in production.
Current violations: eslint 8 (EOL), vite 5 (two majors behind), cypress 13, Node 20 (EOL
2026-04-30). Consequence if adopted: ~8 engineer-days of upgrade work competes with
feature work this quarter, and the SOC 2 observation window (PC-009) makes deferral
progressively more expensive.

## ADR-009 — Observability is a release gate, not a project (proposed, 2026-07-29)

Every incident this quarter was discovered by customers. Proposal: alarms on AppSync
5xx/throttling and Lambda errors become part of the definition of done for any new
resolver, starting with the range-query resolver in EXP-2026-034.

## ADR-010 — Generative and agentic AI where it is the cost-effective path (accepted, 2026-08-25)

**Standing charter for this application**, recorded here and as objective O6 in
`okrs-fy26.yaml` so that it carries strategic-alignment weight in the Signal Scoring
Engine rather than living as folklore.

Where a capability is fundamentally a language or reasoning task over data the product
already holds, the default implementation is a **managed foundation model**, provided the
cost per unit of customer value beats the alternative. The charter is deliberately
conditional — this is not "AI by default", it is "AI where it wins".

Decision rule, applied per capability:

| Test | Requirement |
|---|---|
| Cost | Documented cost/benefit versus the deterministic alternative, including inference cost at projected volume |
| Ceiling | A measured per-user cost ceiling with an alarm before it is exceeded |
| Fallback | A deterministic degradation path, so a model outage or price change degrades the feature instead of removing it |
| Truthfulness | Numbers are computed in code, never generated. The model may narrate figures; it may not produce them |
| Evaluation | A prompt-evaluation suite in CI, so a prompt or model change is a reviewable diff |

First two applications, both ranked top-3 in the current index:

- **Plan generation** (`exercise_plan_generation`). Generating from profile plus logged
  history is ~6 engineer-days against ~30 for a hand-authored template library that then
  needs curating indefinitely. EXP-2026-041 showed a static card lifts W2 return 11.4%
  but 34% abandon it by week 3 because it cannot adapt — the adaptation is the value, and
  adaptation is what a template library cannot do cheaply.
- **Report narration** (`progress_reports_periodic`). Aggregates are computed in the
  resolver; the model writes two sentences over verified figures (ADR-011).

Explicitly *not* in scope under this charter: generating anything a user could mistake for
clinical advice, and any capability whose failure mode is silent incorrectness in stored
data.

Preconditions currently unmet (issue #568, TD-2026-34): no invocation path, no token
budget, no per-user rate limit, no cost metric, no fallback. These are part of the first
capability's cost, not a follow-up.

## ADR-011 — Reports aggregate server-side; only the narrative is generated (proposed, 2026-08-25)

Periodic reports require a range read on the `EXERCISE#<date>#<id>` sort key (a `between()`
on the sort key) plus a rollup in the resolver. The client must not recompute totals:
EXP-2026-044 measured p95 render at 11.2s doing exactly that across a 7-query fan-out, and
it was stopped on performance rather than on demand.

Split of responsibility:

- **Computed, deterministic:** period totals, session counts, per-week buckets,
  period-over-period deltas. These are the numbers a user or a coach acts on.
- **Generated:** a short narrative over those numbers, plus one suggested change.

Consequence: the range query (issue #557) is a shared dependency of periodic reports,
the exercise-history latency fix and `history_range_limit`. It is the single highest-leverage
resolver change available and is already validated at −86.8% p95 in EXP-2026-034.
