import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
from itertools import groupby, repeat, zip_longest
import json
from pathlib import Path
import platform
import shutil
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zlib


DAYS = ("2025-01-15", "2025-01-18")
HOURS = (8, 9, 10, 11)
PAIRS = (((8,), (9,)), ((9,), (10,)), ((10,), (11,)), ((8, 9), (10, 11)))
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
ROW_BYTES = 128
PAGE_BYTES = 4096
MIN_EXTENT_BYTES = 64 * 1024
ROWS_PER_PAGE = PAGE_BYTES // ROW_BYTES
ORIGIN = "https://data.gharchive.org"


def source_name(day, hour):
    return f"{day}-{hour}.json.gz"


def label(hours):
    return "-".join(f"{hour:02d}" for hour in hours)


def fetch(path, url):
    temporary = path.with_suffix(".part")
    try:
        for attempt in range(3):
            try:
                request = Request(url, headers={"User-Agent": "OpenPrototypes-SuperSort-research/1.0"})
                with urlopen(request, timeout=45) as response, temporary.open("wb") as output:
                    shutil.copyfileobj(response, output, length=1 << 20)
                temporary.replace(path)
                return
            except OSError as error:
                if attempt == 2 or (isinstance(error, HTTPError) and error.code in (403, 404, 410)):
                    raise
                time.sleep(2 ** attempt)
    finally:
        temporary.unlink(missing_ok=True)


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    if parsed.utcoffset() != timedelta(0):
        return None
    elapsed = parsed - EPOCH
    return (elapsed.days * 86_400 + elapsed.seconds) * 1_000_000 + elapsed.microseconds


def iso_utc(micros):
    return (EPOCH + timedelta(microseconds=micros)).isoformat().replace("+00:00", "Z")


def load_archive(path, allow_fetch):
    url = f"{ORIGIN}/{path.name}"
    metadata = {"file": path.name, "url": url}
    try:
        if not path.is_file() and allow_fetch:
            fetch(path, url)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)

        counts = Counter()
        invalid_json = invalid_timestamp = 0
        with gzip.open(path, "rb") as handle:
            for raw in handle:
                try:
                    event = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    invalid_json += 1
                    continue
                instant = timestamp(event.get("created_at")) if isinstance(event, dict) else None
                if instant is None:
                    invalid_timestamp += 1
                else:
                    counts[instant] += 1
        if not counts:
            raise ValueError("archive contains no valid event timestamps")
        metadata.update(status="ok", sha256=digest.hexdigest(), compressed_bytes=path.stat().st_size,
                        rows=sum(counts.values()), invalid_json=invalid_json, invalid_timestamp=invalid_timestamp,
                        earliest=iso_utc(min(counts)), latest=iso_utc(max(counts)))
        return counts, metadata
    except (OSError, EOFError, ValueError, zlib.error) as error:
        reason = f"HTTP {error.code}" if isinstance(error, HTTPError) else type(error).__name__
        metadata.update(status="unavailable", reason=reason)
        print(f"{path.name}: unavailable ({reason})", flush=True)
        return None, metadata


def grouped_slices(first, second):
    groups = ((instant, side, count) for side, batch in enumerate((first, second))
              for instant, count in batch.items())
    for side, group in groupby(sorted(groups), key=lambda value: value[1]):
        yield side, sum(count for _, _, count in group)


def stable_row_sides(first, second):
    def expanded(batch):
        for instant, count in sorted(batch.items()):
            yield from repeat(instant, count)

    left, right = expanded(first), expanded(second)
    a, b = next(left, None), next(right, None)
    while a is not None and b is not None:
        if a <= b:
            yield 0
            a = next(left, None)
        else:
            yield 1
            b = next(right, None)
    if a is not None:
        yield 0
        for _ in left:
            yield 0
    if b is not None:
        yield 1
        for _ in right:
            yield 1


def page_geometry(first, second):
    reference = ((side, sum(1 for _ in group)) for side, group in groupby(stable_row_sides(first, second)))
    consumed = [0, 0]
    source_bytes = aligned_bytes = mappable_bytes = extents = largest = slices = 0
    for measured, expected in zip_longest(grouped_slices(first, second), reference):
        if measured != expected:
            raise ValueError("grouped merge diverged from the independent stable row merge")
        side, count = measured
        offset = consumed[side]
        destination = sum(consumed)
        consumed[side] += count
        slices += 1
        prefix = (-offset) % ROWS_PER_PAGE
        full_bytes = max(0, count - prefix) // ROWS_PER_PAGE * PAGE_BYTES
        source_bytes += full_bytes
        if offset % ROWS_PER_PAGE == destination % ROWS_PER_PAGE:
            aligned_bytes += full_bytes
            if full_bytes >= MIN_EXTENT_BYTES:
                mappable_bytes += full_bytes
                largest = max(largest, full_bytes)
                extents += 1
    if consumed != [sum(first.values()), sum(second.values())]:
        raise ValueError("merge did not consume all records")
    return {"rows_a": consumed[0], "rows_b": consumed[1], "slices": slices,
            "full_source_bytes": source_bytes, "same_phase_bytes": aligned_bytes,
            "mappable_bytes": mappable_bytes, "mappable_extents": extents, "largest_extent_bytes": largest}


def pair_cases():
    return [(day, left, right) for day in DAYS for left, right in PAIRS]


def probe(cache, output, allow_fetch):
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True)
    names = [source_name(day, hour) for day in DAYS for hour in HOURS]
    started = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=4) as executor:
        inputs = dict(zip(names, executor.map(lambda name: load_archive(cache / name, allow_fetch), names)))
    for name, (_, info) in inputs.items():
        if info["status"] == "ok":
            print(f"{name}: {info['rows']:,} events", flush=True)

    metrics = ("rows_a", "rows_b", "overlap_us", "shared_timestamps", "slices", "full_source_bytes",
               "same_phase_bytes", "mappable_bytes", "mappable_extents", "largest_extent_bytes")
    with (output / "coverage.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("day", "capture_a", "capture_b", "status", *metrics))
        writer.writeheader()
        for day, left, right in pair_cases():
            cohorts = [[inputs[source_name(day, hour)][0] for hour in hours] for hours in (left, right)]
            row = {"day": day, "capture_a": label(left), "capture_b": label(right), "status": "ok"}
            if any(counts is None for cohort in cohorts for counts in cohort):
                writer.writerow({**row, "status": "missing_source"})
                continue
            first, second = Counter(), Counter()
            for merged, cohort in zip((first, second), cohorts):
                for counts in cohort:
                    merged.update(counts)
            overlap = max(0, min(max(first), max(second)) - max(min(first), min(second)))
            shared = len(first.keys() & second.keys())
            writer.writerow({**row, **page_geometry(first, second), "overlap_us": overlap,
                             "shared_timestamps": shared})

    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent, text=True).strip()
    metadata = {"source_commit": revision, "python": platform.python_version(), "os": platform.system(),
                "started_utc": started.isoformat(timespec="seconds"),
                "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "row_bytes": ROW_BYTES, "page_bytes": PAGE_BYTES, "min_extent_bytes": MIN_EXTENT_BYTES,
                "archives": [info for _, info in inputs.values()]}
    (output / "archives.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def report(path):
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if [(row["day"], row["capture_a"], row["capture_b"]) for row in rows] != [
            (day, label(left), label(right)) for day, left, right in pair_cases()]:
        raise ValueError("input does not contain the full preregistered pair matrix")
    print("| Capture date | UTC batches | Events | Timestamp-range overlap | Full source pages | Same phase | Mappable | Extents |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    passing_days = set()
    missing = 0
    for row in rows:
        day = row["day"]
        batches = f"{row['capture_a']} → {row['capture_b']}"
        if row["status"] == "missing_source":
            missing += 1
            print(f"| {day} | {batches} | missing source | — | — | — | — | — |")
            continue
        if row["status"] != "ok":
            raise ValueError("unrecognized case status")
        events = int(row["rows_a"]) + int(row["rows_b"])
        total = events * ROW_BYTES
        source, phase, mappable = (int(row[key]) for key in ("full_source_bytes", "same_phase_bytes", "mappable_bytes"))
        extents = int(row["mappable_extents"])
        if not 0 <= mappable <= phase <= source <= total or bool(mappable) != bool(extents):
            raise ValueError("invalid coverage counts")
        if mappable * 8 >= total * 3:
            passing_days.add(day)
        print(f"| {day} | {batches} | {events:,} | {int(row['overlap_us']) / 1e6:.1f} s | "
              f"{source / total:.2%} | {phase / total:.2%} | {mappable / total:.2%} | {extents:,} |")
    verdict = "passed" if len(passing_days) == len(DAYS) else "incomplete" if missing else "failed"
    print(f"\nTiming gate {verdict}. {len(passing_days)}/{len(DAYS)} dates had a pair with at least 37.5% mappable bytes.")


def self_test():
    tests = (
        ({1: 1024, 3: 1024}, {2: 512}, 2560, 3),
        ({1: 1024, 3: 1024}, {2: 513}, 1536, 2),
        ({1: 1, 3: 544}, {2: 32}, 512, 1),
        ({1: 32}, {2: 32}, 0, 0),
        ({1: 512}, {1: 512}, 1024, 2),
    )
    for first, second, expected_rows, expected_calls in tests:
        result = page_geometry(first, second)
        if (result["mappable_bytes"], result["mappable_extents"]) != (expected_rows * ROW_BYTES, expected_calls):
            raise ValueError(f"wrong page geometry for {first}, {second}")
    if list(grouped_slices({1: 512}, {1: 512})) != [(0, 512), (1, 512)]:
        raise ValueError("timestamp ties did not keep the earlier capture first")
    if timestamp("1970-01-01T00:00:00.25Z") != 250_000 or timestamp("1970-01-01T00:00:00") is not None:
        raise ValueError("UTC timestamp handling changed")
    print("Page geometry, cutoff, stable ties and UTC timestamps verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measure remappable page coverage of GH Archive capture batches.")
    parser.add_argument("--cache", type=Path, help="directory for the original gzip files")
    parser.add_argument("--output", type=Path, help="new directory for aggregate data and source metadata")
    parser.add_argument("--fetch", action="store_true", help="download missing preregistered gzip files")
    parser.add_argument("--report", type=Path, help="render the preregistered pair table from coverage.csv")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.report:
        report(args.report)
    elif args.cache and args.output:
        probe(args.cache, args.output, args.fetch)
        report(args.output / "coverage.csv")
    else:
        parser.error("provide --cache and --output, --report, or --self-test")
