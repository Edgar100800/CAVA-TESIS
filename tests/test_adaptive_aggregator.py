import numpy as np

from topicagg.adaptive_aggregator import aggregate


def _topic(rng, center, size, noise):
    return [center + noise * rng.normal(size=center.shape) for _ in range(size)]


def test_merges_within_topics_not_across():
    rng = np.random.default_rng(0)
    c1, c2 = rng.normal(size=16), rng.normal(size=16)
    x = np.asarray(_topic(rng, c1, 30, 0.2) + _topic(rng, c2, 30, 0.2), np.float32)
    init = list(range(3, 60, 3))  # over-segmented proposal, true cut at 30
    plan = aggregate({"visual": x, "dialogue": x + 0.05 * rng.normal(size=x.shape)},
                     {}, init, 60, rho=0.9)
    assert plan.cuts == [30]
    assert len(plan.levels) >= 2  # hierarchy recorded


def test_abstaining_voter_does_not_block():
    rng = np.random.default_rng(1)
    c1 = rng.normal(size=16)
    x = np.asarray(_topic(rng, c1, 20, 0.2), np.float32)
    silent = np.zeros_like(x)  # no dialogue at all -> abstains everywhere
    plan = aggregate({"visual": x, "dialogue": silent}, {}, [5, 10, 15], 20)
    assert plan.cuts == []
    assert all("dialogue" in m["abstain"] for m in plan.merges)


def test_boundary_voter_can_hold_a_cut():
    rng = np.random.default_rng(2)
    c1 = rng.normal(size=16)
    x = np.asarray(_topic(rng, c1, 20, 0.2), np.float32)
    score = np.zeros(19, np.float32)
    score[9] = 0.95  # strong boundary evidence between shots 9 and 10
    plan = aggregate({"visual": x}, {"segloop": (score, 0.5), "speech": (score, 0.5)},
                     [10], 20)
    assert plan.cuts == [10]  # 2 of 3 voters say stop


def test_divisive_splits_heterogeneous_stops_homogeneous():
    from topicagg.adaptive_aggregator import divisive
    rng = np.random.default_rng(3)
    cs = [rng.normal(size=16) for _ in range(4)]
    # 0-40 one homogeneous topic; 40-60 three short distinct topics
    x = np.asarray(_topic(rng, cs[0], 40, 0.2) + _topic(rng, cs[1], 7, 0.2)
                   + _topic(rng, cs[2], 7, 0.2) + _topic(rng, cs[3], 6, 0.2), np.float32)
    order = np.full(59, 0.1, np.float32)
    for c, s in ((40, 0.9), (47, 0.8), (54, 0.7), (20, 0.85)):  # 20 = strong but fake
        order[c - 1] = s
    plan = divisive({"visual": x, "dialogue": x + 0.05 * rng.normal(size=x.shape)},
                    {}, order, 60)
    assert plan.cuts == [40, 47, 54]
