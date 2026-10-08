"""Field-level scoring of a predicted extraction against the gold label.

Both sides are first mapped to canonical keys (terminology.py). Entities are
matched by key: a condition by its concept, a medication by its ingredient, an
observation by its LOINC concept. Then every field is counted:

- each matched or unmatched entity contributes one "present" field
- each attribute the gold label states (dose, route, status, value...) is one more field
- precision = correct fields / fields the model stated; recall = correct / gold fields

Attributes the gold label leaves empty (the dose of a drug stopped years ago, an
unknown allergic reaction) are not scored, so a model isn't punished for filling
them in. A predicted entity that maps to nothing in the tables counts as wrong.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field

from . import terminology as T
from .baseline import parse_date

SECTIONS = ("patient", "conditions", "medications", "allergies", "observations")
ATTRS = {
    "conditions": ("clinical_status",),
    "medications": ("dose_value", "dose_unit", "route", "frequency", "status"),
    "allergies": ("reaction",),
    "observations": ("value",),
}


def _num(x) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    m = re.search(r"-?\d+(?:\.\d+)?", str(x))
    return float(m.group()) if m else None


def _date(x) -> str | None:
    if not x:
        return None
    return parse_date(str(x)) or str(x).strip()


def canon_patient(p: dict | None) -> dict:
    p = p or {}
    return {"given_name": T.clean(p.get("given_name")) or None,
            "family_name": T.clean(p.get("family_name")) or None,
            "gender": T.clean(p.get("gender")) or None,
            "birth_date": _date(p.get("birth_date"))}


def _add(out: dict, key: str, attrs: dict, prefer=None):
    """Keep the first entity per key, unless `prefer` says the new one is better."""
    if key not in out or (prefer and prefer(attrs, out[key])):
        out[key] = attrs


def canon_entities(ex: dict) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {s: {} for s in SECTIONS[1:]}
    for c in ex.get("conditions") or []:
        key = T.norm_condition(c.get("name")) or f"?{T.clean(c.get('name'))}"
        _add(out["conditions"], key, {"clinical_status": c.get("clinical_status") or "active"},
             prefer=lambda new, old: new["clinical_status"] == "active")
    for m in ex.get("medications") or []:
        key = T.norm_medication(m.get("name")) or f"?{T.clean(m.get('name'))}"
        unit = T.norm_dose_unit(m.get("dose_unit"))
        _add(out["medications"], key, {
            "dose_value": _num(m.get("dose_value")),
            "dose_unit": unit if unit else (T.clean(m.get("dose_unit")) or None),
            "route": T.norm_route(m.get("route")) or (T.clean(m.get("route")) or None),
            "frequency": T.norm_frequency(m.get("frequency")) or (T.clean(m.get("frequency")) or None),
            "status": m.get("status") or "active",
        }, prefer=lambda new, old: new["status"] == "active" and old["status"] != "active")
    for a in ex.get("allergies") or []:
        key = T.norm_allergen(a.get("substance")) or f"?{T.clean(a.get('substance'))}"
        r = a.get("reaction")
        reaction = None
        if r and T.clean(r) not in ("unknown", "not stated", "none", "n/a", "reaction unknown"):
            reaction = T.norm_reaction(r) or T.clean(r)
        _add(out["allergies"], key, {"reaction": reaction})
    for o in ex.get("observations") or []:
        for key, value, unit in _split_observation(o):
            v = _num(value)
            if v is None:
                continue
            if key.startswith("?"):
                _add(out["observations"], key, {"value": v})
            else:
                cv, _ = T.to_canonical(key, v, unit)
                _add(out["observations"], key, {"value": cv})
    return out


def _split_observation(o: dict):
    """Yield (key, value, unit); a blood pressure written as '132/84' becomes two readings."""
    name, value, unit = o.get("name"), o.get("value"), o.get("unit")
    key = T.norm_observation(name)
    bp = re.fullmatch(r"\s*(\d{2,3})\s*/\s*(\d{2,3})\s*", str(value)) if value is not None else None
    if bp and (key in (None, "systolic blood pressure", "diastolic blood pressure")):
        yield "systolic blood pressure", bp.group(1), "mmHg"
        yield "diastolic blood pressure", bp.group(2), "mmHg"
        return
    yield (key or f"?{T.clean(name)}"), value, unit


def values_equal(section: str, attr: str, gold, pred) -> bool:
    if gold is None or pred is None:
        return False
    if attr in ("value", "dose_value"):
        return math.isclose(float(gold), float(pred), rel_tol=0.01, abs_tol=0.11)
    return gold == pred


@dataclass
class Counts:
    correct: int = 0
    gold: int = 0
    pred: int = 0
    tp: int = 0   # entities
    fn: int = 0
    fp: int = 0
    attr_correct: dict = field(default_factory=dict)
    attr_total: dict = field(default_factory=dict)

    def add(self, other: "Counts"):
        for f in ("correct", "gold", "pred", "tp", "fn", "fp"):
            setattr(self, f, getattr(self, f) + getattr(other, f))
        for k, v in other.attr_correct.items():
            self.attr_correct[k] = self.attr_correct.get(k, 0) + v
        for k, v in other.attr_total.items():
            self.attr_total[k] = self.attr_total.get(k, 0) + v

    @property
    def precision(self):
        return self.correct / self.pred if self.pred else 0.0

    @property
    def recall(self):
        return self.correct / self.gold if self.gold else 0.0

    @property
    def f1(self):
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def entity_f1(self):
        d = 2 * self.tp + self.fp + self.fn
        return 2 * self.tp / d if d else 1.0


def _score_section(section: str, gold: dict, pred: dict) -> Counts:
    c = Counts()
    for key, g in gold.items():
        attrs = {a: v for a, v in g.items() if v is not None}
        c.gold += 1 + len(attrs)
        p = pred.get(key)
        if p is None:
            c.fn += 1
            continue
        c.tp += 1
        c.pred += 1
        c.correct += 1
        for a, gv in attrs.items():
            c.attr_total[a] = c.attr_total.get(a, 0) + 1
            pv = p.get(a)
            if pv is not None:
                c.pred += 1
            if values_equal(section, a, gv, pv):
                c.correct += 1
                c.attr_correct[a] = c.attr_correct.get(a, 0) + 1
    for key, p in pred.items():
        if key not in gold:
            c.fp += 1
            c.pred += 1 + sum(v is not None for v in p.values())
    return c


def score_note(gold: dict, pred: dict | None) -> dict[str, Counts]:
    """Counts per section for one note. `pred` None (unparseable reply) scores as all missed."""
    pred = pred or {}
    out = {}
    gp, pp = canon_patient(gold.get("patient")), canon_patient(pred.get("patient"))
    pc = Counts()
    for f, gv in gp.items():
        if gv is None:
            continue
        pc.gold += 1
        pc.attr_total[f] = 1
        if pp.get(f) is not None:
            pc.pred += 1
        if pp.get(f) == gv:
            pc.correct += 1
            pc.attr_correct[f] = 1
    out["patient"] = pc
    ge, pe = canon_entities(gold), canon_entities(pred)
    for s in SECTIONS[1:]:
        out[s] = _score_section(s, ge[s], pe[s])
    return out


def trap_outcomes(note: dict, pred: dict | None) -> dict[str, list[bool]]:
    """For each trap in the note, whether the model handled it. One bool per trapped item."""
    pe = canon_entities(pred or {})
    ge = canon_entities(note["gold"])
    out: dict[str, list[bool]] = {}
    for trap, keys in note.get("traps", {}).items():
        res = []
        for k in keys:
            if trap in ("negated", "family_history"):
                res.append(k not in pe["conditions"])
            elif trap == "resolved":
                res.append(pe["conditions"].get(k, {}).get("clinical_status") == "resolved")
            elif trap == "stopped_med":
                res.append(pe["medications"].get(k, {}).get("status") == "stopped")
            elif trap == "dose_change":
                g, p = ge["medications"][k], pe["medications"].get(k, {})
                res.append(values_equal("medications", "dose_value", g["dose_value"], p.get("dose_value")))
            elif trap in ("new_med", "brand_name"):
                res.append(k in pe["medications"])
            elif trap in ("prior_lab", "unit_conversion"):
                g, p = ge["observations"][k], pe["observations"].get(k, {})
                res.append(values_equal("observations", "value", g["value"], p.get("value")))
        out[trap] = res
    return out


def total(per_note: list[dict[str, Counts]], sections=SECTIONS) -> Counts:
    t = Counts()
    for note in per_note:
        for s in sections:
            t.add(note[s])
    return t


def bootstrap_f1(per_note: list[dict[str, Counts]], n: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% interval for overall field F1, resampling notes with replacement."""
    if not per_note:
        return 0.0, 0.0
    rng = random.Random(seed)
    flat = [(sum(c.correct for c in note.values()), sum(c.gold for c in note.values()),
             sum(c.pred for c in note.values())) for note in per_note]
    scores = []
    for _ in range(n):
        cor = gol = pre = 0
        for _ in flat:
            a, b, c = flat[rng.randrange(len(flat))]
            cor, gol, pre = cor + a, gol + b, pre + c
        p, r = (cor / pre if pre else 0), (cor / gol if gol else 0)
        scores.append(2 * p * r / (p + r) if p + r else 0.0)
    scores.sort()
    return scores[int(0.025 * n)], scores[int(0.975 * n) - 1]
