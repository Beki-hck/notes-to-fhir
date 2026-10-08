import pytest

from notes_to_fhir import terminology as T


@pytest.mark.parametrize("text,key", [
    ("HTN", "hypertension"), ("essential hypertension, well controlled", "hypertension"),
    ("T2DM", "type 2 diabetes"), ("Type II diabetes mellitus", "type 2 diabetes"),
    ("COPD exacerbation", "copd"), ("CKD stage 3a", "chronic kidney disease"),
    ("HFrEF", "heart failure"), ("acute cystitis", "urinary tract infection"),
    ("gestational diabetes", "gestational diabetes"), ("Alzheimer's dementia", "alzheimer disease"),
])
def test_conditions(text, key):
    assert T.norm_condition(text) == key


def test_short_abbreviations_do_not_match_inside_words():
    assert T.norm_condition("after dinner") is None
    assert T.norm_condition("chest pain") is None


@pytest.mark.parametrize("text,key", [
    ("Lipitor", "atorvastatin"), ("lisinopril 20 mg", "lisinopril"), ("Metoprolol succinate ER", "metoprolol"),
    ("glibenclamide", "glyburide"), ("EpiPen", "epinephrine"), ("Lantus", "insulin glargine"),
])
def test_medications(text, key):
    assert T.norm_medication(text) == key


@pytest.mark.parametrize("text,key", [
    ("BID", "twice daily"), ("b.i.d.", "twice daily"), ("qHS", "at bedtime"), ("q4h prn SOB", "as needed"),
    ("TID PRN pain", "as needed"), ("every morning", "once daily"), ("qod", "every other day"),
])
def test_frequencies(text, key):
    assert T.norm_frequency(text) == key


def test_routes_and_units():
    assert T.norm_route("PO") == "oral"
    assert T.norm_route("subQ") == "subcutaneous"
    assert T.norm_route("IM") == "intramuscular"
    assert T.norm_dose_unit("µg") == "mcg"
    assert T.norm_dose_unit("IU") == "units"


def test_observation_conversions():
    assert T.to_canonical("body weight", 176, "lbs") == (79.83, "kg")
    assert T.to_canonical("body temperature", 98.6, "°F") == (37.0, "Cel")
    assert T.to_canonical("body temperature", 98.6, None) == (37.0, "Cel")  # unit missing, range decides
    assert T.to_canonical("body temperature", 37.2, None) == (37.2, "Cel")
    assert T.to_canonical("glucose", 9.2, "mmol/L")[0] == pytest.approx(165.7, abs=0.1)


def test_every_concept_has_codes_and_unique_synonyms():
    for table in (T.CONDITIONS, T.MEDICATIONS, T.OBSERVATIONS):
        seen = {}
        for c in table.values():
            assert c.codes, c.key
            for s in c.synonyms:
                s = T.clean(s)
                assert seen.setdefault(s, c.key) == c.key, f"{s!r} maps to {seen[s]} and {c.key}"
