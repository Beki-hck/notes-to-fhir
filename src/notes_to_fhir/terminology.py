"""Code tables and normalizers.

Every name a model writes ("HTN", "Zestril", "b.i.d.", "O2 sat") is mapped to one
canonical key before scoring and before building FHIR resources. The same tables
are used by the note generator, so the gold labels and the scorer agree on what
counts as the same thing.

The codes are a small hand-built subset of SNOMED CT, ICD-10-CM, RxNorm
(ingredient level) and LOINC. `scripts/verify_codes.py` checks them against the
public NLM and HL7 terminology servers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SNOMED = "http://snomed.info/sct"
ICD10CM = "http://hl7.org/fhir/sid/icd-10-cm"
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"


@dataclass(frozen=True)
class Concept:
    key: str
    display: str
    codes: dict[str, str]
    synonyms: tuple[str, ...] = field(default_factory=tuple)


def _c(key, display, codes, *synonyms):
    return Concept(key, display, codes, (key, *synonyms))


CONDITIONS = {
    c.key: c
    for c in [
        _c("hypertension", "Hypertensive disorder", {SNOMED: "38341003", ICD10CM: "I10"},
           "htn", "high blood pressure", "essential hypertension", "hypertensive disorder"),
        _c("type 2 diabetes", "Diabetes mellitus type 2", {SNOMED: "44054006", ICD10CM: "E11.9"},
           "t2dm", "dm2", "dm ii", "type 2 diabetes mellitus", "diabetes mellitus type 2",
           "type ii diabetes", "type ii diabetes mellitus", "diabetes type 2", "niddm"),
        _c("hyperlipidemia", "Hyperlipidemia", {SNOMED: "55822004", ICD10CM: "E78.5"},
           "hld", "high cholesterol"),
        _c("asthma", "Asthma", {SNOMED: "195967001", ICD10CM: "J45.909"}, "bronchial asthma"),
        _c("copd", "Chronic obstructive lung disease", {SNOMED: "13645005", ICD10CM: "J44.9"},
           "chronic obstructive pulmonary disease", "chronic obstructive lung disease"),
        _c("gerd", "Gastroesophageal reflux disease", {SNOMED: "235595009", ICD10CM: "K21.9"},
           "gastroesophageal reflux disease", "gastroesophageal reflux", "acid reflux", "reflux"),
        _c("hypothyroidism", "Hypothyroidism", {SNOMED: "40930008", ICD10CM: "E03.9"},
           "underactive thyroid"),
        _c("osteoarthritis", "Osteoarthritis", {SNOMED: "396275006", ICD10CM: "M19.90"},
           "oa", "degenerative joint disease", "djd"),
        _c("major depressive disorder", "Major depressive disorder",
           {SNOMED: "370143000", ICD10CM: "F32.9"}, "mdd", "depression", "major depression"),
        _c("generalized anxiety disorder", "Generalized anxiety disorder",
           {SNOMED: "21897009", ICD10CM: "F41.1"}, "gad"),
        _c("atrial fibrillation", "Atrial fibrillation", {SNOMED: "49436004", ICD10CM: "I48.91"},
           "afib", "a-fib", "a fib", "af"),
        _c("chronic kidney disease", "Chronic kidney disease",
           {SNOMED: "709044004", ICD10CM: "N18.9"}, "ckd"),
        _c("migraine", "Migraine", {SNOMED: "37796009", ICD10CM: "G43.909"},
           "migraines", "migraine headache", "migraine headaches"),
        _c("coronary artery disease", "Coronary arteriosclerosis",
           {SNOMED: "53741008", ICD10CM: "I25.10"}, "cad", "coronary heart disease"),
        _c("heart failure", "Heart failure", {SNOMED: "84114007", ICD10CM: "I50.9"},
           "chf", "congestive heart failure", "hf"),
        _c("obesity", "Obesity", {SNOMED: "414916001", ICD10CM: "E66.9"}),
        _c("pneumonia", "Pneumonia", {SNOMED: "233604007", ICD10CM: "J18.9"},
           "community acquired pneumonia", "cap"),
        _c("urinary tract infection", "Urinary tract infectious disease",
           {SNOMED: "68566005", ICD10CM: "N39.0"}, "uti"),
        _c("iron deficiency anemia", "Iron deficiency anemia",
           {SNOMED: "87522002", ICD10CM: "D50.9"}, "ida", "iron-deficiency anemia"),
        # These appear in notes only as negated or family history, so a correct
        # extraction never contains them. They are coded so a wrong one still maps.
        _c("breast cancer", "Malignant neoplasm of breast", {SNOMED: "254837009", ICD10CM: "C50.919"}),
        _c("colon cancer", "Malignant tumor of colon", {SNOMED: "363406005", ICD10CM: "C18.9"},
           "colorectal cancer"),
        _c("stroke", "Cerebrovascular accident", {SNOMED: "230690007", ICD10CM: "I63.9"},
           "cva", "cerebrovascular accident"),
        _c("myocardial infarction", "Myocardial infarction", {SNOMED: "22298006", ICD10CM: "I21.9"},
           "mi", "heart attack"),
        _c("alzheimer disease", "Alzheimer's disease", {SNOMED: "26929004", ICD10CM: "G30.9"},
           "alzheimer's disease", "alzheimers disease", "alzheimer's", "dementia"),
    ]
}

MEDICATIONS = {
    c.key: c
    for c in [
        _c("metformin", "metformin", {RXNORM: "6809"}, "glucophage", "metformin hcl"),
        _c("empagliflozin", "empagliflozin", {RXNORM: "1545653"}, "jardiance"),
        _c("insulin glargine", "insulin glargine", {RXNORM: "274783"}, "lantus", "basaglar", "glargine"),
        _c("lisinopril", "lisinopril", {RXNORM: "29046"}, "zestril", "prinivil"),
        _c("amlodipine", "amlodipine", {RXNORM: "17767"}, "norvasc"),
        _c("losartan", "losartan", {RXNORM: "52175"}, "cozaar"),
        _c("hydrochlorothiazide", "hydrochlorothiazide", {RXNORM: "5487"}, "hctz"),
        _c("atorvastatin", "atorvastatin", {RXNORM: "83367"}, "lipitor"),
        _c("simvastatin", "simvastatin", {RXNORM: "36567"}, "zocor"),
        _c("rosuvastatin", "rosuvastatin", {RXNORM: "301542"}, "crestor"),
        _c("levothyroxine", "levothyroxine", {RXNORM: "10582"}, "synthroid", "levoxyl"),
        _c("albuterol", "albuterol", {RXNORM: "435"}, "proair", "ventolin", "salbutamol"),
        _c("fluticasone", "fluticasone", {RXNORM: "41126"}, "flovent"),
        _c("tiotropium", "tiotropium", {RXNORM: "69120"}, "spiriva"),
        _c("omeprazole", "omeprazole", {RXNORM: "7646"}, "prilosec"),
        _c("pantoprazole", "pantoprazole", {RXNORM: "40790"}, "protonix"),
        _c("sertraline", "sertraline", {RXNORM: "36437"}, "zoloft"),
        _c("escitalopram", "escitalopram", {RXNORM: "321988"}, "lexapro"),
        _c("buspirone", "buspirone", {RXNORM: "1827"}, "buspar"),
        _c("metoprolol", "metoprolol", {RXNORM: "6918"},
           "metoprolol tartrate", "metoprolol succinate", "lopressor", "toprol", "toprol xl"),
        _c("carvedilol", "carvedilol", {RXNORM: "20352"}, "coreg"),
        _c("apixaban", "apixaban", {RXNORM: "1364430"}, "eliquis"),
        _c("warfarin", "warfarin", {RXNORM: "11289"}, "coumadin"),
        _c("furosemide", "furosemide", {RXNORM: "4603"}, "lasix"),
        _c("aspirin", "aspirin", {RXNORM: "1191"}, "asa", "baby aspirin"),
        _c("acetaminophen", "acetaminophen", {RXNORM: "161"}, "tylenol", "paracetamol"),
        _c("ibuprofen", "ibuprofen", {RXNORM: "5640"}, "advil", "motrin"),
        _c("gabapentin", "gabapentin", {RXNORM: "25480"}, "neurontin"),
        _c("sumatriptan", "sumatriptan", {RXNORM: "37418"}, "imitrex"),
        _c("ferrous sulfate", "ferrous sulfate", {RXNORM: "24947"}, "iron sulfate", "feso4"),
        _c("amoxicillin", "amoxicillin", {RXNORM: "723"}, "amoxil"),
        _c("nitrofurantoin", "nitrofurantoin", {RXNORM: "7454"}, "macrobid"),
    ]
}

OBSERVATIONS = {
    c.key: c
    for c in [
        _c("systolic blood pressure", "Systolic blood pressure", {LOINC: "8480-6"},
           "systolic", "sbp", "systolic bp", "bp systolic", "blood pressure systolic"),
        _c("diastolic blood pressure", "Diastolic blood pressure", {LOINC: "8462-4"},
           "diastolic", "dbp", "diastolic bp", "bp diastolic", "blood pressure diastolic"),
        _c("heart rate", "Heart rate", {LOINC: "8867-4"}, "hr", "pulse", "pulse rate", "p"),
        _c("respiratory rate", "Respiratory rate", {LOINC: "9279-1"}, "rr", "resp rate", "respirations"),
        _c("body temperature", "Body temperature", {LOINC: "8310-5"}, "temperature", "temp", "t"),
        _c("body weight", "Body weight", {LOINC: "29463-7"}, "weight", "wt"),
        _c("oxygen saturation", "Oxygen saturation in Arterial blood by Pulse oximetry",
           {LOINC: "59408-5"}, "spo2", "o2 sat", "o2 saturation", "pulse ox", "sao2", "oxygen sat"),
        _c("hemoglobin a1c", "Hemoglobin A1c/Hemoglobin.total in Blood", {LOINC: "4548-4"},
           "hba1c", "a1c", "hgb a1c", "glycated hemoglobin"),
        _c("glucose", "Glucose [Mass/volume] in Serum or Plasma", {LOINC: "2345-7"},
           "blood glucose", "fasting glucose", "serum glucose", "fasting blood glucose"),
        _c("ldl cholesterol", "Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation",
           {LOINC: "13457-7"}, "ldl", "ldl-c", "ldl c"),
        _c("creatinine", "Creatinine [Mass/volume] in Serum or Plasma", {LOINC: "2160-0"},
           "cr", "serum creatinine", "creat"),
        _c("tsh", "Thyrotropin [Units/volume] in Serum or Plasma", {LOINC: "3016-3"},
           "thyroid stimulating hormone", "thyrotropin"),
    ]
}

VITAL_KEYS = {"systolic blood pressure", "diastolic blood pressure", "heart rate",
              "respiratory rate", "body temperature", "body weight", "oxygen saturation"}

ALLERGENS = {
    c.key: c
    for c in [
        _c("penicillin", "Penicillin", {}, "penicillins", "pcn", "pcn antibiotics"),
        _c("sulfonamide", "Sulfonamide antibiotics", {},
           "sulfa", "sulfa drugs", "sulfonamides", "sulfa antibiotics", "bactrim"),
        _c("peanut", "Peanut", {}, "peanuts", "peanut butter"),
        _c("shellfish", "Shellfish", {}, "shrimp", "shellfish (shrimp)"),
        _c("latex", "Latex", {}),
        _c("codeine", "Codeine", {}),
        _c("egg", "Egg", {}, "eggs"),
        _c("iodinated contrast", "Iodinated contrast media", {},
           "iv contrast", "contrast dye", "iodine contrast", "contrast"),
        _c("cephalosporin", "Cephalosporin", {}, "cephalosporins", "cephalexin", "keflex"),
        _c("morphine", "Morphine", {}),
    ]
}

REACTIONS = {
    "hives": ("hives", "urticaria"),
    "rash": ("rash", "skin rash"),
    "anaphylaxis": ("anaphylaxis", "anaphylactic reaction", "anaphylactic shock"),
    "swelling": ("swelling", "angioedema", "facial swelling", "lip swelling"),
    "nausea": ("nausea", "nausea and vomiting", "gi upset", "vomiting"),
    "shortness of breath": ("shortness of breath", "sob", "wheezing", "trouble breathing",
                            "difficulty breathing"),
    "itching": ("itching", "pruritus", "itchiness"),
}

# Canonical frequency -> (surface forms, FHIR Timing.repeat fields).
FREQUENCIES = {
    "once daily": (("daily", "once daily", "qd", "q.d.", "once a day", "every day", "every morning",
                    "qam", "q am", "1x/day", "od", "each morning", "once per day", "q24h"),
                   {"frequency": 1, "period": 1, "periodUnit": "d"}),
    "twice daily": (("bid", "b.i.d.", "twice daily", "twice a day", "q12h", "every 12 hours",
                     "2x/day", "two times daily", "two times a day", "twice per day"),
                    {"frequency": 2, "period": 1, "periodUnit": "d"}),
    "three times daily": (("tid", "t.i.d.", "three times daily", "three times a day", "q8h",
                           "every 8 hours", "3x/day"),
                          {"frequency": 3, "period": 1, "periodUnit": "d"}),
    "four times daily": (("qid", "q.i.d.", "four times daily", "four times a day", "4x/day"),
                         {"frequency": 4, "period": 1, "periodUnit": "d"}),
    "at bedtime": (("qhs", "q.h.s.", "at bedtime", "nightly", "every night", "hs", "qpm",
                    "every evening", "at night", "in the evening", "once daily at bedtime"),
                   {"frequency": 1, "period": 1, "periodUnit": "d", "when": ["HS"]}),
    "as needed": (("prn", "as needed", "p.r.n.", "as necessary", "when needed", "q4-6h prn",
                   "every 4-6 hours as needed", "q6h prn", "every 6 hours as needed",
                   "as needed for pain", "as needed for wheezing", "as needed for migraine"),
                  {}),
    "weekly": (("weekly", "once weekly", "once a week", "qweek", "q week", "every week"),
               {"frequency": 1, "period": 1, "periodUnit": "wk"}),
}

ROUTES = {
    "oral": (("oral", "po", "p.o.", "by mouth", "orally", "per os", "tablet"), "26643006", "Oral route"),
    "inhaled": (("inhaled", "inhalation", "inh", "via inhaler", "by inhalation", "inhaler",
                 "respiratory tract"), "447694001", "Respiratory tract route"),
    "subcutaneous": (("subcutaneous", "sc", "subq", "sq", "s.c.", "subcutaneously", "sub-q",
                      "injection"), "34206005", "Subcutaneous route"),
}

DOSE_UNITS = {
    "mg": (("mg", "milligram", "milligrams"), "mg"),
    "mcg": (("mcg", "µg", "ug", "microgram", "micrograms"), "ug"),
    "units": (("units", "unit", "u", "iu", "international units"), "[IU]"),
    "puffs": (("puffs", "puff", "inhalations", "inhalation"), "{puff}"),
    "g": (("g", "gram", "grams"), "g"),
}

# Observation units: canonical unit per concept, plus conversions into it.
OBS_UNITS = {
    "systolic blood pressure": ("mmHg", "mm[Hg]"),
    "diastolic blood pressure": ("mmHg", "mm[Hg]"),
    "heart rate": ("/min", "/min"),
    "respiratory rate": ("/min", "/min"),
    "body temperature": ("Cel", "Cel"),
    "body weight": ("kg", "kg"),
    "oxygen saturation": ("%", "%"),
    "hemoglobin a1c": ("%", "%"),
    "glucose": ("mg/dL", "mg/dL"),
    "ldl cholesterol": ("mg/dL", "mg/dL"),
    "creatinine": ("mg/dL", "mg/dL"),
    "tsh": ("mIU/L", "m[IU]/L"),
}

UNIT_ALIASES = {
    "mmhg": "mmHg", "mm hg": "mmHg", "mm[hg]": "mmHg",
    "/min": "/min", "bpm": "/min", "beats/min": "/min", "beats per minute": "/min",
    "breaths/min": "/min", "breaths per minute": "/min", "per min": "/min", "min-1": "/min",
    "c": "Cel", "°c": "Cel", "cel": "Cel", "celsius": "Cel", "deg c": "Cel", "degc": "Cel",
    "f": "degF", "°f": "degF", "fahrenheit": "degF", "deg f": "degF", "degf": "degF", "[degf]": "degF",
    "kg": "kg", "kgs": "kg", "kilograms": "kg",
    "lb": "lb", "lbs": "lb", "pounds": "lb", "[lb_av]": "lb",
    "%": "%", "percent": "%",
    "mg/dl": "mg/dL", "mmol/l": "mmol/L",
    "miu/l": "mIU/L", "uiu/ml": "mIU/L", "µiu/ml": "mIU/L", "m[iu]/l": "mIU/L", "miu/ml": "mIU/L",
}


def clean(text: str | None) -> str:
    """Lowercase, drop punctuation at the edges, collapse whitespace."""
    if text is None:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .,;:()[]")


def _index(table: dict[str, Concept]) -> dict[str, str]:
    return {clean(s): c.key for c in table.values() for s in c.synonyms}


_COND_IDX = _index(CONDITIONS)
_MED_IDX = _index(MEDICATIONS)
_OBS_IDX = _index(OBSERVATIONS)
_ALLERGEN_IDX = _index(ALLERGENS)
_REACTION_IDX = {clean(s): k for k, syns in REACTIONS.items() for s in syns}
_FREQ_IDX = {clean(s): k for k, (syns, _) in FREQUENCIES.items() for s in (k, *syns)}
_ROUTE_IDX = {clean(s): k for k, (syns, _, _) in ROUTES.items() for s in (k, *syns)}
_DOSE_UNIT_IDX = {clean(s): k for k, (syns, _) in DOSE_UNITS.items() for s in syns}


def _lookup(text: str | None, index: dict[str, str], contains: bool = True) -> str | None:
    """Exact synonym match, then the longest synonym found as whole words inside the text.

    The fallback maps "lisinopril 20 mg" to lisinopril and "essential hypertension,
    well controlled" to hypertension. Synonyms of three characters or fewer only
    match exactly, so "af" doesn't match inside "after".
    """
    t = clean(text)
    if not t:
        return None
    if t in index:
        return index[t]
    if t.endswith("s") and t[:-1] in index:
        return index[t[:-1]]
    if not contains:
        return None
    best = None
    for syn, key in index.items():
        if len(syn) <= 3:
            continue
        if re.search(rf"(?<![\w-]){re.escape(syn)}(?![\w-])", t):
            if best is None or len(syn) > len(best[0]):
                best = (syn, key)
    return best[1] if best else None


def norm_condition(text):
    return _lookup(text, _COND_IDX)


def norm_medication(text):
    return _lookup(text, _MED_IDX)


def norm_observation(text):
    return _lookup(text, _OBS_IDX)


def norm_allergen(text):
    return _lookup(text, _ALLERGEN_IDX)


def norm_reaction(text):
    return _lookup(text, _REACTION_IDX)


def norm_frequency(text):
    return _lookup(text, _FREQ_IDX)


def norm_route(text):
    return _lookup(text, _ROUTE_IDX)


def norm_dose_unit(text):
    return _lookup(text, _DOSE_UNIT_IDX, contains=False)


def norm_obs_unit(text: str | None) -> str | None:
    t = clean(text).replace(" ", "") if text is not None else ""
    if not t:
        return None
    for alias, unit in UNIT_ALIASES.items():
        if t == alias.replace(" ", ""):
            return unit
    return str(text).strip()


def to_canonical(key: str, value: float, unit: str | None) -> tuple[float, str | None]:
    """Convert an observation into the concept's canonical unit (°F→°C, lb→kg, mmol/L→mg/dL).

    A missing unit is accepted when the value only makes sense in one unit; the
    two cases that are ambiguous (temperature and weight) are resolved by range.
    """
    u = norm_obs_unit(unit)
    if key == "body temperature":
        if u == "degF" or (u is None and value > 45):
            return round((value - 32) * 5 / 9, 2), "Cel"
        return value, "Cel"
    if key == "body weight":
        if u == "lb":
            return round(value * 0.45359237, 2), "kg"
        return value, "kg"
    if key == "glucose" and u == "mmol/L":
        return round(value * 18.016, 1), "mg/dL"
    canonical = OBS_UNITS[key][0]
    return value, (canonical if u in (None, canonical) else u)
