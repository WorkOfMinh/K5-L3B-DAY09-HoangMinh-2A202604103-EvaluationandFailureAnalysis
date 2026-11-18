"""Gate must reject corrupted evidence without recognizing variant names."""

import copy

import pytest

pytestmark = pytest.mark.student


def _fixture():
    from tests.test_lab9_advanced import ROWS, SPEC, _report
    return _report(copy.deepcopy(ROWS), {"pass_rate": 1.0}), copy.deepcopy(SPEC)


@pytest.mark.parametrize("mode", ["duplicate", "null", "grader_error", "slice_tags", "inf"])
def test_lab9_advanced_blocks_corrupt_evidence(mode):
    from lab9.gate import integrity_check
    base, spec = _fixture()
    pr = copy.deepcopy(base)
    if mode == "duplicate":
        pr["rows"][-1] = copy.deepcopy(pr["rows"][0])
    elif mode == "null":
        pr["rows"][0]["pass_rate"] = None
    elif mode == "grader_error":
        pr["evaluator_failures"] = ["grader failed on otherwise green run"]
    elif mode == "slice_tags":
        for row in pr["rows"]:
            row["slices"] = []
    else:
        pr["metrics"]["pass_rate"] = float("inf")
    assert integrity_check(pr, base, spec)


@pytest.mark.parametrize("mode", ["drop_metric", "disable_block", "drop_slice", "drop_ci", "raise_max"])
def test_lab9_advanced_ratchet_retains_existing_constraints(mode):
    from lab9.gate import integrity_check
    base, spec = _fixture()
    spec["slices"] = [{"name": "denial", "metric": "pass_rate", "min": 0.8,
                       "no_significant_drop": True, "blocking": True}]
    spec["metrics"][0]["threshold"]["max"] = 1.0
    loose = copy.deepcopy(spec)
    if mode == "drop_metric":
        loose["metrics"] = []
    elif mode == "disable_block":
        loose["metrics"][0]["blocking"] = False
    elif mode == "drop_slice":
        loose["slices"] = []
    elif mode == "drop_ci":
        loose["slices"][0]["no_significant_drop"] = False
    else:
        loose["metrics"][0]["threshold"]["max"] = 2.0
    assert integrity_check(base, base, loose, spec)


@pytest.mark.parametrize("args", [(0, 0, 1), (5, -1, 1), (5, 6, 1), (5, 2, 0),
                                  (3, 1, 4), (5.0, 2, 1), (True, 0, 1)])
def test_lab9_advanced_both_pass_estimators_reject_bad_inputs(args):
    from lab9.stats import pass_at_k, pass_hat_k
    for fn in (pass_at_k, pass_hat_k):
        with pytest.raises(ValueError):
            fn(*args)
