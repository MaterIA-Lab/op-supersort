#!/usr/bin/env python3
"""Build the run ledger and the progress views from the front matter of runs/*/README.md.

Every run README starts with a front matter block between two `---` lines:

    ---
    title: Blocked record permutation probe
    date: 2026-11-12 16:48              # UTC time is optional; it orders runs of the same day
    verdict: failed
    summary: One sentence for humans on what was learned, including why it failed.
    model: agent:gpt-6 (Codex)
    idea: record-permutation            # optional, a heading slug in notes/ideas.md
    result: 0.542–0.648×                # optional, headline number
    baseline: fastest measured reference  # optional, what the result is compared with
    closes: [tile-and-sort permutation]   # optional, lines of work this run closes
    opens: [prefetch gather as control]   # optional, lines of work this run opens
    cost: not captured                     # optional
    ---

The script writes `runs/index.json` (machine-readable, read by the OpenPrototypes index)
and refreshes the generated blocks between `<!-- RUNS:START -->` and `<!-- RUNS:END -->`
in PROGRESS.md (for humans) and notes/agent-brief.md (for agents).

Usage:
    python scripts/build_progress.py           # write files
    python scripts/build_progress.py --check   # exit 1 if a run is invalid or outputs are stale

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
INDEX = RUNS / "index.json"
PROGRESS = ROOT / "PROGRESS.md"
BRIEF = ROOT / "notes" / "agent-brief.md"

VERDICTS = {
    "works": "✅ works",
    "promising": "🟡 promising",
    "failed": "❌ failed",
    "inconclusive": "❔ inconclusive",
    "diagnostic": "🔎 diagnostic",
    "setup": "⚙️ setup",
}
REQUIRED = ("title", "date", "verdict", "summary", "model")
OPTIONAL = ("idea", "result", "baseline", "closes", "opens", "cost")
LISTS = ("closes", "opens")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")
START = "<!-- RUNS:START -->"
END = "<!-- RUNS:END -->"


def parse_value(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [parse_value(x) for x in split_list(inner)] if inner else []
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def split_list(inner: str) -> list[str]:
    items, buf, quote = [], "", None
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            items.append(buf)
            buf = ""
        else:
            buf += ch
    items.append(buf)
    return [x.strip() for x in items if x.strip()]


def read_front_matter(path: Path) -> tuple[dict | None, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None, ["missing front matter (the file must start with a '---' line)"]
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, ["front matter is not closed with a '---' line"]
    data: dict = {}
    errors: list[str] = []
    for n, line in enumerate(lines[1:end], start=2):
        text = line.split(" #", 1)[0].rstrip() if not line.lstrip().startswith("#") else ""
        if not text.strip():
            continue
        if ":" not in text:
            errors.append(f"line {n}: expected 'key: value'")
            continue
        key, value = text.split(":", 1)
        data[key.strip()] = parse_value(value)
    return data, errors


def load_runs() -> tuple[list[dict], list[str]]:
    runs, errors = [], []
    if not RUNS.is_dir():
        return runs, errors
    for readme in sorted(RUNS.glob("*/README.md")):
        rid = readme.parent.name
        data, errs = read_front_matter(readme)
        errs = [f"runs/{rid}/README.md: {e}" for e in errs]
        if data is not None:
            for key in REQUIRED:
                if not data.get(key):
                    errs.append(f"runs/{rid}/README.md: missing '{key}'")
            unknown = set(data) - set(REQUIRED) - set(OPTIONAL)
            if unknown:
                errs.append(f"runs/{rid}/README.md: unknown keys {sorted(unknown)}")
            if data.get("verdict") and data["verdict"] not in VERDICTS:
                errs.append(f"runs/{rid}/README.md: verdict '{data['verdict']}' not in {sorted(VERDICTS)}")
            if data.get("date") and not DATE_RE.match(str(data["date"])):
                errs.append(f"runs/{rid}/README.md: date must be YYYY-MM-DD or YYYY-MM-DD HH:MM (UTC)")
            for key in LISTS:
                if key in data and not isinstance(data[key], list):
                    data[key] = [data[key]] if data[key] else []
            for key in set(data) - set(LISTS):
                if isinstance(data[key], list):
                    errs.append(f"runs/{rid}/README.md: '{key}' must be a single value")
            if not errs:
                runs.append({"id": rid, "path": f"runs/{rid}/", **data})
        errors.extend(errs)
    runs.sort(key=lambda r: (str(r["date"]), r["id"]))
    return runs, errors


def cell(text) -> str:
    if isinstance(text, list):
        text = "; ".join(text)
    return " ".join(str(text or "").split()).replace("|", "\\|")


def counts_line(runs: list[dict]) -> str:
    if not runs:
        return "No runs recorded yet."
    parts = []
    for v, label in VERDICTS.items():
        n = sum(r["verdict"] == v for r in runs)
        if n:
            parts.append(f"{n} {label.split(' ', 1)[1]}")
    return f"{len(runs)} runs: " + ", ".join(parts) + "."


def human_table(runs: list[dict]) -> str:
    lines = [counts_line(runs)]
    if runs:
        lines += ["", "| Date | Run | Verdict | Result | What we learned |", "|---|---|---|---|---|"]
        for r in reversed(runs):
            lines.append(f"| {r['date']} | [{cell(r['title'])}]({r['path']}) | {VERDICTS[r['verdict']]} "
                         f"| {cell(r.get('result', '—'))} | {cell(r['summary'])} |")
    return "\n".join(lines)


def agent_table(runs: list[dict]) -> str:
    lines = [counts_line(runs)]
    if runs:
        lines += ["", "| Run | Date | Verdict | Idea | Result | Baseline | Closes | Opens | Model |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in runs:
            lines.append(f"| [{r['id']}](../{r['path']}) | {r['date']} | {r['verdict']} | {cell(r.get('idea', '—'))} "
                         f"| {cell(r.get('result', '—'))} | {cell(r.get('baseline', '—'))} "
                         f"| {cell(r.get('closes', []) or '—')} | {cell(r.get('opens', []) or '—')} | {cell(r['model'])} |")
        lines += ["", "Summaries, oldest first:", ""]
        lines += [f"- **{r['id']}** ({r['verdict']}): {cell(r['summary'])}" for r in runs]
    return "\n".join(lines)


def render_block(path: Path, body: str) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        sys.exit(f"{path.relative_to(ROOT)} is missing the {START} / {END} markers")
    return pattern.sub(lambda _: f"{START}\n{body}\n{END}", text, count=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if a run is invalid or outputs are stale")
    args = parser.parse_args()

    runs, errors = load_runs()
    if errors:
        sys.exit("Invalid run front matter:\n  " + "\n  ".join(errors))

    outputs: dict[Path, str] = {
        INDEX: json.dumps({"runs": runs}, indent=2, ensure_ascii=False) + "\n",
    }
    for path, body in ((PROGRESS, human_table(runs)), (BRIEF, agent_table(runs))):
        rendered = render_block(path, body)
        if rendered is None:
            sys.exit(f"{path.relative_to(ROOT)} does not exist")
        outputs[path] = rendered

    stale = [p for p, c in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != c]
    if args.check:
        if stale:
            sys.exit("Out of date: " + ", ".join(str(p.relative_to(ROOT)) for p in stale)
                     + "\nRun: python scripts/build_progress.py")
        print(f"Progress is up to date ({len(runs)} runs).")
        return
    for path in stale:
        path.write_text(outputs[path], encoding="utf-8", newline="\n")
        print(f"Updated {path.relative_to(ROOT)}")
    if not stale:
        print("Nothing to update.")


if __name__ == "__main__":
    main()
