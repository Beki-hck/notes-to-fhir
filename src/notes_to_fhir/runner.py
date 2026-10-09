"""Run models over the notes, cache their answers, and compute metrics."""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

from . import generate, handwritten
from . import score as S
from .extract import PROMPT_VERSION, get_model, run_one

SETS = ("template", "handwritten")


def load_notes(which: str = "all") -> list[dict]:
    notes = []
    if which in ("all", "template"):
        notes += [dict(n, set="template") for n in generate.load()]
    if which in ("all", "handwritten"):
        notes += [dict(n, set="handwritten") for n in handwritten.NOTES]
    if not notes:
        raise ValueError(f"unknown set {which!r}; use all, template or handwritten")
    return notes


def model_dir(out: Path, spec: str) -> Path:
    return out / re.sub(r"[^\w.-]+", "_", spec)


def load_predictions(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    preds = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                preds[rec["id"]] = rec
    return preds


def run(spec: str, notes: list[dict], out: Path, use_schema: bool = True, log=print,
        use_format: bool = True) -> dict[str, dict]:
    """Extract every note not already in predictions.jsonl. Safe to stop and re-run."""
    model = get_model(spec, use_schema=use_schema, use_format=use_format)
    d = model_dir(out, spec)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "predictions.jsonl"
    preds = load_predictions(path)
    todo = [n for n in notes if n["id"] not in preds or preds[n["id"]]["status"] == "model_error"]
    if not todo:
        log(f"{spec}: all {len(notes)} notes already done")
    for i, n in enumerate(todo, 1):
        rec = {"id": n["id"], "model": spec, "prompt_version": PROMPT_VERSION, **run_one(model, n["text"])}
        preds[n["id"]] = rec
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log(f"{spec}: [{i}/{len(todo)}] {n['id']} {rec['status']} {rec['seconds']}s")
        if rec["status"] == "model_error" and i == 1:
            log(f"  error: {rec['error']}")
            if "Connection refused" in (rec["error"] or "") or "No connection" in (rec["error"] or ""):
                log("  Is Ollama running? Start it, then re-run; finished notes are kept.")
                sys.exit(1)
    return preds


def evaluate(notes: list[dict], preds: dict[str, dict]) -> dict:
    """Metrics for one model, overall and per note set."""
    out = {"sets": {}}
    groups = {"all": notes, **{s: [n for n in notes if n.get("set") == s] for s in SETS}}
    for name, group in groups.items():
        if not group:
            continue
        per_note, traps = [], {}
        statuses, seconds = {}, []
        for n in group:
            rec = preds.get(n["id"])
            pred = rec["extraction"] if rec else None
            per_note.append(S.score_note(n["gold"], pred))
            for t, results in S.trap_outcomes(n, pred).items():
                traps.setdefault(t, []).extend(results)
            st = rec["status"] if rec else "missing"
            statuses[st] = statuses.get(st, 0) + 1
            if rec and rec.get("seconds") is not None:
                seconds.append(rec["seconds"])
        t = S.total(per_note)
        lo, hi = S.bootstrap_f1(per_note)
        sections = {}
        for s in S.SECTIONS:
            c = S.total(per_note, [s])
            sections[s] = {"f1": c.f1, "precision": c.precision, "recall": c.recall,
                           "entity_f1": c.entity_f1, "tp": c.tp, "fp": c.fp, "fn": c.fn,
                           "attrs": {a: {"correct": c.attr_correct.get(a, 0), "total": v}
                                     for a, v in c.attr_total.items()}}
        out["sets"][name] = {
            "notes": len(group), "f1": t.f1, "precision": t.precision, "recall": t.recall,
            "f1_ci": [lo, hi], "fields": {"correct": t.correct, "gold": t.gold, "pred": t.pred},
            "sections": sections,
            "traps": {k: {"passed": sum(v), "total": len(v)} for k, v in sorted(traps.items())},
            "status": statuses,
            "seconds_mean": statistics.mean(seconds) if seconds else None,
        }
    return out
