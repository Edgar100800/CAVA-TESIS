import numpy as np

from topicagg.multimodal_manager import _collapse_runs, manage


def _blocks(sizes, dim=8, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in sizes:
        c = rng.normal(size=dim)
        rows += [c + 0.01 * rng.normal(size=dim) for _ in range(s)]
    return np.asarray(rows, np.float32)


def test_collapse_runs_one_cut_per_run():
    passing = np.array([0, 1, 1, 1, 0, 0, 1, 0], bool)
    votes = np.array([0, 1, 2, 1, 0, 0, 2, 0], np.float32)
    assert _collapse_runs(passing, votes) == [2, 6]


def test_consensus_one_cut_per_agreed_boundary():
    x = _blocks([10, 10, 10])
    plan = manage({"visual": x, "transcript": x.copy()}, percentile=90,
                  link_quorum=2, tolerance_bins=1)
    cuts = plan.consensus_cuts
    assert all(b - a > 1 for a, b in zip(cuts, cuts[1:])), cuts
    assert len(cuts) <= len(plan.per_signal_cuts["visual"])


def test_flat_signal_emits_no_cuts():
    x = _blocks([10, 10])
    plan = manage({"visual": x, "transcript": np.ones_like(x)}, percentile=50)
    assert plan.per_signal_cuts["transcript"] == []


def test_signal_votes_once_per_index():
    # 3 signals -> majority 2. One signal cutting at 6 and 8 (windows overlap at 7)
    # must not confirm a cut on its own.
    a = _blocks([6, 2, 12], seed=1)
    flat = np.ones_like(a)
    plan = manage({"visual": a, "transcript": flat, "ocr": flat.copy()},
                  percentile=80, min_gap=2, link_quorum=2, tolerance_bins=1)
    assert plan.per_signal_cuts["visual"] == [6, 8]
    assert plan.consensus_cuts == []


def test_min_gap_respected():
    a = _blocks([6, 2, 12], seed=1)
    for gap in (2, 3):
        cuts = manage({"visual": a}, percentile=50, min_gap=gap).per_signal_cuts["visual"]
        assert all(b - a_ >= gap for a_, b in zip(cuts, cuts[1:])), (gap, cuts)
