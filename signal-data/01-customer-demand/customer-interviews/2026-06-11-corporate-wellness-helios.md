---
interview_id: INT-2026-014
date: 2026-06-11
duration_minutes: 45
type: discovery_call
account: Helios Health Systems
account_tier: corporate_enterprise
arr_usd: 17880
contract_stage: pilot_expansion_at_risk
participants:
  - role: Director, Benefits & Wellbeing (buyer)
  - role: IT Security Analyst (blocker)
  - role: Kiro Fit PM
  - role: Kiro Fit AE
signal_class: customer_demand
themes: [sso_required, data_export_missing, admin_audit_log, wearable_integration, accessibility_a11y]
---

# Discovery call — Helios Health Systems (pilot expansion)

## Context

Pilot of 240 employees since March; contract contemplates expansion to 4,200 seats
in Q4 FY26. Expansion is currently **blocked on two hard gates and one soft gate**.

## What is working

- Employee-reported satisfaction with logging UX is high ("people actually open it").
- Guest browse mode removed the onboarding friction their previous vendor had —
  employees could see the app before creating an account.
- Purple theme tested well against their brand palette; no white-label ask.

## Hard gate 1 — SSO (security)

> Security Analyst: "We do not provision credentials for a benefits app. It federates
> with our IdP or it does not go past pilot."

- Needs SAML 2.0 or OIDC against their IdP with SCIM-lite deprovisioning on offboarding.
- Noted Cognito already supports federation — the ask is configuration plus a
  tenant-aware sign-in route, not a new auth system.
- Deadline: security re-review window closes **2026-10-15** for a Q4 rollout.

## Hard gate 2 — Participation reporting / export

> Benefits Director: "I cannot renew a wellbeing spend I cannot report on."

- Needs monthly aggregated, de-identified participation: active users, days logged
  per cohort, average adherence. Cohort = department, min cohort size 25 for
  anonymity.
- CSV is sufficient. Does not need dashboards in v1.
- Flagged that the Premium page in-product *advertises* "Data export (CSV, JSON)",
  which their team read as available. Set expectation problem.

## Soft gate — wearables and accessibility

- Android fleet is standardising on Health Connect; Google Fit API retirement was
  raised by their mobility team unprompted.
- Accessibility: their procurement requires a VPAT/ACR. VoiceOver failure on the
  weekly progress ring was reproduced live on the call.
- Units: roughly 40% of enrolled staff sit at US sites. Metric-only entry was raised
  as enrolment friction on this call, not a blocker. It became a named renewal
  condition for a different account two months later (PC-2026-12).

## Explicitly *not* asked for

- Social/community features — flagged as an HR risk ("we do not want leaderboards
  ranking employees by weight").

## Quantified

| Ask | Blocking? | Seats at stake | Latest useful date |
|---|---|---|---|
| SAML SSO | yes | 4200 | 2026-10-15 |
| Cohort participation export | yes | 4200 | 2026-11-01 |
| Admin audit log | no (Q1 ask) | 4200 | 2027-01-31 |
| Health Connect sync | no | ~1900 Android | 2027-Q1 |
| VPAT / a11y remediation | procurement | 4200 | 2026-12-01 |

## PM takeaways

1. Enterprise ARR is gated by three items that are all *adjacent to code that already
   exists* (Cognito federation, health single-table reads, aria attributes).
2. Community/challenges demand is coming from SMB accounts, not enterprise — segment
   the signal, do not average it.
3. In-product Premium marketing copy is generating support load and trust damage.
   Cheapest fix in the repository: gate the copy behind what is shipped.
