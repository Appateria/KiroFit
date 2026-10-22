---
document_id: PSR-BRIEFS-2026-09
generated_from: signal-index/signal-index.csv (scoring config v3, 2026-08-27)
signal_count: 491
theme_count: 36
cluster_count: 13
author: pm_rowan (drafted from clusters, human-reviewed)
status: awaiting_sprint_intake_gate
---

# Opportunity briefs — sprint intake, 2026-09

Drafted from the top clusters in the Signal Index. Each brief is the artifact the
Signal-to-Story pipeline hands to spec generation: problem, evidence, outcome, and the
code surface it lands on. Evidence lists cite `source_ref` values that resolve to raw
records in the class folders and to normalized records in `signal-store/signals.jsonl`.

## Reading the ranking

| Rank | Theme | Weight | Classes | Signals | Effort (d) | Cluster |
|---|---|---|---|---|---|---|
| 1 | progress_reports_periodic | 0.971 | 6 | 36 | 4 | CL-03 |
| 2 | unit_system_imperial | 0.952 | 6 | 27 | 2 | CL-11 |
| 3 | exercise_plan_generation | 0.946 | 6 | 29 | 6 | CL-01 |
| 4 | accessibility_a11y | 0.932 | 6 | 25 | 2 | CL-06 |
| 5 | gdpr_dsar | 0.905 | 6 | 12 | 5 | CL-02 |
| 6 | data_export_missing | 0.891 | 5 | 20 | 1 | CL-02 |
| 7 | sso_required | 0.862 | 6 | 21 | — | CL-06 |
| 8 | analytics_missing | 0.833 | 6 | 20 | 1 | CL-03 |
| 9 | billing_missing | 0.828 | 6 | 24 | 12 | CL-05 |
| 10 | guest_sync_loss | 0.762 | 5 | 18 | 6 | CL-04 |
| 11 | history_range_limit | 0.757 | 4 | 15 | 1 | CL-07 |
| 12 | genai_charter | 0.746 | 5 | 20 | 5 | CL-12 |

The top three all carry full six-class corroboration, which is unusual and worth pausing
on: users, telemetry, defects, competitors, strategy and the ambient channels are all
saying the same three things. The ranking between them is decided by the effort-inverse
factor, not by importance — `unit_system_imperial` sits at rank 2 on a 2-day estimate.
Read the ranking as "do these, cheapest-first, within the same sprint" rather than as a
strict sequence of value.

One structural note. **Ranks 1, 11 and 17 share a single dependency**: a range read on the
`EXERCISE#<date>#<id>` sort key. Periodic reports, the history range limit and the history
latency regression are three symptoms of one missing resolver capability. That resolver is
already validated at −86.8% p95 in EXP-2026-034. It is the highest-leverage single change
available this sprint.

---

## OB-01 — Progress reports over a period the user chooses (CL-03, rank 1, weight 0.971)

**User problem.** The product can render exactly one period: the current week. A user who
wants to know what changed this month, or compare this week to last, cannot. 39.8% of
history sessions attempt a range change and **none succeed**, across all 21 measured
weeks. `report_export_attempted` also converts to zero, and its `requested_period`
property splits between `1w` and `1m` — users are asking for precisely two periods.

Four of six power-user panellists maintain a **parallel spreadsheet** purely to hold the
monthly rollup. That is unmet demand with a measured workaround cost.

**Why it is a retention problem, not a reporting nicety.** Users who viewed history in
week 1 retain at 35% by W4 against 21% for users who only logged. Looking back predicts
retention better than logging does.

**Evidence (6 classes, 36 signals).**
- Demand: ZD-11319 (Helios, contractual), ZD-11326, PFR-0441 (588 votes), PFR-0457,
  NPS-4460#1, NPS-4474#0, EXIT-2138, EXIT-2214 ($119 MRR), AS-IOS-79410#1, AS-IOS-79822#0,
  INT-2026-021#1
- Defect: GH-557 (single required `AWSDate`), GH-562 (no server-side aggregation),
  KIROFIT-FE-1214 (11,402 events / 4,038 users), FLK-017
- Behavioral: BEH-report-range-deadend, BEH-retention-history-cohort,
  BEH-funnel-zero-report_export_attempted, BEH-helpsearch-progress_reports_periodic
  (~15,000 unanswered help searches), BEH-adoption-decline, EXP-2026-034#2,
  **EXP-2026-044 (stopped on performance at p95 11.2s, not on demand)**
- Market: CMP-REL-0745 (FitLedger shipped it), MTX-periodic-reports (universal in the
  category), MKT-ANALYST-014#2
- Strategic: O1-KR2, O1-KR3, O6-KR1, **PC-2026-11 (Helios, named deliverable, due
  2026-11-01)**, TD-2026-33, STRAT-ADR-011, STRAT-PRICING#6
- Ambient: SOC-2026-0741#1, SOC-2026-0779#0 (practitioner: "no report to review in a
  session"), JOB-2026-0344#0, OSS-apache-echarts

**Outcome.** Weekly and monthly reports over a user-selected range (O1-KR2), and the
Helios monthly cohort report delivered before 2026-11-01.

**Shape.** ADR-011. Range read via `between()` on the sort key; aggregate in the resolver
and return computed figures. The client must not recompute totals — EXP-2026-044 measured
exactly that failure. Narrative layer is generated over verified numbers (see OB-08);
the numbers themselves are never generated.

**Sequencing note.** Do the range query first and standalone. It closes rank 11 and rank 17
at the same time and de-risks this brief before any report UI exists.

---

## OB-02 — Per-user unit system (CL-11, rank 2, weight 0.952)

**User problem.** `HealthProfile` exposes `heightCm` and `weightKg` and nothing else. There
is no unit preference anywhere in the schema or the UI. Imperial-locale users type imperial
numbers into metric fields and the product **persists them unconverted**. One panellist's
profile has read `154 kg` since March.

This is the cheapest item in the top ten (2 days) and the one with the largest measured
effect: EXP-2026-047 lifted profile completion **22.7%** and cut implausible-weight
warnings **81%** with display-only conversion.

**Evidence (6 classes, 27 signals).**
- Demand: ZD-11290, ZD-11298, ZD-11333 (Aurora, renewal condition), PFR-0432 (612 votes),
  PFR-0448, NPS-4467#0, EXIT-2208, AS-PLAY-51188#0, INT-2026-021#2
- Defect: GH-546, KIROFIT-FE-1207 (6,188 events / 2,417 users, `en-US` and `en-GB`),
  FLK-016
- Behavioral: BEH-unit-entry-anomaly, BEH-helpsearch-unit_system_imperial (~18,300
  unanswered help searches — the single largest group), **EXP-2026-047 (+22.7% profile
  completion, `ship`)**
- Market: MTX-unit-system (universal in the category), CMP-REL-0758, MKT-ANALYST-014#7
  (US ≈ 63% of category revenue), TSW-2026-16
- Strategic: O2-KR5, **PC-2026-12 (Aurora renewal, due 2026-10-15)**, TD-2026-31,
  STRAT-ADR-001, STRAT-PRICING#8 (never a paid feature)
- Ambient: SOC-2026-0755#0, JOB-2026-0357#0, OSS-convert-units-convert-units

**Outcome.** Height and weight captured, stored and displayed in the user's chosen system,
round-trip safe (O2-KR5). Aurora renewal condition cleared.

**Shape.** ADR-005. Canonical storage stays SI so no historical value is rewritten and no
aggregate needs a unit-aware path. A `unitSystem` field on the profile drives conversion at
entry and display only. Do **not** infer from locale — CLDR defaults are wrong for enough
of the population (TSW-2026-16) that guessing produces an uncorrectable error.

**Data-integrity caveat.** Existing implausible values are already persisted. Shipping the
preference does not fix them, and a silent bulk conversion would corrupt correctly-entered
data. Prompt affected users to confirm once; do not guess on their behalf.

---

## OB-03 — Generated exercise plans (CL-01, rank 3, weight 0.946)

**User problem.** The product proposes nothing. Every type in the health domain is
retrospective — `ExerciseEntry` has a date in the past and a duration that already
happened — so there is no way to express a planned session at all. The consequence is
measurable: **71.2%** of logged sessions are verbatim repeats of the previous one, with up
to 9 consecutive identical sessions and `plan_source: null` throughout. Users whose
sessions repeat retain at 11% by W4 against 21% for the general logging cohort.

Panellists are doing the work themselves: plans live in a notes app, a coach's PDF, or
memory. "I write the week in Notes on Sunday, then I type it into the app after each
session. I'm the integration."

**Evidence (6 classes, 29 signals).**
- Demand: ZD-11305, ZD-11312, PFR-0435 (**724 votes — highest in the window**), PFR-0453,
  NPS-4460#0, CSAT-9088#1, EXIT-2201, AS-IOS-79410#0, INT-2026-021#0
- Defect: GH-551 (no plan entity; needs a `PLAN#` sort-key prefix)
- Behavioral: BEH-session-repetition (71.2% verbatim repeat),
  BEH-helpsearch-exercise_plan_generation (~15,700 unanswered help searches),
  **EXP-2026-041 (static starter card: +11.4% W2 return, then 34% abandoned by week 3)**
- Market: MTX-plan-generation (5 of 6 competitors), CMP-REL-0731 (PulseCoach headline paid
  feature), CMP-REL-0766, MKT-ANALYST-014#1 (r ≈ 0.68 with W4)
- Strategic: O1-KR1, O1-KR3, O1-KR4, O6-KR1, TD-2026-32, STRAT-ADR-010b, STRAT-PRICING#4
- Ambient: AMB-REDDIT-VELOCITY, SOC-2026-0741#0, SOC-2026-0768#1, SOC-2026-0779#1,
  JOB-2026-0331#0 (PulseCoach hiring 3 for plan generation)

**Outcome.** Users can generate a multi-week plan from profile and history (O1-KR1), and
plan adherence becomes measurable (O1-KR4).

**Shape.** ADR-010b. Generate from profile plus logged history through a managed model:
~6 engineer-days against ~30 for a hand-authored template library that then needs curating
indefinitely. **EXP-2026-041 is the argument for generation rather than against plans** —
the static card proved demand and then proved that a plan which cannot adapt gets abandoned.
Adaptation is the value.

**Prerequisite.** GH-551 first: the data model needs planned-vs-completed before any
generated plan has somewhere to live. This is schema work, so batch it with OB-02 and OB-05
under ADR-001's weekly review.

---

## OB-04 — Enterprise procurement gates (CL-06, ranks 4 and 7)

**User problem.** Two things block $35.8k of committed corporate ARR, and neither is a
consumer feature: no SSO, and an inaccessible primary screen. The weekly progress ring is a
decorative div stack — no `role="progressbar"`, no `aria-valuenow` — so VoiceOver announces
the app's most important number as an empty group. Dark-mode contrast measures 2.6:1.

**Evidence (6 classes, 25 + 21 signals).**
- Demand: ZD-10979, ZD-10668, ZD-11122, PFR-0385, PFR-0410, NPS-4538, NPS-4622, EXIT-2175,
  EXIT-2198 ($1,490 MRR), AS-IOS-78033, INT-2026-014
- Defect: GH-455, GH-449, FLK-013 (98% failure rate — the test already knows),
  PEN-2026-03-F07, SEC-POSTURE-2026-08b
- Behavioral: EXP-2026-027 (+16.8% task success, no aesthetic cost)
- Market: MTX-a11y, MTX-sso, CMP-REL-0454, CMP-REL-0485, MKT-REG-2026-08#2, TSW-007, TSW-015
- Strategic: O4-KR1, O4-KR3, O4-KR4, TD-010, TD-011, PC-001, PC-009
- Ambient: SOC-0448, SOC-0505, SOC-0524, AMB-DISCORD-PRACTITIONERS, AMB-OSS-AXE

**Outcome.** Zero serious axe violations and a published ACR by 2026-12-01; SSO available
before the Helios security re-review closes **2026-10-15** (O4-KR1, O4-KR3, O4-KR4).

**Shape.** Accessibility is 6 engineer-days total (2 for tokens, 4 for semantics) and already
has a failing Cypress spec to gate on. SSO is Cognito federation configuration plus a
tenant-aware sign-in route — no new auth system.

---

## OB-05 — Users can own and correct their own data (CL-02, ranks 5 and 6)

**User problem.** There is no rectification, erasure or export path. A user cannot correct
a logged session, delete their account, or take their data out. Erasure is currently
actioned by ad-hoc DynamoDB deletes. Meanwhile the Premium page advertises "Data export
(CSV, JSON)", which corporate buyers read as available.

**Evidence.** ZD-10510, PFR-0363, GH-491, PEN-2026-03-F08, MKT-REG-2026-08#1,
MTX-export, O2-KR1, O2-KR3, O4-KR2, TD-008, STRAT-PRICING#2, STRAT-PRICING#3,
plus the help-centre searches for "edit an activity" and "delete my account".

**Outcome.** Self-serve export and account deletion (O2-KR3); rectification on the free
tier (O2-KR1, STRAT-PRICING#2).

**Shape.** Schema work — batch with OB-02 and OB-03 under ADR-001. Rectification cannot sit
behind a paywall. Note the split in STRAT-PRICING#3: a user's own-data export is an access
right and therefore free; the employer's cohort report is a corporate-plan feature.

---

## OB-06 — Stop losing data at sign-up (CL-04, rank 10, weight 0.762)

**User problem.** `syncGuestDataToAccount` awaits one mutation per entry inside a `for`
loop, swallows each failure with `console.warn`, then calls `clear()` unconditionally.
About 39% of successfully signed-up guests lose some or all of their pre-signup entries,
and the error rate stepped 3.4x after r-1.0.14.

**Evidence.** ZD-10588, ZD-11004, PFR-0327, CSAT-9012, EXIT-2117, EXIT-2212, AS-AND-31219,
GH-413 (P0), GH-418, KIROFIT-FE-1131, KIROFIT-FE-1136, INC-2026-018, INC-2026-029,
FLK-009 (41% flake), BEH-guest-sync-leak, BEH-logmutation-error-step,
**EXP-2026-007 (+54.5% sign-up conversion, marked `ship_blocked` on this exact gap)**,
O2-KR2, TD-006, TD-013, STRAT-ADR-007, SOC-0455, AMB-DISCORD-GUEST.

**Outcome.** Sync loss below 0.5% of entries (O2-KR2), unblocking a 54.5% conversion lift.

**Shape.** ADR-007: a local draft/outbox with idempotency keys — not an offline-first
rewrite. Batch the sync, retry with backoff, and only clear local state for entries the
server acknowledged.

**Note on `offline_mode` (rank 13).** It scores highly on corroboration but the power-user
panel ranked it last of six asks. Deliver the outbox as part of this brief and treat
general offline-first as the declared non-goal it is (NG4).

---

## OB-07 — A way to pay (CL-05, rank 9, weight 0.828)

**User problem.** 9,877 distinct users tapped Upgrade and received
"Premium subscriptions will be available soon." There is no billing provider, and nothing
writes the `tier` claim `useAccessTier()` reads, so premium is unreachable even for a
manually flagged account. Free-to-paid conversion is structurally 0%.

**Evidence.** ZD-10641, PFR-0338, NPS-4440, NPS-4526, EXIT-2146, AS-AND-31488, GH-442,
GH-505, KIROFIT-FE-1358, FLK-012, BEH-upgrade-intent-deadend,
BEH-funnel-zero-checkout_started, BEH-funnel-zero-subscription_active, EXP-2026-019,
MTX-billing, MKT-ANALYST-014#3, MKT-REG-2026-08#4, O3-KR1, O3-KR3, TD-009,
**PC-007 (Stride Payments slot expires 2026-09-30; re-queue is 6 weeks)**, SOC-0470.

**Outcome.** Working checkout with entitlement write-back; conversion at or above 2.0%.

**Shape.** Web checkout (no native launch required), webhook → entitlement store → Cognito
pre-token-generation trigger that sets `tier`. Sequence behind at least one real premium
capability so the first purchase buys something — on current ranking that is the monthly
report (STRAT-PRICING#6).

---

## OB-08 — Apply GenAI where it pays for itself (CL-12, rank 12, weight 0.746)

**Not a feature brief.** This is a standing charter (ADR-010, objective O6) recorded so that
it carries alignment weight in scoring rather than living as folklore. It is included here
because it constrains *how* OB-01 and OB-03 get built, and because its preconditions are
unbuilt work that belongs in the same sprint estimate.

**The argument.** Two of the three top-ranked capabilities are language-and-reasoning tasks
over data the product already holds. Published competitor unit economics put plan generation
and report narration at **$0.01–0.05 per active user per month** on managed models —
NutriPilot published $0.018. At this scale a hand-built template library or rule engine is
the *more* expensive path and it ages badly. The charter is deliberately conditional: AI
where it beats the alternative on cost per unit of customer value, not AI by default.

**Evidence (5 classes, 20 signals).**
- Demand: ZD-11340, CSAT-9088#0
- Defect: GH-568 (no invocation path, no token budget, no cost metric, no fallback)
- Market: MTX-ai-assist, CMP-REL-0772 (NutriPilot published $0.018/MAU),
  MKT-ANALYST-014#6, TSW-2026-17 (managed-model pricing falling again)
- Strategic: O6-KR1, O6-KR2 (<$0.04/MAU, measured and alarmed), O6-KR3 (cost/benefit note
  plus deterministic fallback in the definition of done), STRAT-ADR-010, STRAT-PRICING#7,
  TD-2026-34
- Ambient: AMB-DISCORD-COST, AMB-HIRING-ROLLUP, SOC-2026-0768#0, JOB-2026-0331#1,
  JOB-2026-0344#1, OSS-bedrock-samples-prompt-eval-harness, OSS-langfuse-langfuse

**Guardrails that are part of the first capability's cost, not a follow-up.** Numbers are
computed in code and never generated; the model may narrate figures it is given. Every AI
capability carries a documented cost/benefit, a measured per-user ceiling with an alarm, a
deterministic fallback so an outage or price change degrades rather than removes the
feature, and a prompt-evaluation suite in CI. TD-2026-34 estimates 5 days for the platform
work. ADR-006 is the binding constraint on shape: a managed model invoked from an existing
resolver or Lambda preserves one-command deployability; a containerised agent service does
not.

**Explicitly out of scope under this charter.** Anything a user could mistake for clinical
advice, and any capability whose failure mode is silent incorrectness in stored data.

---

## Sequencing recommendation for the intake gate

| Slot | Work | Basis |
|---|---|---|
| 1 | Range-query resolver on the `EXERCISE#` sort key (1d) | shared dependency of ranks 1, 11, 17; already validated at −86.8% p95 (EXP-2026-034) |
| 2 | Unit system: preference field + entry/display conversion (2d) | rank 2, cheapest top-10 item, Aurora renewal 2026-10-15, largest measured effect (EXP-2026-047) |
| 3 | Accessibility tokens + semantics (6d) | rank 4, hard external date 2026-12-01, failing spec already exists to gate on |
| 4 | Batched schema change: plan/planned-session types + rectification + account deletion | ranks 3, 5 in one review (ADR-001); unblocks slot 6 |
| 5 | Weekly report over the range query (4d) | rank 1, contractual date 2026-11-01 (PC-2026-11) |
| 6 | AI platform preconditions, then plan generation (5d + 6d) | rank 3 and rank 12; TD-2026-34 is a precondition, not a follow-up |
| 7 | Guest-sync outbox | rank 10, unblocks a measured 54.5% lift |
| 8 | SSO configuration | rank 7, external date 2026-10-15 |
| exploration (15%) | Observability alarms on the new resolvers; prompt-eval harness spike | reserved allocation per scoring config; O6-KR2 depends on the cost metric existing |

Slots 1 and 2 are three days combined and close two top-three themes plus two more further
down the index. Start there regardless of what else makes the sprint.

Everything in CL-10 stays deferred with a rejection record and an expiry date. Nothing is
silently dropped.
