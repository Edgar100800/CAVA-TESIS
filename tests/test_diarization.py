import numpy as np

from topicagg.diarization import unit_labels, unit_major
from topicagg.pipeline import PROFILES
from topicagg.profiles import get_profile


def test_default_profiles_remain_frozen():
    assert get_profile("v1.0", "film") == PROFILES["film"]
    assert "speaker_backend" not in get_profile("v1.0", "film")
    assert get_profile("v1.1", "film")["speaker_backend"] == "pyannote_c1"
    assert get_profile("v1.1", "meeting")["speaker_backend"] == "pyannote_c1"
    assert get_profile("v1.1", "documentary")["speaker_backend"] == "wavlm_sv"


def test_unit_major_is_exp043_rule():
    units = [(0.0, 5.0), (5.0, 10.0)]
    turns = [(0.0, 2.0, "A"), (1.0, 4.0, "B"), (7.0, 8.0, "A")]
    assert unit_major(units, turns) == ["B", "A"]


def test_unit_labels_gate_and_total_speech_order():
    units = [(0.0, 5.0), (5.0, 10.0), (10.0, 15.0)]
    turns = [(0.0, 2.0, "A"), (5.0, 9.0, "B"), (10.0, 12.0, "A"), (12.0, 15.0, "B")]
    # B habla 7 s y A 4 s: B=V1. La unidad 1 queda fuera por el filtro ASR.
    np.testing.assert_array_equal(unit_labels(units, turns, [True, False, True]), [2, -1, 1])
