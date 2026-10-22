---
document_id: BEH-READOUT-2026-08
signal_class: behavioral
period: 2026-04-01 .. 2026-08-26
prepared_by: data_eng
provenance_tier: tier1_first_party_instrumentation
caveat: >
  Instrumentation coverage is incomplete. No surface emits an event when a user asks for a
  capability the product does not have (issue #540), so unmet demand had to be
  reconstructed from the hosted help-centre search log and a Sentry warning added ad hoc
  in July (KIROFIT-FE-1214). The product itself has no search surface.
companion_files:
  - feature-adoption-daily.csv
  - funnel-dropoff-weekly.csv
  - help-center-search-terms.csv
  - cohort-retention-weekly.csv
  - product-events-sample.jsonl
  - ab-test-results.jsonl
---

# Behavioral readout — what users actually do

## 1. Four funnel steps convert at exactly zero

These are not optimisation opportunities; they are unimplemented code paths that the UI
invites users into.

| Funnel | Step that never fires | Cause in code |
|---|---|---|
| premium_upgrade | `checkout_started` | `handleUpgrade()` shows a toast |
| premium_upgrade | `subscription_active` | no billing, no tier-claim writer |
| history_view | `range_change_succeeded` | `Query.exerciseEntries` takes one required `AWSDate` |
| history_view | `report_export_attempted` | no periodic report or export path exists |

39.8% of history sessions attempt a range change and none succeed, across all 21 measured
weeks. `report_export_attempted` splits its `requested_period` between `1w` and `1m` —
users are asking for exactly two periods. `upgrade_tapped` fires ~10% of the time premium
is surfaced (9,877 distinct users over the window) and terminates.

## 2. The logged sessions are almost all the same session

`exercise_logging_session` carries `repeat_of_previous_session` at **71.2%** for the whole
window. `repeat_previous_session` events carry `plan_source: null` and up to **9
consecutive identical sessions**.

Users are not failing to log. They are logging the same thing indefinitely because nothing
in the product proposes anything else.

## 3. Retention is decided by whether a user ever looks back

From `cohort-retention-weekly.csv`:

| Week-1 behaviour | W4 retention | W8 retention |
|---|---|---|
| Corporate program member | 44% | 36% |
| Set an exercise goal | 37% | 30% |
| **Viewed history** | **35%** | **30%** |
| Logged exercise | 21% | 16% |
| **Sessions were verbatim repeats** | **11%** | **7%** |
| Browsed Discover only | 3% | 1% |
| Guest, never signed up | 2% | 1% |

Two findings sit in this table and they point the same way. Looking back at progress
predicts retention far better than logging does (35% vs 21%). And users whose sessions
repeat verbatim retain at roughly half the rate of the general logging cohort — the
absence of a plan is measurable in churn, not just in satisfaction.

The reporting surface is therefore a retention lever, not a reporting nicety.

## 4. Help-centre search is dominated by three capabilities that do not exist

The product has no search box, so this is the hosted help-centre log. Unanswered queries
grouped by what they imply:

| Implied capability | Unanswered searches | Representative terms |
|---|---|---|
| Generated exercise plan | ~15,700 | "workout plan", "training plan", "beginner program", "what should i train today", "12 week plan", "rest days", "progressive overload" |
| Periodic progress report | ~15,000 | "weekly report", "monthly summary", "progress report", "last 30 days", "month view", "printable summary", "share report with coach" |
| Imperial units | ~18,300 | "how do i change to pounds", "lbs instead of kg", "feet and inches height", "imperial units", "miles not kilometres", "stone and pounds" |

The help centre has no article for any of these because there is nothing to document.
Unit questions are the single largest group — the cheapest of the three to fix.

## 5. Guest funnel: strong top, lossy middle

`guest_to_first_log` (weekly medians):

- 94.7% of guest sessions reach the dashboard — the browse-before-signup design works.
- 51.2% tap a log CTA, 49.8% see the sign-up prompt, but only 17.1% start sign-up.
- Of those completing sign-up, **only 61% end with a successful guest-data sync**
  (12.1% → 7.4% of entrants). `guest_sync_partial_failure` events carry
  `local_cache_cleared: true` in every instance.

EXP-2026-007 showed that prompting *after* the entry is composed lifts conversion 54.5%,
but shipping it without a local draft/outbox would widen the same data-loss hole.

## 6. Adoption trend: everything declines except purchase intent

Slope of feature DAU share over the window (`feature-adoption-daily.csv`):

| Feature | Trend |
|---|---|
| exercise_log | declining |
| discover_list | declining (stale content, no new articles since 2026-07-01) |
| exercise_history | declining |
| exercise_dashboard | flat-ish (landing route) |
| subscription_page | flat/slightly up (intent persists) |

Dashboard traffic holding while logging declines means users open the app, see numbers that
look like last week's, and leave.

## 7. Body metrics are being stored wrong

`profile_unit_confusion` fires where a persisted value is only plausible in imperial — a
`weightKg` of 154, a `heightCm` of 5.9. KIROFIT-FE-1207 recorded 6,188 events across 2,417
users, concentrated in `en-US` and `en-GB`. The values persist regardless of the warning.

EXP-2026-047 is the largest effect measured this quarter for the smallest change: a
display-only imperial toggle lifted profile completion **22.7%** and cut implausible-weight
warnings **81%**. Display-only conversion is not sufficient on its own — entry has to
convert too — but the direction is unambiguous.

## 8. Latency and reliability are visible in behaviour

- `history_opened` events carry `queries_issued: 7` and render times up to 9.6s;
  31% of history views are abandoned before render.
- EXP-2026-044 tried to build a weekly recap on that same fan-out and hit p95 of 11.2s.
  It was stopped on performance, not on demand — re-run it after the range query lands.
- `Mutation.logExercise` error rate stepped ~3.4x after r-1.0.14 (2026-06-18), matching the
  guest-sync ticket cluster and INC-2026-029.
- On 2026-07-27 query error rates spiked ~6x (INC-2026-041); no alarm existed to catch it.

## 9. What the behavioral data does *not* support

- **Offline** is loud in tickets but ranks last in the power-user panel and shows a small
  affected population outside commuting hours. Real, not urgent.
- **Community/challenges** shows no in-product demand signal at all; the ask comes
  entirely from SMB program admins, and enterprise buyers actively object.
- **A generated plan as a static artefact.** EXP-2026-041 is the cautionary result: a
  hardcoded starter week lifted W2 return 11.4%, then 34% of treatment users abandoned it
  by week 3. The demand is for something that adapts, which is an argument about
  implementation shape (ADR-010), not about whether to build it.
