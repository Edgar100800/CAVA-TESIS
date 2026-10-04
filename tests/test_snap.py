import numpy as np

from topicagg.topic_map import snap_boundaries


def test_snap_moves_boundary_to_nearest_reference_within_radius():
    lab = np.array([0, 0, 0, 0, 4, 4, 4, 4, 4, 4])
    ref = np.array([0, 0, 0, 0, 0, 0, 6, 6, 6, 6])   # frontera de referencia entre 5 y 6
    ends = np.arange(1, 11) * 5.0
    out = snap_boundaries(lab, ref, ends, R=10.0)
    assert out.tolist() == [0, 0, 0, 0, 0, 0, 4, 4, 4, 4]


def test_snap_leaves_boundary_beyond_radius():
    lab = np.array([0, 0, 0, 0, 4, 4, 4, 4, 4, 4])
    ref = np.array([0, 0, 0, 0, 0, 0, 0, 0, 8, 8])
    ends = np.arange(1, 11) * 5.0
    assert snap_boundaries(lab, ref, ends, R=10.0).tolist() == lab.tolist()


def test_snap_moves_left_and_keeps_returns():
    lab = np.array([0, 0, 0, 3, 3, 3, 0, 0])          # tópico 0 retorna
    ref = np.array([0, 0, 2, 2, 2, 2, 2, 2])
    ends = np.arange(1, 9) * 5.0
    out = snap_boundaries(lab, ref, ends, R=5.0)
    assert out.tolist() == [0, 0, 3, 3, 3, 3, 0, 0]
