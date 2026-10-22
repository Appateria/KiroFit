# 07 — Tech Debt & Modernization (offline fixture)

Signal class 7. One file: `atx-findings-comprehensive.json` — **31 real findings** from an
AWS Transform continuous modernization `tech-debt-comprehensive` analysis of
[`../../src`](../../src), captured verbatim.

## What this is, and what it is not

This directory is a **test fixture, not the data path.** The real source of class-7 signals
is the connector: the console runs a CM analysis against the PSR workspace and writes the
findings as an artifact. See `PLAN-modernization-signal.md` §6.

The fixture exists so the taxonomy and scoring guidance can be exercised end to end — 7
class cards render, sources survive a reload, the agent emits `tech_debt` in
`classes_processed` — **without** AWS credentials, the `atx` CLI, or a 50-minute analysis.

## Provenance

Not synthetic, and not hand-written. This is the recorded output of:

```bash
atx ct source add --name kirofit-local --provider local --path <workspace>/kirofit
atx ct discovery scan --source kirofit-local
atx ct analysis run --type tech-debt-comprehensive \
  --source kirofit-local --repo kirofit-local::src
atx ct findings list --analysis-id <id> --json
```

Analysis `01M53VY1PW74R0CK8GXZ8AQ83E`, run 2026-10-17, **~52 minutes** for this one small
repo in local mode. That duration is itself a design input: it is why the connector caches
on `HEAD` rather than re-scanning per Generate.

Only the ANSI colour codes and Node version warnings that the CLI writes **before** the JSON
have been stripped. Every finding is untouched.

## Shape — this is the contract

A **bare JSON array**, not an object with a `findings` key. Fields are **snake_case**:

```
id  schema_version  created_at  updated_at  created_by  analysis_id  repo
category  severity  title  description  analysis_type  status  recommendation
file_refs  fix  metadata
```

Things worth knowing before writing a parser:

- `file_refs` is an **array** of repo-relative paths. There are **no line numbers**.
- `fix` is **`null` on 30 of 31** findings — present-but-null, never omitted. When non-null
  it is an object: `{"kind": "atx-transform", "transform_name": "AWS/…", "effort": "Medium"}`.
  So an effort grade exists, but only for auto-remediable findings.
- `metadata` is an empty object on every finding here.
- `status` is `open` on all 31; a fresh analysis produces no `dismissed` or `obsolete`.
  Those states appear only after human triage or a re-analysis, so this fixture cannot
  exercise the `rejected`/`stale` mappings — see the gap noted below.
- **The CLI prints ANSI-coloured warnings to stdout before the JSON**, and those escape
  codes contain `[`. A parser that seeks the first `[` lands inside an escape sequence.
  Strip ANSI, then find the line that is exactly `[`.

## What is actually in it

| Severity | Count |
|---|---|
| high | 4 |
| medium | 15 |
| low | 12 |

| Category | Count |
|---|---|
| security | 9 |
| dependency | 6 |
| code-quality | 6 |
| maintainability | 4 |
| architecture | 3 |
| infrastructure | 3 |

The four HIGH findings are not dependency staleness:

- Hardcoded demo credentials seeded by default and emitted as a plaintext CloudFormation
  output *(security)*
- Privilege escalation: client-writable Cognito `tier` attribute trusted from an unverified
  JWT claim *(security)*
- `aws-cdk-lib` 2.232.1 carries two HIGH command-injection CVEs *(dependency)*
- Lambda runtime pinned to the outdated `nodejs20.x` managed runtime *(infrastructure)*

Note that `category: security` findings came out of a plain `tech-debt-comprehensive` run —
the separate `security` analysis type and its one-time infrastructure setup were **not**
needed for these.

## Known gap

Every finding here is `status: open`, so the fixture exercises the severity, `fix.effort`
and category mappings but **not** the lifecycle mappings (`dismissed` → `rejected` with the
reason preserved, `obsolete` → `stale`). Those need either a triaged finding
(`atx ct findings update --status dismissed --reason …`) or a second analysis that no longer
reproduces a finding. Until then, that part of the skill guidance is unverified.
