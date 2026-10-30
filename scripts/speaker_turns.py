"""EXP-023: votante de fronteras por cambio de quién tiene la palabra.

score[k] (frontera entre unidad k y k+1) = divergencia Jensen-Shannon entre el
histograma de identidades de voz (ward + BIC, EXP-022d) de las `w` unidades
anteriores y el de las `w` siguientes. Unidades sin voz no cuentan. Es un
votante de fronteras (boundary_signals de manage()), no un embedding.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.identities import speaker_turn_scores  # noqa: E402,F401  (movido a topicagg/identities.py)
