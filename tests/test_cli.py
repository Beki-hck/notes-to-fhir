import json

from notes_to_fhir import handwritten
from notes_to_fhir import score as S
from notes_to_fhir.baseline import extract
from notes_to_fhir.cli import main
from notes_to_fhir.runner import load_notes


def test_run_and_report(tmp_path, capsys):
    main(["run", "-m", "baseline", "--limit", "4", "-o", str(tmp_path)])
    assert (tmp_path / "baseline" / "predictions.jsonl").exists()
    for f in ("leaderboard.md", "results.json", "details.html"):
        assert (tmp_path / f).exists()
    main(["report", "-o", str(tmp_path)])
    results = json.loads((tmp_path / "results.json").read_text())
    assert results["baseline"]["sets"]["all"]["notes"] == 70


def test_run_is_resumable(tmp_path):
    main(["run", "-m", "baseline", "--limit", "3", "-o", str(tmp_path)])
    main(["run", "-m", "baseline", "--limit", "3", "-o", str(tmp_path)])
    lines = (tmp_path / "baseline" / "predictions.jsonl").read_text().splitlines()
    assert len(lines) == 3


def test_convert(tmp_path, capsys):
    note = tmp_path / "note.txt"
    note.write_text(handwritten.NOTES[2]["text"])
    out = tmp_path / "bundle.json"
    main(["convert", str(note), "-o", str(out)])
    bundle = json.loads(out.read_text())
    assert bundle["resourceType"] == "Bundle"
    assert "passed" in capsys.readouterr().err


def test_baseline_reference_scores():
    """The rule baseline is near-perfect on template notes and clearly worse on hand-written ones.

    This is the reason the hand-written set exists: template notes alone can't separate a
    model that understands notes from one that memorized the template.
    """
    def f1(group):
        return S.total([S.score_note(n["gold"], extract(n["text"]).model_dump()) for n in group]).f1
    assert f1(load_notes("template")) > 0.99
    assert f1(load_notes("handwritten")) < 0.95
