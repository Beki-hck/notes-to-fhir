import copy

from notes_to_fhir import handwritten
from notes_to_fhir import score as S

GOLD = handwritten.NOTES[0]["gold"]  # hw-01


def f1(pred, gold=GOLD):
    return S.total([S.score_note(gold, pred)]).f1


def test_perfect_and_empty():
    assert f1(GOLD) == 1.0
    assert f1(None) == 0.0
    assert f1({}) == 0.0


def test_missing_drug_lowers_recall_only():
    pred = copy.deepcopy(GOLD)
    pred["medications"].pop()
    t = S.total([S.score_note(GOLD, pred)])
    assert t.precision == 1.0 and t.recall < 1.0


def test_extra_condition_lowers_precision_only():
    pred = copy.deepcopy(GOLD)
    pred["conditions"].append({"name": "breast cancer", "clinical_status": "active"})
    t = S.total([S.score_note(GOLD, pred)])
    assert t.recall == 1.0 and t.precision < 1.0


def test_unmapped_names_count_as_wrong():
    pred = copy.deepcopy(GOLD)
    pred["conditions"][0]["name"] = "sugar problem"
    c = S.score_note(GOLD, pred)["conditions"]
    assert (c.tp, c.fp, c.fn) == (1, 1, 1)


def test_wrong_dose_is_one_wrong_field():
    pred = copy.deepcopy(GOLD)
    pred["medications"][1]["dose_value"] = 20  # lisinopril: the old dose, not the new one
    c = S.score_note(GOLD, pred)["medications"]
    assert c.gold - c.correct == 1 and c.tp == 3


def test_equivalent_spellings_score_as_correct():
    pred = copy.deepcopy(GOLD)
    pred["patient"]["birth_date"] = "07/02/1958"
    pred["conditions"][0]["name"] = "T2DM"
    pred["medications"][0].update(name="Glucophage", dose_value="1000 mg", dose_unit="milligrams",
                                  frequency="b.i.d.")
    pred["medications"][2].update(name="Lantus", dose_unit="IU", frequency="qHS")
    pred["observations"] = [o for o in pred["observations"] if "blood pressure" not in o["name"]]
    pred["observations"].append({"name": "Blood pressure", "value": "152/88", "unit": "mmHg"})
    for o in pred["observations"]:
        if o["name"] == "body weight":
            o.update(value=79.8, unit="kg")  # 176 lb, converted by the model
        if o["name"] == "body temperature":
            o.update(value=36.7, unit="C")   # 98.1 °F
    assert f1(pred) == 1.0


def test_mass_doses_compare_across_units():
    gold = {"medications": [{"name": "acetaminophen", "dose_value": 1, "dose_unit": "g"},
                            {"name": "levothyroxine", "dose_value": 125, "dose_unit": "mcg"}]}
    pred = {"medications": [{"name": "acetaminophen", "dose_value": 1000, "dose_unit": "mg"},
                            {"name": "levothyroxine", "dose_value": 0.125, "dose_unit": "mg"}]}
    assert f1(pred, gold) == 1.0
    pred["medications"][1]["dose_value"] = 0.112
    assert f1(pred, gold) < 1.0


def test_unstated_gold_attributes_are_not_scored():
    gold = {"medications": [{"name": "buspirone", "status": "stopped"}]}
    pred = {"medications": [{"name": "buspirone", "dose_value": 10, "dose_unit": "mg", "route": "oral",
                             "status": "stopped"}]}
    assert f1(pred, gold) == 1.0


def test_trap_outcomes():
    note = handwritten.NOTES[0]
    pred = copy.deepcopy(note["gold"])
    pred["conditions"].append({"name": "breast cancer"})          # family history leaked
    pred["medications"][1]["dose_value"] = 20                      # kept the old dose
    out = S.trap_outcomes(note, pred)
    assert out["family_history"] == [False]
    assert out["dose_change"] == [False]
    assert out["new_med"] == [True]


def test_bootstrap_interval_contains_point_estimate():
    notes = handwritten.NOTES
    per = [S.score_note(n["gold"], n["gold"] if i % 3 else None) for i, n in enumerate(notes)]
    lo, hi = S.bootstrap_f1(per, n=500)
    assert lo <= S.total(per).f1 <= hi
