"""Generate supplementary evidence; never edit the resulting JSON by hand.

Run from src: python scripts/day09_evidence.py
This uses provided bug switches for diagnosis, without editing Lab8 or variants.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic_evals.evaluators import EvaluatorContext

from lab8.shapes import SHAPES
from lab9 import gate, stats, variants
from lab9.eval import load_spec, load_world, make_task, per_item, run_eval
from lab9.graders import GRADERS
from lab9.judge import calibrate
from lab9.mutation import detect, scorecard
from lab9.traps import build as build_traps
from lab9.variant_agent import make_shape


def main() -> None:
    variants.register()
    spec = load_spec()
    v2 = load_spec(Path("config/metric_spec_v2.yaml"))
    base = json.loads(Path("reports/baseline_v1.json").read_text())
    base2 = json.loads(Path("reports/baseline_v2.json").read_text())
    diagnostics = [
        ("FM-01", "leaky_trace", "C-001", "debug_claim_row"),
        ("FM-02", "ignore_denied", "C-007", "reply"),
        ("FM-03", "ticket_trust", "C-002", "model_override"),
        ("FM-04", "round_down", "C-001", "proposal"),
        ("FM-05", "pre_deducted", "C-014", "proposal"),
        ("FM-06", "stale_clause", "C-006", "quote"),
        ("FM-07", "sibling_refund", "C-001", "batch_refund"),
        ("FM-08", "misreport", "C-008", "reply"),
        ("FM-09", None, "C-110", "investigator"),
    ]
    evidence = []
    world, claims = load_world(v2)
    labels = json.loads(Path(v2["labels"]).read_text())
    with tempfile.TemporaryDirectory(prefix="day09-evidence-") as tmp:
        for fm, bug, claim, kind in diagnostics:
            name = f"diagnostic_{fm.lower().replace('-', '')}"
            SHAPES[name] = make_shape(name, {"no_override", *([bug] if bug else [])})
            trial = make_task(name, world, claims, labels, Path(tmp))({"claim_id": claim, "seed": 11})
            ctx = EvaluatorContext(name=name, inputs={}, metadata=None, expected_output=labels[claim],
                output=trial, duration=0.0, _span_tree=None, attributes={}, metrics={})
            events = trial["events"]
            index = next((i for i, event in enumerate(events, 1) if event["kind"] == kind), None)
            if index is None:
                raise ValueError(f"{fm}: wanted {kind}, got {[e['kind'] for e in events]}")
            event = events[index - 1]
            evidence.append({"fm": fm, "shape": name, "claim": claim, "seed": 11,
                "run_id": trial["result"]["run_id"], "event_index": index, "event_kind": kind,
                # Do not copy diagnostic FM-01's deliberately secret-bearing payload.
                "event_payload_keys": sorted(event.get("payload", {})),
                "status": trial["result"]["status"], "expected_status": labels[claim]["status"],
                "proposal": trial["result"]["proposal_amount"], "expected_proposal": labels[claim]["proposal_amount"],
                "ledger": trial["snapshot"]["refund_vnd"], "expected_ledger": labels[claim]["refund_vnd"],
                "lab8_pass": trial["lab8_pass"], "lab8_reason": trial["lab8_reason"].split(":", 1)[0],
                "graders": {mid: bool(grader().evaluate(ctx).value) for mid, grader in GRADERS.items()},
                "evidence_type": "observed_injected_failure" if bug else "negative_scope_control"})
    comparisons = {}
    for shape in ("fixed", "seeded_regression"):
        pr = json.loads(Path(f"reports/eval_{shape}.json").read_text())
        a, b = per_item(pr, "pass_rate"), per_item(base, "pass_rate")
        keys = sorted(a)
        delta, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys])
        blocked, lines = gate.check(pr, base, spec)
        comparisons[shape] = {"run_id": pr["run_id"], "delta": delta, "ci95": [lo, hi],
                              "exit": int(bool(blocked)), "blocked": blocked, "gate_output": lines}
    alt = run_eval("swarm", v2, [66, 77, 88, 99, 110])
    detection, false_alarms = detect(spec)
    slice_report = json.loads(Path("reports/eval_slice_regression.json").read_text())
    traps = {}
    for name, (pr, loosened) in build_traps(slice_report, v2).items():
        blocked, lines = gate.check(pr, base2, loosened or v2, v2 if loosened else None)
        traps[name] = {"exit": int(bool(blocked)), "blocked": blocked, "gate_output": lines}
    report = {"owner": "Hoang Minh / 2A202604103", "kind": "local_assistant_run",
        "baseline_run_ids": [base["run_id"], base2["run_id"]], "diagnostics": evidence,
        "calibration": {"tone": calibrate(Path("data/eval/judge_tone_public.csv")),
                        "helpful": calibrate(Path("data/eval/judge_helpful_public.csv"))},
        "comparisons": comparisons, "detection": detection, "false_alarms": false_alarms,
        "aa": {"base_seeds": base2["manifest"]["seeds"], "alternate_seeds": alt["manifest"]["seeds"],
               "base_metrics": base2["metrics"], "alternate_metrics": alt["metrics"],
               "delta": {mid: alt["metrics"][mid] - value for mid, value in base2["metrics"].items()}},
        "scorecard": [{"shape": name, "expected": want, "actual": got, "blocked": why}
                      for name, want, got, why in scorecard(v2, base2, v2)], "traps": traps}
    out = Path("reports/day09_evidence.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}; {len(evidence)} diagnostic examples; detection={detection:.0%}, false alarms={false_alarms:.0%}")


if __name__ == "__main__":
    main()
