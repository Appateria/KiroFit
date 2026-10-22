---
document_id: MKT-REG-2026-08
signal_class: market
captured_at: 2026-08-20
analyst: Kiro Fit product ops
provenance_tier: tier2_secondary_research
verification_status: synthetic_placeholder
note: >
  Dates and obligations below are illustrative for this synthetic dataset. Treat them as
  scenario inputs to the Signal Scoring Engine, not as legal guidance.
---

# Regulatory & compliance watch — health/fitness consumer apps

## 1. Data subject rights (GDPR / UK GDPR / US state privacy laws)

| Obligation | Kiro Fit today | Gap | Blocking |
|---|---|---|---|
| Right of access (export) | none | No export path; Premium page advertises one | ZD-10884, ZD-10510 |
| Right to erasure | none | No delete mutation, no account deletion; actioned by ad-hoc DynamoDB deletes | issue #533, INC-2026-058 |
| Right to rectification | none | Entries cannot be edited | issue #388 |
| Data minimisation | at risk | `Profile.dob`/`location` exposed to API-key reads | PEN-2026-03 F-02 |
| Processor obligations (DPA) | signed with 2 corporate accounts | 30-day erasure SLA cannot currently be met reliably | Helios, Aurora DPAs |

**Notable coupling:** rectification and erasure are the same missing schema surface as
a top-ranked consumer request (correcting a logged session). One schema change satisfies a
compliance obligation *and* the most-corroborated demand signal.

## 2. Health data classification

- Self-reported weight, height, dietary restrictions and activity are **health-related
  personal data** in EU terms, warranting elevated handling even where US HIPAA does not
  apply (no covered entity, no PHI flowing from a provider).
- Corporate wellness deployments change the analysis: employer-sponsored programs raise
  employment-law and works-council questions in EU jurisdictions. Aurora Manufacturing
  Co's works council has already asked for a data-flow diagram.
- Consequence for roadmap: individual leaderboards are a compliance and HR risk in the
  enterprise segment even though SMB accounts request them (ZD-10802).

## 3. Accessibility

- EU European Accessibility Act obligations apply to consumer digital services in scope;
  public-sector-adjacent and large-enterprise procurement increasingly require an ACR/VPAT.
- Current state: `axe` reports serious violations on the primary dashboard
  (no `role="progressbar"`, no `aria-valuenow`, dark-mode contrast 2.6:1 vs 4.5:1 required).
- Competitor LeanLoop published a conformance report in July 2026 (CMP-REL-0485) and is
  using it in procurement.
- Practical exposure: Helios procurement requires a VPAT by **2026-12-01**.

## 4. App store and billing rules

- Publishing native apps triggers privacy-manifest and data-safety declarations covering
  every bundled SDK (Cognito, Apollo, any analytics).
- Web-based subscription checkout avoids store commission and does not require a native
  launch — relevant because Kiro Fit has purchase intent (9,877 distinct users tapped
  Upgrade into a placeholder toast) and no billing at all.

## 5. Marketing claims

`SubscriptionPage.vue` advertises six Premium benefits, of which **zero** are implemented:
full history, advanced analytics, custom activities, data export, multiple goal types,
community features. Charging for these would create a straightforward unfair/deceptive
practice exposure; advertising them while unable to charge creates trust damage instead
(NPS-4526, ZD-11061, CSAT verbatims). The cheapest mitigation is a copy change gated to
shipped functionality.

## 6. Watch items with dates

| Item | Date | Consequence if missed |
|---|---|---|
| Helios security re-review window | 2026-10-15 | 4,200-seat expansion slips a quarter |
| Helios VPAT requirement | 2026-12-01 | procurement stop |
| Aurora renewal (Health Connect + export asks) | 2027-01-31 | $17.9k ARR at risk |
| Erasure SLA (rolling, per DPA) | 30 days from request | DPA breach; currently met manually |
| SOC 2 observation start | ASAP | each month of delay pushes enterprise pipeline out by a month |
