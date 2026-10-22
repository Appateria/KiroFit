#!/usr/bin/env python3
"""Bulk-load a local signal-data tree into a KiroCrew gateway's artifact library.

WHY THIS EXISTS: the Signal repository's "Browse folder" picker runs in the
dashboard renderer on YOUR laptop, but the only process that ever opens a
`type: "file"` source is `psr-agent`, which the gateway spawns on ITS OWN host.
Against a remote gateway every absolute path you can pick locally is therefore
wrong, and it fails invisibly — the agent is told to continue past an unreadable
source, so the run completes "successfully" having indexed nothing.

`type: "artifact"` sources have no such problem: an artifact is resolved by slug
through `artifact_get`, and it lives in the gateway's own store. So this script
pushes the data over HTTP and (optionally) wires the six signal classes straight
onto the app's PSR config, which removes both the path problem and ~50 manual
picker clicks.

TWO WAYS TO RUN IT, and the simpler one is ON THE GATEWAY HOST — in an SSM or
SSH session on the box, where the data, the gateway and this script are all the
same machine. Then there is no tunnel, no origin override, and no cross-machine
path question at all:

    ./psr-load-artifacts.py                        # dry run, whatever is on this host
    ./psr-load-artifacts.py --yes --wire-config    # load + assign to classes
    ./psr-load-artifacts.py --yes --wire-config --if-unconfigured   # first-boot seeding (crew-remote)

From a laptop against a REMOTE gateway you need a tunnel, because the dashboard
binds loopback only. `--token-cmd` mints the session on the far end while
`--base-url` names the origin you actually connect to:

    ./psr-load-artifacts.py --token-cmd 'ssh box kirocrew token' \
        --base-url http://localhost:5476 --yes --wire-config

DRY RUN BY DEFAULT, like `demo-reset.sh`. Nothing is written without `--yes`.

Stdlib only, and no syntax newer than 3.7 (`from __future__ import annotations`
keeps the PEP 604 hints out of the runtime), so it runs on whatever interpreter
the host happens to ship without a virtualenv.

## Class mapping

The leading number of each directory is the mapping, so `01-customer-demand/`
is `customer_demand` regardless of what the rest of the name says:

    01 -> customer_demand   02 -> defect       03 -> market
    04 -> behavioral        05 -> strategic    06 -> ambient

## How to find them again

Each artifact is named `PSR <NN> <class> - <path under the class dir>`, and the
`q` filter on `GET /api/artifacts` is a NAME-ONLY substring match unless
`?content=1` is passed (see `dashboard/handlers/artifacts.py:api_artifacts_list`).
The console's own Artifacts picker passes only `q` and `kind`, so typing
`customer_demand` there returns exactly that class and nothing else.

## Auth

The gateway has no bearer-token path; auth is the per-port cookie
`mc_token_<port>`, and the port is read from the *Host header the client
connects to* (`token_auth._cookie_port_from_host`), not from the port the
gateway listens on. Over an SSH tunnel that means the cookie is named for your
LOCAL port while the token value comes from the REMOTE gateway. `--base-url`
plus `--token-cmd` is that combination.

The token is a live credential for the whole dashboard. It is never printed,
never placed in argv, and never written to disk by this script — which is why
the remote token arrives as a COMMAND to run (`--token-cmd`) rather than as a
flag value that would land in your shell history.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# The dataset contract
# --------------------------------------------------------------------------

#: Directory number -> PSR signal class key. The six keys are the closed set in
#: `skills/psr-knowledge/SKILL.md` and `ui/src/psr.ts:SIGNAL_CLASSES`; a seventh
#: would be dropped by `psrApi.normalizeSources` on read, so this map is the
#: whole vocabulary and is deliberately not configurable.
CLASS_BY_NUM = {
    "01": "customer_demand",
    "02": "defect",
    "03": "market",
    "04": "behavioral",
    "05": "strategic",
    "06": "ambient",
}

#: Extension -> artifact kind. `ALLOWED_KINDS` in the gateway's `artifacts.py`.
#:
#: `.jsonl` is TEXT, not `json`: JSON Lines is not a JSON document, and the
#: console filters `kind=json` when it hunts for the PSR Index artifact
#: (`psrApi.artifactsForWorkspace`). Mislabelling a source as `json` puts it in
#: that result set for no reason.
KIND_BY_EXT = {
    ".md": "markdown",
    ".json": "json",
    ".jsonl": "text",
    ".csv": "text",
    ".tsv": "text",
    ".yaml": "text",
    ".yml": "text",
    ".log": "text",
    ".txt": "text",
}

#: Extensions that are tooling, not signal. Excluded even under --include-extras.
SKIP_EXT = {".py", ".pyc", ".sh", ".DS_Store"}


def is_normalized_psr_output(path: Path) -> bool:
    """True when this file is ALREADY a normalized PSR signal set.

    A dataset can ship its generator's own output alongside its raw inputs, e.g.
    a `{"class": ..., "signals": [{"signal_id": ..., "raw_content": ...}]}` file
    whose `raw_content` quotes sibling raw files this loader also uploads.

    Handing that to `psr-agent` as a source is contamination, not input. The agent
    would index the same underlying evidence twice — once from the raw file and
    once from the pre-scored record — and the duplicate then reads as independent
    CORROBORATION, which is the single heaviest factor in the Signal Scoring
    Engine. It is the same failure the spawn's `include_memory: false` exists to
    prevent, arriving through the source list instead of through context.

    Detected rather than deny-listed by name so it holds for any dataset.
    """
    if path.suffix.lower() != ".json":
        return False
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(doc, dict):
        return False
    signals = doc.get("signals")
    if not isinstance(signals, list) or not signals:
        return False
    head = signals[0]
    return isinstance(head, dict) and "signal_id" in head

#: Non-class directories, loaded only with --include-extras. `tools/` is never
#: loaded. `signal-index/` and `signal-store/` are DERIVED products of the
#: dataset's own generator: indexing them would feed the agent a pre-scored
#: index as if it were raw evidence, which is the exact contamination
#: `include_memory: false` exists to prevent on the spawn.
EXTRA_DIRS = ("signal-index", "signal-store")

#: `artifacts._SLUG_RE` is `^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$` — 80 chars,
#: lowercase, digits and hyphens only. No underscores, no dots.
SLUG_MAX = 80

#: `artifacts.MAX_NAME_LEN`.
NAME_MAX = 200

#: `artifacts.MAX_CONTENT_BYTES` (25 MiB). Nothing in a signal tree should come
#: close; a file that does is a mistake worth reporting rather than truncating.
CONTENT_MAX = 25 * 1024 * 1024

APP = "ai-adl-console"

#: Where to look for the tree when `--data-dir` is not given, first hit wins.
#:
#: Probed rather than defaulted because this script is run from BOTH ends: on a
#: laptop against a checkout under `~/src`, and on the gateway host itself over an
#: SSM/SSH session, where the same tree sits under `~/workspace` (a crew-remote
#: box) or `~/workplace` (older boxes). A single default is
#: therefore wrong on one of the two machines, and a wrong ABSOLUTE default is the
#: worst kind here — it is the same class of mistake this whole script exists to
#: eliminate, where a path that resolves nowhere produces an empty index instead
#: of an error.
DATA_DIR_CANDIDATES = (
    "./signal-data",
    "~/workspace/kirofit/signal-data",
    "~/workplace/kirofit/signal-data",
    "~/src/kirofit/signal-data",
)


# --------------------------------------------------------------------------
# Naming
# --------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Lowercase, hyphen-separated, and legal under `_SLUG_RE`."""
    out = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return out.strip("-")


def slug_for(num: str, rel: str) -> str:
    """Deterministic slug for one file, capped at `SLUG_MAX`.

    Determinism is the point: a re-run must derive the SAME slug so an existing
    artifact is updated in place rather than duplicated as `-2`. The hash suffix
    on an over-long path preserves that, where a bare truncation would collide
    two deep paths that share a prefix onto one slug.
    """
    body = f"psr-{num}-{slugify(rel)}"
    if len(body) <= SLUG_MAX:
        return body
    digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:8]
    return f"{body[: SLUG_MAX - 9].rstrip('-')}-{digest}"


def name_for(num: str, cls: str, rel: str) -> str:
    """`PSR 01 customer_demand - customer-interviews/panel.md`.

    The class key is in the NAME on purpose. The picker's search is a name-only
    substring match, so this is what makes "show me only this class" a single
    keystroke sequence rather than a reading exercise over 46 filenames.
    """
    return f"PSR {num} {cls} - {rel}"[:NAME_MAX]


# --------------------------------------------------------------------------
# Gateway client
# --------------------------------------------------------------------------


class Gateway:
    """The narrow slice of the dashboard API this script needs.

    Errors are values only where a miss is expected (`exists`); everything else
    raises `GatewayError` with the gateway's own message, because a silent
    failure here is a half-loaded library that looks complete.
    """

    def __init__(self, base: str, cookie: str) -> None:
        self.base = base.rstrip("/")
        self._cookie = cookie

    def _call(self, method: str, path: str, body: Any = None) -> Any:
        url = f"{self.base}{path}"
        data = None
        headers = {"Cookie": self._cookie, "Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:600]
            raise GatewayError(f"HTTP {exc.code} on {method} {path}: {detail}") from None
        except urllib.error.URLError as exc:
            raise GatewayError(f"cannot reach {self.base}: {exc.reason}") from None
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise GatewayError(f"{method} {path} returned non-JSON: {raw[:200]!r}") from None

    def list_artifacts(self, tag: str | None = None) -> list[dict[str, Any]]:
        q = f"?tag={urllib.parse.quote(tag)}" if tag else ""
        got = self._call("GET", f"/api/artifacts{q}")
        items = got.get("artifacts") if isinstance(got, dict) else None
        return items if isinstance(items, list) else []

    def create(self, body: dict[str, Any]) -> str:
        got = self._call("POST", "/api/artifacts", body)
        slug = got.get("slug") or (got.get("artifact") or {}).get("slug")
        if not slug:
            raise GatewayError(f"create returned no slug: {str(got)[:200]}")
        return str(slug)

    def update(self, slug: str, body: dict[str, Any]) -> None:
        self._call("PATCH", f"/api/artifacts/{urllib.parse.quote(slug)}", body)

    def delete(self, slug: str) -> None:
        self._call("DELETE", f"/api/artifacts/{urllib.parse.quote(slug)}")

    def get_config(self) -> dict[str, Any]:
        got = self._call("GET", f"/api/apps/{APP}/config")
        return got if isinstance(got, dict) else {}

    def put_config(self, doc: dict[str, Any]) -> None:
        self._call("PUT", f"/api/apps/{APP}/config", doc)

    def health(self) -> bool:
        try:
            got = self._call("GET", f"/api/apps/{APP}/health")
        except GatewayError:
            return False
        return bool(isinstance(got, dict) and got.get("ok"))


class GatewayError(RuntimeError):
    pass


def resolve_auth(token_cmd: str, base_override: str) -> Gateway:
    """Mint a session and return a client, without ever exposing the token.

    `kirocrew token` prints a dashboard URL carrying `?token=`. The origin of
    that URL is the gateway as IT sees itself; `--base-url` overrides it for the
    tunnel case, where the token is minted on the far end but the port you
    connect to — and therefore the cookie NAME — is local.
    """
    raw = os.environ.get("KIROCREW_TOKEN_URL", "").strip()
    if not raw:
        try:
            proc = subprocess.run(
                token_cmd, shell=True, capture_output=True, text=True, timeout=60, check=False
            )
        except subprocess.TimeoutExpired:
            raise GatewayError(f"`{token_cmd}` timed out after 60s") from None
        if proc.returncode != 0:
            raise GatewayError(
                f"`{token_cmd}` exited {proc.returncode}. Is that gateway running?\n"
                f"       {proc.stderr.strip()[:300]}"
            )
        found = re.search(r"https?://\S+", proc.stdout)
        if not found:
            raise GatewayError(f"`{token_cmd}` printed no dashboard URL")
        raw = found.group(0)

    parsed = urllib.parse.urlsplit(raw)
    token = urllib.parse.parse_qs(parsed.query).get("token", [""])[0]
    if not token:
        raise GatewayError("the dashboard URL carries no ?token= value")

    base = base_override.rstrip("/") or f"{parsed.scheme}://{parsed.netloc}"
    # The cookie is named for the port the REQUEST goes to, not the gateway's own
    # listen port — so it must be derived from `base`, after the override.
    port = urllib.parse.urlsplit(base).port
    if port is None:
        port = 443 if base.startswith("https") else 80
    return Gateway(base, f"mc_token_{port}={token}")


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------


class Item:
    """One local file and everything the gateway needs to hold it."""

    def __init__(self, path: Path, num: str, cls: str, rel: str, dataset: str) -> None:
        self.path = path
        self.num = num
        self.cls = cls
        self.rel = rel
        self.slug = slug_for(num, rel)
        self.name = name_for(num, cls, rel)
        self.kind = KIND_BY_EXT.get(path.suffix.lower(), "text")
        self.size = path.stat().st_size
        self.dataset = dataset
        self.action = "create"
        self.problem = ""
        self._content: str | None = None

    @property
    def tags(self) -> list[str]:
        # 4 of the 16 `artifacts.MAX_TAGS`, all legal under `_TAG_RE` (which
        # permits `_` and `:` but never `/`).
        ext = self.path.suffix.lower().lstrip(".") or "none"
        return ["psr-source", f"psr:{self.cls}", self.dataset, f"fmt:{ext}"]

    @property
    def folder(self) -> str:
        return f"PSR/{self.dataset}/{self.num}-{self.cls}"

    def read(self) -> str:
        """Decode strictly. A mojibake source is worse than a reported skip."""
        if self._content is None:
            self._content = self.path.read_text(encoding="utf-8")
        return self._content

    def body(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "kind": self.kind,
            "content": self.read(),
            "description": (
                f"{self.cls} signal source - {self.dataset}/{self.num}-{self.cls}/{self.rel} "
                f"({self.size} bytes). Local origin: {self.path}"
            ),
            "tags": self.tags,
            "folder": self.folder,
            "source": "import",
        }


def collect(
    data_dir: Path, dataset: str, include_extras: bool, include_derived: bool
) -> list[Item]:
    """Walk the tree and build the plan, in class order then path order."""
    items: list[Item] = []
    for child in sorted(data_dir.iterdir()):
        if not child.is_dir():
            continue
        head = child.name[:2]
        cls = CLASS_BY_NUM.get(head)
        if cls is None:
            if not (include_extras and child.name in EXTRA_DIRS):
                continue
            # An extra directory has no class of its own; file it under ambient,
            # which is the framework's bucket for weak/derived context.
            head, cls = "06", "ambient"
        base = child
        for path in sorted(p for p in child.rglob("*") if p.is_file()):
            if path.suffix.lower() in SKIP_EXT or path.name.startswith("."):
                continue
            rel = str(path.relative_to(base))
            if child.name in EXTRA_DIRS:
                rel = f"{child.name}/{rel}"
            item = Item(path, head, cls, rel, dataset)
            if item.size > CONTENT_MAX:
                item.problem = f"exceeds the {CONTENT_MAX} byte artifact cap"
            elif not include_derived and is_normalized_psr_output(path):
                item.problem = (
                    "already a normalized PSR signal set - indexing it would "
                    "double-count its raw sources as corroboration (--include-derived "
                    "to load anyway)"
                )
            else:
                try:
                    item.read()
                except (UnicodeDecodeError, OSError) as exc:
                    item.problem = f"unreadable as utf-8 text: {exc}"
            items.append(item)
    return items


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def human(n: int) -> str:
    for unit in ("B", "K", "M"):
        if n < 1024 or unit == "M":
            return f"{n}{unit}" if unit == "B" else f"{n:.0f}{unit}"
        n //= 1024
    return f"{n}B"


def report(items: list[Item], stale: list[dict[str, Any]], dry: bool) -> None:
    # 18 columns because `01 customer_demand` is the longest label the closed
    # class vocabulary can produce; a narrower field shears the header off it.
    print(f"\n  {'CLASS':<18} {'KIND':<9} {'SIZE':>6}  {'DO':<7} SLUG")
    print(f"  {'-' * 18} {'-' * 9} {'-' * 6}  {'-' * 7} {'-' * 46}")
    current = ""
    for it in items:
        label = f"{it.num} {it.cls}" if it.cls != current else ""
        current = it.cls
        action = "SKIP" if it.problem else it.action
        print(f"  {label:<18} {it.kind:<9} {human(it.size):>6}  {action:<7} {it.slug}")
        if it.problem:
            print(f"  {'':<18} {'':<9} {'':>6}  {'':<7} !! {it.problem}")

    counts: dict[str, int] = {}
    for it in items:
        if not it.problem:
            counts[it.cls] = counts.get(it.cls, 0) + 1
    print("\n  per class: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    creates = sum(1 for i in items if not i.problem and i.action == "create")
    updates = sum(1 for i in items if not i.problem and i.action == "update")
    skips = sum(1 for i in items if i.problem)
    print(f"  {creates} to create, {updates} to update, {skips} skipped")
    if stale:
        print(f"\n  {len(stale)} tagged artifact(s) no longer in the tree:")
        for art in stale:
            print(f"    - {art.get('slug')}  {art.get('name')}")
        print("    (removed only with --prune)")
    if dry:
        print("\n  DRY RUN — nothing was written. Re-run with --yes.")


# --------------------------------------------------------------------------
# Config wiring
# --------------------------------------------------------------------------


def wire_config(
    gw: Gateway, items: list[Item], workspace: str, dry: bool, if_unconfigured: bool = False
) -> None:
    """Point the six classes at the uploaded artifacts.

    READ-MODIFY-WRITE, always. `PUT /api/apps/<app>/config` replaces the WHOLE
    document, and both views of this app persist through it — a bare PUT of just
    `psr` destroys the charter, the per-loop configuration and the `_units`
    fallback ledger. Only `psr.workspaces[<workspace>].sources` is touched here;
    `notes`, `_spawn_id`, `last_generated` and every other workspace are carried
    through untouched.
    """
    env = gw.get_config()
    psr = env.get("psr") if isinstance(env.get("psr"), dict) else {}
    workspaces = psr.get("workspaces") if isinstance(psr.get("workspaces"), dict) else {}
    prior = workspaces.get(workspace) if isinstance(workspaces.get(workspace), dict) else {}
    replaced = sum(
        len(v) for v in (prior.get("sources") or {}).values() if isinstance(v, list)
    )
    if if_unconfigured and replaced:
        print(
            f"\n  config: workspace {workspace} already has {replaced} source(s); "
            "--if-unconfigured, left untouched."
        )
        print("          (re-run without --if-unconfigured to replace them)")
        return

    sources: dict[str, list[dict[str, str]]] = {cls: [] for cls in CLASS_BY_NUM.values()}
    for it in items:
        if it.problem:
            continue
        sources[it.cls].append({"type": "artifact", "slug": it.slug, "name": it.name})

    entry = dict(prior)
    entry["sources"] = sources
    entry.setdefault("name", Path(workspace).name or "project")
    entry.setdefault("created_at", "1970-01-01T00:00:00Z")

    total = sum(len(v) for v in sources.values())
    print(f"\n  config: workspace {workspace}")
    print(f"          {replaced} existing source(s) -> {total} artifact source(s)")
    for cls, entries in sources.items():
        print(f"            {cls:<16} {len(entries)}")
    canary = "present" if env.get("charter") else "absent"
    print(f"          charter in the envelope being rewritten: {canary}")

    if dry:
        print("          DRY RUN — config not written.")
        return

    env["psr"] = {
        **psr,
        "workspaces": {**workspaces, workspace: entry},
        "active_workspace": workspace,
    }
    gw.put_config(env)
    back = gw.get_config()
    wrote = (
        ((back.get("psr") or {}).get("workspaces") or {}).get(workspace) or {}
    ).get("sources") or {}
    landed = sum(len(v) for v in wrote.values() if isinstance(v, list))
    print(f"          wrote and re-read {landed} source(s).")
    if bool(env.get("charter")) and not back.get("charter"):
        print("          !! the charter did NOT survive the write — check the app config.")


# --------------------------------------------------------------------------


def resolve_data_dir(raw: str) -> Path | None:
    """Resolve the tree to load, or print why it could not be found.

    Always returns an ABSOLUTE path, because `--workspace` defaults to a path
    derived from it (`default_workspace`) and the console refuses a workspace
    that is not absolute.
    """
    if raw:
        path = Path(raw).expanduser().resolve()
        if not path.is_dir():
            print(f"  !! {path} is not a directory")
            return None
        return path
    for candidate in DATA_DIR_CANDIDATES:
        path = Path(candidate).expanduser().resolve()
        if path.is_dir():
            return path
    print("  !! no signal-data tree found. Looked for:")
    for candidate in DATA_DIR_CANDIDATES:
        # Resolved, so the `./signal-data` candidate names the actual directory it
        # probed rather than a relative fragment the reader has to re-derive.
        print(f"       {Path(candidate).expanduser().resolve()}")
    print("     Pass the path explicitly:  --data-dir /path/to/signal-data")
    return None


def default_workspace(data_dir: Path) -> str:
    """`<data_dir.parent>/src` when it exists — the git repo the Build loop
    targets (GETTING_STARTED §3, demo-reset.sh) — else the data dir's parent."""
    src = data_dir.parent / "src"
    return str(src if src.is_dir() else data_dir.parent)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Load a signal-data tree into a KiroCrew gateway as artifacts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--data-dir",
        default="",
        help="the signal-data tree. Default: the first of "
        + ", ".join(DATA_DIR_CANDIDATES)
        + " that exists",
    )
    ap.add_argument(
        "--dataset",
        default="",
        help="tag + folder namespace (default: the data dir's parent name)",
    )
    ap.add_argument(
        "--token-cmd",
        default="kirocrew token",
        help="command that prints a dashboard URL. For a remote gateway: "
        "'ssh HOST kirocrew token' (default: %(default)s)",
    )
    ap.add_argument(
        "--base-url",
        default="",
        help="origin to talk to, overriding the token URL's. Use this when the "
        "gateway is reached through an SSH tunnel, e.g. http://localhost:5476",
    )
    ap.add_argument(
        "--workspace",
        default="",
        help="PSR workspace path to wire sources onto (default: <data dir's parent>/src "
        "if it exists, else the data dir's parent)",
    )
    ap.add_argument("--include-extras", action="store_true", help=f"also load {EXTRA_DIRS}")
    ap.add_argument(
        "--include-derived",
        action="store_true",
        help="also load files that are already normalized PSR output (contaminates scoring)",
    )
    ap.add_argument(
        "--wire-config",
        action="store_true",
        help="assign the uploaded artifacts to their signal classes in the app config",
    )
    ap.add_argument(
        "--if-unconfigured",
        action="store_true",
        help="with --wire-config: skip the wiring when the workspace already has any "
        "sources, so a re-run never clobbers manual edits",
    )
    ap.add_argument(
        "--prune",
        action="store_true",
        help="DELETE tagged artifacts no longer present in the tree",
    )
    ap.add_argument("--yes", action="store_true", help="actually write (default: dry run)")
    args = ap.parse_args()
    if args.if_unconfigured and not args.wire_config:
        ap.error("--if-unconfigured requires --wire-config")

    data_dir = resolve_data_dir(args.data_dir)
    if data_dir is None:
        return 2
    # `--workspace` must end up ABSOLUTE: the console rejects anything that does
    # not start with `/` (`psr.isAbsolutePath`), and `data_dir` is resolved above
    # precisely so a relative `--data-dir` cannot yield a relative default here.
    dataset = slugify(args.dataset or data_dir.parent.name) or "dataset"
    workspace = args.workspace or default_workspace(data_dir)
    dry = not args.yes

    try:
        gw = resolve_auth(args.token_cmd, args.base_url)
    except GatewayError as exc:
        print(f"  !! {exc}")
        return 2

    print(f"  gateway   {gw.base}")
    print(f"  data      {data_dir}")
    print(f"  dataset   {dataset}")
    if args.wire_config:
        print(f"  workspace {workspace}")
    if not gw.health():
        print(f"  !! the {APP} backend is not answering /health at {gw.base}.")
        print("     Artifacts may still load, but --wire-config needs the app installed.")

    items = collect(data_dir, dataset, args.include_extras, args.include_derived)
    if not items:
        print(f"  !! no loadable files under {data_dir} (expected 01-..06-* directories)")
        return 2

    try:
        existing = gw.list_artifacts()
    except GatewayError as exc:
        print(f"  !! {exc}")
        print("     If this is HTTP 401/403, the cookie port does not match --base-url.")
        return 2
    by_slug = {str(a.get("slug")): a for a in existing if a.get("slug")}
    for it in items:
        if it.slug in by_slug:
            it.action = "update"

    planned = {it.slug for it in items if not it.problem}
    stale = [
        a
        for a in existing
        if dataset in (a.get("tags") or [])
        and "psr-source" in (a.get("tags") or [])
        and str(a.get("slug")) not in planned
    ]

    report(items, stale, dry)

    failed = 0
    if not dry:
        print()
        written = 0
        for it in (i for i in items if not i.problem):
            try:
                if it.action == "update":
                    gw.update(it.slug, it.body())
                else:
                    gw.create(it.body())
            except GatewayError as exc:
                failed += 1
                print(f"  !! {it.slug}: {exc}")
                continue
            written += 1
            print(f"  {it.action}d {it.slug}", flush=True)
        print(f"\n  {written} artifact(s) written, {failed} failed")

        if args.prune and stale:
            for art in stale:
                try:
                    gw.delete(str(art["slug"]))
                    print(f"  deleted {art['slug']}")
                except GatewayError as exc:
                    print(f"  !! delete {art['slug']}: {exc}")

    if args.wire_config and failed:
        print(f"  !! config not wired: {failed} upload(s) failed — re-run to retry")
        return 1

    if args.wire_config:
        try:
            wire_config(gw, items, workspace, dry, args.if_unconfigured)
        except GatewayError as exc:
            print(f"  !! config: {exc}")
            return 1

    if dry:
        print()
    else:
        print("\n  Refresh the dashboard tab, then Signal repository -> Generate.")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  interrupted")
        sys.exit(130)
