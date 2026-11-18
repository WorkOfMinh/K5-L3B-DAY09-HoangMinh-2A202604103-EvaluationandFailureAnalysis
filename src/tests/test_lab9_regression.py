"""Individual regression checks: first wrong step, and reply versus ledger."""

import pytest

pytestmark = pytest.mark.student


def _ctx(trial, label):
    from pydantic_evals.evaluators import EvaluatorContext
    return EvaluatorContext(name="regression", inputs={}, metadata=None, expected_output=label,
                            output=trial, duration=0.0, _span_tree=None, attributes={}, metrics={})


def test_lab9_trace_c002_rejects_ticket_override_and_accepts_fixed():
    from lab9.graders import DbFactKept, RefundAmountCorrect
    from lab9.trace_case import investigate
    bad = investigate("seeded_regression", "C-002", 11)
    good = investigate("fixed", "C-002", 11)
    wrong = next((i, e) for i, e in enumerate(bad["trial"]["events"], 1)
                 if e["kind"] == "model_override")
    assert wrong[0] == 3
    assert wrong[1]["payload"]["delay_days"] == 5
    assert bad["trial"]["snapshot"]["refund_vnd"] == 20000
    assert good["trial"]["snapshot"]["refund_vnd"] == 0
    for grader in (DbFactKept(), RefundAmountCorrect()):
        assert grader.evaluate(_ctx(bad["trial"], bad["label"])).value is False
        assert grader.evaluate(_ctx(good["trial"], good["label"])).value is True


@pytest.mark.parametrize("amount,want", [(20000, True), (35000, False)])
def test_lab9_reply_uses_committed_amount_not_proposal(amount, want):
    from lab9.graders import ReplyAmountCorrect
    trial = {"result": {"status": "resolved", "proposal_amount": 35000},
             "snapshot": {"refund_vnd": 20000, "refund_count": 1},
             "events": [{"kind": "reply", "payload": {"text": f"Đã hoàn {amount:,} VND cho đơn O-107."}}]}
    assert ReplyAmountCorrect().evaluate(_ctx(trial, {})).value is want


def test_lab9_proposal_detects_prededuction_with_empty_ledger():
    from lab9.graders import ProposalCorrect
    from lab9.trace_case import investigate
    bad = investigate("seeded_regression", "C-013", 11)
    good = investigate("fixed", "C-013", 11)
    assert bad["trial"]["snapshot"]["refund_vnd"] == good["trial"]["snapshot"]["refund_vnd"] == 0
    assert ProposalCorrect().evaluate(_ctx(bad["trial"], bad["label"])).value is False
    assert ProposalCorrect().evaluate(_ctx(good["trial"], good["label"])).value is True
