"""Perfiles congelados de tfm-v1.0. No modificar: son la referencia de R1."""

PROFILES = {"film": {"unit_s": 5.0, "percentile": 80, "return_percentile": 90, "snap_visual_s": 30.0,  # EXP-027
                     "speaker_embed": True},  # EXP-028
            "documentary": {"unit_s": 5.0, "percentile": 90, "return_percentile": 90,  # EXP-025
                            "snap_visual_s": 30.0, "speaker_embed": True,
                            # narrador único: K por BIC nunca da 1 y sobre-divide (EXP-028, BBC 4.1 grupos)
                            "speaker_kind": "acoustic_group"},
            "meeting": {"unit_s": 10.0, "speaker_embed": True,  # EXP-028 (AMI ARI 0.29 → 0.73)
                        "percentile": 95, "return_percentile": 90,
                        "speaker_turns_w": 6}}  # EXP-023
