---
document_id: MKT-ANALYST-2026-H2-014
signal_class: market
source: Meridian Category Research (fictional analyst firm, synthetic dataset)
published: 2026-08-12
provenance_tier: tier2_secondary_research
verification_status: synthetic_placeholder
subject: Consumer fitness tracking & corporate wellbeing — H2 2026 category note
themes: [exercise_plan_generation, progress_reports_periodic, unit_system_imperial, genai_charter, wearable_integration, pricing_pressure, sso_required, guest_onboarding]
---

# Category note — fitness tracking, H2 2026

## Thesis

The category's differentiation has moved **away from recording and toward prescribing**.
Every credible entrant now generates a plan and returns a periodic readout. Products that
only store what the user did are losing the retention comparison, because the habit is
formed by being told something, not by typing something.

Three consequences for a late entrant:

1. **Prescription is the retention variable.** In our panel, whether a product proposes the
   next session correlates with W4 retention at r ≈ 0.68 — a stronger relationship than any
   logging-ergonomics metric we track. Five of the six vendors we follow generate a plan;
   two make it the headline paid feature.
2. **Generation is now cheaper than authoring.** Vendors shipping plans and narrative
   summaries are doing so on managed foundation models at **$0.01–0.05 per active user per
   month** — comfortably inside consumer subscription margin. NutriPilot published $0.018.
   Hand-built template libraries and rule engines are now the *more* expensive path at this
   scale, and they age badly: a template library needs curating forever.
3. **Corporate wellbeing is where the retained revenue is.** Consumer churn in the category
   remains brutal (median 90-day retention in the mid-teens); employer-sponsored cohorts
   retain 2–3x better. Entry requirements are non-product: SSO, de-identified cohort
   reporting, accessibility conformance, and a security attestation.

A fourth, smaller observation with outsized economics: **the US is roughly 63% of category
revenue and every vendor we track offers imperial units.** Metric-only entry is not a
localisation nicety, it is a conversion blocker in the largest revenue pool.

## Where Kiro Fit sits (assessment against the public build)

**Genuine differentiators**

- *Browse-before-signup guest mode.* Rare in the category; competitors force account
  creation. Category-leading top-of-funnel — currently undermined by a sign-up sync path
  that loses data.
- *Interface and theming quality.* Consistently the first thing users praise, including in
  otherwise negative reviews. This is a real asset and a poor moat.
- *Single-command deployability.* Unusual, and strategically interesting for data-residency
  and self-hosted enterprise deals that incumbents cannot serve.

**Structural exposure**

- The product proposes nothing. There is no plan concept anywhere in the data model, so it
  cannot express a future session at all. In a category that now competes on prescription,
  this is not a missing feature but a missing category entry.
- No period other than the current week can be rendered. Users cannot see a month, cannot
  compare periods, and cannot show anything to a coach or a physio.
- Body metrics are metric-only, and in imperial locales they are being stored incorrectly
  rather than rejected.
- Premium is advertised but unpurchasable, so the product currently has no revenue
  instrument at all.

## Category retention benchmarks (blended, self-reported vendor data + panel)

| Metric | Category median | Category top quartile | Kiro Fit (observed) |
|---|---|---|---|
| D1 retention | 41% | 58% | 34% |
| W4 retention | 19% | 31% | 11% |
| 90-day retention | 14% | 26% | 6% |
| Share of sessions following a plan | 54% | 78% | 0% |
| Verbatim session repeat rate | 22% | 11% | 71% |
| Free → paid conversion | 3.1% | 6.8% | 0.0% |
| Sessions/week (retained users) | 9.4 | 15.1 | 6.2 |

The repeat-rate row is the one we would flag to an investment committee. A 71% verbatim
repeat rate against a category median of 22% is not a usage pattern, it is the absence of
any progression mechanism, and it shows up directly in the W4 number.

## What we would expect a rational roadmap to sequence

1. A range query on activity history — it is a shared dependency of periodic reports, the
   history latency problem, and any period comparison. Cheap and unblocks three things.
2. Periodic reports (weekly, then monthly) over that range query.
3. Generated plans, with adaptation against logged adherence.
4. Per-user unit system — two days of work against the largest revenue pool; sequence it
   first if the team wants a fast win, since it does not compete for the same reviewers.
5. A functioning subscription (there is demonstrated intent and no way to pay).
6. Enterprise gates: SSO, cohort export, accessibility conformance.

Items 2 and 3 are the same product loop — decide the week, do the week, review the week —
and shipping either alone leaves the loop open.

## Risks to this view

- **Generated plans carry a trust cost.** A plan that is wrong for an injured or deconditioned
  user is worse than no plan. We would expect any vendor here to keep computed figures out
  of the model's hands and to hold a deterministic fallback.
- **Inference pricing is a dependency, not a constant.** The current unit economics assume
  managed-model pricing continues to fall. A vendor with no measured cost ceiling is exposed
  to a supplier price change becoming a margin event.
- The enterprise path requires non-product investment (attestation, VPAT) that does not
  improve the consumer product and competes for the same quarter.
