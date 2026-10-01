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


def _partition(labels):
    seen, out = {}, []
    for lab in labels:
        seen.setdefault(int(lab), len(seen))
        out.append(seen[int(lab)])
    return out


def test_default_behaviour_matches_v21_golden():
    import json
    from pathlib import Path
    cases = json.loads((Path(__file__).parent / "fixtures" / "manage_golden_v21.json").read_text())
    for c in cases:
        sig = {k: np.asarray(v, np.float32) for k, v in c["signals"].items()}
        plan = manage(sig, speech_times=c["speech_times"], **c["kw"])
        assert _partition(plan.labels) == _partition(c["labels"])
        assert plan.consensus_cuts == c["consensus_cuts"]
        assert plan.per_signal_cuts == c["per_signal_cuts"]
        assert [g.segment_indices for g in plan.groups] == c["groups"]
        assert [[bool(getattr(g, "no_topic", False)), bool(getattr(g, "needs_review", False))]
                for g in plan.groups] == c["flags"]
        assert [g.signal_support for g in plan.groups] == c["support"]


def _abab(seed=5, size=12, dims=16):
    """Topic A, then B, then A again, then C: the TPU case (a topic returns)."""
    rng = np.random.default_rng(seed)
    cA, cB, cC = (rng.normal(size=dims) for _ in range(3))
    blocks = [cA, cB, cA, cC]
    return np.asarray([c + 0.15 * rng.normal(size=dims) for c in blocks for _ in range(size)],
                      np.float32), size


def test_returning_topic_is_linked_across_signals():
    x, size = _abab()
    y = x + 0.05 * np.random.default_rng(9).normal(size=x.shape)
    plan = manage({"visual": x, "vjudge": y}, percentile=95, link_quorum=2,
                  return_percentile=50)
    lab = plan.labels
    assert lab[0] == lab[2 * size]            # A returns: same topic
    assert lab[0] != lab[size]                # B stays separate
    assert lab[0] != lab[3 * size]            # C stays separate


def test_contiguous_default_cannot_link_return():
    x, size = _abab()
    plan = manage({"visual": x, "vjudge": x.copy()}, percentile=95, link_quorum=2)
    assert plan.labels[0] != plan.labels[2 * size]


def test_return_needs_quorum():
    x, size = _abab()
    rng = np.random.default_rng(3)
    other = np.asarray([rng.normal(size=16) for _ in range(len(x))], np.float32)
    # only one signal sees the return -> with quorum 2 it must not link
    plan = manage({"visual": x, "noise": other}, percentile=95, link_quorum=2,
                  return_percentile=50)
    assert plan.labels[0] != plan.labels[2 * size]


def test_boundary_signal_votes_and_labels():
    x, size = _abab()
    seg = np.zeros(len(x) - 1, np.float32)
    seg[size - 1] = 1.0
    plan = manage({"visual": x}, boundary_signals={"segloop": seg}, percentile=95,
                  link_quorum=2, return_percentile=50)
    assert size in plan.per_signal_cuts["segloop"]
    assert "segloop" in plan.per_signal_labels


def test_average_link_mode_links_return():
    x, size = _abab()
    y = x + 0.05 * np.random.default_rng(9).normal(size=x.shape)
    plan = manage({"visual": x, "vjudge": y}, percentile=95, link_quorum=2,
                  return_percentile=50, link_mode="average")
    lab = plan.labels
    assert lab[0] == lab[2 * size] and lab[0] != lab[size] and lab[0] != lab[3 * size]


def test_average_link_mode_does_not_chain():
    # 3 signals, quorum 2. Pairs (A,B) share labels in s1+s2, (B,C) in s2+s3,
    # but A and C are grouped together by only ONE signal (s2).
    # components chains A-B-C into one topic; average must not merge all three.
    n = 30
    A, B, C = range(0, 10), range(10, 20), range(20, 30)
    s1 = np.zeros(n, int); s1[list(C)] = 1               # {A,B} | {C}
    s2 = np.zeros(n, int)                                  # {A,B,C}
    s3 = np.zeros(n, int); s3[list(A)] = 1                # {A} | {B,C}
    from topicagg import multimodal_manager as mm
    orig = mm._return_labels
    fixed = {"s1": s1, "s2": s2, "s3": s3}
    try:
        mm._return_labels = lambda embs, cuts, pct, **kw: fixed[int(embs[0, 0])]
        sig = {k: np.full((n, 2), float(i), np.float32) for i, k in enumerate(["s1", "s2", "s3"])}
        fixed = {0: s1, 1: s2, 2: s3}
        comp = mm.manage(sig, percentile=99, link_quorum=2, return_percentile=50)
        avg = mm.manage(sig, percentile=99, link_quorum=2, return_percentile=50,
                        link_mode="average")
    finally:
        mm._return_labels = orig
    assert len(set(comp.labels.tolist())) == 1            # percolation
    assert len(set(avg.labels.tolist())) >= 2             # average does not chain


def test_topic_map_structure_and_returns():
    from topicagg.topic_map import build_topic_map
    x, size = _abab()
    y = x + 0.05 * np.random.default_rng(9).normal(size=x.shape)
    times = [[i * 2.0, i * 2.0 + 2.0] for i in range(len(x))]
    units = [{"lo": i, "hi": i + size, "summary": f"block {i // size}"}
             for i in range(0, len(x), size)]
    doc = build_topic_map("synthetic", {"visual": x, "vjudge": y}, times,
                          unit_summaries=units, percentile=95, return_percentile=50)
    assert set(doc["levels"]) == {"default", "fine"}
    topics = doc["levels"]["default"]["topics"]
    covered = sorted(s for t in topics for s in t["shots"])
    assert covered == list(range(len(x)))                       # partition of the video
    a = next(t for t in topics if 0 in t["shots"])
    assert a["returns"] >= 1 and len(a["spans"]) == a["returns"] + 1  # A comes back
    assert a["label"] == "block 0"
    assert set(a["provenance"]) == {"visual", "vjudge"}
    assert len(a["context"]) == len(a["spans"]) and a["context"][0]["seen"] == ["block 0"]
    import json
    json.dumps(doc)                                             # serializable


def test_versions_gate_on_synthetic_map():
    from topicagg.topic_map import build_topic_map
    from topicagg.versions import build_versions, check_versions
    x, size = _abab(size=40)
    y = x + 0.05 * np.random.default_rng(9).normal(size=x.shape)
    times = [[i * 2.0, i * 2.0 + 2.0] for i in range(len(x))]
    units = [{"lo": i, "hi": i + size, "summary": f"block {i // size}"}
             for i in range(0, len(x), size)]
    doc = build_topic_map("synthetic", {"visual": x, "vjudge": y}, times,
                          unit_summaries=units, percentile=95, return_percentile=50)
    v = build_versions(doc, recap_s=60, highlight_frac=0.2, thread_cap_frac=0.9)
    rep = check_versions(v)
    assert rep["G_version"], rep
    assert rep["recap60"]["total_s"][0] <= 60
    thread = v["threads"]["playlists"][0]
    assert len({c["topic_id"] for c in thread}) == 1 and len(thread) >= 2  # follows a returning topic


def test_abstention_silence_does_not_block_links():
    x, size = _abab()
    y = x + 0.05 * np.random.default_rng(9).normal(size=x.shape)
    dia = x + 0.05 * np.random.default_rng(4).normal(size=x.shape)
    dia[2 * size:3 * size] = 0.0          # the returning block A has no dialogue
    kw = dict(percentile=95, link_quorum=2, return_percentile=50, link_mode="average")
    no_abst = manage({"visual": x, "vjudge": y, "dialogue": dia}, **kw)
    abst = manage({"visual": x, "vjudge": y, "dialogue": dia}, abstain=True, **kw)
    assert abst.labels[0] == abst.labels[2 * size]          # visual + vjudge (both active) link it
    assert abst.labels[0] != abst.labels[size]
    assert abst.per_signal_labels["dialogue"][2 * size] == -1
    assert no_abst.per_signal_labels["dialogue"][2 * size] >= 0


def test_abstention_needs_quorum_of_active_voters():
    x, size = _abab()
    silent = np.zeros_like(x)
    plan = manage({"visual": x, "dialogue": silent, "ocr": silent.copy()}, percentile=95,
                  link_quorum=2, return_percentile=50, link_mode="average", abstain=True)
    assert len(set(plan.labels.tolist())) == len(x)          # 1 active voter < quorum 2: no links
