import re

import pytest

from notes_to_fhir import generate, handwritten
from notes_to_fhir import score as S
from notes_to_fhir import terminology as T

TEMPLATE = generate.load()
ALL = TEMPLATE + handwritten.NOTES


def test_data_file_matches_generator():
    assert TEMPLATE == generate.generate(), "run: notes-to-fhir generate"


def test_ids_unique():
    ids = [n["id"] for n in ALL]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("note", ALL, ids=lambda n: n["id"])
def test_gold_maps_to_the_code_tables(note):
    ents = S.canon_entities(note["gold"])
    for section, items in ents.items():
        for key in items:
            assert not key.startswith("?"), f"{section}: {key} is not in terminology.py"


@pytest.mark.parametrize("note", ALL, ids=lambda n: n["id"])
def test_traps_are_consistent_with_gold(note):
    ents = S.canon_entities(note["gold"])
    for trap, keys in note["traps"].items():
        for k in keys:
            if trap in ("negated", "family_history"):
                assert T.norm_condition(k) == k
                assert k not in ents["conditions"], f"{k} is both a trap and a gold condition"
            elif trap == "resolved":
                assert ents["conditions"][k]["clinical_status"] == "resolved"
            elif trap == "stopped_med":
                assert ents["medications"][k]["status"] == "stopped"
            elif trap in ("dose_change", "new_med", "brand_name"):
                assert k in ents["medications"]
            else:
                assert k in ents["observations"]


@pytest.mark.parametrize("note", ALL, ids=lambda n: n["id"])
def test_gold_scores_perfectly_against_itself(note):
    t = S.total([S.score_note(note["gold"], note["gold"])])
    assert t.f1 == 1.0
    assert all(all(v) for v in S.trap_outcomes(note, note["gold"]).values())


@pytest.mark.parametrize("note", TEMPLATE, ids=lambda n: n["id"])
def test_template_text_mentions_every_gold_drug(note):
    text = note["text"].lower()
    for m in note["gold"]["medications"]:
        names = [s for s in T.MEDICATIONS[m["name"]].synonyms]
        assert any(re.search(rf"\b{re.escape(n)}\b", text) for n in names), m["name"]


def test_handwritten_birth_dates_appear_in_text():
    for n in handwritten.NOTES:
        year = n["gold"]["patient"]["birth_date"][:4]
        assert year in n["text"] or n["id"] == "hw-15", n["id"]


def test_template_set_covers_every_style_and_trap():
    assert {n["style"] for n in TEMPLATE} == set(generate.RENDERERS)
    traps = {t for n in TEMPLATE for t in n["traps"]}
    assert traps == {"negated", "family_history", "resolved", "stopped_med", "dose_change", "new_med",
                     "brand_name", "prior_value", "unit_conversion"}
