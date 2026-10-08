"""Build a FHIR R4 transaction Bundle from an extraction.

Resources: Patient, Condition, MedicationStatement, AllergyIntolerance and
Observation, linked by urn:uuid references. Anything that maps to the code
tables gets a coding (SNOMED CT and ICD-10-CM for conditions, RxNorm for
drugs, LOINC for observations, UCUM for units); anything that doesn't keeps
its text, which is valid FHIR and shows exactly what the model wrote.
"""

from __future__ import annotations

import uuid

from . import terminology as T
from .schema import Extraction
from .score import _num

CLINICAL = "http://terminology.hl7.org/CodeSystem/condition-clinical"
VERIFICATION = "http://terminology.hl7.org/CodeSystem/condition-ver-status"
CATEGORY = "http://terminology.hl7.org/CodeSystem/condition-category"
ALLERGY_CLINICAL = "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical"
OBS_CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"
UCUM_OBS = {"mmHg": "mm[Hg]", "/min": "/min", "Cel": "Cel", "degF": "[degF]", "kg": "kg", "lb": "[lb_av]",
            "%": "%", "mg/dL": "mg/dL", "mmol/L": "mmol/L", "mIU/L": "m[IU]/L"}


def _uid(namespace: str, *parts) -> str:
    """Deterministic ids, so the same extraction always produces the same bundle."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"notes-to-fhir/{namespace}/" + "/".join(map(str, parts))))


def _concept(text: str, concept: T.Concept | None) -> dict:
    if concept is None:
        return {"text": text}
    return {"coding": [{"system": s, "code": c, "display": concept.display} for s, c in concept.codes.items()],
            "text": text}


def to_bundle(ex: Extraction, note_id: str = "note", effective: str | None = None) -> dict:
    pid = _uid(note_id, "patient")
    patient_ref = {"reference": f"urn:uuid:{pid}"}
    p = ex.patient
    patient = {"resourceType": "Patient"}
    if p.given_name or p.family_name:
        name = {}
        if p.family_name:
            name["family"] = p.family_name
        if p.given_name:
            name["given"] = p.given_name.split()
        patient["name"] = [name]
    if p.gender:
        patient["gender"] = p.gender
    if p.birth_date and len(p.birth_date) == 10:
        patient["birthDate"] = p.birth_date
    entries = [(pid, patient)]

    for i, c in enumerate(ex.conditions):
        key = T.norm_condition(c.name)
        entries.append((_uid(note_id, "condition", i), {
            "resourceType": "Condition",
            "clinicalStatus": {"coding": [{"system": CLINICAL, "code": c.clinical_status}]},
            "verificationStatus": {"coding": [{"system": VERIFICATION, "code": "confirmed"}]},
            "category": [{"coding": [{"system": CATEGORY, "code": "problem-list-item"}]}],
            "code": _concept(c.name, T.CONDITIONS.get(key)),
            "subject": patient_ref,
        }))

    for i, m in enumerate(ex.medications):
        key = T.norm_medication(m.name)
        dosage: dict = {}
        text = " ".join(str(x) for x in (m.dose_value, m.dose_unit, m.route, m.frequency) if x not in (None, ""))
        if text:
            dosage["text"] = text
        freq = T.norm_frequency(m.frequency)
        if freq == "as needed":
            dosage["asNeededBoolean"] = True
        elif freq:
            dosage["timing"] = {"repeat": dict(T.FREQUENCIES[freq][1])}
        route = T.norm_route(m.route)
        if route:
            _, code, display = T.ROUTES[route]
            dosage["route"] = {"coding": [{"system": T.SNOMED, "code": code, "display": display}]}
        value = _num(m.dose_value)
        unit = T.norm_dose_unit(m.dose_unit)
        if value is not None:
            q = {"value": value}
            if unit:
                q.update(unit=unit, system=T.UCUM, code=T.DOSE_UNITS[unit][1])
            elif m.dose_unit:
                q["unit"] = m.dose_unit
            dosage["doseAndRate"] = [{"doseQuantity": q}]
        res = {"resourceType": "MedicationStatement", "status": m.status,
               "medicationCodeableConcept": _concept(m.name, T.MEDICATIONS.get(key)), "subject": patient_ref}
        if dosage:
            res["dosage"] = [dosage]
        entries.append((_uid(note_id, "medication", i), res))

    for i, a in enumerate(ex.allergies):
        key = T.norm_allergen(a.substance)
        res = {"resourceType": "AllergyIntolerance",
               "clinicalStatus": {"coding": [{"system": ALLERGY_CLINICAL, "code": "active"}]},
               "code": {"text": T.ALLERGENS[key].display if key else a.substance},
               "patient": patient_ref}
        if a.reaction:
            res["reaction"] = [{"manifestation": [{"text": a.reaction}]}]
        entries.append((_uid(note_id, "allergy", i), res))

    for i, o in enumerate(ex.observations):
        key = T.norm_observation(o.name)
        value = _num(o.value)
        if value is None:
            continue
        res = {"resourceType": "Observation", "status": "final",
               "category": [{"coding": [{"system": OBS_CATEGORY,
                                         "code": "vital-signs" if key in T.VITAL_KEYS else "laboratory"}]}],
               "code": _concept(o.name, T.OBSERVATIONS.get(key)), "subject": patient_ref}
        if effective:
            res["effectiveDateTime"] = effective
        unit = T.norm_obs_unit(o.unit) if o.unit else (T.OBS_UNITS[key][0] if key else None)
        q = {"value": value}
        if unit:
            q["unit"] = unit
            if unit in UCUM_OBS:
                q.update(system=T.UCUM, code=UCUM_OBS[unit])
        res["valueQuantity"] = q
        entries.append((_uid(note_id, "observation", i), res))

    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [{"fullUrl": f"urn:uuid:{rid}", "resource": res,
                   "request": {"method": "POST", "url": res["resourceType"]}} for rid, res in entries],
    }


def validate(bundle: dict) -> list[str]:
    """Validate with the fhir.resources R4B models. Returns error messages ([] if valid)."""
    try:
        from fhir.resources.R4B.bundle import Bundle
    except ImportError as e:  # optional dependency
        raise RuntimeError("pip install fhir.resources to validate bundles") from e
    from pydantic import ValidationError
    try:
        Bundle.model_validate(bundle)
        return []
    except ValidationError as e:
        return [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
