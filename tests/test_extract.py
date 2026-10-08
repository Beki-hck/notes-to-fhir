import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from notes_to_fhir import handwritten
from notes_to_fhir import score as S
from notes_to_fhir.extract import OllamaModel, get_model, parse_reply, run_one


def test_parses_json_inside_prose_and_fences():
    r = parse_reply('Here you go:\n```json\n{"conditions": [{"name": "HTN"}]}\n```\nLet me know!')
    assert r.status == "ok" and r.extraction.conditions[0].name == "HTN"


def test_null_lists_and_loose_enums_are_tidied():
    r = parse_reply('{"patient": {"gender": "F"}, "conditions": null, '
                    '"medications": [{"name": "x", "status": "Discontinued"}]}')
    assert r.status == "ok"
    assert r.extraction.patient.gender == "female"
    assert r.extraction.medications[0].status == "stopped"


def test_bad_items_are_dropped_not_the_whole_note():
    r = parse_reply('{"medications": [{"dose_value": 5}, {"name": "lisinopril"}]}')
    assert r.status == "partial"
    assert [m.name for m in r.extraction.medications] == ["lisinopril"]


def test_truncated_reply_keeps_complete_items():
    r = parse_reply('{"conditions": [{"name": "htn"}, {"name": "gerd"}], "medications": [{"name": "lisin')
    assert r.status == "truncated"
    assert [c.name for c in r.extraction.conditions] == ["htn", "gerd"]


def test_no_json():
    assert parse_reply("I cannot help with that.").status == "no_json"


def test_unknown_model_spec():
    with pytest.raises(ValueError):
        get_model("gpt")


def test_baseline_runs_through_the_same_pipeline():
    rec = run_one(get_model("baseline"), handwritten.NOTES[2]["text"])
    assert rec["status"] == "ok" and rec["extraction"]["patient"]["family_name"] == "Gebremedhin"


class FakeOllama(BaseHTTPRequestHandler):
    """Answers /api/chat with the gold label of hw-01, and records the request."""
    requests = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        FakeOllama.requests.append(body)
        reply = json.dumps({"message": {"content": json.dumps(handwritten.NOTES[0]["gold"])}})
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(reply.encode())

    def log_message(self, *args):
        pass


def test_ollama_request_and_round_trip():
    server = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        model = OllamaModel("fake:1b", host=f"http://127.0.0.1:{server.server_port}")
        rec = run_one(model, handwritten.NOTES[0]["text"])
    finally:
        server.shutdown()
    req = FakeOllama.requests[-1]
    assert req["model"] == "fake:1b" and req["options"]["temperature"] == 0
    assert req["format"]["title"] == "Extraction"          # structured output with the JSON schema
    assert "Meron" in req["messages"][1]["content"]
    assert rec["status"] == "ok"
    assert S.total([S.score_note(handwritten.NOTES[0]["gold"], rec["extraction"])]).f1 == 1.0


def test_ollama_down_is_a_model_error():
    rec = run_one(OllamaModel("x", host="http://127.0.0.1:9", timeout=2), "note")
    assert rec["status"] == "model_error"
