"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    graded = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS]
    pairs, tags = {}, {}
    for name, report in (("PR", pr), ("baseline", base)):
        try:
            manifest, rows, metrics = report["manifest"], report["rows"], report["metrics"]
            seeds, items = manifest["seeds"], manifest["items"]
            if not isinstance(items, int) or isinstance(items, bool) or items < 1:
                raise ValueError("invalid item count")
            if not seeds or any(not isinstance(x, int) or isinstance(x, bool) for x in seeds) or len(seeds) != len(set(seeds)):
                raise ValueError("invalid or duplicate manifest seeds")
            if len(rows) != items * len(seeds):
                problems.append(f"{name}: row count differs from items x seeds")
            if report.get("evaluator_failures"):
                problems.append(f"{name}: evaluator_failures is nonempty")
            for mid, val in metrics.items():
                if not isinstance(val, (int, float)) or not math.isfinite(val):
                    problems.append(f"{name}: nonfinite/missing metric {mid}")
            for metric in spec["metrics"]:
                if metric["id"] not in metrics:
                    problems.append(f"{name}: missing metric {metric['id']}")
            counts, per_item_tags = Counter(), {}
            for row in rows:
                pair = row["item_id"], row["seed"]
                counts[pair] += 1
                row_tags = row.get("slices", [])
                if not isinstance(row_tags, list) or any(not isinstance(t, str) for t in row_tags):
                    raise ValueError("invalid slice tags")
                frozen_tags = frozenset(row_tags)
                if pair[0] in per_item_tags and per_item_tags[pair[0]] != frozen_tags:
                    problems.append(f"{name}: inconsistent tags within item {pair[0]}")
                per_item_tags[pair[0]] = frozen_tags
                for mid in graded:
                    if type(row.get(mid)) is not bool:
                        problems.append(f"{name}: missing/invalid row metric {mid} at {pair}")
                if "cost" in row and (not isinstance(row["cost"], (int, float)) or not math.isfinite(row["cost"]) or row["cost"] < 0):
                    problems.append(f"{name}: invalid row cost")
            item_ids = set(per_item_tags)
            expected = {(item, seed) for item in item_ids for seed in seeds}
            if len(item_ids) != items or set(counts) != expected or any(n != 1 for n in counts.values()):
                problems.append(f"{name}: missing or duplicate item/seed pairs")
            pairs[name], tags[name] = set(counts), per_item_tags
            # Detect changed aggregate numbers even when the rows were left intact.
            if not problems and all("cost" in row for row in rows):
                computed = aggregate(rows, graded, k_values=spec.get("pass_k", []))
                for mid, value in computed.items():
                    if mid in metrics and metrics[mid] != value:
                        problems.append(f"{name}: aggregate does not match rows: {mid}")
        except (KeyError, TypeError, ValueError, AttributeError):
            problems.append(f"{name}: malformed report")
    if pairs.get("PR") != pairs.get("baseline"):
        problems.append("PR item/seed set differs from baseline")
    if tags.get("PR") != tags.get("baseline"):
        problems.append("PR slice tags differ from baseline")
    if pr.get("manifest", {}).get("seeds") != base.get("manifest", {}).get("seeds"):
        problems.append("PR manifest seeds differ from baseline")
    if base_spec and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems += _ratchet(spec, base_spec)
    return list(dict.fromkeys(problems))


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices", []):
        sid = f"slice:{sl['name']}/{sl['metric']}"
        a = per_item(pr, sl["metric"], slice_name=sl["name"])
        b = per_item(base, sl["metric"], slice_name=sl["name"])
        failed, note = not a or set(a) != set(b), ""
        value = sum(a.values()) / len(a) if a else None
        if value is not None and "min" in sl and value < sl["min"]:
            failed = True
        if value is not None and sl.get("no_significant_drop") and set(a) == set(b):
            keys = sorted(a)
            delta, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                confidence=bs.get("confidence", 0.95))
            note = f"delta={delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            failed |= hi < 0
        if failed and sl.get("blocking"):
            blocked.append(sid)
        lines.append(f"  {sid}: {value} {note} {'BLOCK' if failed and sl.get('blocking') else 'warn' if failed else 'ok'}")
    return blocked, lines



def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    """Existing metrics/slices may only become stricter within an eval-set version."""
    problems = []
    for section in ("metrics", "slices"):
        identity = (lambda m: m["id"]) if section == "metrics" else (lambda m: (m["name"], m["metric"]))
        current = {identity(m): m for m in spec.get(section, [])}
        for before in base_spec.get(section, []):
            key = identity(before)
            after = current.get(key)
            if after is None:
                problems.append(f"ratchet: removed {section} {key}")
                continue
            if before.get("blocking") and not after.get("blocking"):
                problems.append(f"ratchet: disabled blocking {key}")
            old = before.get("threshold", {}) if section == "metrics" else before
            new = after.get("threshold", {}) if section == "metrics" else after
            for bound in ("min", "max", "max_increase"):
                if bound in old and (bound not in new or
                    (new[bound] < old[bound] if bound == "min" else new[bound] > old[bound])):
                    problems.append(f"ratchet: loosened {key}/{bound}")
            if old.get("no_significant_drop") and not new.get("no_significant_drop"):
                problems.append(f"ratchet: removed no_significant_drop {key}")
    return problems


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    if pr["manifest"].get("eval_set_sha") != base["manifest"].get("eval_set_sha"):
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                               confidence=bs.get("confidence", 0.95))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
