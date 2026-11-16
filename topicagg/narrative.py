"""Evidence-grounded narrative layer; does not change multimodal topic votes."""
from __future__ import annotations

import csv
import json
import math
import subprocess
from pathlib import Path

from .narrative_model import CONTRACT, MODEL, canonical, digest, file_hash, save_json

ROLES = {"setup", "goal", "conflict", "development", "turning_point", "consequence",
         "resolution", "transition", "credits", "unknown"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, key):
    require(isinstance(value.get(key), str) and bool(value[key].strip()), f"{key}: nonempty string required")


def strings(value, key):
    require(isinstance(value.get(key), list) and all(isinstance(x, str) for x in value[key]),
            f"{key}: list of strings required")


def reference_list(value, key, allowed):
    strings(value, key)
    require(set(value[key]) <= set(allowed), f"{key}: unknown references {set(value[key]) - set(allowed)}")
    require(len(value[key]) == len(set(value[key])), f"{key}: duplicated reference")


def timed_script(path, duration):
    if not path:
        return []
    require(Path(path).suffix == ".json", "Provide a time-aligned JSON screenplay; raw TXT is not aligned")
    rows = json.loads(Path(path).read_text())
    require(isinstance(rows, list) and rows, "Script must be a nonempty list")
    out = []
    for i, row in enumerate(rows):
        text(row, "text")
        a, b = row["t0"], row["t1"]
        require(isinstance(a, (int, float)) and isinstance(b, (int, float))
                and math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= duration,
                "Script times must align with the prepared video")
        out.append({"id": f"s{i:05}", "kind": "external_script", "t0": a, "t1": b, "text": row["text"]})
    return sorted(out, key=lambda x: (x["t0"], x["t1"]))


def make_candidates(doc, duration, max_seconds=60.0):
    require(max_seconds >= 5, "max_seconds must be >= 5")
    spans = []
    for topic in doc["levels"]["default"]["topics"]:
        for a, b in topic["spans"]:
            require(0 <= a < b <= duration + 0.15, "Invalid original topic span")
            spans.append({"t0": a, "t1": min(b, duration), "topic_id": topic["topic_id"],
                          "topic_label": topic.get("topic_label") or topic.get("label"),
                          "original_flags": topic["flags"], "provenance": topic["provenance"]})
    out, end = [], 0.0
    for span in sorted(spans, key=lambda x: x["t0"]):
        require(span["t0"] >= end - 0.01, "Original topic spans overlap")
        if span["t0"] > end + 0.01:
            out.append({"t0": end, "t1": span["t0"], "topic_id": None,
                        "topic_label": None, "original_flags": {"no_topic": True}, "provenance": {}})
        out.append(span)
        end = span["t1"]
    if end < duration - 0.01:
        if out and duration - end < 1.0:
            # AAC/container tails can outlive the final video frame by milliseconds.
            # Attach a subsecond tail to real context instead of inventing a visual scene.
            out[-1] = out[-1] | {"t1": duration, "container_tail_s": duration - end}
        else:
            out.append({"t0": end, "t1": duration, "topic_id": None,
                        "topic_label": None, "original_flags": {"no_topic": True}, "provenance": {}})
    candidates = []
    for span in out:
        a = span["t0"]
        while a < span["t1"] - 1e-6:
            b = min(a + max_seconds, span["t1"])
            if span["t1"] - b < 1.0:
                b = span["t1"]
            candidates.append(span | {"candidate_id": f"c{len(candidates):05}", "t0": a, "t1": b})
            a = b
    require(bool(candidates), "No candidates")
    return candidates


def build_evidence(state, summaries, script):
    rows = [{"id": f"a{i:05}", "kind": "asr", "t0": a, "t1": b, "text": t}
            for i, (a, b, t) in enumerate(state["asr_segments"]) if t.strip()]
    units = state["units"]
    for i, s in enumerate(summaries):
        rows.append({"id": f"v{i:05}", "kind": "legacy_visual_summary",
                     "t0": units[s["lo"]][0], "t1": units[s["hi"] - 1][1], "text": s["summary"]})
    rows += script
    return sorted(rows, key=lambda x: (x["t0"], x["t1"], x["id"]))


def pack_rows(rows, max_chars=11000):
    batches, batch, size = [], [], 0
    for row in rows:
        # Oversized individual evidence is split without dropping text or changing its source ID.
        fragments = [row]
        if len(canonical(row)) > max_chars:
            content = row["text"]
            fragments = [row | {"text": content[i:i + max_chars // 2]}
                         for i in range(0, len(content), max_chars // 2)]
        for fragment in fragments:
            n = len(canonical(fragment))
            if batch and size + n > max_chars:
                batches.append(batch)
                batch, size = [], 0
            batch.append(fragment)
            size += n
    if batch:
        batches.append(batch)
    return batches


def extract_frames(video, candidate, directory, count=10):
    from PIL import Image
    require(count >= 2, "At least two frames required")
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    for i in range(count):
        t = candidate["t0"] + (candidate["t1"] - candidate["t0"]) * (i + 0.5) / count
        p = directory / f"{i:02}.jpg"
        valid = False
        if p.exists():
            try:
                with Image.open(p) as im:
                    im.verify()
                valid = True
            except (OSError, ValueError):
                pass
        if not valid:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.6f}",
                            "-i", str(video), "-map", "0:v:0", "-frames:v", "1", "-threads", "1",
                            "-vf", "scale=448:-2", str(p)], check=True, capture_output=True)
            with Image.open(p) as im:
                im.verify()
        records.append({"time_s": t, "file": str(p), "sha256": file_hash(p)})
    return records


def validate_description(value):
    for key in ["description", "setting", "change", "uncertainty"]:
        text(value, key)
    for key in ["characters", "actions"]:
        strings(value, key)
    require(value.get("content_kind") in {"story", "credits", "logos", "unknown"}, "Invalid content_kind")


def build_events(model, evidence):
    events, coverage = [], []
    for bi, batch in enumerate(pack_rows(evidence)):
        allowed = {r["id"]: r for r in batch}

        def validate(value):
            require(isinstance(value.get("events"), list) and 1 <= len(value["events"]) <= 8,
                    "Return 1 to 8 events")
            for e in value["events"]:
                text(e, "title")
                text(e, "description")
                reference_list(e, "evidence_ids", allowed)
                require(bool(e["evidence_ids"]), "Each event must cite evidence")

        answer = model.ask("events", 'Write in Spanish. Identify chronological story events, including '
                           'silent actions visible in observations; mark credits/background when relevant. '
                           'Do not infer unobserved causes. Schema: {"events":[{"title":"...",'
                           '"description":"...","evidence_ids":["source ID"]}]}. 1 to 8 events.',
                           batch, validate)
        for e in answer["events"]:
            refs = [allowed[k] for k in e["evidence_ids"]]
            events.append(e | {"event_id": f"e{len(events):05}",
                               "t0": min(r["t0"] for r in refs), "t1": max(r["t1"] for r in refs)})
        coverage += list(allowed)
        print(f"[narrative] global evidence batch {bi + 1}: {len(events)} events", flush=True)
    require(set(coverage) == {e["id"] for e in evidence}, "Global analysis omitted source evidence")
    return events


def describe_candidates(model, video, candidates, evidence, out, frame_count):
    result = []
    for i, c in enumerate(candidates):
        frames = extract_frames(video, c, out / "frames" / c["candidate_id"], frame_count)
        nearby = [e for e in evidence if e["t0"] < c["t1"] and e["t1"] > c["t0"]]
        # Complete local evidence is available on disk; only original ASR/script and the frames
        # enter this pass, so a legacy visual summary cannot overwrite new visual observations.
        local = [e for e in nearby if e["kind"] != "legacy_visual_summary"]
        local_text = [{"kind": e["kind"], "id": e["id"], "text": e["text"]} for e in local]
        require(len(canonical(local_text)) <= 42000, "Local text too long; use shorter candidate spans")
        answer = model.ask("description", 'Describe this interval using its ordered frames and dialogue. '
                           'Write in Spanish. Distinguish visible actions from spoken claims. '
                           'Use "no observado" when nothing is established. Do not infer character names '
                           'from familiarity with a film. Schema: {"description":"...","characters":[], '
                           '"actions":[],"setting":"...","change":"...","uncertainty":"...",'
                           '"content_kind":"story|credits|logos|unknown"}.',
                           {"t0": c["t0"], "t1": c["t1"], "dialogue_and_script": local_text,
                            "frame_times": [f["time_s"] for f in frames]},
                           validate_description, images=[f["file"] for f in frames], max_tokens=800)
        frames = [f | {"file": str(Path(f["file"]).relative_to(out))} for f in frames]
        result.append(c | {"observation": answer, "frames": frames,
                           "evidence_ids": [e["id"] for e in nearby]})
        save_json(out / "candidates.json", result)
        print(f"[narrative] description {i + 1}/{len(candidates)}", flush=True)
    return result


def build_outline(model, events, candidates):
    nodes = [{"id": e["event_id"], "t0": e["t0"], "t1": e["t1"],
              "text": e["title"] + ": " + e["description"]} for e in events]
    nodes += [{"id": c["candidate_id"], "t0": c["t0"], "t1": c["t1"],
               "text": c["observation"]["description"]} for c in candidates]
    nodes.sort(key=lambda r: (r["t0"], r["t1"]))

    def validate(value):
        text(value, "synopsis")
        require(isinstance(value.get("topics"), list) and 1 <= len(value["topics"]) <= 10,
                "Return 1 to 10 global topics")
        for topic in value["topics"]:
            text(topic, "title")
            text(topic, "description")

    level = 0
    while True:
        batches = pack_rows(nodes, max_chars=12000)
        reduced = []
        for batch in batches:
            answer = model.ask("outline", 'Write in Spanish. Synthesize the supplied chronological '
                               'observations into a story overview and thematic topics. Distinguish '
                               'events from themes. Preserve uncertainty and distinguish credits/logos '
                               'from story. Do not add facts from outside the evidence. '
                               'Schema: {"synopsis":"at most 200 words","topics":[{"title":"...",'
                               '"description":"at most 40 words"}]}. At most 10 topics.', batch, validate,
                               max_tokens=1600)
            reduced.append({"id": f"reduce_{level}_{len(reduced)}", "text": canonical(answer),
                            "source_ids": [r["id"] for r in batch]})
        if len(reduced) == 1:
            return answer | {"topics": [t | {"global_topic_id": f"g{i:03}"}
                                        for i, t in enumerate(answer["topics"])],
                             "source_event_ids": [e["event_id"] for e in events],
                             "source_candidate_ids": [c["candidate_id"] for c in candidates],
                             "reduction_levels": level + 1}
        require(level < 12 and len(reduced) < len(nodes), "Global reduction did not converge")
        nodes, level = reduced, level + 1


def assess_candidates(model, candidates, events, outline, out):
    assessments = []
    by_id = {c["candidate_id"]: c for c in candidates}
    global_ids = [t["global_topic_id"] for t in outline["topics"]]
    for c in candidates:
        nearby = [e for e in events if e["t0"] < c["t1"] and e["t1"] > c["t0"]]
        # Keep recent context and earlier representatives of each identified global topic.
        history = {a["candidate_id"]: a for a in assessments[-6:]}
        for topic in global_ids:
            options = [a for a in assessments if topic in a["global_topic_ids"] and a["importance"] != "exclude"]
            if options:
                history[options[0]["candidate_id"]] = options[0]
        previous = [{"candidate_id": a["candidate_id"], "t0": by_id[a["candidate_id"]]["t0"],
                     "description": by_id[a["candidate_id"]]["observation"]["description"],
                     "role": a["role"]} for a in history.values()]

        def validate(value):
            reference_list(value, "global_topic_ids", global_ids)
            reference_list(value, "event_ids", [e["event_id"] for e in nearby])
            reference_list(value, "prerequisite_candidate_ids", history)
            require(value.get("role") in ROLES, "Invalid narrative role")
            require(value.get("importance") in {"essential", "supporting", "optional", "exclude"},
                    "Invalid importance")
            require(value.get("topic_match") in {"consistent", "mixed", "uncertain", "mismatch"},
                    "Invalid topic_match")
            require(value.get("original_topic_match") in {"consistent", "mixed", "uncertain", "mismatch"},
                    "Invalid original_topic_match")
            text(value, "topic_match_reason")
            text(value, "reason")
            text(value, "uncertainty")

        answer = model.ask("assessment", 'Write in Spanish. Assess this candidate against the global '
                           'story. topic_match evaluates correspondence to the GLOBAL themes; '
                           'original_topic_match separately evaluates the OLD multimodal label, which '
                           'is a hypothesis and can be wrong. Explain both in topic_match_reason. Identify its '
                           'narrative role, theme match and selection usefulness. Do not equate duration '
                           'or repetitions with importance. Credits/logos should be excluded from a '
                           'story recap. Cite only supplied global topics/events. Prerequisites may '
                           'refer only to supplied earlier candidates and must be genuinely necessary '
                           'to understand this event, not just visually similar. Schema: '
                           '{"global_topic_ids":[],"event_ids":[],"role":"' + "|".join(sorted(ROLES)) + '",'
                           '"importance":"essential|supporting|optional|exclude",'
                           '"topic_match":"consistent|mixed|uncertain|mismatch",'
                           '"original_topic_match":"consistent|mixed|uncertain|mismatch",'
                           '"topic_match_reason":"...",'
                           '"prerequisite_candidate_ids":[],"reason":"...","uncertainty":"..."}.',
                           {"candidate": {k: c[k] for k in ["candidate_id", "t0", "t1", "topic_label", "observation"]},
                            "global_story": outline, "nearby_events": nearby, "earlier_candidates": previous},
                           validate, max_tokens=700)
        if c["observation"]["content_kind"] in {"credits", "logos"}:
            answer["importance"] = "exclude"
            answer["reason"] = "Contenido identificado como créditos o logotipos; fuera del resumen narrativo. " + answer["reason"]
        if answer["topic_match"] == "mismatch":
            answer["importance"] = "exclude"
            answer["reason"] = "Sin correspondencia con los tópicos narrativos globales. " + answer["reason"]
        assessments.append(answer | {"candidate_id": c["candidate_id"]})
        save_json(out / "assessments.json", assessments)
        print(f"[narrative] assessment {len(assessments)}/{len(candidates)}", flush=True)
    return assessments


def select_linear(candidates, assessments, budget):
    require(budget > 0, "Positive narrative budget required")
    by_id = {c["candidate_id"]: c for c in candidates}
    by_assessment = {a["candidate_id"]: a for a in assessments}
    require(set(by_id) == set(by_assessment), "Every candidate needs an assessment")
    for a in assessments:
        for dep in a["prerequisite_candidate_ids"]:
            require(dep in by_id and by_id[dep]["t1"] <= by_id[a["candidate_id"]]["t0"] + 1e-6,
                    "Prerequisites must be known, strictly earlier candidates")

    def closure(cid):
        result = {cid}
        for dep in by_assessment[cid]["prerequisite_candidate_ids"]:
            result |= closure(dep)
        return result

    priority = {"essential": 0, "supporting": 1, "optional": 2, "exclude": 3}
    selected, reasons, represented = set(), {}, set()
    duration = max(c["t1"] for c in candidates)
    band = lambda cid: min(4, int(5 * by_id[cid]["t0"] / duration))
    band_order = {0: 0, 4: 1, 2: 2, 1: 3, 3: 4}
    band_counts, role_counts = {}, {}
    remaining = [a for a in assessments if a["importance"] != "exclude"]
    while remaining:
        a = min(remaining, key=lambda a: (priority[a["importance"]],
                band_counts.get(band(a["candidate_id"]), 0), role_counts.get(a["role"], 0),
                bool(set(a["event_ids"]) & represented) if a["event_ids"] else True,
                band_order[band(a["candidate_id"])],
                by_id[a["candidate_id"]]["t0"]))
        remaining.remove(a)
        cid = a["candidate_id"]
        if cid in selected:
            continue
        chain = closure(cid)
        if any(by_assessment[k]["importance"] == "exclude" for k in chain):
            reasons[cid] = "Descartado: requiere un antecedente marcado como excluido."
            continue
        cost = sum(by_id[k]["t1"] - by_id[k]["t0"] for k in selected | chain)
        if cost <= budget + 1e-6:
            for k in chain - selected:
                reasons[k] = ("Incluido por función narrativa: " if k == cid else
                              f"Incluido como antecedente necesario de {cid}: ") + by_assessment[k]["reason"]
                band_counts[band(k)] = band_counts.get(band(k), 0) + 1
                role = by_assessment[k]["role"]
                role_counts[role] = role_counts.get(role, 0) + 1
            selected |= chain
            represented.update(e for k in chain for e in by_assessment[k]["event_ids"])
        else:
            reasons[cid] = "Descartado: el tramo y sus antecedentes exceden el presupuesto disponible."
    decisions = []
    for c in candidates:
        cid, a = c["candidate_id"], by_assessment[c["candidate_id"]]
        decisions.append({"candidate_id": cid, "selected": cid in selected,
                          "reason": reasons.get(cid, "Descartado por evaluación narrativa: " + a["reason"]),
                          "assessment_reason": a["reason"], "role": a["role"],
                          "topic_match": a.get("topic_match"),
                          "original_topic_match": a.get("original_topic_match"),
                          "topic_match_reason": a.get("topic_match_reason"),
                          "global_topic_ids": a["global_topic_ids"], "event_ids": a["event_ids"],
                          "prerequisite_candidate_ids": a["prerequisite_candidate_ids"]})
    return decisions


def narrative_topic_map(candidates, assessments, outline):
    by_id = {c["candidate_id"]: c for c in candidates}
    topics = []
    for topic in outline["topics"]:
        members = [a for a in assessments if topic["global_topic_id"] in a["global_topic_ids"]]
        spans = []
        for a in members:
            c = by_id[a["candidate_id"]]
            if spans and abs(spans[-1][1] - c["t0"]) < 1e-6:
                spans[-1][1] = c["t1"]
            else:
                spans.append([c["t0"], c["t1"]])
        topics.append(topic | {"candidate_ids": [a["candidate_id"] for a in members],
                               "event_ids": sorted({e for a in members for e in a["event_ids"]}),
                               "spans": spans, "returns": max(0, len(spans) - 1),
                               "duration_s": sum(b - a for a, b in spans)})
    return {"schema": CONTRACT, "method": "posthoc_global_narrative_themes_not_multimodal_votes",
            "topics": topics,
            "unmatched_candidate_ids": [a["candidate_id"] for a in assessments if not a["global_topic_ids"]],
            "allows_multiple_themes_per_candidate": True}


def check_selection(candidates, decisions, budget):
    by_id = {c["candidate_id"]: c for c in candidates}
    require(len(decisions) == len(by_id) and {d["candidate_id"] for d in decisions} == set(by_id),
            "Decisions must cover every candidate exactly once")
    selected = [d for d in decisions if d["selected"]]
    require(bool(selected), "Narrative selection is empty")
    ids = {d["candidate_id"] for d in selected}
    last, total = 0.0, 0.0
    for d in selected:
        c = by_id[d["candidate_id"]]
        require(c["t0"] >= last - 1e-6, "Selection is not chronological or overlaps")
        require(set(d["prerequisite_candidate_ids"]) <= ids, "Selected clip has missing prerequisites")
        for dep in d["prerequisite_candidate_ids"]:
            require(by_id[dep]["t1"] <= c["t0"] + 1e-6, "Future/cyclic dependency")
        total += c["t1"] - c["t0"]
        last = c["t1"]
    require(total <= budget + 1e-6, "Narrative exceeds budget")
    return {"selected": len(selected), "duration_s": total, "budget_s": budget,
            "chronological": True, "prerequisites_present": True}


def review_continuity(model, candidates, decisions, outline):
    selected = {d["candidate_id"] for d in decisions if d["selected"]}
    previous, reviews, viewer_history = None, [], []
    for c in candidates:
        if c["candidate_id"] not in selected:
            continue

        def validate(value):
            require(isinstance(value.get("coherent"), bool), "coherent must be boolean")
            strings(value, "issues")
            text(value, "reason")
            reference_list(value, "needed_candidate_ids", [x["candidate_id"] for x in omitted])
            require(not value["coherent"] or not value["needed_candidate_ids"],
                    "Coherent transitions cannot require extra clips")
            require(value["coherent"] == (len(value["issues"]) == 0), "coherent conflicts with issues")

        compact = lambda x: {k: x[k] for k in ["candidate_id", "t0", "t1", "observation"]}
        omitted = [x for x in candidates if x["candidate_id"] not in selected
                   and x["t1"] <= c["t0"] + 1e-6
                   and (previous is None or x["t0"] >= previous["t1"] - 1e-6)][-4:]
        review = model.ask("continuity", 'Write in Spanish. Review whether the current clip is '
                           'understandable after the preceding selected clip (or as the opening). '
                           'A time jump or an in-medias-res opening is allowed if its action is '
                           'understandable. An unfamiliar name alone is not an issue. Flag genuinely '
                           'missing prerequisites, not every introduction. Earlier selected history '
                           'is known to the viewer. The global synopsis is NOT shown to the viewer '
                           'and cannot compensate for missing context. If omitted clips can repair an '
                           'issue, cite their supplied IDs. Evaluate supplied evidence only. '
                           'Schema: {"coherent":true,"issues":[],"reason":"...","needed_candidate_ids":[]}. '
                           'If there is an issue set coherent=false and list concrete issues.',
                           {"synopsis": outline["synopsis"], "previous": compact(previous) if previous else None,
                            "current": compact(c), "viewer_history": viewer_history,
                            "omitted_context_options": [compact(x) for x in omitted]},
                           validate, max_tokens=600)
        reviews.append(review | {"candidate_id": c["candidate_id"],
                                 "previous_candidate_id": previous["candidate_id"] if previous else None})
        previous = c
        viewer_history.append({"candidate_id": c["candidate_id"], "observed_change": c["observation"]["change"][:160],
                               "characters": c["observation"]["characters"]})
    return {"method": "model_review_not_human_validation", "transitions": reviews,
            "coherent": all(r["coherent"] for r in reviews),
            "issues_count": sum(len(r["issues"]) for r in reviews)}


def repair_continuity(candidates, decisions, assessments, review, budget):
    """Insert model-requested antecedents only when the entire dependency chain fits."""
    by_id = {c["candidate_id"]: c for c in candidates}
    by_assessment = {a["candidate_id"]: a for a in assessments}
    by_decision = {d["candidate_id"]: dict(d) for d in decisions}

    def closure(cid):
        result = {cid}
        for dep in by_assessment[cid]["prerequisite_candidate_ids"]:
            result |= closure(dep)
        return result

    for transition in review["transitions"]:
        for needed in transition["needed_candidate_ids"]:
            chain = closure(needed)
            selected = {k for k, d in by_decision.items() if d["selected"]}
            cost = sum(by_id[k]["t1"] - by_id[k]["t0"] for k in selected | chain)
            if cost > budget + 1e-6 or any(by_assessment[k]["importance"] == "exclude" for k in chain):
                continue
            for cid in chain - selected:
                by_decision[cid]["selected"] = True
                by_decision[cid]["reason"] = (f"Incluido para reparar continuidad antes de "
                    f"{transition['candidate_id']}: {transition['reason']}")
            target = by_decision[transition["candidate_id"]]
            target["prerequisite_candidate_ids"] = sorted(set(target["prerequisite_candidate_ids"]) | {needed})
    return [by_decision[c["candidate_id"]] for c in candidates]


def build_narration(model, candidates, decisions, out):
    selected = {d["candidate_id"] for d in decisions if d["selected"]}
    lines, narration = [], []
    for c in candidates:
        if c["candidate_id"] not in selected:
            continue

        def validate(value):
            text(value, "narration")
            text(value, "uncertainty")

        answer = model.ask("narration", 'Write one or two Spanish narration sentences describing '
                           'the current clip in chronological order. This is proposed text, not audio. '
                           'Use only observed actions and established dialogue. Do not invent causal '
                           'connectors or explain missing events. Preserve uncertainty. '
                           'Schema: {"narration":"...","uncertainty":"..."}.',
                           {"candidate_id": c["candidate_id"], "observation": c["observation"],
                            "previous_narration": lines[-1] if lines else None}, validate, max_tokens=300)
        narration.append(answer | {"candidate_id": c["candidate_id"], "t0": c["t0"], "t1": c["t1"]})
        lines.append(answer["narration"])
    save_json(out / "narration.json", narration)
    (out / "narration.md").write_text("# Propuesta de narración lineal\n\nTexto automático para revisión; no incluye voz sintetizada.\n\n"
                                     + "\n\n".join(lines) + "\n")
    return narration


def export_clips(video, candidates, decisions, out, decode=False):
    clips = out / "clips"
    clips.mkdir(exist_ok=True)
    selected = {d["candidate_id"] for d in decisions if d["selected"]}
    records = []
    for c in candidates:
        if c["candidate_id"] not in selected:
            continue
        name = f"narrative_{len(records):03}_{c['candidate_id']}_{c['t0']:.2f}-{c['t1']:.2f}.mp4"
        path = clips / name
        if not path.exists():
            partial = path.with_suffix(".part.mp4")
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(c["t0"]),
                            "-i", str(video), "-t", str(c["t1"] - c["t0"]),
                            "-map", "0:v:0", "-map", "0:a:0", "-sn", "-dn", "-map_chapters", "-1",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "4",
                            "-c:a", "aac", "-movflags", "+faststart", str(partial)],
                           check=True, capture_output=True)
            partial.replace(path)
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                           "format=duration:stream=codec_type", "-of", "json", str(path)], text=True))
        error = abs(float(probe["format"]["duration"]) - (c["t1"] - c["t0"]))
        require(error <= 0.15, f"Incorrect exported duration: {path}")
        require({"audio", "video"} <= {s["codec_type"] for s in probe["streams"]}, "Clip missing audio/video")
        if decode:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(path),
                            "-f", "null", "-"], check=True, capture_output=True)
        records.append({"candidate_id": c["candidate_id"], "t0": c["t0"], "t1": c["t1"],
                        "file": str(path.relative_to(out)), "duration_error_s": error,
                        "actual_duration_s": float(probe["format"]["duration"])})
    require(bool(records), "No clips exported")
    listing = clips / "playlist.txt"
    listing.write_text("".join(f"file '{Path(r['file']).name}'\n" for r in records))
    movie = out / "narrative_linear.mp4"
    partial = movie.with_suffix(".part.mp4")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", str(partial)], check=True, capture_output=True)
    partial.replace(movie)
    actual_total = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                  "-of", "csv=p=0", str(movie)], text=True).strip())
    require(abs(actual_total - sum(r["actual_duration_s"] for r in records)) <= 0.3,
            "Concatenated duration differs from exported clips")
    save_json(out / "linear_playlist.json", {"clips": records, "actual_total_duration_s": actual_total})
    if decode:
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(movie),
                        "-f", "null", "-"], check=True, capture_output=True)
    return records


def write_reports(out, candidates, decisions, outline, continuity, records):
    from html import escape
    by_id = {d["candidate_id"]: d for d in decisions}
    files = {r["candidate_id"]: r["file"] for r in records}
    with (out / "clip_decisions.jsonl").open("w") as fh:
        for c in candidates:
            row = c | {"decision": by_id[c["candidate_id"]], "file": files.get(c["candidate_id"])}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out / "clip_times.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["candidate_id", "t0", "t1", "duration_s", "selected", "topic_id",
                         "global_topic_ids", "role", "description", "reason", "file"])
        for c in candidates:
            d = by_id[c["candidate_id"]]
            writer.writerow([c["candidate_id"], c["t0"], c["t1"], c["t1"] - c["t0"],
                             d["selected"], c["topic_id"], ",".join(d["global_topic_ids"]), d["role"],
                             c["observation"]["description"], d["reason"], files.get(c["candidate_id"], "")])
    lines = ["# Selección narrativa experimental", "", outline["synopsis"], "",
             "Descripciones, funciones y continuidad: hipótesis automáticas; requieren revisión humana.",
             f"Continuidad del modelo: {continuity['coherent']} ({continuity['issues_count']} incidencias).", ""]
    for c in candidates:
        d = by_id[c["candidate_id"]]
        lines += [f"## {c['candidate_id']} · {c['t0']:.2f}–{c['t1']:.2f} s · "
                  + ("INCLUIDO" if d["selected"] else "DESCARTADO"),
                  c["observation"]["description"], "", d["reason"], ""]
    (out / "review.md").write_text("\n".join(lines))
    esc = lambda value: escape(str(value))
    evidence = {e["id"]: e for e in json.loads((out / "evidence.json").read_text())}
    cards = []
    for c in candidates:
        cid = c["candidate_id"]
        d, obs = by_id[cid], c["observation"]
        frames = "".join(f'<figure><img loading="lazy" src="{esc(f["file"])}">'
                         f'<figcaption>{f["time_s"]:.2f} s</figcaption></figure>' for f in c["frames"])
        said = " ".join(evidence[k]["text"] for k in c["evidence_ids"] if evidence[k]["kind"] == "asr")
        video = f'<video controls preload="none" src="{esc(files[cid])}"></video>' if cid in files else ""
        cards.append(f'''<article data-selected="{str(d['selected']).lower()}">
<h2>{esc(cid)} · {c['t0']:.2f}–{c['t1']:.2f} s · {'Incluido' if d['selected'] else 'Descartado'}</h2>
<p>{esc(obs['description'])}</p><p><strong>Decisión:</strong> {esc(d['reason'])}</p>
<p>Función: {esc(d['role'])} · Tópicos globales: {esc(', '.join(d['global_topic_ids']))}</p>
{video}<div class="frames">{frames}</div><details><summary>Evidencia y correspondencia</summary>
<p><strong>Etiqueta anterior:</strong> {esc(c['topic_label'])}</p>
<p><strong>Correspondencia:</strong> {esc(d.get('topic_match_reason'))}</p>
<p><strong>Cambio observado:</strong> {esc(obs['change'])}</p>
<p><strong>Incertidumbre:</strong> {esc(obs['uncertainty'])}</p>
<p><strong>Diálogo ASR:</strong> {esc(said or '(sin diálogo)')}</p>
<p><strong>Referencias:</strong> {esc(', '.join(c['evidence_ids']))}</p>
<p><strong>Antecedentes:</strong> {esc(', '.join(d['prerequisite_candidate_ids']) or '(ninguno identificado)')}</p>
</details></article>''')
    (out / "review.html").write_text('''<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CAVA · Revisión narrativa</title>
<style>body{font:16px/1.55 system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#f5f5f5;color:#202020}
article{background:white;padding:1.5rem;margin:1.5rem 0;border-radius:12px}h2{font-size:1.15rem}
.frames{display:flex;overflow-x:auto;gap:8px}figure{margin:0;min-width:180px}img{width:180px}figcaption{font-size:12px}
video{width:100%;max-height:360px}details{margin-top:1rem}button{padding:.6rem;margin-right:8px;cursor:pointer}</style>
<h1>Revisión narrativa de CAVA</h1><p>Descripciones y decisiones automáticas para revisión humana.</p>'''
        + f'<p>{esc(outline["synopsis"])}</p><p>Continuidad del modelo: {esc(continuity["coherent"])}; '
        + f'{continuity["issues_count"]} incidencias pendientes.</p>'
        + '<p><a href="narrative_linear.mp4">Video lineal</a> · <a href="narration.md">Narración propuesta</a> · '
        + '<a href="clip_times.csv">CSV</a> · <a href="clip_decisions.jsonl">Decisiones completas</a></p>'
        + '''<button onclick="filterClips(false)">Todos los candidatos</button>
<button onclick="filterClips(true)">Solo incluidos</button>'''
        + "".join(cards)
        + '''<script>function filterClips(selected){document.querySelectorAll('article').forEach(
el=>el.hidden=selected&&el.dataset.selected!=='true')}</script></html>''')


def run_narrative(run_dir, out, model, *, script=None, budget_fraction=0.10, frame_count=10,
                  max_candidate_s=60.0, decode=False, require_continuity=False):
    run_dir, out = Path(run_dir).resolve(), Path(out).resolve()
    require(out != run_dir and run_dir not in out.parents, "Use a separate output directory")
    out.mkdir(parents=True, exist_ok=True)
    inputs = {name: run_dir / name for name in ["topic_map.json", "work/state.json", "work/summaries.json",
                                               "run_manifest.json"]}
    manifest = json.loads(inputs["run_manifest.json"].read_text())
    video = Path(manifest["video"]["path"])
    if not video.is_absolute():
        video = Path(__file__).resolve().parents[1] / video
    require(video.is_file(), f"Missing prepared source: {video}")
    state = json.loads(inputs["work/state.json"].read_text())
    doc = json.loads(inputs["topic_map.json"].read_text())
    duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                             "-of", "csv=p=0", str(video)], text=True).strip())
    script_rows = timed_script(script, duration)
    require(0 < budget_fraction <= 1, "budget_fraction must be in (0, 1]")
    protocol = {"contract": CONTRACT, "model": list(MODEL), "video": {"path": str(video), "sha256": file_hash(video)},
                "input_hashes": {k: file_hash(p) for k, p in inputs.items()},
                "script_sha256": file_hash(script) if script else None,
                "script_source": "external_time_aligned_plus_asr_visual" if script else "asr_and_visual",
                "budget_fraction": budget_fraction, "frame_count": frame_count, "max_candidate_s": max_candidate_s,
                "code_hashes": {p.name: file_hash(p) for p in [Path(__file__), Path(__file__).with_name("narrative_model.py")]}}
    protocol_file = out / "protocol.json"
    if protocol_file.exists():
        require(json.loads(protocol_file.read_text()) == protocol,
                "Output protocol differs; use a new output directory to avoid stale caches")
    save_json(protocol_file, protocol)
    model.source_key = digest(protocol)
    evidence = build_evidence(state, json.loads(inputs["work/summaries.json"].read_text()), script_rows)
    save_json(out / "evidence.json", evidence)
    candidates = make_candidates(doc, duration, max_candidate_s)
    events = build_events(model, evidence)
    save_json(out / "events.json", events)
    candidates = describe_candidates(model, video, candidates, evidence, out, frame_count)
    outline = build_outline(model, events, candidates)
    save_json(out / "global_story.json", outline)
    assessments = assess_candidates(model, candidates, events, outline, out)
    save_json(out / "narrative_topic_map.json", narrative_topic_map(candidates, assessments, outline))
    budget = duration * budget_fraction
    # Leave room to insert context discovered by the continuity pass.
    reserve = 0.0 if budget_fraction == 1 else 0.15
    decisions = select_linear(candidates, assessments, budget * (1 - reserve))
    gate = check_selection(candidates, decisions, budget)
    continuity = review_continuity(model, candidates, decisions, outline)
    review_history = [continuity]
    for _ in range(2):
        if continuity["coherent"]:
            break
        repaired = repair_continuity(candidates, decisions, assessments, continuity, budget)
        if repaired == decisions:
            break
        decisions = repaired
        gate = check_selection(candidates, decisions, budget)
        continuity = review_continuity(model, candidates, decisions, outline)
        review_history.append(continuity)
    save_json(out / "selection.json", decisions)
    save_json(out / "continuity.json", continuity)
    save_json(out / "continuity_history.json", review_history)
    build_narration(model, candidates, decisions, out)
    records = export_clips(video, candidates, decisions, out, decode)
    write_reports(out, candidates, decisions, outline, continuity, records)
    report = {"schema": CONTRACT, "candidates": len(candidates), "events": len(events),
              "source_records_analyzed": len(evidence),
              "events_represented_in_selection": len({e for d in decisions if d["selected"] for e in d["event_ids"]}),
              "selection_policy": "importance_then_temporal_band_and_role_coverage_with_prerequisites",
              "repair_reserve_fraction": reserve,
              "frames": sum(len(c["frames"]) for c in candidates), "global_topics": len(outline["topics"]),
              "selection": gate, "continuity": {"coherent": continuity["coherent"],
              "issues_count": continuity["issues_count"]}, "decoded": decode,
              "model_calls": model.calls, "cache_hits": model.cache_hits,
              "model_tasks_devices": {k: sorted(v) for k, v in getattr(model, "task_devices", {}).items()},
              "G_narrative": gate["chronological"] and continuity["coherent"],
              "max_clip_duration_error_s": max(r["duration_error_s"] for r in records),
              "script_source": protocol["script_source"], "human_validated": False}
    save_json(out / "run_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    require(not require_continuity or report["G_narrative"], "Narrative continuity has unresolved issues; inspect continuity.json")
    return report
