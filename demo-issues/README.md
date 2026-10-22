# Demo issue manager

Creates and deletes synthetic GitHub issues and Jira issues for demos of the
Kiro Fit PSR (Product Signal Repository) loop. Issue content comes straight
from `signal-data/signal-index/signal-index.json`, so the backlog you show in
a demo always matches the themes the signal data actually supports.

Every issue is tagged `demo-psr-signal` (plus a `psr-theme:<theme>` label) so
it can be found and removed later, even if the local state file is lost.

## Setup

```bash
pip install requests   # already present in most environments
```

GitHub (needs a token with issue read/write on the target repo):

```bash
export GITHUB_TOKEN=ghp_xxx
export GITHUB_REPO=my-org/kirofit
```

Jira (needs an [API token](https://id.atlassian.com/manage-profile/security/api-tokens)):

```bash
export JIRA_BASE_URL=https://your-domain.atlassian.net
export JIRA_EMAIL=you@example.com
export JIRA_API_TOKEN=xxxx
export JIRA_PROJECT_KEY=KF
```

## Use

Preview first, no credentials required:

```bash
python3 demo-issues/create_demo_issues.py create --targets github,jira --top 8 --dry-run
```

Create for real:

```bash
python3 demo-issues/create_demo_issues.py create --targets github,jira --top 8
```

Pick specific themes instead of top-N (see `signal-data/signal-index/signal-index.json` for names):

```bash
python3 demo-issues/create_demo_issues.py create --targets github --themes billing_missing,sso_required
```

See what's currently tracked:

```bash
python3 demo-issues/create_demo_issues.py list
```

Tear down after the demo:

```bash
python3 demo-issues/create_demo_issues.py delete --targets github,jira
```

Add `--sweep` to also catch anything made outside the state file (e.g. the
state file was deleted, or a previous run was interrupted) by searching for
the `demo-psr-signal` label:

```bash
python3 demo-issues/create_demo_issues.py delete --targets github,jira --sweep
```

## Notes

- GitHub issues can't be hard-deleted through the REST API without org-admin
  GraphQL access, so `delete` closes them instead (reversible, always
  permitted). Jira issues are hard-deleted.
- `.demo-issues-state.json` tracks what this script created. It's local only
  (gitignored) since it just holds issue numbers/keys and URLs, nothing
  sensitive — but it is specific to one person's demo run.
- Re-running `create` does not check for existing demo issues first, so
  running it twice without a `delete` in between will create duplicates.
