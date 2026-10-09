"""Turn a note into an Extraction with a model.

Models are named like `ollama:qwen2.5:3b`, `anthropic:claude-haiku-4-5` or
`baseline` (the rule-based extractor, no model needed). Ollama is asked for
structured output with the Extraction JSON schema; replies are still parsed
defensively because small models wrap JSON in prose or code fences.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from pydantic import ValidationError

from .schema import Allergy, Condition, Extraction, Medication, Observation, Patient, json_schema

PROMPT_VERSION = "v1"

SYSTEM = """You extract structured data from clinical notes. Reply with JSON only.

Rules:
- patient: given_name, family_name, gender ("male"/"female"), birth_date as YYYY-MM-DD.
- conditions: the patient's own diagnoses only. Skip anything denied or negated ("denies asthma",
  "no history of CAD") and anything in the family history. Use clinical_status "resolved" for
  past problems described as resolved, otherwise "active".
- medications: one entry per drug. name is the drug name without dose. If the plan changes a dose,
  use the new dose. Include drugs started today. Include discontinued drugs with status "stopped".
  dose_value is a number, dose_unit is mg, mcg, units or puffs. route is oral, inhaled or
  subcutaneous. frequency is one of: once daily, twice daily, three times daily, four times daily,
  at bedtime, as needed, weekly.
- allergies: substance and reaction (null if not stated). Empty list for "NKDA".
- observations: today's vital signs and lab results. value is a number and unit is as written.
  Write blood pressure as two entries, "systolic blood pressure" and "diastolic blood pressure".
  When a note gives a previous lab value too, report only today's.
"""

USER = "Clinical note:\n\n{note}\n\nReturn the JSON."


class ModelError(RuntimeError):
    pass


def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise ModelError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ModelError(str(e)) from e


@dataclass
class OllamaModel:
    model: str
    host: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    use_schema: bool = True
    use_format: bool = True  # False: no `format` at all (Gemma 3 replies "{}" in JSON mode)
    max_tokens: int = 1536
    timeout: float = 300

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def generate(self, note: str) -> str:
        host = self.host if self.host.startswith("http") else f"http://{self.host}"
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": USER.format(note=note)}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": self.max_tokens, "num_ctx": 8192},
        }
        if self.use_format:
            payload["format"] = json_schema() if self.use_schema else "json"
        data = _post_json(f"{host.rstrip('/')}/api/chat", payload, {}, self.timeout)
        return data["message"]["content"]


@dataclass
class AnthropicModel:
    model: str
    max_tokens: int = 2048
    timeout: float = 120

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"

    def generate(self, note: str) -> str:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ModelError("ANTHROPIC_API_KEY is not set")
        schema = json.dumps(json_schema())
        data = _post_json("https://api.anthropic.com/v1/messages", {
            "model": self.model, "max_tokens": self.max_tokens, "temperature": 0,
            "system": SYSTEM + "\nJSON schema:\n" + schema,
            "messages": [{"role": "user", "content": USER.format(note=note)}],
        }, {"x-api-key": key, "anthropic-version": "2023-06-01"}, self.timeout)
        return "".join(b.get("text", "") for b in data["content"])


@dataclass
class BaselineModel:
    """The rule-based extractor wrapped as a model, so it runs through the same pipeline."""

    @property
    def name(self) -> str:
        return "baseline"

    def generate(self, note: str) -> str:
        from .baseline import extract
        return extract(note).model_dump_json()


def get_model(spec: str, use_schema: bool = True, use_format: bool = True):
    if spec == "baseline":
        return BaselineModel()
    provider, _, model = spec.partition(":")
    if provider == "ollama" and model:
        return OllamaModel(model, use_schema=use_schema, use_format=use_format)
    if provider == "anthropic" and model:
        return AnthropicModel(model)
    raise ValueError(f"Unknown model {spec!r}. Use baseline, ollama:<model> or anthropic:<model>.")


def find_json(text: str) -> str | None:
    """The JSON object starting at the first '{', skipping code fences and prose around it.

    Returns None if that object never closes (a truncated reply; see repair_truncated).
    """
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


@dataclass
class Parsed:
    extraction: Extraction | None
    status: str  # ok | partial | truncated | no_json | invalid_json | schema_error
    error: str | None = None


def repair_truncated(text: str) -> str | None:
    """Close a JSON object that was cut off mid-reply (the model hit its token limit).

    Cuts back to the last comma between complete items and closes the open
    brackets, so the finished items survive and the half-written one is dropped.
    """
    start = text.find("{")
    if start == -1:
        return None
    stack, in_str, esc, cut = [], False, False, None
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
        elif ch == "," and stack:
            cut = (i, list(stack))
    if cut is None:
        return None
    i, open_ = cut
    closing = "".join("}" if b == "{" else "]" for b in reversed(open_))
    return text[start:i] + closing


def parse_reply(text: str) -> Parsed:
    raw = find_json(text)
    truncated = False
    if raw is None:
        raw = repair_truncated(re.sub(r"```(?:json)?", "", text))
        truncated = raw is not None
    if raw is None:
        return Parsed(None, "no_json", "no JSON object in reply")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return Parsed(None, "invalid_json", str(e))
    data = _tidy(data)
    try:
        ex = Extraction.model_validate(data)
        return Parsed(ex, "truncated", "reply was cut off; kept the complete items") if truncated else Parsed(ex, "ok")
    except ValidationError as e:
        error = str(e).splitlines()[0]
    salvaged = _salvage(data)
    if salvaged is None:
        return Parsed(None, "schema_error", error)
    return Parsed(salvaged, "partial", error)


def _salvage(data) -> Extraction | None:
    """Keep the valid parts of a reply that fails validation: drop bad list items, not the note."""
    if not isinstance(data, dict):
        return None
    out = {}
    try:
        out["patient"] = Patient.model_validate(data.get("patient") or {})
    except ValidationError:
        out["patient"] = Patient()
    for key, cls in (("conditions", Condition), ("medications", Medication),
                     ("allergies", Allergy), ("observations", Observation)):
        items = data.get(key) if isinstance(data.get(key), list) else []
        kept = []
        for item in items:
            try:
                kept.append(cls.model_validate(item))
            except ValidationError:
                pass
        out[key] = kept
    return Extraction(**out)


def _tidy(data):
    """Small, mechanical repairs: null lists, lower-case enums, a bare 'stopped' or 'discontinued'."""
    if not isinstance(data, dict):
        return data
    for key in ("conditions", "medications", "allergies", "observations"):
        if data.get(key) is None:
            data[key] = []
    if data.get("patient") is None:
        data["patient"] = {}
    p = data["patient"]
    if isinstance(p, dict) and isinstance(p.get("gender"), str):
        g = p["gender"].strip().lower()
        p["gender"] = {"m": "male", "f": "female", "man": "male", "woman": "female"}.get(g, g)
        if p["gender"] not in ("male", "female", "other", "unknown"):
            p["gender"] = "unknown"
    for c in data["conditions"] if isinstance(data["conditions"], list) else []:
        if isinstance(c, dict):
            s = str(c.get("clinical_status") or "active").lower()
            c["clinical_status"] = "resolved" if s in ("resolved", "inactive", "past", "remission") else "active"
    for m in data["medications"] if isinstance(data["medications"], list) else []:
        if isinstance(m, dict):
            s = str(m.get("status") or "active").lower()
            m["status"] = "stopped" if s in ("stopped", "discontinued", "inactive", "completed") else "active"
    return data


def run_one(model, note_text: str) -> dict:
    """Generate and parse one note. Returns a record ready to be cached as JSONL."""
    t0 = time.time()
    try:
        reply = model.generate(note_text)
    except ModelError as e:
        return {"reply": None, "status": "model_error", "error": str(e), "seconds": round(time.time() - t0, 2),
                "extraction": None}
    parsed = parse_reply(reply)
    return {"reply": reply, "status": parsed.status, "error": parsed.error,
            "seconds": round(time.time() - t0, 2),
            "extraction": parsed.extraction.model_dump() if parsed.extraction else None}
