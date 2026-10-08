"""Look up every code in terminology.py on public terminology services and print what they say.

    python scripts/verify_codes.py > code-check.txt

RxNorm:      NLM RxNav             (rxnav.nlm.nih.gov)
ICD-10-CM:   NLM Clinical Tables   (clinicaltables.nlm.nih.gov)
LOINC:       NLM Clinical Tables
SNOMED CT:   HL7 terminology server (tx.fhir.org)

No API keys needed. Each line shows our display name next to the official one, so a
wrong code stands out. "MISSING" means the service didn't recognise the code.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from notes_to_fhir import terminology as T  # noqa: E402


def get(url: str, accept: str = "application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "notes-to-fhir"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def rxnorm(code):
    props = get(f"https://rxnav.nlm.nih.gov/REST/rxcui/{code}/properties.json").get("properties")
    return props["name"] if props else None


def icd10(code):
    data = get("https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?sf=code&df=code,name&terms="
               + urllib.parse.quote(code))
    return next((name for c, name in data[3] if c == code), None)


def loinc(code):
    data = get("https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search?df=LOINC_NUM,LONG_COMMON_NAME&terms="
               + urllib.parse.quote(code))
    return next((name for c, name in data[3] if c == code), None)


def snomed(code):
    url = ("https://tx.fhir.org/r4/CodeSystem/$lookup?system=" + urllib.parse.quote(T.SNOMED, safe="")
           + "&code=" + code)
    data = get(url, "application/fhir+json")
    return next((p.get("valueString") for p in data.get("parameter", []) if p.get("name") == "display"), None)


LOOKUPS = {T.RXNORM: ("RxNorm", rxnorm), T.ICD10CM: ("ICD-10-CM", icd10), T.LOINC: ("LOINC", loinc),
           T.SNOMED: ("SNOMED", snomed)}


def main():
    problems = 0
    routes = [(f"route:{k}", {T.SNOMED: code}, display) for k, (_, code, display) in T.ROUTES.items()]
    concepts = [(c.key, c.codes, c.display) for table in (T.CONDITIONS, T.MEDICATIONS, T.OBSERVATIONS)
                for c in table.values()] + routes
    for key, codes, display in concepts:
        for system, code in codes.items():
            name, fn = LOOKUPS[system]
            try:
                official = fn(code)
            except Exception as e:  # network or service error: report it, keep going
                official, problems = f"ERROR {e}", problems + 1
            if official is None:
                problems += 1
            print(f"{name:9} {code:10} ours: {display:45} official: {official or 'MISSING'}")
    print(f"\n{problems} codes missing or failed. Read the list for names that don't match.")


if __name__ == "__main__":
    main()
