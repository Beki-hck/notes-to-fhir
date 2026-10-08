"""A rule-based extractor: dictionary lookup, regular expressions and NegEx-style cues.

It is the comparison point for the models. It uses the same terminology tables
the scorer uses, plus generic patterns ("DOB:", "BP 120/80", "Allergies:"), and
no knowledge of which patient profile produced a note.
"""

from __future__ import annotations

import re
from datetime import date

from . import terminology as T
from .schema import Allergy, Condition, Extraction, Medication, Observation, Patient

NEGATION = re.compile(r"\b(denies|denied|no history of|no known|negative for|without|no)\b", re.I)
FAMILY = re.compile(r"\b(family history|fhx|mother|father|sister|brother|grandmother|grandfather|uncle|aunt)\b", re.I)
STOPPED = re.compile(r"\b(stopped|discontinued|d/c'?d|previously on|no longer)\b", re.I)
RESOLVED = re.compile(r"\b(resolved|remote)\b", re.I)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
                                       "oct", "nov", "dec"], 1)}

DOSE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|µg|units|unit|puffs|puff)\b", re.I)
DOSE_TO = re.compile(r"\bto\s+(\d+(?:\.\d+)?)\s*(mg|mcg|units|puffs)\b", re.I)


def _segments(text: str) -> list[str]:
    """Lines, then sentences, then '; ' items, so each piece mentions about one thing."""
    out = []
    for line in text.splitlines():
        for sent in re.split(r"(?<=[a-z0-9)%])\.\s+(?=[A-Z])", line):
            out.extend(p.strip() for p in sent.split(";") if p.strip())
    return out


def _find_terms(seg: str, index: dict[str, str]) -> list[tuple[int, str]]:
    """(position, key) for every synonym in a segment, longest match first, no overlaps."""
    hits, taken = [], []
    low = seg.lower()
    for syn in sorted(index, key=len, reverse=True):
        for m in re.finditer(rf"(?<![\w-]){re.escape(syn)}(?![\w-])", low):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            hits.append((m.start(), index[syn]))
    return sorted(hits)


def parse_date(text: str) -> str | None:
    t = text.strip()
    if m := re.match(r"(\d{4})-(\d{2})-(\d{2})", t):
        y, mo, d = map(int, m.groups())
    elif m := re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", t):
        mo, d, y = map(int, m.groups())
    elif m := re.match(r"([A-Za-z]{3})[a-z]*\.? (\d{1,2}),? (\d{4})", t):
        mo, d, y = MONTHS.get(m.group(1).lower()), int(m.group(2)), int(m.group(3))
    elif m := re.match(r"(\d{1,2})[ -]([A-Za-z]{3})[a-z]*[ -](\d{4})", t):
        d, mo, y = int(m.group(1)), MONTHS.get(m.group(2).lower()), int(m.group(3))
    else:
        return None
    try:
        return date(y, mo, d).isoformat()
    except (TypeError, ValueError):
        return None


def _patient(text: str) -> Patient:
    p = Patient()
    if m := re.search(r"(?:Patient|Name):\s*([A-Z][\w'-]+),\s*([A-Z][\w'-]+)", text):
        p.family_name, p.given_name = m.group(1), m.group(2)
    elif m := re.search(r"(?:Patient|Name):\s*([A-Z][\w'-]+)\s+([A-Z][\w'-]+)", text):
        p.given_name, p.family_name = m.group(1), m.group(2)
    elif m := re.match(r"([A-Z][A-Z'-]+),\s*([A-Z][\w'-]+)", text):
        p.family_name, p.given_name = m.group(1).title(), m.group(2)
    elif m := re.search(r"([A-Z][\w'-]+)\s+([A-Z][\w'-]+)\s*\((?:date of birth|DOB)", text):
        p.given_name, p.family_name = m.group(1), m.group(2)
    if m := re.search(r"(?:DOB|date of birth)[:\s]+(.{0,20})", text, re.I):
        p.birth_date = parse_date(m.group(1))
    if m := re.search(r"\b(?:Sex|Gender):\s*(male|female|m|f)\b", text, re.I):
        p.gender = "female" if m.group(1).lower().startswith("f") else "male"
    elif m := re.search(r"\d+[- ]?(?:year-old|yo)\s+(woman|female|f|man|male|m)\b", text, re.I):
        p.gender = "female" if m.group(1).lower() in ("woman", "female", "f") else "male"
    return p


def _conditions(segments: list[str]) -> list[Condition]:
    found: dict[str, str] = {}
    idx = T._COND_IDX
    for seg in segments:
        if FAMILY.search(seg) or re.match(r"\s*(all|allergies)\b", seg, re.I):
            continue
        hits = _find_terms(seg, idx)
        neg = NEGATION.search(seg)
        for pos, key in hits:
            if neg and neg.start() < pos:
                continue
            status = "resolved" if RESOLVED.search(seg) else "active"
            if found.get(key) != "active":
                found[key] = status
    return [Condition(name=k, clinical_status=v) for k, v in found.items()]


def _medications(segments: list[str]) -> list[Medication]:
    meds: dict[str, Medication] = {}
    for seg in segments:
        hits = _find_terms(seg, T._MED_IDX)
        for i, (pos, key) in enumerate(hits):
            end = hits[i + 1][0] if i + 1 < len(hits) else len(seg)
            part = seg[pos:end]
            stopped = bool(STOPPED.search(seg))
            dose = DOSE_TO.search(part) or DOSE.search(part)
            route = _longest(part, T._ROUTE_IDX)
            freq = _longest(part, T._FREQ_IDX)
            new = Medication(name=key, status="stopped" if stopped else "active",
                             dose_value=float(dose.group(1)) if dose else None,
                             dose_unit=T.norm_dose_unit(dose.group(2)) if dose else None,
                             route=route, frequency=freq)
            old = meds.get(key)
            if old is None:
                meds[key] = new
            else:  # a later mention (the plan) updates what it states
                for f in ("dose_value", "dose_unit", "route", "frequency"):
                    if getattr(new, f) is not None:
                        setattr(old, f, getattr(new, f))
                if stopped:
                    old.status = "stopped"
    return list(meds.values())


def _longest(text: str, index: dict[str, str]) -> str | None:
    hits = _find_terms(text, index)
    return hits[0][1] if hits else None


def _allergies(text: str) -> list[Allergy]:
    m = re.search(r"(?:Allergies|All):\s*(.+)", text) or re.search(r"allergies to (.+?)\.(?:\s|$)", text)
    if not m:
        return []
    out = []
    for item in re.split(r",(?![^(]*\))", m.group(1)):
        key = T.norm_allergen(re.sub(r"\(.*?\)", "", item))
        if key:
            r = re.search(r"\((.*?)\)", item)
            out.append(Allergy(substance=key, reaction=T.norm_reaction(r.group(1)) if r else None))
    return out


OBS_PATTERNS = [
    ("heart rate", r"\b(?:HR|P|pulse|heart rate)\s*(?:is\s*)?(\d{2,3})\b", "/min"),
    ("respiratory rate", r"\b(?:RR|respiratory rate)\s*(\d{1,2})\b", "/min"),
    ("oxygen saturation", r"\b(?:SpO2|O2 sat|oxygen saturation)\s*(\d{2,3})\s*%", "%"),
    ("hemoglobin a1c", r"\b(?:HbA1c|A1c|hemoglobin A1c)\s*(\d+(?:\.\d+)?)\s*%", "%"),
    ("glucose", r"\b(?:fasting glucose|glucose)\s*(\d+(?:\.\d+)?)\s*mg/dL", "mg/dL"),
    ("ldl cholesterol", r"\bLDL(?: cholesterol)?\s*(\d+(?:\.\d+)?)\s*mg/dL", "mg/dL"),
    ("creatinine", r"\b(?:creatinine|Cr)\s*(\d+(?:\.\d+)?)\s*mg/dL", "mg/dL"),
    ("tsh", r"\bTSH\s*(\d+(?:\.\d+)?)\s*mIU/L", "mIU/L"),
]


def _observations(text: str) -> list[Observation]:
    out = []
    if m := re.search(r"\b(\d{2,3})/(\d{2,3})\b(?!/)", text.split("BP", 1)[-1] if "BP" in text else
                      text.split("lood pressure", 1)[-1]):
        out.append(Observation(name="systolic blood pressure", value=float(m.group(1)), unit="mmHg"))
        out.append(Observation(name="diastolic blood pressure", value=float(m.group(2)), unit="mmHg"))
    for key, pat, unit in OBS_PATTERNS:
        if m := re.search(pat, text, re.I):
            out.append(Observation(name=key, value=float(m.group(1)), unit=unit))
    if m := re.search(r"\b(?:T|Temp|temperature)\s*(\d{2,3}(?:\.\d)?)\s*(?:degrees\s*)?(°?F|°?C|Fahrenheit|Celsius)",
                      text):
        out.append(Observation(name="body temperature", value=float(m.group(1)),
                               unit="degF" if m.group(2).lstrip("°")[0] == "F" else "Cel"))
    if m := re.search(r"\b(?:Wt|Weight|weighs)\s*(\d+(?:\.\d+)?)\s*(lb|kg|pounds|kilograms)", text, re.I):
        out.append(Observation(name="body weight", value=float(m.group(1)),
                               unit="lb" if m.group(2).lower() in ("lb", "pounds") else "kg"))
    return out


def extract(text: str) -> Extraction:
    segments = _segments(text)
    return Extraction(patient=_patient(text), conditions=_conditions(segments),
                      medications=_medications(segments), allergies=_allergies(text),
                      observations=_observations(text))
