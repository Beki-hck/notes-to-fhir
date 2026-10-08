import pytest

from notes_to_fhir import generate, handwritten
from notes_to_fhir import terminology as T
from notes_to_fhir.fhir import to_bundle, validate
from notes_to_fhir.schema import Extraction

ALL = generate.load() + handwritten.NOTES


@pytest.mark.parametrize("note", ALL, ids=lambda n: n["id"])
def test_gold_bundles_are_valid_fhir(note):
    bundle = to_bundle(Extraction.model_validate(note["gold"]), note["id"], note.get("visit_date"))
    assert validate(bundle) == []


def test_invalid_bundle_is_caught():
    bundle = to_bundle(Extraction.model_validate(handwritten.NOTES[0]["gold"]), "x")
    bundle["entry"][0]["resource"]["birthDate"] = "July 2nd"
    assert validate(bundle)


def test_resources_and_codes():
    bundle = to_bundle(Extraction.model_validate(handwritten.NOTES[0]["gold"]), "hw-01", "2026-03-01")
    res = [e["resource"] for e in bundle["entry"]]
    types = [r["resourceType"] for r in res]
    assert types.count("Patient") == 1 and types.count("MedicationStatement") == 3
    cond = next(r for r in res if r["resourceType"] == "Condition")
    assert {"system": T.SNOMED, "code": "44054006", "display": "Diabetes mellitus type 2"} in cond["code"]["coding"]
    glargine = next(r for r in res if r["resourceType"] == "MedicationStatement"
                    and r["medicationCodeableConcept"]["coding"][0]["code"] == "274783")
    assert glargine["dosage"][0]["timing"]["repeat"]["when"] == ["HS"]
    weight = next(r for r in res if r["resourceType"] == "Observation" and r["code"]["coding"][0]["code"] == "29463-7")
    assert weight["valueQuantity"]["code"] == "[lb_av]"
    pid = bundle["entry"][0]["fullUrl"]
    assert all(r.get("subject", r.get("patient", {"reference": pid}))["reference"] == pid for r in res[1:])


def test_unmapped_names_keep_their_text():
    ex = Extraction.model_validate({"conditions": [{"name": "sugar problem"}]})
    cond = to_bundle(ex)["entry"][1]["resource"]
    assert cond["code"] == {"text": "sugar problem"}
    assert validate(to_bundle(ex)) == []


def test_bundle_ids_are_deterministic():
    ex = Extraction.model_validate(handwritten.NOTES[1]["gold"])
    assert to_bundle(ex, "a") == to_bundle(ex, "a")
