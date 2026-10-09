"""Command line: generate, list, show, run, report, convert."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import fhir, generate, report, runner
from .extract import get_model, parse_reply


def _out(args) -> Path:
    return Path(args.out).expanduser()


def cmd_generate(args):
    notes = generate.generate(args.n, args.seed)
    generate.write(notes)
    print(f"wrote {len(notes)} notes to {generate.DATA_PATH}")


def cmd_list(args):
    notes = runner.load_notes("all")
    for s in runner.SETS:
        group = [n for n in notes if n["set"] == s]
        traps = {}
        for n in group:
            for t, keys in n["traps"].items():
                traps[t] = traps.get(t, 0) + len(keys)
        print(f"{s}: {len(group)} notes; traps: " + ", ".join(f"{k} {v}" for k, v in sorted(traps.items())))


def cmd_show(args):
    for n in runner.load_notes("all"):
        if n["id"] == args.note_id:
            print(n["text"])
            if args.gold:
                print("\n" + json.dumps(n["gold"], indent=2))
            return
    sys.exit(f"no note {args.note_id!r}")


def _report(out: Path, notes):
    dirs = [d for d in sorted(out.iterdir()) if (d / "predictions.jsonl").exists()] if out.exists() else []
    preds, results = {}, {}
    for d in dirs:
        p = runner.load_predictions(d / "predictions.jsonl")
        if not p:
            continue
        name = next(iter(p.values()))["model"]
        preds[name] = p
        results[name] = runner.evaluate(notes, p)
    if not results:
        sys.exit(f"no predictions in {out}")
    print(report.write_all(out, notes, results, preds))
    print(f"\nwrote {out / 'leaderboard.md'}, results.json and details.html")


def cmd_run(args):
    notes = runner.load_notes(args.set)
    if args.limit:
        notes = notes[: args.limit]
    out = _out(args)
    for spec in args.model:
        runner.run(spec, notes, out, use_schema=not args.no_schema, use_format=not args.no_format)
    _report(out, runner.load_notes(args.set) if not args.limit else notes)


def cmd_report(args):
    notes = runner.load_notes(args.set)
    _report(_out(args), notes)


def cmd_convert(args):
    text = Path(args.file).read_text(encoding="utf-8") if args.file != "-" else sys.stdin.read()
    model = get_model(args.model)
    parsed = parse_reply(model.generate(text))
    if parsed.extraction is None:
        sys.exit(f"could not parse the model's reply: {parsed.status} {parsed.error}")
    bundle = fhir.to_bundle(parsed.extraction, Path(args.file).stem)
    out = json.dumps(bundle, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(out)
    try:
        errors = fhir.validate(bundle)
        print("FHIR R4B validation: " + ("passed" if not errors else f"{len(errors)} errors: {errors[:3]}"),
              file=sys.stderr)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="notes-to-fhir", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="regenerate the template notes")
    g.add_argument("--n", type=int, default=generate.DEFAULT_N)
    g.add_argument("--seed", type=int, default=generate.DEFAULT_SEED)
    g.set_defaults(func=cmd_generate)

    sub.add_parser("list", help="note sets and trap counts").set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="print one note")
    s.add_argument("note_id")
    s.add_argument("--gold", action="store_true", help="also print the gold label")
    s.set_defaults(func=cmd_show)

    r = sub.add_parser("run", help="extract with one or more models, then report")
    r.add_argument("-m", "--model", action="append", required=True,
                   help="baseline, ollama:<model> or anthropic:<model>; repeatable")
    r.add_argument("--set", default="all", choices=["all", *runner.SETS])
    r.add_argument("-o", "--out", default="results")
    r.add_argument("--limit", type=int, help="only the first N notes (smoke test)")
    r.add_argument("--no-schema", action="store_true", help="ask Ollama for plain JSON instead of the schema")
    r.add_argument("--no-format", action="store_true",
                   help="send no output format at all and pull the JSON out of the reply (for Gemma 3)")
    r.set_defaults(func=cmd_run)

    p = sub.add_parser("report", help="rescore saved predictions without calling any model")
    p.add_argument("-o", "--out", default="results")
    p.add_argument("--set", default="all", choices=["all", *runner.SETS])
    p.set_defaults(func=cmd_report)

    c = sub.add_parser("convert", help="turn one note (text file) into a FHIR Bundle")
    c.add_argument("file", help="path to a .txt note, or - for stdin")
    c.add_argument("-m", "--model", default="baseline")
    c.add_argument("-o", "--output")
    c.set_defaults(func=cmd_convert)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
