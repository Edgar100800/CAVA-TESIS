"""Narrative contracts: coverage, provenance, dependencies, budget and real media."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from topicagg.narrative import (build_evidence, check_selection, make_candidates,
                                pack_rows, repair_continuity, run_narrative, select_linear, timed_script)
from topicagg.narrative_model import MODEL, file_hash, parse_json


def topic(tid, spans, no_topic=False):
    return {"topic_id": tid, "spans": spans, "topic_label": "test",
            "flags": {"no_topic": no_topic}, "provenance": {}}


def doc(topics):
    return {"levels": {"default": {"topics": topics}}}


def assessment(cid, importance="essential", deps=()):
    return {"candidate_id": cid, "importance": importance, "prerequisite_candidate_ids": list(deps),
            "event_ids": [cid], "global_topic_ids": ["g000"], "reason": "Evidence", "role": "setup"}


def test_candidates_cover_returning_topics_rejected_units_gaps_and_tail():
    value = doc([topic(0, [[0, 10], [25, 35]]), topic(1, [[10, 15]], True)])
    candidates = make_candidates(value, 37, 5)
    assert candidates[0]["t0"] == 0 and candidates[-1]["t1"] == 37
    assert all(a["t1"] == b["t0"] for a, b in zip(candidates, candidates[1:]))
    assert any(c["topic_id"] == 1 for c in candidates)
    assert any(c["topic_id"] is None for c in candidates)
    with pytest.raises(ValueError, match="overlap"):
        make_candidates(doc([topic(0, [[0, 10]]), topic(1, [[5, 15]])]), 20)
    tail = make_candidates(doc([topic(0, [[0, 10]])]), 10.032, 30)
    assert len(tail) == 1 and tail[0]["t1"] == 10.032
    tail_at_limit = make_candidates(doc([topic(0, [[0, 30]])]), 30.032, 30)
    assert len(tail_at_limit) == 1


def test_selection_cannot_omit_required_antecedent_to_fit_budget():
    candidates = make_candidates(doc([topic(0, [[0, 30]])]), 30, 10)
    a = [assessment("c00000", "supporting"), assessment("c00001", deps=["c00000"]),
         assessment("c00002", "optional")]
    choices = select_linear(candidates, a, 20)
    assert [r["candidate_id"] for r in choices if r["selected"]] == ["c00000", "c00001"]
    assert check_selection(candidates, choices, 20)["duration_s"] == 20
    choices[0]["selected"] = False
    with pytest.raises(ValueError, match="prerequisites"):
        check_selection(candidates, choices, 20)
    a[0]["prerequisite_candidate_ids"] = ["c00002"]
    with pytest.raises(ValueError, match="earlier"):
        select_linear(candidates, a, 30)


def test_tight_budget_preserves_beginning_middle_and_late_events():
    candidates = make_candidates(doc([topic(0, [[0, 50]])]), 50, 5)
    a = [assessment(c["candidate_id"]) for c in candidates]
    choices = select_linear(candidates, a, 15)
    starts = [c["t0"] for c, d in zip(candidates, choices) if d["selected"]]
    assert starts == [0, 20, 40]


def test_evidence_packing_never_truncates_long_script():
    rows = [{"id": "s00000", "text": "x" * 26000, "t0": 0, "t1": 50}]
    batches = pack_rows(rows, 1000)
    assert "".join(row["text"] for batch in batches for row in batch) == rows[0]["text"]
    assert all(len(batch) > 0 for batch in batches)


def test_script_requires_alignment_and_valid_bounds(tmp_path):
    p = tmp_path / "script.json"
    p.write_text(json.dumps([{"t0": 0, "t1": 12, "text": "Action"}]))
    assert timed_script(p, 20)[0]["kind"] == "external_script"
    with pytest.raises(ValueError, match="align"):
        timed_script(p, 5)
    with pytest.raises(ValueError, match="aligned"):
        timed_script(tmp_path / "script.txt", 20)
    assert parse_json('```json\n{"ok": true}\n```')["ok"] is True


def test_continuity_repair_cannot_exceed_budget_or_insert_excluded_credits():
    candidates = make_candidates(doc([topic(0, [[0, 30]])]), 30, 10)
    a = [assessment("c00000", "optional"), assessment("c00001", "essential"),
         assessment("c00002", "exclude")]
    choices = select_linear(candidates, a, 10)
    review = {"transitions": [{"candidate_id": "c00001", "needed_candidate_ids": ["c00000"],
                                "reason": "Requires introduction"}]}
    assert repair_continuity(candidates, choices, a, review, 10) == choices
    repaired = repair_continuity(candidates, choices, a, review, 20)
    assert [d["candidate_id"] for d in repaired if d["selected"]] == ["c00000", "c00001"]
    assert check_selection(candidates, repaired, 20)["prerequisites_present"]


def test_ds_guard_rejects_cpu_results_and_changed_code(tmp_path):
    from scripts.cava_narrative import verify_smoke
    root = Path(__file__).resolve().parents[1]
    protocol = {"model": list(MODEL), "frame_count": 10, "max_candidate_s": 30,
                "code_hashes": {name: file_hash(root / "topicagg" / name)
                                for name in ["narrative.py", "narrative_model.py"]}}
    report = {"G_narrative": True, "decoded": True,
              "model_tasks_devices": {task: ["cuda"] for task in
                                      ["events", "description", "outline", "assessment", "continuity", "narration"]}}
    for name in ["Avengers_Endgame", "Spider_Man"]:
        p = tmp_path / name
        p.mkdir()
        (p / "protocol.json").write_text(json.dumps(protocol))
        (p / "run_report.json").write_text(json.dumps(report))
    verify_smoke(tmp_path, 10, 30)
    report["model_tasks_devices"]["description"] = ["cpu"]
    (tmp_path / "Spider_Man/run_report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="successful smoke"):
        verify_smoke(tmp_path, 10, 30)
    report["model_tasks_devices"]["description"] = ["cuda"]
    (tmp_path / "Spider_Man/run_report.json").write_text(json.dumps(report))
    protocol["code_hashes"]["narrative.py"] = "changed"
    (tmp_path / "Spider_Man/protocol.json").write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="successful smoke"):
        verify_smoke(tmp_path, 10, 30)


def test_dispatcher_does_not_submit_before_validation_or_twice(tmp_path, monkeypatch):
    import sys
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import narrative_dispatch
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["narrative_dispatch.py", "--smoke-root", str(tmp_path)])
    submissions = []
    monkeypatch.setattr(narrative_dispatch.subprocess, "check_output",
                        lambda *a, **kw: submissions.append(a) or "12345\n")

    def rejected(*args):
        raise ValueError("GPU smoke failed")

    monkeypatch.setattr(narrative_dispatch, "verify_smoke", rejected)
    with pytest.raises(ValueError, match="GPU smoke failed"):
        narrative_dispatch.main()
    assert not submissions
    monkeypatch.setattr(narrative_dispatch, "verify_smoke", lambda *a: None)
    narrative_dispatch.main()
    narrative_dispatch.main()
    assert len(submissions) == 1
    assert json.loads((tmp_path / "ds_submission.json").read_text())["production_job_id"] == "12345"


class FixtureModel:
    source_key = ""
    calls = 0
    cache_hits = 0

    def ask(self, task, instruction, data, validate, images=(), max_tokens=1400):
        self.calls += 1
        if task == "events":
            answer = {"events": [{"title": "Encuentro", "description": "Dos participantes se reúnen.",
                                  "evidence_ids": [data[0]["id"]]}]}
        elif task == "description":
            assert len(images) == 10
            answer = {"description": "Dos participantes se reúnen.", "setting": "Interior",
                      "change": "Comienza la reunión", "uncertainty": "Identidades no confirmadas",
                      "characters": ["dos participantes"], "actions": ["reunirse"], "content_kind": "story"}
        elif task == "outline":
            answer = {"synopsis": "Dos participantes se reúnen.",
                      "topics": [{"title": "Encuentro", "description": "Una reunión"}]}
        elif task == "assessment":
            answer = {"global_topic_ids": ["g000"], "event_ids": [], "role": "setup",
                      "importance": "essential", "topic_match": "consistent", "reason": "Presenta el encuentro",
                      "original_topic_match": "uncertain", "topic_match_reason": "El tema global es un encuentro",
                      "uncertainty": "Nombres no confirmados", "prerequisite_candidate_ids": []}
        elif task == "continuity":
            answer = {"coherent": True, "issues": [], "reason": "Continúa el encuentro", "needed_candidate_ids": []}
        elif task == "narration":
            answer = {"narration": "Dos participantes se reúnen.", "uncertainty": "Identidades no confirmadas"}
        else:
            raise AssertionError(task)
        validate(answer)
        return answer


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is required for media integration")
def test_real_media_export_protocol_and_ten_frames(tmp_path):
    run = tmp_path / "baseline"
    (run / "work").mkdir(parents=True)
    video = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=96x64:r=10:d=10",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=10", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(video)], check=True)
    state = {"asr_segments": [[0, 5, "Hello"], [5, 10, "We meet"]], "units": [[0, 5], [5, 10]]}
    (run / "work/state.json").write_text(json.dumps(state))
    (run / "work/summaries.json").write_text(json.dumps([{"lo": 0, "hi": 2, "summary": "Two meet"}]))
    (run / "topic_map.json").write_text(json.dumps(doc([topic(0, [[0, 10]])])))
    (run / "run_manifest.json").write_text(json.dumps({"video": {"path": str(video)}}))
    out = tmp_path / "narrative"
    report = run_narrative(run, out, FixtureModel(), budget_fraction=1,
                           max_candidate_s=5, decode=True, require_continuity=True)
    assert report["G_narrative"] and report["frames"] == 20
    assert report["selection"]["selected"] == 2
    assert (out / "narrative_linear.mp4").stat().st_size > 0
    assert len((out / "clip_decisions.jsonl").read_text().splitlines()) == 2
    # Same inputs can resume; JSON serialization must not invalidate an unchanged protocol.
    resumed = run_narrative(run, out, FixtureModel(), budget_fraction=1,
                           max_candidate_s=5, decode=True, require_continuity=True)
    assert resumed["G_narrative"]
    with pytest.raises(ValueError, match="protocol differs"):
        run_narrative(run, out, FixtureModel(), budget_fraction=0.5, max_candidate_s=5)
