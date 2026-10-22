# Product Signal Repository (PSR)

> **Kiro DLC — Left-Side SDLC Framework**
> The intake, synthesis, and routing layer that continuously feeds the product backlog
> and ultimately enables autonomous product development.

> **Status:** This document is the specification for the KDLC **Sense loop** and is
> incorporated by reference into [RFC-0001](rfc/0001-kdlc-core-framework.md).
> Five amendments are required and are specified in
> [RFC-0001 §5.1](rfc/0001-kdlc-core-framework.md#51-sense--signals-to-intent):
> signal provenance tiers, outcome feedback into scoring, rejection with expiry,
> a mandatory exploration allocation, and effort-estimate calibration.
> The maturity rubric for this layer is dimension **D1** in
> [RFC-0003 §3](rfc/0003-maturity-and-readiness.md#d1--signal--intent).
> Note that D1 gates autonomous *product direction* (L5), not autonomous *engineering*
> (L3–L4) — see [RFC-0003 §8](rfc/0003-maturity-and-readiness.md#8-investment-sequencing)
> for why this layer should generally not be built first.

---

## Overview

The **Product Signal Repository (PSR)** is the canonical, continuously-updated store
of all raw and processed signals that inform what should be built, in what order, and
why. It is not a backlog — it is the *input layer* that feeds the backlog.

Three sub-layers:

| Layer | What it holds |
|---|---|
| **Signal Intake** | Raw, unprocessed signals from all sources |
| **Signal Store** | Normalized, deduplicated, enriched signals |
| **Signal Index** | Ranked/weighted view used for backlog decisions |

---

## Signal Taxonomy: The 6 Signal Classes

### 1. Customer Demand Signals
Direct expressions of unmet need from paying or prospective customers.

- Feature Requests (PFRs submitted via support, sales, in-product)
- Support ticket themes / escalations
- NPS/CSAT verbatims
- Customer interviews and discovery calls (structured notes)
- Churn exit surveys

### 2. Defect & Degradation Signals
System-observed evidence that current behavior is wrong or deteriorating.

- Bug reports (internal QA + external user-reported)
- Error rate spikes / anomaly detection alerts
- Performance regressions (p99 latency, memory, throughput)
- Security vulnerability disclosures (CVEs, pen test findings)
- Flaky test reports

### 3. Market & Competitive Signals
External environment changes that shift what "good" looks like.

- Competitor feature releases (product changelogs, review sites, teardowns)
- Analyst reports / category research
- Industry standards changes (regulatory, protocol, API deprecation)
- Technology shifts (new model releases, framework EOL, infra pricing)

### 4. Usage & Behavioral Signals
What users actually do, not what they say.

- Feature adoption rates / DAU per feature
- Funnel drop-off points
- Search terms / zero-result queries inside the product
- A/B test results
- Cohort retention curves per feature area

### 5. Strategic & Business Signals
Internal directional inputs that represent company intent.

- OKRs and strategic bets (quarterly/annual)
- Partnership commitments with delivery obligations
- Pricing/packaging constraints
- Platform/dependency decisions (e.g., "we are standardizing on X")
- Technical debt risk assessments

### 6. Ambient / Ecosystem Signals
Weak-signal but high-value environmental intelligence.

- Social listening (Reddit, Hacker News, X/Twitter, forums)
- Open source project momentum (star velocity, issue trends on adjacent repos)
- Job postings from competitors (reveals roadmap intent)
- Developer community discussions (Discord, Slack communities)

---

## Signal Normalization Schema

Every signal, regardless of source, normalizes to a common record in the Signal Store:

```json
{
  "signal_id": "uuid",
  "class": "customer_demand | defect | market | behavioral | strategic | ambient",
  "source": "zendesk | github | mixpanel | slack | internal | ...",
  "raw_content": "...",
  "normalized_summary": "one sentence",
  "entities": ["feature_area", "persona", "severity_tag"],
  "created_at": "ISO8601",
  "weight": 0.0,
  "linked_signals": ["uuid", "..."],
  "status": "raw | processed | mapped | shipped | rejected"
}
```

The `weight` field is computed by the Signal Scoring Engine (below), not entered
manually.

---

## Signal Scoring Engine (SSE)

The SSE continuously runs over the Signal Store and produces a ranked Signal Index.

| Factor | Weight | Notes |
|---|---|---|
| **Frequency** | High | How many distinct sources/customers reference this signal |
| **Recency** | Medium | Signals decay; recent signals score higher |
| **Customer Tier** | High | Enterprise / strategic accounts weighted more than long-tail |
| **Severity** | High | Data loss / security / P0 bugs float to top |
| **Strategic Alignment** | High | Proximity to current OKRs |
| **Effort Inverse** | Medium | Low-effort high-signal items get a lift (quick wins) |
| **Corroboration** | High | Signal mentioned across ≥2 classes gets a multiplier |

The **corroboration multiplier** is the most important factor. A feature request that
also shows up in behavioral data (low adoption of a workaround) *and* a competitive
signal (competitor just shipped it) is far more actionable than any single source alone.

---

## Signal-to-Story Pipeline

The path from raw signal to generated code:

```
PSR Signal Index
      │
      ▼
  [Clustering]              Group signals by theme/feature area
      │
      ▼
  [Opportunity Framing]     Draft "opportunity brief" per cluster
  (PM or Agent)             What user problem? What outcome? Evidence?
      │
      ▼
  [Backlog Item Creation]   Generate User Stories + Acceptance Criteria
  (Agent-assisted)          Linked to source signals (traceability)
      │
      ▼
  [Sprint Intake Gate]      Weighted stack rank meets sprint capacity
  (PM decision)             Human override always allowed
      │
      ▼
  [Spec Generation]         Kiro Spec from prioritized backlog items
  (Kiro Agent)              → Requirements → Design → Tasks
      │
      ▼
  [Code Generation]         Kiro implements per spec + tasks
  (Kiro Agent)
```

**Traceability is bidirectional.** Every line of generated code is linkable back to
a signal. Every signal is trackable forward to a shipped feature or a rejected
decision with a reason.

---

## Continuous Evaluation Loop (Sprint Model)

In a timebox sprint model, the PSR feeds three recurring rituals:

### Pre-Sprint — Backlog Refinement
The SSE re-scores the entire backlog before each sprint. Items that were deprioritized
but have since accumulated new corroborating signals are surfaced. The agent or PM
reviews the delta: *"what changed since last sprint?"*

### Mid-Sprint — In-Progress Steering
Active sprint items are monitored against live signals. If a defect signal spikes in
an area under active development, the agent flags it. If a competitive signal changes
the spec assumptions, it surfaces for PM review. This prevents shipping work that is
already obsolete.

### Post-Sprint — Signal Closure
Shipped items mark their linked signals as `shipped`. Signals with no backlog item
after N sprints are escalated or formally rejected with a reason. This prevents the
PSR from becoming a graveyard.

---

## Path to Autonomous Product Development

The autonomy gradient moves left to right across each layer:

| Stage | Human role | Agent role |
|---|---|---|
| **Signal Collection** | Defines sources, reviews ambient | Continuously ingests and normalizes |
| **Signal Scoring** | Tunes weights, reviews outliers | Runs SSE continuously |
| **Opportunity Framing** | Reviews and approves briefs | Drafts opportunity briefs from clusters |
| **Backlog Prioritization** | Final stack rank approval | Proposes ranked list with rationale |
| **Spec Generation** | Reviews and approves spec | Writes requirements, design, tasks |
| **Code Generation** | Reviews and merges | Implements per spec |
| **Verification** | Sets acceptance criteria | Runs tests, evals, confirms DoD |

Full autonomy is achieved when the human role at each stage shrinks to *exception
handling* rather than routine operation. The PSR is the foundation — without a
structured, continuously evaluated signal layer, autonomous code generation produces
fast answers to wrong questions.

---

## Design Principles

1. **Source-agnostic normalization** — the same schema works for human PM dashboards
   and agent queries alike.
2. **Corroboration over volume** — one signal from five sources beats five signals
   from one source.
3. **Explicit rejection** — every signal that doesn't become a backlog item gets a
   rejection record with a reason. No silent dropping.
4. **Decay by default** — signals lose weight over time unless reinforced. A
   two-year-old feature request with no repeat mentions should not block new
   priorities.
5. **Traceability always** — every backlog item, spec, and commit traces back to one
   or more signals. This makes retrospectives and rollback decisions tractable.
