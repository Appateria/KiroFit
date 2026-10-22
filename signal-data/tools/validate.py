#!/usr/bin/env python3
"""
Validates the Kiro Fit PSR synthetic dataset and writes signal-data/manifest.json.

Checks performed:
  1. Every .csv / .tsv parses and has a uniform column count.
  2. Every .jsonl parses line-by-line.
  3. Every .json / .yaml parses.
  4. signals.jsonl conforms to signal-store/signal.schema.json (structural check:
     required keys, enums, ranges — no external jsonschema dependency needed).
  5. signal_ids are unique; linked_signals resolve to real records.
  6. Every rejected signal has a matching record in rejections.jsonl.
  7. Every theme in the store appears in the index and vice versa.
  8. Every code_ref path exists in ../src (traceability into the real codebase).

    python3 signal-data/tools/validate.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SRC = REPO / "src"

errors: list[str] = []
warnings: list[str] = []
files: list[dict] = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def check_tabular(path: Path) -> int:
    delim = "\t" if path.suffix == ".tsv" else ","
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter=delim))
    if not rows:
        err(f"{path.relative_to(ROOT)}: empty")
        return 0
    width = len(rows[0])
    for i, row in enumerate(rows[1:], start=2):
        if len(row) != width:
            err(f"{path.relative_to(ROOT)}:{i}: {len(row)} fields, header has {width}")
    return len(rows) - 1


def check_jsonl(path: Path) -> int:
    n = 0
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            json.loads(line)
            n += 1
        except json.JSONDecodeError as exc:
            err(f"{path.relative_to(ROOT)}:{i}: invalid JSON — {exc}")
    return n


def walk():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = str(path.relative_to(ROOT))
        suffix = path.suffix.lower()
        records = None
        try:
            if suffix in (".csv", ".tsv"):
                records = check_tabular(path)
            elif suffix == ".jsonl":
                records = check_jsonl(path)
            elif suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            elif suffix in (".yaml", ".yml"):
                yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            err(f"{rel}: {type(exc).__name__}: {exc}")
        files.append({
            "path": rel,
            "format": suffix.lstrip(".") or "none",
            "bytes": path.stat().st_size,
            "records": records,
            "sha256_16": sha256(path),
        })


def check_store():
    schema = json.loads((ROOT / "signal-store" / "signal.schema.json").read_text())
    props = schema["properties"]
    required = set(schema["required"])
    recs = [json.loads(l) for l in (ROOT / "signal-store" / "signals.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]

    ids = set()
    for r in recs:
        ref = r.get("source_ref", "?")
        missing = required - r.keys()
        if missing:
            err(f"signals.jsonl[{ref}]: missing required keys {sorted(missing)}")
        unknown = r.keys() - props.keys()
        if unknown:
            err(f"signals.jsonl[{ref}]: unknown keys {sorted(unknown)}")
        if r["class"] not in props["class"]["enum"]:
            err(f"signals.jsonl[{ref}]: bad class {r['class']}")
        if r["status"] not in props["status"]["enum"]:
            err(f"signals.jsonl[{ref}]: bad status {r['status']}")
        if r["provenance_tier"] not in props["provenance_tier"]["enum"]:
            err(f"signals.jsonl[{ref}]: bad provenance_tier {r['provenance_tier']}")
        if not 0 <= r["weight"] <= 1:
            err(f"signals.jsonl[{ref}]: weight {r['weight']} outside 0..1")
        ent = r["entities"]
        if set(ent) != set(props["entities"]["properties"]):
            err(f"signals.jsonl[{ref}]: entities keys {sorted(ent)}")
        if ent["severity_tag"] not in props["entities"]["properties"]["severity_tag"]["enum"]:
            err(f"signals.jsonl[{ref}]: bad severity_tag {ent['severity_tag']}")
        if ent["persona"] not in props["entities"]["properties"]["persona"]["enum"]:
            err(f"signals.jsonl[{ref}]: bad persona {ent['persona']}")
        if ent["feature_area"] == "unmapped":
            warn(f"signals.jsonl[{ref}]: theme {r['theme']} has no feature_area mapping")
        try:
            datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        except ValueError:
            err(f"signals.jsonl[{ref}]: bad created_at {r['created_at']}")
        if r["signal_id"] in ids:
            err(f"signals.jsonl[{ref}]: duplicate signal_id {r['signal_id']}")
        ids.add(r["signal_id"])

    for r in recs:
        for link in r["linked_signals"]:
            if link not in ids:
                err(f"signals.jsonl[{r['source_ref']}]: dangling link {link}")
            if link == r["signal_id"]:
                err(f"signals.jsonl[{r['source_ref']}]: self-link")

    rejections = [json.loads(l) for l in (ROOT / "signal-store" / "rejections.jsonl")
                  .read_text(encoding="utf-8").splitlines() if l.strip()]
    rejected_ids = {i for rj in rejections for i in rj["signal_ids"]}
    for r in recs:
        if r["status"] == "rejected" and r["signal_id"] not in rejected_ids:
            err(f"signals.jsonl[{r['source_ref']}]: status=rejected with no rejection record")

    idx = list(csv.DictReader((ROOT / "signal-index" / "signal-index.csv")
                             .open(encoding="utf-8")))
    store_themes = {r["theme"] for r in recs}
    idx_themes = {r["theme"] for r in idx}
    for t in store_themes - idx_themes:
        err(f"theme {t} in store but not in index")
    for t in idx_themes - store_themes:
        err(f"theme {t} in index but not in store")

    counts = Counter(r["theme"] for r in recs)
    for row in idx:
        if int(row["signal_count"]) != counts[row["theme"]]:
            err(f"index[{row['theme']}]: signal_count {row['signal_count']} != "
                f"{counts[row['theme']]} in store")

    ranks = [int(r["rank"]) for r in idx]
    if ranks != sorted(ranks) or ranks != list(range(1, len(ranks) + 1)):
        err("signal-index.csv: ranks are not a contiguous ascending sequence")
    weights = [float(r["weight"]) for r in idx]
    if weights != sorted(weights, reverse=True):
        err("signal-index.csv: rows are not ordered by descending weight")

    missing_paths = set()
    for r in recs:
        for ref in r.get("code_refs", []):
            p = ref.split(":")[0]
            if not (SRC / p).exists():
                missing_paths.add(p)
    for p in sorted(missing_paths):
        warn(f"code_ref points at a path that does not exist in src/: {p}")

    return recs, rejections, idx


def write_manifest(recs, rejections, idx):
    by_class = Counter(r["class"] for r in recs)
    by_source = Counter(r["source"] for r in recs)
    by_status = Counter(r["status"] for r in recs)
    by_provenance = Counter(r["provenance_tier"] for r in recs)
    by_format = Counter(f["format"] for f in files)

    manifest = {
        "dataset": "Kiro Fit — Product Signal Repository (synthetic)",
        "workload": "src/ (Kiro Fit: Ionic 8 + Vue 3 SPA on AWS CDK / AppSync / DynamoDB / Cognito)",
        "spec": "psr.md",
        "synthetic": True,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of_date": "2026-08-27",
        "observation_window": {"start": "2026-04-01", "end": "2026-08-26"},
        "totals": {
            "files": len(files),
            "bytes": sum(f["bytes"] for f in files),
            "normalized_signals": len(recs),
            "rejection_records": len(rejections),
            "themes": len(idx),
            "distinct_sources": len(by_source),
        },
        "formats": dict(sorted(by_format.items())),
        "signals_by_class": dict(sorted(by_class.items())),
        "signals_by_status": dict(sorted(by_status.items())),
        "signals_by_provenance_tier": dict(sorted(by_provenance.items())),
        "signals_by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
        "top_themes": [{"rank": int(r["rank"]), "theme": r["theme"],
                        "weight": float(r["weight"]), "classes": int(r["class_count"]),
                        "signals": int(r["signal_count"]), "status": r["status"]}
                       for r in idx[:10]],
        "regeneration": [
            "python3 signal-data/tools/generate_timeseries.py   # volumetric telemetry",
            "python3 signal-data/tools/build_signal_store.py    # store + index",
            "python3 signal-data/tools/validate.py              # checks + this manifest",
        ],
        "files": files,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    walk()
    recs, rejections, idx = check_store()
    m = write_manifest(recs, rejections, idx)

    print(f"files checked        : {m['totals']['files']}")
    print(f"formats              : {', '.join(f'{k}:{v}' for k, v in m['formats'].items())}")
    print(f"normalized signals   : {m['totals']['normalized_signals']}")
    print(f"themes               : {m['totals']['themes']}")
    print(f"distinct sources     : {m['totals']['distinct_sources']}")
    print(f"by class             : {m['signals_by_class']}")
    print(f"by status            : {m['signals_by_status']}")
    print(f"total bytes          : {m['totals']['bytes']:,}")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
