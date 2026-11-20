"""Perfiles del stack v1.1: pyannote solo cambia V# en film y meeting."""

PROFILES = {"film": {"unit_s": 5.0, "percentile": 80, "return_percentile": 90, "snap_visual_s": 30.0,
                     "speaker_embed": True, "speaker_backend": "pyannote_c1"},
            "documentary": {"unit_s": 5.0, "percentile": 90, "return_percentile": 90,
                            "snap_visual_s": 30.0, "speaker_embed": True,
                            "speaker_kind": "acoustic_group", "speaker_backend": "wavlm_sv"},
            "meeting": {"unit_s": 10.0, "speaker_embed": True,
                        "percentile": 95, "return_percentile": 90,
                        "speaker_turns_w": 6, "speaker_backend": "pyannote_c1"}}
