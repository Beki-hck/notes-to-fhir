"""Seeded generator for synthetic clinical notes with gold labels.

Each note comes from a random patient profile, written in one of four styles
(SOAP note, narrative H&P, terse abbreviated note, discharge summary). The gold
label is built from the profile, not parsed back out of the text, so it can't
inherit a parser's mistakes.

Notes include the traps that make real extraction hard:

- negated:        "Denies history of asthma."            -> must not be extracted
- family_history: "Mother with breast cancer."           -> must not be extracted
- stopped_med:    "Simvastatin stopped due to myalgias."  -> status "stopped"
- dose_change:    list says 10 mg, plan says increase to 20 mg -> 20 mg
- new_med:        "Start atorvastatin 40 mg nightly."    -> active medication
- resolved:       "History of pneumonia, resolved."      -> clinical_status "resolved"
- prior_lab:      "A1c 7.4% (8.1% in May)"               -> today's value only
- brand_name:     "Lipitor 40 mg"                        -> atorvastatin
- unit_conversion: weight in lb, temperature in °F       -> scored after conversion

No real patient data is used. Names are drawn from mixed lists and paired at random.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import terminology as T

DATA_PATH = Path(__file__).parent / "data" / "notes.jsonl"
DEFAULT_N = 50
DEFAULT_SEED = 2026

GIVEN = {
    "female": ["Maria", "Selam", "Linda", "Aisha", "Grace", "Hana", "Patricia", "Mei", "Fatima",
               "Rosa", "Helen", "Tigist", "Sarah", "Priya", "Yesenia", "Dorothy", "Mekdes", "Joy",
               "Keisha", "Elena", "Martha", "Nadia", "Bethlehem", "Ruth", "Ngozi"],
    "male": ["James", "Dawit", "Robert", "Ahmed", "Luis", "Samuel", "Wei", "Michael", "Yonas",
             "Carlos", "David", "Kwame", "Thomas", "Raj", "Abebe", "William", "Hector", "Daniel",
             "Tesfaye", "Andre", "George", "Omar", "Henok", "Peter", "Jamal"],
}
FAMILY = ["Johnson", "Tadesse", "Garcia", "Nguyen", "Okafor", "Smith", "Haile", "Patel", "Kim",
          "Rodriguez", "Bekele", "Williams", "Chen", "Mensah", "Lopez", "Alemu", "Brown", "Ali",
          "Martinez", "Girma", "Davis", "Wolde", "Hernandez", "Osei", "Miller", "Kebede", "Wilson",
          "Mekonnen", "Anderson", "Singh"]

CHRONIC = ["hypertension", "type 2 diabetes", "hyperlipidemia", "asthma", "copd", "gerd",
           "hypothyroidism", "osteoarthritis", "major depressive disorder",
           "generalized anxiety disorder", "atrial fibrillation", "chronic kidney disease",
           "migraine", "coronary artery disease", "heart failure", "obesity",
           "iron deficiency anemia"]
CHRONIC_WEIGHTS = [10, 8, 8, 4, 3, 5, 4, 4, 3, 3, 3, 2, 3, 3, 2, 3, 2]
ACUTE = ["pneumonia", "urinary tract infection"]
RESOLVABLE = ["pneumonia", "urinary tract infection", "iron deficiency anemia"]
NEGATABLE = ["asthma", "copd", "type 2 diabetes", "coronary artery disease", "heart failure",
             "atrial fibrillation", "chronic kidney disease", "hypothyroidism", "stroke",
             "myocardial infarction", "major depressive disorder"]
FAMILY_HX = ["breast cancer", "colon cancer", "stroke", "myocardial infarction", "alzheimer disease",
             "type 2 diabetes", "hypertension", "coronary artery disease"]
RELATIVES = ["mother", "father", "sister", "brother", "maternal grandmother", "paternal uncle"]

# condition -> (drug, dose options, unit, route, frequency)
MED_OPTIONS = {
    "hypertension": [("lisinopril", [10, 20, 40], "mg", "oral", "once daily"),
                     ("amlodipine", [5, 10], "mg", "oral", "once daily"),
                     ("losartan", [50, 100], "mg", "oral", "once daily"),
                     ("hydrochlorothiazide", [12.5, 25], "mg", "oral", "once daily")],
    "type 2 diabetes": [("metformin", [500, 1000], "mg", "oral", "twice daily"),
                        ("empagliflozin", [10, 25], "mg", "oral", "once daily"),
                        ("insulin glargine", [10, 14, 20, 24, 30], "units", "subcutaneous", "at bedtime")],
    "hyperlipidemia": [("atorvastatin", [20, 40, 80], "mg", "oral", "at bedtime"),
                       ("rosuvastatin", [10, 20], "mg", "oral", "once daily"),
                       ("simvastatin", [20, 40], "mg", "oral", "at bedtime")],
    "asthma": [("albuterol", [2], "puffs", "inhaled", "as needed"),
               ("fluticasone", [110, 220], "mcg", "inhaled", "twice daily")],
    "copd": [("tiotropium", [18], "mcg", "inhaled", "once daily"),
             ("albuterol", [2], "puffs", "inhaled", "as needed")],
    "gerd": [("omeprazole", [20, 40], "mg", "oral", "once daily"),
             ("pantoprazole", [40], "mg", "oral", "once daily")],
    "hypothyroidism": [("levothyroxine", [50, 75, 88, 100, 125], "mcg", "oral", "once daily")],
    "osteoarthritis": [("acetaminophen", [500, 650], "mg", "oral", "as needed"),
                       ("ibuprofen", [400, 600], "mg", "oral", "three times daily")],
    "major depressive disorder": [("sertraline", [50, 100], "mg", "oral", "once daily"),
                                  ("escitalopram", [10, 20], "mg", "oral", "once daily")],
    "generalized anxiety disorder": [("buspirone", [10, 15], "mg", "oral", "twice daily"),
                                     ("escitalopram", [10], "mg", "oral", "once daily")],
    "atrial fibrillation": [("apixaban", [5], "mg", "oral", "twice daily"),
                            ("metoprolol", [25, 50], "mg", "oral", "twice daily"),
                            ("warfarin", [5], "mg", "oral", "once daily")],
    "chronic kidney disease": [("furosemide", [20, 40], "mg", "oral", "once daily")],
    "migraine": [("sumatriptan", [50, 100], "mg", "oral", "as needed")],
    "coronary artery disease": [("aspirin", [81], "mg", "oral", "once daily"),
                                ("atorvastatin", [40, 80], "mg", "oral", "at bedtime"),
                                ("metoprolol", [25, 50], "mg", "oral", "twice daily")],
    "heart failure": [("furosemide", [20, 40], "mg", "oral", "once daily"),
                      ("carvedilol", [6.25, 12.5], "mg", "oral", "twice daily")],
    "obesity": [],
    "iron deficiency anemia": [("ferrous sulfate", [325], "mg", "oral", "once daily")],
    "pneumonia": [("amoxicillin", [875], "mg", "oral", "twice daily")],
    "urinary tract infection": [("nitrofurantoin", [100], "mg", "oral", "twice daily")],
}
CONFLICTS = [{"apixaban", "warfarin"}, {"atorvastatin", "simvastatin", "rosuvastatin"},
             {"sertraline", "escitalopram"}, {"metoprolol", "carvedilol"},
             {"omeprazole", "pantoprazole"}, {"lisinopril", "losartan"}]
STOP_REASONS = {
    "simvastatin": "myalgias", "atorvastatin": "muscle aches", "rosuvastatin": "myalgias",
    "metformin": "GI upset", "lisinopril": "a persistent dry cough", "amlodipine": "ankle swelling",
    "sertraline": "insomnia", "escitalopram": "fatigue", "warfarin": "difficulty keeping the INR in range",
    "ibuprofen": "worsening kidney function", "metoprolol": "bradycardia",
}
BRANDS = {"metformin": "Glucophage", "lisinopril": "Zestril", "amlodipine": "Norvasc",
          "losartan": "Cozaar", "atorvastatin": "Lipitor", "simvastatin": "Zocor",
          "rosuvastatin": "Crestor", "levothyroxine": "Synthroid", "albuterol": "ProAir",
          "fluticasone": "Flovent", "tiotropium": "Spiriva", "omeprazole": "Prilosec",
          "pantoprazole": "Protonix", "sertraline": "Zoloft", "escitalopram": "Lexapro",
          "apixaban": "Eliquis", "warfarin": "Coumadin", "furosemide": "Lasix",
          "insulin glargine": "Lantus", "empagliflozin": "Jardiance", "carvedilol": "Coreg",
          "sumatriptan": "Imitrex", "acetaminophen": "Tylenol", "ibuprofen": "Motrin"}

LABS = {
    "type 2 diabetes": [("hemoglobin a1c", (6.4, 9.8), 1, "%"), ("glucose", (104, 228), 0, "mg/dL")],
    "hyperlipidemia": [("ldl cholesterol", (72, 188), 0, "mg/dL")],
    "chronic kidney disease": [("creatinine", (1.4, 2.8), 1, "mg/dL")],
    "hypothyroidism": [("tsh", (0.8, 8.6), 1, "mIU/L")],
}

# Surface forms used when writing the note. Several per concept, so models see variety.
COND_SURFACE = {
    "hypertension": ["hypertension", "HTN", "high blood pressure", "essential hypertension"],
    "type 2 diabetes": ["type 2 diabetes", "T2DM", "type 2 diabetes mellitus", "DM2", "diabetes mellitus type 2"],
    "hyperlipidemia": ["hyperlipidemia", "HLD", "high cholesterol"],
    "asthma": ["asthma"],
    "copd": ["COPD", "chronic obstructive pulmonary disease"],
    "gerd": ["GERD", "gastroesophageal reflux disease", "acid reflux"],
    "hypothyroidism": ["hypothyroidism"],
    "osteoarthritis": ["osteoarthritis", "OA", "degenerative joint disease"],
    "major depressive disorder": ["major depressive disorder", "MDD", "depression"],
    "generalized anxiety disorder": ["generalized anxiety disorder", "GAD"],
    "atrial fibrillation": ["atrial fibrillation", "AFib", "paroxysmal atrial fibrillation"],
    "chronic kidney disease": ["chronic kidney disease", "CKD stage 3", "CKD"],
    "migraine": ["migraine", "migraine headaches"],
    "coronary artery disease": ["coronary artery disease", "CAD"],
    "heart failure": ["heart failure", "CHF", "congestive heart failure"],
    "obesity": ["obesity"],
    "iron deficiency anemia": ["iron deficiency anemia"],
    "pneumonia": ["pneumonia", "community-acquired pneumonia"],
    "urinary tract infection": ["urinary tract infection", "UTI"],
    "breast cancer": ["breast cancer"], "colon cancer": ["colon cancer"],
    "stroke": ["stroke", "CVA"], "myocardial infarction": ["MI", "a heart attack", "myocardial infarction"],
    "alzheimer disease": ["Alzheimer's disease", "Alzheimer's"],
}
FREQ_SURFACE = {
    "once daily": ["daily", "once daily", "qd", "once a day", "every morning"],
    "twice daily": ["BID", "twice daily", "twice a day", "b.i.d.", "every 12 hours"],
    "three times daily": ["TID", "three times daily", "three times a day"],
    "at bedtime": ["at bedtime", "qhs", "nightly"],
    "as needed": ["PRN", "as needed"],
}
PRN_SURFACE = {"albuterol": ["every 4-6 hours as needed for wheezing", "q4-6h PRN", "PRN wheezing"],
               "acetaminophen": ["every 6 hours as needed for pain", "q6h PRN pain"],
               "sumatriptan": ["PRN migraine", "as needed at migraine onset"]}
ROUTE_SURFACE = {"oral": ["PO", "by mouth", "orally", "PO"], "inhaled": ["inhaled", "via inhaler", "inh"],
                 "subcutaneous": ["SC", "subcutaneously", "subQ"]}
ALLERGY_REACTIONS = ["hives", "rash", "anaphylaxis", "swelling", "nausea", "shortness of breath", "itching"]
ALLERGEN_SURFACE = {"penicillin": ["penicillin", "PCN"], "sulfonamide": ["sulfa drugs", "sulfa"],
                    "peanut": ["peanuts"], "shellfish": ["shellfish"], "latex": ["latex"],
                    "codeine": ["codeine"], "egg": ["eggs"], "iodinated contrast": ["IV contrast"],
                    "cephalosporin": ["cephalosporins", "cephalexin"], "morphine": ["morphine"]}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


@dataclass
class Med:
    drug: str
    dose: float | None
    unit: str | None
    route: str | None
    freq: str | None
    status: str = "active"
    trap: str | None = None
    old_dose: float | None = None   # dose_change: what the medication list still says
    brand: bool = False


@dataclass
class Profile:
    given: str
    family: str
    gender: str
    dob: date
    visit: date
    style: str
    conditions: list[str]
    acute: str | None
    resolved: list[tuple[str, int]]
    meds: list[Med]
    allergies: list[tuple[str, str | None]]
    vitals: list[tuple[str, float, str]]
    labs: list[tuple[str, float, str, float | None]]  # (key, value, unit, prior value)
    negated: list[str] = field(default_factory=list)
    family_hx: list[tuple[str, str]] = field(default_factory=list)
    traps: list[str] = field(default_factory=list)

    @property
    def age(self) -> int:
        v, b = self.visit, self.dob
        return v.year - b.year - ((v.month, v.day) < (b.month, b.day))


def _fmt_num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _conflicts(drug: str, taken: set[str]) -> bool:
    if drug in taken:
        return True
    return any(drug in group and taken & (group - {drug}) for group in CONFLICTS)


def make_profile(rng: random.Random, style: str) -> Profile:
    gender = rng.choice(["female", "male"])
    dob = date(1940, 1, 1) + timedelta(days=rng.randrange(0, 365 * 50))
    visit = date(2026, 1, 5) + timedelta(days=rng.randrange(0, 260))

    k = rng.choice([1, 2, 2, 3, 3, 4])
    conditions: list[str] = []
    while len(conditions) < k:
        c = rng.choices(CHRONIC, CHRONIC_WEIGHTS)[0]
        if c not in conditions:
            conditions.append(c)
    acute = rng.choice(ACUTE) if rng.random() < 0.2 else None
    resolved = []
    if rng.random() < 0.3:
        r = rng.choice([c for c in RESOLVABLE if c not in conditions and c != acute])
        resolved.append((r, visit.year - rng.randint(1, 6)))

    traps: list[str] = []
    meds: list[Med] = []
    taken: set[str] = set()
    for c in conditions:
        options = [o for o in MED_OPTIONS[c] if not _conflicts(o[0], taken)]
        rng.shuffle(options)
        for drug, doses, unit, route, freq in options[: rng.choice([1, 1, 2])]:
            if _conflicts(drug, taken):
                continue
            meds.append(Med(drug, rng.choice(doses), unit, route, freq))
            taken.add(drug)

    # Trap: a medication was stopped (with a reason). Dose often omitted.
    stoppable = [o for c in conditions for o in MED_OPTIONS[c]
                 if o[0] in STOP_REASONS and not _conflicts(o[0], taken - {o[0]}) and o[0] not in taken]
    if stoppable and rng.random() < 0.4:
        drug, doses, unit, *_ = rng.choice(stoppable)
        with_dose = rng.random() < 0.5
        meds.append(Med(drug, rng.choice(doses) if with_dose else None, unit if with_dose else None,
                        None, None, status="stopped", trap="stopped_med"))
        taken.add(drug)
        traps.append("stopped_med")

    # Trap: the plan changes a dose that the medication list still shows at the old value.
    changeable = [m for m in meds if m.status == "active" and m.trap is None
                  and len(_doses(m.drug)) > 1]
    if changeable and rng.random() < 0.3:
        m = rng.choice(changeable)
        others = [d for d in _doses(m.drug) if d != m.dose]
        m.old_dose, m.dose = m.dose, rng.choice(others)
        m.trap = "dose_change"
        traps.append("dose_change")

    # Trap: a medication started today, mentioned only in the plan.
    startable = [(c, o) for c in conditions for o in MED_OPTIONS[c] if not _conflicts(o[0], taken)]
    if acute:
        drug, doses, unit, route, freq = MED_OPTIONS[acute][0]
        meds.append(Med(drug, doses[0], unit, route, freq, trap="new_med"))
        taken.add(drug)
        traps.append("new_med")
    elif startable and rng.random() < 0.3:
        _, (drug, doses, unit, route, freq) = rng.choice(startable)
        meds.append(Med(drug, rng.choice(doses), unit, route, freq, trap="new_med"))
        taken.add(drug)
        traps.append("new_med")

    for m in meds:
        if m.drug in BRANDS and rng.random() < 0.2:
            m.brand = True
    if any(m.brand for m in meds):
        traps.append("brand_name")

    allergies: list[tuple[str, str | None]] = []
    if rng.random() < 0.6:
        for a in rng.sample(list(T.ALLERGENS), rng.choice([1, 1, 2])):
            allergies.append((a, rng.choice(ALLERGY_REACTIONS) if rng.random() < 0.8 else None))

    sick = acute is not None
    temp_f = round(rng.uniform(100.6, 102.4) if sick else rng.uniform(97.6, 99.2), 1)
    weight_kg = round(rng.uniform(50, 120), 1)
    vitals = [
        ("systolic blood pressure", rng.randint(108, 166), "mmHg"),
        ("diastolic blood pressure", rng.randint(62, 98), "mmHg"),
        ("heart rate", rng.randint(58, 112 if sick else 96), "/min"),
    ]
    if rng.random() < 0.65:
        vitals.append(("body temperature", temp_f, "degF"))
    else:
        vitals.append(("body temperature", round((temp_f - 32) * 5 / 9, 1), "Cel"))
    if rng.random() < 0.55:
        vitals.append(("body weight", round(weight_kg / 0.45359237), "lb"))
    else:
        vitals.append(("body weight", weight_kg, "kg"))
    if rng.random() < 0.8:
        vitals.append(("oxygen saturation", rng.randint(89, 94) if acute == "pneumonia" else rng.randint(94, 99), "%"))
    if rng.random() < 0.5:
        vitals.append(("respiratory rate", rng.randint(20, 26) if acute == "pneumonia" else rng.randint(12, 18), "/min"))
    if any(u in ("lb", "degF") for _, _, u in vitals):
        traps.append("unit_conversion")

    labs = []
    for c in conditions:
        for key, (lo, hi), nd, unit in LABS.get(c, []):
            value = round(rng.uniform(lo, hi), nd)
            prior = None
            if key in ("hemoglobin a1c", "ldl cholesterol", "tsh") and rng.random() < 0.4:
                prior = round(value + rng.choice([-1, 1]) * rng.uniform(0.4, 1.6) * (30 if key == "ldl cholesterol" else 1), nd)
                prior = max(prior, 0.3)
            labs.append((key, int(value) if nd == 0 else value, unit, prior))
    if any(p is not None for *_, p in labs):
        traps.append("prior_lab")

    negated = []
    if rng.random() < 0.5:
        pool = [c for c in NEGATABLE if c not in conditions]
        negated = rng.sample(pool, rng.choice([1, 1, 2]))
        traps.append("negated")
    family_hx = []
    if rng.random() < 0.6:
        pool = [c for c in FAMILY_HX if c not in conditions and c not in negated]
        family_hx = [(rng.choice(RELATIVES), c) for c in rng.sample(pool, rng.choice([1, 2]))]
        traps.append("family_history")
    if resolved:
        traps.append("resolved")

    gender_names = GIVEN[gender]
    return Profile(rng.choice(gender_names), rng.choice(FAMILY), gender, dob, visit, style,
                   conditions, acute, resolved, meds, allergies, vitals, labs, negated, family_hx,
                   sorted(set(traps)))


def _doses(drug: str) -> list[float]:
    for options in MED_OPTIONS.values():
        for o in options:
            if o[0] == drug:
                return o[1]
    return []


# ---------------------------------------------------------------- rendering


class Writer:
    def __init__(self, p: Profile, rng: random.Random):
        self.p, self.rng = p, rng

    def pick(self, xs):
        return self.rng.choice(xs)

    def cond(self, key):
        return self.pick(COND_SURFACE[key])

    def dob(self):
        d = self.p.dob
        return self.pick([f"{d.month:02d}/{d.day:02d}/{d.year}", d.isoformat(),
                          f"{MONTHS[d.month - 1]} {d.day}, {d.year}",
                          f"{d.day} {MONTHS[d.month - 1][:3]} {d.year}",
                          f"{d.day:02d}-{MONTHS[d.month - 1][:3]}-{d.year}"])

    def visit(self):
        v = self.p.visit
        return self.pick([f"{v.month:02d}/{v.day:02d}/{v.year}", f"{MONTHS[v.month - 1]} {v.day}, {v.year}"])

    def sex_word(self):
        return {"female": self.pick(["woman", "female"]), "male": self.pick(["man", "male"])}[self.p.gender]

    def drug_name(self, m: Med):
        if m.brand:
            return BRANDS[m.drug]
        return m.drug

    def med_line(self, m: Med, dose=None, terse=False):
        dose = m.dose if dose is None else dose
        name = self.drug_name(m)
        if m.drug in PRN_SURFACE and m.freq == "as needed":
            freq = self.pick(PRN_SURFACE[m.drug])
        else:
            freq = self.pick(FREQ_SURFACE[m.freq])
        route = self.pick(ROUTE_SURFACE[m.route])
        sp = "" if terse and m.unit in ("mg", "mcg") else " "
        if m.unit == "puffs":
            amount = f"{_fmt_num(dose)} puffs"
            name = f"{name} HFA" if m.drug == "albuterol" and not m.brand else name
        else:
            amount = f"{_fmt_num(dose)}{sp}{m.unit}"
        return f"{name} {amount} {route} {freq}"

    def stopped_sentence(self, m: Med):
        name = self.drug_name(m)
        name_cap = name[0].upper() + name[1:]
        reason = STOP_REASONS[m.drug]
        dose = f" {_fmt_num(m.dose)} {m.unit}" if m.dose is not None else ""
        month = self.pick(MONTHS)
        return self.pick([
            f"{name_cap}{dose} was discontinued in {month} because of {reason}.",
            f"Previously on {name}{dose}; stopped due to {reason}.",
            f"{name_cap}{dose} was stopped last year ({reason}) and has not been restarted.",
        ])

    def vitals_line(self, terse=False):
        v = {k: (val, unit) for k, val, unit in self.p.vitals}
        parts = [f"BP {v['systolic blood pressure'][0]}/{v['diastolic blood pressure'][0]}"
                 + ("" if terse else self.pick(["", " mmHg"]))]
        parts.append(self.pick(["HR", "P", "pulse"]) + f" {v['heart rate'][0]}" + self.pick(["", " bpm"]))
        t, tu = v["body temperature"]
        parts.append(self.pick(["T", "Temp"]) + f" {t}" + ("F" if tu == "degF" else "C")
                     if terse else self.pick(["T", "Temp"]) + f" {t} " + ("°F" if tu == "degF" else "°C"))
        if "respiratory rate" in v:
            parts.append(f"RR {v['respiratory rate'][0]}")
        if "oxygen saturation" in v:
            parts.append(self.pick(["SpO2", "O2 sat"]) + f" {v['oxygen saturation'][0]}%" + self.pick(["", " on room air", " RA"]))
        w, wu = v["body weight"]
        parts.append(self.pick(["Wt", "Weight"]) + f" {_fmt_num(w)} " + ("lb" if wu == "lb" else "kg"))
        sep = " | " if terse else ", "
        return sep.join(parts)

    def vitals_prose(self):
        v = {k: (val, unit) for k, val, unit in self.p.vitals}
        t, tu = v["body temperature"]
        w, wu = v["body weight"]
        s = (f"Blood pressure is {v['systolic blood pressure'][0]}/{v['diastolic blood pressure'][0]} mmHg, "
             f"heart rate {v['heart rate'][0]} beats per minute, temperature {t} degrees "
             + ("Fahrenheit" if tu == "degF" else "Celsius"))
        if "respiratory rate" in v:
            s += f", respiratory rate {v['respiratory rate'][0]}"
        if "oxygen saturation" in v:
            s += f", and oxygen saturation {v['oxygen saturation'][0]}% on room air"
        s += f". She weighs {_fmt_num(w)} " if self.p.gender == "female" else f". He weighs {_fmt_num(w)} "
        s += ("pounds." if wu == "lb" else "kilograms.")
        return s

    def labs_line(self):
        names = {"hemoglobin a1c": ["HbA1c", "A1c", "hemoglobin A1c"],
                 "glucose": ["fasting glucose", "glucose"], "ldl cholesterol": ["LDL", "LDL cholesterol"],
                 "creatinine": ["creatinine", "Cr"], "tsh": ["TSH"]}
        out = []
        for key, value, unit, prior in self.p.labs:
            name = self.pick(names[key])
            unit_s = "%" if unit == "%" else f" {unit}"
            s = f"{name} {_fmt_num(value)}{unit_s}"
            if prior is not None:
                when = self.pick(MONTHS[: max(1, self.p.visit.month - 1)])
                s += self.pick([f" (previously {_fmt_num(prior)}{unit_s} in {when})",
                                f", down from {_fmt_num(prior)}{unit_s} in {when}" if prior > value
                                else f", up from {_fmt_num(prior)}{unit_s} in {when}"])
            out.append(s)
        return "; ".join(out)

    def allergy_text(self):
        if not self.p.allergies:
            return self.pick(["NKDA", "No known drug allergies", "None known", "NKA"])
        parts = []
        for a, r in self.p.allergies:
            s = self.pick(ALLERGEN_SURFACE[a])
            parts.append(f"{s} ({r})" if r else f"{s} (reaction unknown)")
        return ", ".join(parts)

    def negation_sentence(self):
        names = [self.cond(c) for c in self.p.negated]
        joined = " or ".join(names)
        return self.pick([f"Denies history of {joined}.", f"No history of {joined}.",
                          f"Negative for {joined}.", f"No known {joined}."])

    def family_sentence(self, terse=False):
        parts = []
        for rel, c in self.p.family_hx:
            if terse:
                parts.append(f"{rel} - {self.cond(c)}")
            else:
                parts.append(self.pick([f"{rel} with {self.cond(c)}", f"{rel} had {self.cond(c)}"]))
        s = "; ".join(parts)
        return s[0].upper() + s[1:] + "."

    def resolved_sentence(self):
        c, year = self.p.resolved[0]
        return self.pick([f"History of {self.cond(c)} in {year}, resolved.",
                          f"{self.cond(c).capitalize()} in {year}, fully treated and resolved.",
                          f"Remote {self.cond(c)} ({year}), resolved."])

    def plan_items(self):
        items = []
        for m in self.p.meds:
            if m.trap == "dose_change":
                verb = "Increase" if m.dose > m.old_dose else "Decrease"
                items.append(f"{verb} {self.drug_name(m)} from {_fmt_num(m.old_dose)} {m.unit} to "
                             f"{_fmt_num(m.dose)} {m.unit} {self.pick(FREQ_SURFACE[m.freq])}.")
            if m.trap == "new_med":
                items.append(f"Start {self.med_line(m)}.")
        items.append(self.pick(["Follow up in 3 months.", "Return in 6 weeks.", "Recheck labs before next visit.",
                                "Follow up in 4 weeks or sooner if symptoms worsen."]))
        return items

    def listed_meds(self, terse=False):
        """The medication list as it stood before today's changes."""
        return [self.med_line(m, dose=m.old_dose if m.trap == "dose_change" else None, terse=terse)
                for m in self.p.meds if m.status == "active" and m.trap != "new_med"]

    def complaint(self, admitted=False):
        p = self.p
        if p.acute == "pneumonia":
            return self.pick(["cough and fever for 4 days", "productive cough, fever and shortness of breath"])
        if p.acute == "urinary tract infection":
            return self.pick(["burning with urination for 3 days", "dysuria and urinary frequency"])
        if admitted:
            return self.pick(["dehydration", "dizziness", "a fall at home", "chest pain with a negative cardiac workup"])
        return self.pick(["follow-up of chronic conditions", "routine follow-up", "medication review",
                          "annual physical", "follow-up visit"])

    def assessment(self):
        out = [self.cond(c) for c in self.p.conditions]
        if self.p.acute:
            out.insert(0, self.cond(self.p.acute))
        return out


def render_soap(p: Profile, rng: random.Random) -> str:
    w = Writer(p, rng)
    lines = [
        "CLINIC NOTE",
        f"Patient: {p.given} {p.family}    DOB: {w.dob()}    Sex: {w.pick(['F', 'Female']) if p.gender == 'female' else w.pick(['M', 'Male'])}",
        f"Date of visit: {w.visit()}",
        "",
        "SUBJECTIVE:",
        f"{p.age}-year-old {w.sex_word()} presenting for {w.complaint()}. "
        f"Past medical history significant for {', '.join(w.cond(c) for c in p.conditions)}."
        + (f" {w.resolved_sentence()}" if p.resolved else "")
        + (f" {w.negation_sentence()}" if p.negated else ""),
    ]
    if p.family_hx:
        lines.append(f"Family history: {w.family_sentence()}")
    lines += ["", "Current medications:"]
    lines += [f"- {m}" for m in w.listed_meds()] or ["- none"]
    for m in p.meds:
        if m.status == "stopped":
            lines.append(w.stopped_sentence(m))
    lines += [f"Allergies: {w.allergy_text()}", "", "OBJECTIVE:", f"Vitals: {w.vitals_line()}"]
    if p.labs:
        lines.append(f"Labs: {w.labs_line()}")
    lines += ["", "ASSESSMENT:"]
    lines += [f"{i}. {a}" for i, a in enumerate(w.assessment(), 1)]
    lines += ["", "PLAN:"]
    lines += [f"- {x}" for x in w.plan_items()]
    return "\n".join(lines)


def render_narrative(p: Profile, rng: random.Random) -> str:
    w = Writer(p, rng)
    he = "She" if p.gender == "female" else "He"
    his = "Her" if p.gender == "female" else "His"
    meds = w.listed_meds()
    s = [f"HISTORY AND PHYSICAL — {w.visit()}",
         f"{p.given} {p.family} (date of birth {w.dob()}) is a {p.age}-year-old {w.sex_word()} seen today for "
         f"{w.complaint()}. {his} history includes {', '.join(w.cond(c) for c in p.conditions[:-1])}"
         + (" and " if len(p.conditions) > 1 else "") + f"{w.cond(p.conditions[-1])}."]
    para = []
    if p.resolved:
        para.append(w.resolved_sentence())
    if p.negated:
        para.append(w.negation_sentence())
    if meds:
        para.append(f"{he} currently takes " + "; ".join(meds) + ".")
    else:
        para.append(f"{he} takes no regular medications.")
    for m in p.meds:
        if m.status == "stopped":
            para.append(w.stopped_sentence(m))
    if p.allergies:
        para.append(f"{he} reports allergies to {w.allergy_text()}.")
    else:
        para.append(f"{he} has no known drug allergies.")
    if p.family_hx:
        para.append(f"Family history is notable for: {w.family_sentence().lower()}")
    s.append(" ".join(para))
    exam = w.vitals_prose()
    if p.labs:
        exam += f" Labs drawn today show {w.labs_line()}."
    s.append(exam)
    plan = " ".join(w.plan_items())
    s.append(f"Assessment and plan: {', '.join(w.assessment())}. {plan}")
    return "\n\n".join(s)


def render_terse(p: Profile, rng: random.Random) -> str:
    w = Writer(p, rng)
    sx = "F" if p.gender == "female" else "M"
    lines = [
        f"{p.family.upper()}, {p.given}  DOB {w.dob()}  {sx}",
        f"{p.age}yo {sx} f/u {w.complaint()}.",
        "PMH: " + ", ".join(w.cond(c) for c in p.conditions) + "."
        + (f" {w.resolved_sentence()}" if p.resolved else "")
        + (f" {w.negation_sentence()}" if p.negated else ""),
    ]
    if p.family_hx:
        lines.append(f"FHx: {w.family_sentence(terse=True)}")
    meds = w.listed_meds(terse=True)
    lines.append("Meds: " + ("; ".join(meds) if meds else "none"))
    for m in p.meds:
        if m.status == "stopped":
            lines.append(w.stopped_sentence(m))
    lines.append(f"All: {w.allergy_text()}")
    lines.append(f"VS: {w.vitals_line(terse=True)}")
    if p.labs:
        lines.append(f"Labs: {w.labs_line()}")
    lines.append("A/P: " + "; ".join(w.assessment()) + ". " + " ".join(w.plan_items()))
    return "\n".join(lines)


def render_discharge(p: Profile, rng: random.Random) -> str:
    w = Writer(p, rng)
    lines = [
        "DISCHARGE SUMMARY",
        f"Name: {p.family}, {p.given}",
        f"Date of birth: {w.dob()}",
        f"Gender: {p.gender}",
        f"Discharge date: {w.visit()}",
        "",
        "Discharge diagnoses:",
    ]
    lines += [f"  {i}. {a}" for i, a in enumerate(w.assessment(), 1)]
    if p.resolved:
        lines += ["", "Past history: " + w.resolved_sentence()]
    hpi = f"Hospital course: {p.age}-year-old {w.sex_word()} admitted for {w.complaint(admitted=True)}, treated and now stable."
    if p.negated:
        hpi += " " + w.negation_sentence()
    lines += ["", hpi]
    if p.family_hx:
        lines.append(f"Family history: {w.family_sentence()}")
    lines += ["", f"Vital signs at discharge: {w.vitals_line()}"]
    if p.labs:
        lines.append(f"Discharge labs: {w.labs_line()}")
    lines += ["", "Discharge medications:"]
    for m in p.meds:
        if m.status == "active" and m.trap != "dose_change":
            lines.append(f"  - {w.med_line(m)}" + ("  (NEW)" if m.trap == "new_med" else ""))
        elif m.trap == "dose_change":
            verb = "increased" if m.dose > m.old_dose else "decreased"
            lines.append(f"  - {w.med_line(m)}  (CHANGED: {verb} from {_fmt_num(m.old_dose)} {m.unit})")
    stopped = [m for m in p.meds if m.status == "stopped"]
    if stopped:
        lines.append("Medications stopped:")
        lines += [f"  - {w.stopped_sentence(m)}" for m in stopped]
    lines += [f"Allergies: {w.allergy_text()}", "",
              "Follow-up: primary care in 1-2 weeks."]
    return "\n".join(lines)


RENDERERS = {"soap": render_soap, "narrative": render_narrative, "terse": render_terse,
             "discharge": render_discharge}


def gold_label(p: Profile) -> dict:
    conditions = [{"name": c, "clinical_status": "active"} for c in p.conditions]
    if p.acute:
        conditions.append({"name": p.acute, "clinical_status": "active"})
    conditions += [{"name": c, "clinical_status": "resolved"} for c, _ in p.resolved]
    meds = [{"name": m.drug, "dose_value": m.dose, "dose_unit": m.unit, "route": m.route,
             "frequency": m.freq, "status": m.status} for m in p.meds]
    observations = [{"name": k, "value": v, "unit": u} for k, v, u in p.vitals]
    observations += [{"name": k, "value": v, "unit": u} for k, v, u, _ in p.labs]
    return {
        "patient": {"given_name": p.given, "family_name": p.family, "gender": p.gender,
                    "birth_date": p.dob.isoformat()},
        "conditions": conditions,
        "medications": meds,
        "allergies": [{"substance": a, "reaction": r} for a, r in p.allergies],
        "observations": observations,
    }


def trap_items(p: Profile) -> dict[str, list[str]]:
    """Trap type -> the canonical keys it applies to, so each trap can be scored on its own."""
    items = {
        "negated": list(p.negated),
        "family_history": [c for _, c in p.family_hx],
        "stopped_med": [m.drug for m in p.meds if m.status == "stopped"],
        "dose_change": [m.drug for m in p.meds if m.trap == "dose_change"],
        "new_med": [m.drug for m in p.meds if m.trap == "new_med"],
        "resolved": [c for c, _ in p.resolved],
        "prior_lab": [k for k, _, _, prior in p.labs if prior is not None],
        "brand_name": [m.drug for m in p.meds if m.brand],
        "unit_conversion": [k for k, _, u in p.vitals if u in ("lb", "degF")],
    }
    return {k: v for k, v in items.items() if v}


def generate(n: int = DEFAULT_N, seed: int = DEFAULT_SEED) -> list[dict]:
    styles = list(RENDERERS)
    notes = []
    for i in range(n):
        rng = random.Random(f"{seed}-{i}")
        style = styles[i % len(styles)]
        p = make_profile(rng, style)
        text = RENDERERS[style](p, rng)
        notes.append({"id": f"note-{i + 1:03d}", "style": style, "visit_date": p.visit.isoformat(),
                      "traps": trap_items(p), "text": text, "gold": gold_label(p)})
    return notes


def write(notes: list[dict], path: Path = DATA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for n in notes:
            f.write(json.dumps(n, ensure_ascii=False) + "\n")


def load(path: Path | str = DATA_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
