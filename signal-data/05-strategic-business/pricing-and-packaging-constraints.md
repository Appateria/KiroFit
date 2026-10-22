---
document_id: STRAT-PRICING-2026-Q3
signal_class: strategic
owner: pm_rowan
last_reviewed: 2026-08-24
themes: [billing_missing, analytics_missing, data_export_missing, history_range_limit, custom_activities, community_challenges, pricing_pressure]
---

# Pricing & packaging constraints

## Current declared packaging (as implemented in `ui/src/config/access.ts`)

| Tier | Gate | What the code actually allows |
|---|---|---|
| `guest` | no account | exercise dashboard, discover list |
| `free` | Cognito account | logging exercise, profile, settings, 7-day exercise history, article detail |
| `premium` | `tier` JWT claim | `exercise-history-full`, `analytics`, `data-export`, `custom-activities`, `community` |

**Every premium entitlement is unimplemented, and nothing writes the `tier` claim.**
`useAccessTier()` defaults unrecognised claims to `free`, so premium is currently
unreachable by any means, including manual account flagging.

## Constraints the roadmap must respect

1. **No revenue instrument exists.** Until checkout plus an entitlement store exists, every
   packaging decision is theoretical. `Stride Payments` (PC-007) holds an integration slot
   that expires 2026-09-30.
2. **Do not sell what the category gives away.** Competitors moved basic plan generation and
   weight trends to their free tiers during this window (CMP-REL-0513, CMP-REL-0499).
   Packaging basic logging capability as premium would be priced against a free competitor
   feature.
3. **Free tier must remain able to correct its own data.** Rectification is a
   obligation, not an upsell. Gating it would convert a compliance duty into a paywall.
4. **Export is doubly constrained.** It is advertised premium copy *and* a data-subject
   access right *and* an enterprise contract obligation (PC-001, PC-002). The individual
   user's own-data export cannot sit behind a paywall; the employer's cohort report can.
5. **Guest tier is a growth asset, not a packaging tier.** Guest browse mode is the one
   category differentiator (94.7% of guest sessions reach the dashboard). Restricting it
   to force sign-up would trade the top of the funnel for a conversion metric that is
   currently broken anyway.
6. **Corporate pricing is per-seat and reporting-gated.** SMB accounts sit at $4.15/seat/yr
   equivalent, enterprise at $4.26; both renew on evidence of participation, which requires
   the export that does not exist.

## Candidate premium boundary that survives the constraints

| Capability | Tier | Reasoning |
|---|---|---|
| Edit / delete / backdate entries | free | rectification obligation; category floor |
| Basic generated plan (1 per month) | free | category entry requirement; competitors free |
| Unlimited plan regeneration | premium | carries marginal inference cost per user |
| Weekly progress report | free | retention hook; cheap once the range query exists |
| Monthly report + narrative + export | premium | the paid unit; splits by period, not capability |
| Imperial / metric unit choice | free | accessibility-adjacent basic, never paid |
| Exercise netted into daily budget | free | correctness of the headline number |
| Data export of one's own data | free | access right |
| Reminders (single daily) | free | retention driver, cheap |
| Adaptive targets | premium | competitor paid boundary too |
| Analytics, weight trend, insights | premium | genuine incremental value |
| Full history beyond 90 days | premium | storage/compute-justified |
| Custom activity types | premium | low marginal cost, real willingness to pay |
| Cohort reporting, SSO, audit log | corporate plan | contract-driven, not consumer packaging |

## Immediate copy fix (already partly shipped)

EXP-2026-019 replaced six unqualified premium claims with roadmap labels: upgrade intent
fell 17.7% while premium-complaint tickets fell 75%. Intent has no value while checkout
does not exist, so the trade was accepted. The remaining exposure is the `benefits` array
in `SubscriptionPage.vue`, which should be derived from shipped capability rather than
hand-maintained.

## Open pricing questions (needing a decision this quarter)

- Monthly/annual price point relative to a category that just moved to ~$12.99/mo while
  expanding free tiers.
- Whether trial length is 7 or 14 days, given a 190s median time-to-log makes a short
  trial unlikely to demonstrate value.
- Whether the corporate plan is sold per seat or per active participant — the participation
  export will make this measurable for the first time.
