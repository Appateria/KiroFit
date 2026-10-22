---
document_id: PSR-DELTA-2026-09
ritual: pre_sprint_backlog_refinement
sprint: 2026-09 (S18)
previous_scoring_run: 2026-08-13 (config v2)
current_scoring_run: 2026-08-27 (config v3)
question: what changed since last sprint?
---

# Signal Index delta — S17 → S18

The SSE re-scores the whole store before each sprint. This is the review artifact: only
what *moved*, and why.

## Scope change this cycle — calorie tracking left the product

The largest movement in this delta is not a re-score. **Calorie-consumption tracking was
removed from the codebase**, and with it thirteen themes were retired from the store:
`food_search_empty`, `barcode_scanner`, `recipes_meals`, `ai_photo_logging`,
`portion_fidelity`, `edit_delete_missing`, `backdating_missing`, `meal_type_inference`,
`pagination_missing`, `exercise_not_netted`, `macro_goals`, `water_tracking`,
`guest_empty_dashboard`.

Cluster CL-01 ("Make food logging possible") dissolved entirely. CL-02 and CL-03 lost most
of their members and CL-03 was retitled. The store went from 515 signals across 45 themes
to 491 across 36.

This is a deliberate curation decision, not decay. A signal asserting that a feature is
broken is worthless once the feature does not exist — it would keep drawing weight and
keep proposing work that cannot be done. Retired themes are removed rather than rejected,
because a rejection record implies the ask could be revived, and these cannot: there is
nothing left to fix. `validate.py` enforces the consequence — every `code_ref` in the store
must still resolve against `../src`, and the retired themes' refs no longer did.

Two themes survived the removal by re-anchoring onto surfaces that still exist rather than
being retired: `accessibility_a11y` (the progress ring moved from `CalorieProgressBar` to
the exercise `WeeklySummary`) and `server_validation_gap` (`mutation.logFood` →
`mutation.logExercise`). The underlying defects were never calorie-specific.

## New themes this cycle

Three capability gaps that were previously masked by the calorie work, plus one standing
charter. All four arrive with cross-class corroboration already in place, which is why they
enter near the top rather than at the bottom.

| Theme | Rank | Classes | Signals | Why it enters high |
|---|---|---|---|---|
| progress_reports_periodic | **1** | 6 | 36 | Contractual (PC-2026-11, due 2026-11-01), a hard-zero funnel, and the strongest retention correlation in the cohort data (35% vs 21% W4) |
| unit_system_imperial | **2** | 6 | 27 | 2-day estimate against a US-majority revenue pool; EXP-2026-047 measured +22.7% profile completion |
| exercise_plan_generation | **3** | 6 | 29 | Highest-vote PFR in the window (724); 71.2% verbatim session repeat rate |
| genai_charter | **12** | 5 | 20 | Standing charter (ADR-010, objective O6); constrains how ranks 1 and 3 are built |

`genai_charter` is not a feature. It is recorded as a theme so the charter carries strategic
alignment weight in scoring and so its unbuilt preconditions (TD-2026-34, GH-568) are
visible in the same backlog as the capabilities that depend on them.

## Themes that rose

| Theme | S17 rank | S18 rank | What reinforced it |
|---|---|---|---|
| accessibility_a11y | 6 | **4** | EXP-2026-027 concluded (+16.8% task success, no aesthetic cost) and PC-001 attached a hard VPAT date of 2026-12-01. Effort estimate fell from 9d to 6d once the token change was scoped separately. |
| gdpr_dsar | 11 | **5** | INC-2026-058 opened (erasure serviced by ad-hoc DynamoDB deletes) and GH-533 was filed. Gained a sixth class, moving the multiplier to 1.85. |
| data_export_missing | 14 | **6** | Now referenced by four separate OKR key results (O2-KR3, O3-KR2, O4-KR2, O4-KR4) after O4 was added this quarter. |
| history_range_limit | 22 | **11** | EXP-2026-034 produced an 86.8% render-time improvement, and the resolver is now a shared dependency of the rank-1 theme rather than a history-only fix. |
| sso_required | 9 | **7** | SOC-0524 and AMB-DISCORD-PRACTITIONERS added ambient corroboration; TSW-015 added the SOC 2 timing constraint. |

## Themes that fell

| Theme | S17 rank | S18 rank | Why |
|---|---|---|---|
| discover_stale_content | 19 | 26 | Decay: last reinforcement 2026-06-03 (GH-461). No new tickets in 12 weeks even though the content is still static. PC-008 keeps it alive as a commitment, not as demand. |
| native_mobile_apps | 16 | 25 | Formally rejected as NG1 on 2026-07-01, dropping strategic alignment to 0.15. Rejection expires 2026-12-28. |
| custom_activities | 24 | 20 | Held roughly flat in absolute terms; moved up only because the field above it shrank. Still no new signals since PFR-0372 and CSAT-9044. |
| instrumentation_gap | 38 | 31 | Re-anchored: it is no longer about an unmeasured search box but about the absence of any event when a user asks for a capability the product lacks (GH-540, rewritten). |

## Rejections expiring soon

| Rejection | Theme | Expires | Trigger to revive early |
|---|---|---|---|
| REJ-native_mobile_apps | native_mobile_apps | 2026-12-28 | two corporate accounts requiring wearable sync, or web-push lift holding 60 days |
| REJ-community_challenges | community_challenges | 2026-12-28 | a privacy-preserving format validated with two program admins |

`REJ-ai_photo_logging`, `REJ-water_tracking` and `REJ-EXP-2026-023` were withdrawn rather
than expired: all three attach to retired themes. NG2 was removed from `okrs-fy26.yaml`
accordingly — a non-goal for a feature area that no longer exists is noise.

## Deadlines inside the sprint window

| Date | Item | Consequence |
|---|---|---|
| 2026-09-30 | Stride Payments integration slot (PC-007) | 6-week re-queue; O3 unreachable this year |
| 2026-09-30 | Northwind program cycle decision (PC-003) | second churn of the same SMB account |
| 2026-10-15 | Helios security re-review window (PC-001) | 4,200-seat expansion slips a quarter |
| 2026-10-15 | Aurora imperial-units renewal condition (PC-2026-12) | named condition on a $5k/yr renewal; 2 days of work |
| 2026-11-01 | Helios monthly cohort report (PC-2026-11) | named deliverable in the expansion agreement |

The Meridian nutrition-data LOI (PC-005, previously expiring 2026-09-15) is void — it was a
commitment against a feature area that no longer exists.

## Mid-sprint steering watchlist

Live signals to monitor against in-flight work, per the PSR continuous evaluation loop:

- `Mutation.logExercise` error rate — must fall, not rise, when the guest-sync outbox lands.
- `history_render_p95_ms` — range-query rollout; also watch AppSync `ThrottledRequests`,
  which has no alarm yet (O5-KR1).
- `profile_unit_confusion` event rate — should fall to near zero once entry-side conversion
  ships, not just display-side. If it does not, the conversion is in the wrong layer.
- `repeat_of_previous_session` rate (currently 71.2%) — the single clearest measure of
  whether plan generation is working. EXP-2026-041 moved it to 58% with a static card;
  a generated plan that does not beat that is not earning its inference cost.
- Premium-complaint ticket rate — should stay at the post-EXP-2026-019 level (1.2 per 1k
  views) as billing work begins.
- Inference cost per MAU, once any model call ships — O6-KR2 sets the ceiling at $0.04 and
  the metric does not exist yet.

## Exploration allocation

15% of capacity is reserved for work outside the top of the stack rank (per
`scoring-config.yaml: governance.exploration_allocation_pct`). This sprint it goes to the
first CloudWatch alarms and a prompt-evaluation harness spike — both rank outside the top
10, and both are preconditions for measuring whether the top-ranked work is succeeding
rather than features in themselves.
