"""The structured record a model must produce from a note.

The same models describe the gold labels. Field types are deliberately loose
(a dose can arrive as "20" or 20) because the scorer, not the parser, decides
whether a value is right; a reply only fails validation when its shape is wrong.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

Number = Union[float, int, str]


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Patient(_Base):
    given_name: Optional[str] = Field(None, description="First name")
    family_name: Optional[str] = Field(None, description="Last name")
    gender: Optional[Literal["male", "female", "other", "unknown"]] = None
    birth_date: Optional[str] = Field(None, description="Date of birth as YYYY-MM-DD")


class Condition(_Base):
    name: str = Field(description="The patient's own diagnosis, e.g. 'hypertension'")
    clinical_status: Literal["active", "resolved"] = "active"


class Medication(_Base):
    name: str = Field(description="Drug name without the dose, e.g. 'lisinopril'")
    dose_value: Optional[Number] = Field(None, description="Amount per dose, e.g. 20")
    dose_unit: Optional[str] = Field(None, description="mg, mcg, units or puffs")
    route: Optional[str] = Field(None, description="oral, inhaled or subcutaneous")
    frequency: Optional[str] = Field(
        None, description="once daily, twice daily, three times daily, at bedtime, as needed or weekly"
    )
    status: Literal["active", "stopped"] = "active"


class Allergy(_Base):
    substance: str
    reaction: Optional[str] = None


class Observation(_Base):
    name: str = Field(description="e.g. 'systolic blood pressure', 'heart rate', 'hemoglobin a1c'")
    value: Number
    unit: Optional[str] = Field(None, description="The unit as written in the note")


class Extraction(_Base):
    patient: Patient = Field(default_factory=Patient)
    conditions: list[Condition] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    allergies: list[Allergy] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)


def json_schema() -> dict:
    """The JSON schema sent to Ollama's structured-output `format` field."""
    return Extraction.model_json_schema()
