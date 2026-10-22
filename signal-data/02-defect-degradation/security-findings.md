---
document_id: SEC-ROLLUP-2026-Q3
signal_class: defect
sources: [pen_test, dependency_scanner, cloud_posture_scan, bug_bounty]
period: 2026-04-01 .. 2026-08-26
system: Kiro Fit (KiroFit-development / KiroFit-production)
---

# Security & vulnerability findings rollup — 2026 Q2/Q3

## A. Penetration test PEN-2026-03 (external, 2026-06-08 → 2026-06-12)

Scope: CloudFront-hosted SPA, AppSync GraphQL API, Cognito user pool, S3 media bucket.

| ID | Severity | Title | Status | Component |
|---|---|---|---|---|
| F-01 | High | AppSync API key embedded in publicly served `config.json` | open | `infra/lib/constructs/ui-hosting.ts` |
| F-02 | High | `Query.profile` exposes `dob`, `location`, `bio` to API-key callers; `userId` is enumerable | open | `infra/graphql/schema.graphql` |
| F-03 | Medium | No field-level authorization: any authenticated user may read another user's `profile` | open | `infra/resolvers/query.profile.ts` |
| F-04 | Medium | Mutations perform no server-side validation; client zod bounds are the only limits | open | `infra/resolvers/mutation.logExercise.ts` |
| F-05 | Medium | Presigned upload URL is not scoped by content-length; arbitrary-size object write | open | `infra/lib/lambda/profile-photo/index.ts` |
| F-06 | Low | No WAF / rate limiting in front of AppSync (descoped at consolidation) | accepted-risk | `infra/lib/kirofit-stack.ts` |
| F-07 | Low | Cognito password policy accepts 8 chars with no breach-list check | open | `infra/lib/constructs/auth.ts` |
| F-08 | Informational | No account deletion or data-export path (erasure obligations unmet) | open | schema |

### F-02 detail (highest business risk)

`Query.profile(userId: ID!)` carries both `@aws_api_key` and `@aws_cognito_user_pools`.
The schema comment describes it as "public, non-sensitive", but the `Profile` type
returns `dob`, `location` and `bio`. The API key is written into `/config.json`
next to the SPA bundle at deploy time, so it is retrievable by any visitor.
Cognito `sub` values are not guessable, but `userId` values appear in client-side
GraphQL responses and in shared profile links, giving a practical enumeration seed.

Recommended remediation (ordered by cost):
1. Remove `dob` and `location` from the API-key-authorized selection set (split into
   `PublicProfile` type) — schema-only change.
2. Drop `@aws_api_key` from `Query.profile` if no anonymous surface actually needs it;
   the UI only reads `profile` while authenticated.
3. Add an owner check in `query.profile.ts` for the Cognito path.

## B. Dependency vulnerabilities (npm audit, 2026-08-24)

| Advisory | Package | Installed | Severity | Fixed in | Reachable? |
|---|---|---|---|---|---|
| GHSA-7f2x-9cvq | esbuild (via vite 5) | 0.21.5 | moderate | vite 7 | dev server only |
| GHSA-4qm2-jw8k | axios | 1.17.0 | moderate | 1.18.2 | yes (httpClient) |
| GHSA-9jx3-cc2m | tough-cookie (via cypress 13) | 4.1.3 | low | cypress 15 | test only |
| EOL-NOTICE | eslint | 8.57.x | n/a (unsupported) | eslint 9 | build tooling |
| EOL-NOTICE | Node.js runtime | 20.x | n/a (maintenance ended 2026-04-30) | Node 22 LTS | Lambda + CI |

## C. Cloud posture scan (2026-08-01)

- `kirofit-media-{env}` S3 bucket: no lifecycle policy; orphaned avatar objects
  accumulate after failed `confirmProfilePhotoUpload` calls (≈ 41 GB, 118k objects).
- DynamoDB `kirofit-health-{env}`: point-in-time recovery **disabled** in development,
  enabled in production. Given there is no delete mutation, PITR is currently the only
  recovery mechanism for user-reported bad data.
- CloudTrail data events not enabled for the media bucket — no access trail for the
  audit-log ask from Helios Health Systems (ZD-11122).
- No CloudWatch alarms on AppSync 5xx or Lambda errors (see issue #526); MTTD for the
  2026-07-27 throttling incident was 96 minutes and came from social media.

## D. Bug bounty submissions

| ID | Reported | Severity | Summary | Payout | Status |
|---|---|---|---|---|---|
| BB-2026-014 | 2026-05-30 | medium | Profile enumeration via API key (duplicate of F-02) | $0 (dup) | closed |
| BB-2026-019 | 2026-06-21 | low | Missing rate limit allows 12k `logExercise` writes/min per token | $250 | triaged |
| BB-2026-023 | 2026-07-19 | medium | Presigned URL reuse window (`expiresIn` 3600) allows re-upload after key rotation | $750 | open |
| BB-2026-027 | 2026-08-14 | low | Stored HTML in `bio` renders unescaped in shared profile view | $400 | open |

## E. Aggregate signal for the PSR

Three of the four open medium/high findings and both compliance gaps (erasure, audit
trail) are **schema-level changes to `infra/graphql/schema.graphql`** — the same file
blocking the unit-preference field, the plan/planned-session types, weight history and
date-range queries. This is the
single highest-corroboration remediation surface in the codebase.
