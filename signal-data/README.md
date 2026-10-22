# Kiro Fit — Product Signal Repository (synthetic dataset)

Synthetic but internally consistent signal data implementing [`psr.md`](../psr.md) against a
real workload: the **Kiro Fit** app in [`../src`](../src) (Ionic 8 + Vue 3 SPA, AWS CDK with
AppSync, a single-table DynamoDB health store, Cognito, and CloudFront/S3 hosting).

**491 normalized signals · 36 themes · 31 sources · 7 signal classes · 54 files ·
8 formats** (csv, tsv, jsonl, json, yaml, md, log, py).

> Everything here is fabricated. Customers, tickets, competitors, analysts, incidents and
> metrics do not exist. The *product gaps* the signals describe, however, are real
> observations from reading `../src` — that is what makes the dataset useful for exercising
> the PSR loop.

> **Class 7 is the exception twice over.** `07-tech-debt/` is an **offline fixture**, not
> part of the modelled dataset: the real source of class-7 signals is a live AWS Transform
> continuous modernization scan of the workspace. Its findings are also **not fabricated** —
> each one was read off the actual manifests and CDK constructs in `../src`. It is excluded
> from the signal counts above, which describe the modelled six-class dataset only.

## Why the signals are grounded in the codebase

Each theme traces to something actually present (or actually absent) in `../src`. A sample:

| Theme | Grounding in `../src` |
|---|---|
| `progress_reports_periodic` | `Query.exerciseEntries(date: AWSDate!)` — one required day, so no period can be aggregated |
| `unit_system_imperial` | `HealthProfile` exposes only `heightCm`/`weightKg`; no unit preference, no conversion |
| `exercise_plan_generation` | every health type is retrospective; nothing in the schema can express a planned session |
| `genai_charter` | no model invocation path, token budget, cost metric or fallback in `kirofit-stack.ts` |
| `history_range_limit` | same single-`AWSDate` signature; the sort key `EXERCISE#<date>#<id>` would support `between()` |
| `guest_sync_loss` | `syncGuestDataToAccount()` awaits per entry, `console.warn`s failures, then `clear()`s regardless |
| `billing_missing` | `handleUpgrade()` presents a "coming soon" toast; nothing writes the `tier` claim `useAccessTier()` reads |
| `analytics_missing` | `access.ts` gates 5 premium features that have no route, page or service |
| `history_latency` | `Query.exerciseEntries` takes a single required `AWSDate` → one query per day |
| `public_profile_pii` | `Query.profile` is `@aws_api_key` and `Profile` includes `dob`/`location` |
| `discover_stale_content` | `articleService.ts` serves a hardcoded `MOCK_ARTICLES` array |

`code_refs` on every normalized record points at the implicated path (validated to exist),
giving the bidirectional traceability `psr.md` calls for.

## Layout

```
signal-data/
├── README.md                        this file
├── manifest.json                    file inventory, checksums, record counts, rollups
├── 01-customer-demand/              class 1 — PFRs, tickets, surveys, churn, reviews, interviews
│   ├── zendesk-tickets.csv                    31 support tickets w/ tier, severity, CSAT
│   ├── product-feature-requests.jsonl         22 in-product/sales PFRs w/ vote counts
│   ├── nps-csat-verbatims.csv                 25 survey verbatims, 3 NPS waves + post-ticket CSAT
│   ├── churn-exit-surveys.csv                 14 exits w/ reason codes and MRR lost
│   ├── app-store-reviews.jsonl                15 iOS/Play reviews, 5 locales
│   └── customer-interviews/*.md               enterprise discovery call + power-user panel
├── 02-defect-degradation/           class 2 — issues, telemetry, security, CI
│   ├── github-issues.jsonl                    24 issues (#413–#568) w/ file refs and severity
│   ├── appsync-error-rates-daily.csv          148 days × 10 operations
│   ├── appsync-latency-percentiles.tsv        148 days × 5 operations, p50/p90/p99
│   ├── sentry-frontend-errors.jsonl           10 issue groups w/ event and user counts
│   ├── incident-log.csv                       6 incidents w/ MTTD/MTTR and root cause
│   ├── flaky-tests.csv                        12 specs w/ flake rate and suspected cause
│   ├── security-findings.md                   pen test, dependency, posture, bug bounty
│   └── raw/cloudwatch-appsync-2026-07-27.log  raw log excerpt for INC-2026-041
├── 03-market-competitive/           class 3 — competitors, standards, regulation, analysts
│   ├── competitor-releases.jsonl              14 releases from 6 competitors
│   ├── competitor-feature-matrix.csv          23 capabilities × 6 competitors + gap severity
│   ├── tech-standards-watch.csv               14 EOL/deprecation/standards items w/ dates
│   ├── regulatory-and-compliance-watch.md     DSAR, health data, accessibility, store rules
│   └── analyst-note-2026-h2.md                category note w/ retention benchmarks
├── 04-usage-behavioral/             class 4 — what users actually do
│   ├── feature-adoption-daily.csv             148 days × 9 features, DAU share
│   ├── funnel-dropoff-weekly.csv              4 funnels × 21 weeks, incl. 4 hard-zero steps
│   ├── help-center-search-terms.csv           38 query terms w/ implied-theme hints
│   ├── cohort-retention-weekly.csv            12 cohorts × 7 definitions × 8 weeks
│   ├── product-events-sample.jsonl            2,400 raw events w/ properties
│   ├── ab-test-results.jsonl                  8 experiments w/ decisions and secondary metrics
│   └── behavioral-readout-2026-08.md          the analysis a PM would actually read
├── 05-strategic-business/           class 5 — company intent
│   ├── okrs-fy26.yaml                         5 objectives, 16 KRs, 4 declared non-goals
│   ├── tech-debt-register.csv                 21 debt items w/ effort and blast radius
│   ├── partnership-commitments.csv            9 commitments w/ dates and dependent themes
│   ├── pricing-and-packaging-constraints.md   packaging boundary and its constraints
│   └── platform-decisions.md                  ADR-001..011 (ADR-010 = GenAI charter)
├── 06-ambient-ecosystem/            class 6 — weak signals
│   ├── social-listening.jsonl                 16 mentions across reddit/HN/X/Discord
│   ├── competitor-job-postings.jsonl          14 postings → roadmap inference
│   ├── oss-momentum.csv                       17 adjacent repos w/ star/issue velocity
│   └── community-threads.md                   thread digests and hiring rollup
├── 07-tech-debt/                    class 7 — scanner findings (OFFLINE FIXTURE)
│   ├── atx-findings-comprehensive.json        31 real AWS Transform CM findings (verbatim)
│   └── README.md                              why this is a fixture, not the data path
├── signal-store/                    normalized, deduplicated, enriched
│   ├── signal.schema.json                     JSON Schema for a normalized record
│   ├── signals.jsonl                          491 records (canonical)
│   ├── signals.csv                            flattened view for spreadsheets/SQL
│   └── rejections.jsonl                       4 explicit rejections w/ expiry + revive trigger
├── signal-index/                    ranked view used for backlog decisions
│   ├── scoring-config.yaml                    SSE weights (read by the builder)
│   ├── signal-index.csv                       36 themes w/ full factor breakdown
│   ├── signal-index.json                      same, for agent consumption
│   ├── clusters.json                          13 opportunity clusters
│   ├── opportunity-briefs.md                  8 briefs ready for spec generation
│   └── sprint-delta-2026-09.md                "what changed since last sprint?"
└── tools/
    ├── generate_timeseries.py       deterministic telemetry generator (seed 20260827)
    ├── build_signal_store.py        intake → normalize → score → index
    └── validate.py                  schema/consistency checks + manifest.json
```

## Regenerating

```bash
python3 signal-data/tools/generate_timeseries.py   # volumetric telemetry (fixed seed)
python3 signal-data/tools/build_signal_store.py    # store + index from the raw files
python3 signal-data/tools/validate.py              # 0 errors, 0 warnings expected
```

`build_signal_store.py` reads every raw file, so editing a ticket or adding a competitor
release and re-running propagates through normalization, scoring and the ranked index.
Signal IDs are UUIDv5 of `source_ref` under a fixed namespace, so intake is idempotent.

## Scoring model

Weights live in [`signal-index/scoring-config.yaml`](signal-index/scoring-config.yaml) and are
read by the builder, so the documented model and the published numbers cannot drift.

```
base   = 0.22·frequency + 0.12·recency + 0.18·customer_tier
       + 0.18·severity + 0.16·strategic_alignment + 0.14·effort_inverse
weight = base × corroboration_multiplier ÷ 1.85
```

Corroboration is a **multiplier** on distinct signal classes (1 class → ×1.00, 6 → ×1.85),
per the `psr.md` principle that one signal from five sources beats five from one. Dividing by
the maximum multiplier keeps weights in 0..1 while preserving discrimination; clamping at 1.0
made the top 15 themes tie.

Derived inputs, not hand-entered: `strategic_alignment` comes from `okrs-fy26.yaml`
(`blocked_by_themes` × objective `alignment_weight`, with declared non-goals pinned to 0.15),
and `effort_inverse` comes from `remediation_estimate_days` in `tech-debt-register.csv`.

### Current top of the index

| Rank | Theme | Weight | Classes | Signals | Effort | Status |
|---|---|---|---|---|---|---|
| 1 | progress_reports_periodic | 0.971 | 6 | 36 | 4d | mapped |
| 2 | unit_system_imperial | 0.952 | 6 | 27 | 2d | mapped |
| 3 | exercise_plan_generation | 0.946 | 6 | 29 | 6d | mapped |
| 4 | accessibility_a11y | 0.932 | 6 | 25 | 2d | mapped |
| 5 | gdpr_dsar | 0.905 | 6 | 12 | 5d | mapped |
| 6 | data_export_missing | 0.891 | 5 | 20 | 1d | mapped |
| 7 | sso_required | 0.862 | 6 | 21 | — | mapped |
| 12 | genai_charter | 0.746 | 5 | 20 | 5d | processed |

The top three all carry full six-class corroboration, and the ordering between them is
decided by the effort-inverse factor rather than by importance — `unit_system_imperial` is
rank 2 on a 2-day estimate. Ranks 1, 11 and 17 also share one dependency (a range read on
the `EXERCISE#` sort key), which is the kind of thing the index surfaces but does not
decide. Those tensions are discussed rather than hidden in
[`opportunity-briefs.md`](signal-index/opportunity-briefs.md) — the index is an input to the
intake gate, not the decision.

`genai_charter` is listed because it is not a feature: it is a standing charter (ADR-010,
objective O6) recorded as a theme so it earns strategic-alignment weight and so its unbuilt
preconditions appear in the same backlog as the capabilities that depend on them.

### Retired themes

Thirteen themes were **retired** rather than rejected when calorie-consumption tracking was
removed from `../src`: `food_search_empty`, `barcode_scanner`, `recipes_meals`,
`ai_photo_logging`, `portion_fidelity`, `edit_delete_missing`, `backdating_missing`,
`meal_type_inference`, `pagination_missing`, `exercise_not_netted`, `macro_goals`,
`water_tracking`, `guest_empty_dashboard`. Cluster CL-01 dissolved with them.

The distinction matters. A rejection record implies the ask could come back, and carries an
expiry and a revive trigger. These cannot come back — there is no longer a feature to fix,
so the signals are noise that would keep drawing weight and keep proposing undoable work.
`validate.py` is what forces the issue: every `code_ref` in the store must resolve against
`../src`, and theirs no longer did.

Two themes survived by re-anchoring instead of retiring, because the underlying defect was
never calorie-specific: `accessibility_a11y` (progress ring moved from `CalorieProgressBar`
to the exercise `WeeklySummary`) and `server_validation_gap` (`mutation.logFood` →
`mutation.logExercise`). See
[`sprint-delta-2026-09.md`](signal-index/sprint-delta-2026-09.md) for the full delta.

## Design principles from `psr.md`, as implemented

| Principle | How it shows up |
|---|---|
| Source-agnostic normalization | one schema across 31 sources; `signals.csv` for humans, `signals.jsonl` + `signal-index.json` for agents |
| Corroboration over volume | multiplier on distinct classes; `linked_signals` only ever points cross-class |
| Explicit rejection | `rejections.jsonl` — every non-goal has a reason, an expiry date and a revive trigger |
| Decay by default | 45-day half-life; visible in `sprint-delta-2026-09.md` as themes that *fell* |
| Traceability always | `source_ref` → raw file; `code_refs` → paths in `../src`, validated to exist |

RFC-0001 §5.1 amendments are represented too: provenance tiers on every record
(`tier1_first_party_instrumentation` … `tier3_ambient_unverified`), outcome feedback via A/B
decisions that changed status (`EXP-2026-041` and `EXP-2026-044` are rejected *solution
shapes* whose parent themes are ranked 3 and 1 respectively), rejection expiry, a 15%
exploration allocation in the scoring config, and effort estimates sourced from the debt
register rather than guessed per signal.

## Notes on realism and provenance

- **Competitor entities are fictional composites** (MacroMint, FitLedger, NutriPilot,
  PulseCoach, LeanLoop, VitalWorks), as are the analyst firm, data supplier, billing provider
  and corporate accounts. Real product names appear only inside consumer verbatims, where a
  user naming the app they switched to is realistic; no claims are made about those products.
- Market and regulatory rows carry `verification_status: synthetic_placeholder`. Dates for
  EOL/standards items are illustrative scenario inputs, not legal or vendor guidance.
- No real personal data: users are `usr_####`, agents and staff are role handles.
- The dataset deliberately contains **tensions**, because a clean signal set teaches nothing:
  offline ranks 13th on corroboration but last in the user panel; SMB accounts want
  leaderboards that enterprise buyers refuse; the two largest measured experiment effects
  (EXP-2026-041, EXP-2026-044) both belong to *rejected* implementations of themes that
  rank 3rd and 1st; and rank 2 is a two-day change while rank 1 is contractually dated.
  The ordering of the index is an input, not a decision.
- Nothing has status `shipped`. That is itself a finding: the Sense loop has been running
  ahead of delivery for a full quarter.
