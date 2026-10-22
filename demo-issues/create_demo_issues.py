#!/usr/bin/env python3
"""
Demo issue manager for Kiro Fit.

Creates and deletes synthetic/demo GitHub issues and Jira issues from the
themes in signal-data/signal-index/signal-index.json, so a repeated demo of
the PSR (Product Signal Repository) loop always has a believable backlog to
point at -- and can be cleanly wiped between runs.

Every issue this script creates is tagged so it can find them again later:
  - GitHub: label "demo-psr-signal" (plus a per-theme "psr-theme:<theme>" label)
  - Jira:   label "demo-psr-signal" (plus a per-theme "psr-theme-<theme>" label)

Created issue keys are also recorded in a local state file
(demo-issues/.demo-issues-state.json) so `delete` does not have to depend on
label search alone (belt and suspenders: state file first, label search as
a fallback/cleanup for anything the state file missed).

Usage
-----
    # preview what would be created, no network calls, no tokens needed
    python3 create_demo_issues.py create --targets github,jira --top 8 --dry-run

    # actually create issues (reads credentials from env vars, see below)
    python3 create_demo_issues.py create --targets github,jira --top 8

    # list what this script currently has tracked
    python3 create_demo_issues.py list

    # delete everything this script created (by state file + label fallback)
    python3 create_demo_issues.py delete --targets github,jira

Environment variables
----------------------
    GITHUB_TOKEN        A GitHub personal access token with "repo" (issues) scope.
    GITHUB_REPO         "owner/repo", e.g. "my-org/kirofit".

    JIRA_BASE_URL        e.g. "https://your-domain.atlassian.net"
    JIRA_EMAIL           account email for basic auth with the API token
    JIRA_API_TOKEN       Atlassian API token (https://id.atlassian.com/manage-profile/security/api-tokens)
    JIRA_PROJECT_KEY     e.g. "KF"
    JIRA_ISSUE_TYPE       optional, defaults to "Task"

No real credentials are bundled in this script or committed anywhere by it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    print("This script requires the 'requests' package: pip install requests", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNAL_INDEX_PATH = REPO_ROOT / "signal-data" / "signal-index" / "signal-index.json"
STATE_PATH = Path(__file__).resolve().parent / ".demo-issues-state.json"

DEMO_MARKER_LABEL = "demo-psr-signal"
GITHUB_DEMO_LABELS = [DEMO_MARKER_LABEL, "synthetic-demo"]
JIRA_DEMO_LABELS = [DEMO_MARKER_LABEL, "synthetic-demo"]

SEVERITY_FROM_RANK = {
    # Lower rank (closer to 1) = higher weight/urgency in the signal index.
    # Map that into something that reads naturally as a bug/ticket severity.
    "critical_max_rank": 3,
    "high_max_rank": 7,
    "medium_max_rank": 15,
}


def severity_for_rank(rank: int) -> str:
    if rank <= SEVERITY_FROM_RANK["critical_max_rank"]:
        return "critical"
    if rank <= SEVERITY_FROM_RANK["high_max_rank"]:
        return "high"
    if rank <= SEVERITY_FROM_RANK["medium_max_rank"]:
        return "medium"
    return "low"


def github_label_for_severity(severity: str) -> str:
    return {
        "critical": "P0",
        "high": "P1",
        "medium": "P2",
        "low": "P3",
    }[severity]


def jira_priority_for_severity(severity: str) -> str:
    return {
        "critical": "Highest",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }[severity]


def load_themes(top: int | None, only_themes: list[str] | None) -> list[dict[str, Any]]:
    if not SIGNAL_INDEX_PATH.exists():
        raise SystemExit(f"Signal index not found at {SIGNAL_INDEX_PATH}")
    data = json.loads(SIGNAL_INDEX_PATH.read_text())
    themes = data["themes"]
    themes = sorted(themes, key=lambda t: t["rank"])
    if only_themes:
        wanted = set(only_themes)
        themes = [t for t in themes if t["theme"] in wanted]
        missing = wanted - {t["theme"] for t in themes}
        if missing:
            raise SystemExit(f"Unknown theme(s): {', '.join(sorted(missing))}")
    elif top is not None:
        themes = themes[:top]
    return themes


def build_issue_content(theme: dict[str, Any]) -> dict[str, Any]:
    """Turn one signal-index theme record into title/body content shared by
    both trackers."""
    name = theme["theme"]
    rank = theme["rank"]
    severity = severity_for_rank(rank)
    feature_area = theme.get("feature_area", "unknown")
    weight = theme.get("weight")
    signal_count = theme.get("signal_count")
    class_count = theme.get("class_count")
    classes = theme.get("classes", "").replace("|", ", ")
    code_refs = theme.get("code_refs", "")
    code_refs_list = [c for c in code_refs.split("|") if c] if code_refs else []
    source_refs = theme.get("top_source_refs", "")
    source_refs_list = [s for s in source_refs.split("|") if s] if source_refs else []
    okr_refs = theme.get("okr_refs", "")
    effort_days = theme.get("effort_estimate_days")
    status = theme.get("status", "mapped")

    title_text = name.replace("_", " ")
    title = f"[Signal] {title_text} ({feature_area})"

    lines = [
        "> Synthetic demo issue generated from the PSR signal index. Safe to delete; "
        f"see demo-issues/create_demo_issues.py. Theme: `{name}`.",
        "",
        f"**Rank in signal index:** #{rank} (weight {weight})",
        f"**Feature area:** {feature_area}",
        f"**Corroboration:** {class_count} signal classes ({classes}), {signal_count} signals",
        f"**Status in PSR:** {status}",
    ]
    if effort_days not in (None, ""):
        lines.append(f"**Effort estimate:** {effort_days} day(s)")
    if okr_refs:
        lines.append(f"**OKR refs:** {okr_refs}")
    if code_refs_list:
        lines.append("")
        lines.append("**Implicated code:**")
        for ref in code_refs_list:
            lines.append(f"- `{ref}`")
    if source_refs_list:
        lines.append("")
        lines.append("**Top corroborating sources:**")
        for ref in source_refs_list:
            lines.append(f"- `{ref}`")
    lines.append("")
    lines.append(
        "See `signal-data/signal-index/opportunity-briefs.md` and "
        "`signal-data/signal-index/signal-index.json` for full evidence."
    )
    body = "\n".join(lines)

    return {
        "theme": name,
        "title": title,
        "body": body,
        "severity": severity,
        "feature_area": feature_area,
        "rank": rank,
    }


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"created": []}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def record_created(state: dict[str, Any], entry: dict[str, Any]) -> None:
    state["created"].append(entry)
    save_state(state)


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

class GitHubClient:
    def __init__(self) -> None:
        self.token = os.environ.get("GITHUB_TOKEN")
        self.repo = os.environ.get("GITHUB_REPO")
        if not self.token or not self.repo:
            raise SystemExit(
                "GITHUB_TOKEN and GITHUB_REPO env vars are required for --targets github"
            )
        self.base_url = f"https://api.github.com/repos/{self.repo}"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def ensure_labels(self, labels: list[str]) -> None:
        existing = {
            lbl["name"]
            for lbl in self._paginate(f"{self.base_url}/labels", params={"per_page": 100})
        }
        for label in labels:
            if label in existing:
                continue
            resp = self.session.post(f"{self.base_url}/labels", json={"name": label})
            if resp.status_code not in (201, 422):  # 422 = already exists (race)
                resp.raise_for_status()

    def _paginate(self, url: str, params: dict[str, Any] | None = None):
        params = dict(params or {})
        page = 1
        while True:
            params["page"] = page
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            yield from batch
            if len(batch) < params.get("per_page", 30):
                break
            page += 1

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        resp = self.session.post(
            f"{self.base_url}/issues",
            json={"title": title, "body": body, "labels": labels},
        )
        resp.raise_for_status()
        return resp.json()

    def find_demo_issues(self) -> list[dict[str, Any]]:
        return list(
            self._paginate(
                f"{self.base_url}/issues",
                params={"state": "all", "labels": DEMO_MARKER_LABEL, "per_page": 100},
            )
        )

    def close_issue(self, number: int) -> None:
        resp = self.session.patch(
            f"{self.base_url}/issues/{number}", json={"state": "closed"}
        )
        resp.raise_for_status()

    def delete_issue(self, number: int) -> bool:
        """GitHub's REST API has no issue-delete endpoint for non-admins;
        closing is the safe, always-available action. Returns True if an
        actual delete happened (GraphQL, admin-only), False if it only closed."""
        # The REST API cannot delete issues at all (only GraphQL deleteIssue,
        # which requires the issue's node_id and admin/owner rights on the repo).
        # We close + label instead, which is reversible and always permitted.
        self.close_issue(number)
        return False


# ---------------------------------------------------------------------------
# Jira
# ---------------------------------------------------------------------------

class JiraClient:
    def __init__(self) -> None:
        self.base_url = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
        self.email = os.environ.get("JIRA_EMAIL")
        self.token = os.environ.get("JIRA_API_TOKEN")
        self.project_key = os.environ.get("JIRA_PROJECT_KEY")
        self.issue_type = os.environ.get("JIRA_ISSUE_TYPE", "Task")
        if not all([self.base_url, self.email, self.token, self.project_key]):
            raise SystemExit(
                "JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN and JIRA_PROJECT_KEY env vars "
                "are required for --targets jira"
            )
        self.session = requests.Session()
        self.session.auth = (self.email, self.token)
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    def create_issue(self, summary: str, description: str, labels: list[str], priority: str) -> dict[str, Any]:
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "issuetype": {"name": self.issue_type},
                "labels": labels,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": line}],
                        }
                        for line in description.split("\n")
                        if line.strip()
                    ],
                },
            }
        }
        try:
            payload["fields"]["priority"] = {"name": priority}
            resp = self.session.post(f"{self.base_url}/rest/api/3/issue", json=payload)
            if resp.status_code == 400 and "priority" in resp.text.lower():
                # Some Jira projects don't have a Priority field configured; retry without it.
                del payload["fields"]["priority"]
                resp = self.session.post(f"{self.base_url}/rest/api/3/issue", json=payload)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise SystemExit(f"Jira create failed: {exc}\n{exc.response.text}") from exc
        return resp.json()

    def find_demo_issues(self) -> list[dict[str, Any]]:
        jql = f'project = "{self.project_key}" AND labels = "{DEMO_MARKER_LABEL}"'
        resp = self.session.get(
            f"{self.base_url}/rest/api/3/search",
            params={"jql": jql, "maxResults": 100, "fields": "key,summary"},
        )
        resp.raise_for_status()
        return resp.json().get("issues", [])

    def delete_issue(self, key: str) -> None:
        resp = self.session.delete(f"{self.base_url}/rest/api/3/issue/{key}")
        if resp.status_code not in (204, 404):
            resp.raise_for_status()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create(args: argparse.Namespace) -> None:
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    only_themes = [t.strip() for t in args.themes.split(",")] if args.themes else None
    themes = load_themes(top=args.top, only_themes=only_themes)
    if not themes:
        print("No themes matched; nothing to create.")
        return

    print(f"Preparing {len(themes)} demo issue(s) from {SIGNAL_INDEX_PATH.relative_to(REPO_ROOT)}")

    state = load_state()
    gh = GitHubClient() if "github" in targets and not args.dry_run else None
    jira = JiraClient() if "jira" in targets and not args.dry_run else None

    if gh:
        gh.ensure_labels(GITHUB_DEMO_LABELS + [f"psr-theme:{t['theme']}" for t in themes])

    for theme in themes:
        content = build_issue_content(theme)
        print(f"\n--- {content['theme']} (rank {content['rank']}, severity {content['severity']}) ---")
        print(content["title"])

        if args.dry_run:
            continue

        if "github" in targets:
            labels = GITHUB_DEMO_LABELS + [
                f"psr-theme:{content['theme']}",
                github_label_for_severity(content["severity"]),
                f"area/{content['feature_area'].split('/')[0]}",
            ]
            issue = gh.create_issue(content["title"], content["body"], labels)
            print(f"  GitHub: created #{issue['number']} ({issue['html_url']})")
            record_created(
                state,
                {
                    "target": "github",
                    "theme": content["theme"],
                    "number": issue["number"],
                    "url": issue["html_url"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        if "jira" in targets:
            labels = [
                lbl.replace(":", "-") for lbl in
                JIRA_DEMO_LABELS + [f"psr-theme-{content['theme']}"]
            ]
            issue = jira.create_issue(
                content["title"],
                content["body"],
                labels,
                jira_priority_for_severity(content["severity"]),
            )
            key = issue["key"]
            issue_url = f"{jira.base_url}/browse/{key}"
            print(f"  Jira: created {key} ({issue_url})")
            record_created(
                state,
                {
                    "target": "jira",
                    "theme": content["theme"],
                    "key": key,
                    "url": issue_url,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )

    if args.dry_run:
        print("\nDry run: nothing was created, no tokens were used.")
    else:
        print(f"\nState recorded in {STATE_PATH}")


def cmd_delete(args: argparse.Namespace) -> None:
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    state = load_state()
    remaining: list[dict[str, Any]] = []

    if "github" in targets:
        gh_entries = [e for e in state["created"] if e["target"] == "github"]
        if gh_entries or args.sweep:
            gh = GitHubClient()
            seen_numbers = set()
            for entry in gh_entries:
                seen_numbers.add(entry["number"])
                try:
                    gh.close_issue(entry["number"])
                    print(f"GitHub: closed #{entry['number']} ({entry['theme']})")
                except requests.HTTPError as exc:
                    print(f"GitHub: failed to close #{entry['number']}: {exc}", file=sys.stderr)
            if args.sweep:
                for issue in gh.find_demo_issues():
                    if issue["number"] in seen_numbers or issue["state"] == "closed":
                        continue
                    gh.close_issue(issue["number"])
                    print(f"GitHub: closed stray #{issue['number']} (label sweep)")

    if "jira" in targets:
        jira_entries = [e for e in state["created"] if e["target"] == "jira"]
        if jira_entries or args.sweep:
            jira = JiraClient()
            seen_keys = set()
            for entry in jira_entries:
                seen_keys.add(entry["key"])
                try:
                    jira.delete_issue(entry["key"])
                    print(f"Jira: deleted {entry['key']} ({entry['theme']})")
                except requests.HTTPError as exc:
                    print(f"Jira: failed to delete {entry['key']}: {exc}", file=sys.stderr)
            if args.sweep:
                for issue in jira.find_demo_issues():
                    if issue["key"] in seen_keys:
                        continue
                    jira.delete_issue(issue["key"])
                    print(f"Jira: deleted stray {issue['key']} (label sweep)")

    remaining = [e for e in state["created"] if e["target"] not in targets]
    save_state({"created": remaining})
    print(f"\nState updated. {len(remaining)} tracked issue(s) remain (other target(s)).")


def cmd_list(args: argparse.Namespace) -> None:
    state = load_state()
    if not state["created"]:
        print("No demo issues are currently tracked.")
        return
    for entry in state["created"]:
        ident = entry.get("number", entry.get("key"))
        print(f"[{entry['target']:6}] {ident:>6}  {entry['theme']:35}  {entry['url']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create demo issues from PSR signal themes")
    p_create.add_argument("--targets", default="github,jira", help="Comma list: github,jira")
    p_create.add_argument("--top", type=int, default=10, help="Use the top N ranked themes (default 10)")
    p_create.add_argument("--themes", default=None, help="Comma list of specific theme names instead of --top")
    p_create.add_argument("--dry-run", action="store_true", help="Preview without calling any API")
    p_create.set_defaults(func=cmd_create)

    p_delete = sub.add_parser("delete", help="Delete/close demo issues created by this script")
    p_delete.add_argument("--targets", default="github,jira", help="Comma list: github,jira")
    p_delete.add_argument(
        "--sweep",
        action="store_true",
        help="Also search by the demo-psr-signal label for issues missing from the state file",
    )
    p_delete.set_defaults(func=cmd_delete)

    p_list = sub.add_parser("list", help="List issues currently tracked in the local state file")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
