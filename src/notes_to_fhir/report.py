"""Leaderboard (Markdown + JSON) and a per-note HTML report of every field."""

from __future__ import annotations

import html
import json
from pathlib import Path

from . import score as S

TRAP_LABELS = {
    "negated": "Skips negated conditions",
    "family_history": "Skips family history",
    "resolved": "Marks resolved conditions",
    "stopped_med": "Marks stopped drugs",
    "dose_change": "Uses the new dose",
    "new_med": "Includes drugs started today",
    "brand_name": "Maps brand names",
    "prior_value": "Ignores earlier values",
    "unit_conversion": "Units (lb, °F, mmol/L)",
}


def _pct(x):
    return f"{100 * x:.1f}"


def leaderboard(results: dict[str, dict]) -> str:
    """results: model -> evaluate() output."""
    rows = sorted(results.items(), key=lambda kv: -kv[1]["sets"]["all"]["f1"])
    lines = ["| Model | Field F1, all notes | Template notes | Hand-written notes | Patient | Conditions | "
             "Medications | Allergies | Observations | Schema-valid replies | Seconds/note |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for model, r in rows:
        a = r["sets"]["all"]
        lo, hi = a["f1_ci"]
        valid = a["status"].get("ok", 0) / a["notes"]
        sec = a["seconds_mean"]
        cells = [f"`{model}`", f"**{_pct(a['f1'])}** [{_pct(lo)}–{_pct(hi)}]"]
        for s in ("template", "handwritten"):
            cells.append(_pct(r["sets"][s]["f1"]) if s in r["sets"] else "–")
        cells += [_pct(a["sections"][s]["f1"]) for s in S.SECTIONS]
        cells += [f"{100 * valid:.0f}%", f"{sec:.1f}" if sec is not None else "–"]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "Traps handled (all notes):", "",
              "| Model | " + " | ".join(TRAP_LABELS.values()) + " |",
              "|---|" + "---|" * len(TRAP_LABELS)]
    for model, r in rows:
        tr = r["sets"]["all"]["traps"]
        cells = []
        for k in TRAP_LABELS:
            t = tr.get(k)
            cells.append(f"{t['passed']}/{t['total']}" if t else "–")
        lines.append(f"| `{model}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def attribute_table(results: dict[str, dict]) -> str:
    """Accuracy of each attribute on matched entities, e.g. how often the dose was right."""
    labels = {("patient", "birth_date"): "Birth date", ("conditions", "clinical_status"): "Condition status",
              ("medications", "dose_value"): "Dose", ("medications", "dose_unit"): "Dose unit",
              ("medications", "route"): "Route", ("medications", "frequency"): "Frequency",
              ("medications", "status"): "Drug status", ("allergies", "reaction"): "Allergy reaction",
              ("observations", "value"): "Observation value"}
    keys = list(labels)
    lines = ["| Model | " + " | ".join(labels.values()) + " |", "|---|" + "---|" * len(keys)]
    for model, r in sorted(results.items(), key=lambda kv: -kv[1]["sets"]["all"]["f1"]):
        cells = []
        for s, a in keys:
            x = r["sets"]["all"]["sections"][s]["attrs"].get(a)
            cells.append(f"{100 * x['correct'] / x['total']:.0f}%" if x and x["total"] else "–")
        lines.append(f"| `{model}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _fmt(attrs: dict | None) -> str:
    if attrs is None:
        return "—"
    return ", ".join(f"{k}={v}" for k, v in attrs.items() if v is not None) or "✓"


def diff_rows(gold: dict, pred: dict | None) -> list[tuple[str, str, str, str, bool]]:
    """(section, key, gold, pred, all-correct) for every entity on either side."""
    rows = []
    gp, pp = S.canon_patient(gold.get("patient")), S.canon_patient((pred or {}).get("patient"))
    for f, gv in gp.items():
        rows.append(("patient", f, str(gv), str(pp.get(f)), gv == pp.get(f)))
    ge, pe = S.canon_entities(gold), S.canon_entities(pred or {})
    for s in S.SECTIONS[1:]:
        for key in list(ge[s]) + [k for k in pe[s] if k not in ge[s]]:
            g, p = ge[s].get(key), pe[s].get(key)
            ok = g is not None and p is not None and all(
                S.values_equal(s, a, v, p.get(a)) for a, v in g.items() if v is not None)
            rows.append((s, key, _fmt(g), _fmt(p), ok))
    return rows


def details_html(notes: list[dict], preds: dict[str, dict[str, dict]]) -> str:
    """preds: model -> note id -> prediction record."""
    models = list(preds)
    parts = ["<!doctype html><meta charset='utf-8'><title>notes-to-fhir details</title><style>",
             "body{font:14px system-ui,sans-serif;margin:24px;max-width:1200px}"
             "pre{white-space:pre-wrap;background:#f6f6f6;padding:10px;border-radius:6px}"
             "table{border-collapse:collapse;width:100%;margin:8px 0 24px}"
             "td,th{border:1px solid #ddd;padding:4px 6px;text-align:left;vertical-align:top;font-size:13px}"
             ".ok{background:#e8f6ea}.bad{background:#fde8e8}details{margin:8px 0}"
             "@media(prefers-color-scheme:dark){body{background:#111;color:#ddd}pre{background:#1d1d1d}"
             "td,th{border-color:#333}.ok{background:#16301b}.bad{background:#3a1717}}",
             "</style><h1>notes-to-fhir: every note, every field</h1>",
             "<p>Green: the model got every scored field of that entity right. Red: missed, extra or wrong.</p>"]
    for n in notes:
        traps = ", ".join(n.get("traps", {})) or "none"
        parts.append(f"<details><summary><b>{n['id']}</b> ({n.get('set', '')}, {n.get('style', '')}) "
                     f"traps: {html.escape(traps)}</summary><pre>{html.escape(n['text'])}</pre>")
        for m in models:
            rec = preds[m].get(n["id"])
            pred = rec["extraction"] if rec else None
            f1 = S.total([S.score_note(n["gold"], pred)]).f1
            status = rec["status"] if rec else "missing"
            parts.append(f"<h4>{html.escape(m)}: field F1 {_pct(f1)} ({status})</h4><table>"
                         "<tr><th>Section</th><th>Key</th><th>Gold</th><th>Predicted</th></tr>")
            for s, key, g, p, ok in diff_rows(n["gold"], pred):
                parts.append(f"<tr class='{'ok' if ok else 'bad'}'><td>{s}</td><td>{html.escape(key)}</td>"
                             f"<td>{html.escape(g)}</td><td>{html.escape(p)}</td></tr>")
            parts.append("</table>")
            if rec and rec["status"] not in ("ok",) and rec.get("reply"):
                parts.append(f"<p>Raw reply:</p><pre>{html.escape(rec['reply'][:3000])}</pre>")
        parts.append("</details>")
    return "\n".join(parts)


def write_all(out: Path, notes: list[dict], results: dict[str, dict], preds: dict[str, dict[str, dict]]):
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    md = "# notes-to-fhir results\n\n" + leaderboard(results) + "\n\nAttribute accuracy (matched entities):\n\n" \
        + attribute_table(results) + "\n"
    (out / "leaderboard.md").write_text(md, encoding="utf-8")
    (out / "details.html").write_text(details_html(notes, preds), encoding="utf-8")
    return md
