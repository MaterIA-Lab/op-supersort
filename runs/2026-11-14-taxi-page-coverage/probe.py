"""Measure page reuse in a stable merge of completed-trip batches."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, time, timedelta
from fractions import Fraction
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from itertools import groupby
import json
from pathlib import Path
import platform


BOUNDARIES = tuple(date(2019, 3, day) for day in (8, 9, 15, 16, 22, 23))
SOURCE_URL = (
    "https://raw.githubusercontent.com/mwaskom/seaborn-data/"
    "71e2436a092d714350de0fc409ca8a8714e7e78f/taxis.csv"
)
SOURCE_BLOB = "ded045b462d361b8a0e5ddcdd6c3361cce4ddab4"
MIN_COVERAGE = Fraction(3, 8)
MIN_OVERLAP_FRACTION = Fraction(1, 20)
ARCHIVE_PROBE = (
    Path(__file__).resolve().parents[1] / "2026-11-12-gharchive-page-coverage" / "probe.py"
)
EPOCH = datetime(1970, 1, 1)


def wall_clock_microseconds(value):
    elapsed = value - EPOCH
    return (elapsed.days * 86_400 + elapsed.seconds) * 1_000_000 + elapsed.microseconds


def load_archive_probe(path):
    spec = spec_from_file_location("archive_page_coverage", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import page geometry from {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_trips(path):
    raw = path.read_bytes()
    git_object = f"blob {len(raw)}\0".encode("ascii") + raw
    blob = hashlib.sha1(git_object).hexdigest()
    if blob != SOURCE_BLOB:
        raise ValueError(f"unexpected taxi sample blob {blob}")
    batches = {hour: defaultdict(Counter) for hour in (0, 12)}
    counts = Counter(rows=0, invalid_timestamp=0, reverse_clock=0, valid=0)
    for row in csv.DictReader(StringIO(raw.decode("utf-8"), newline="")):
        counts["rows"] += 1
        try:
            pickup = datetime.fromisoformat(row["pickup"])
            dropoff = datetime.fromisoformat(row["dropoff"])
        except (TypeError, ValueError):
            counts["invalid_timestamp"] += 1
            continue
        if pickup.tzinfo is not None or dropoff.tzinfo is not None:
            counts["invalid_timestamp"] += 1
            continue
        if dropoff < pickup:
            counts["reverse_clock"] += 1
            continue
        microseconds = wall_clock_microseconds(pickup)
        for hour, bins in batches.items():
            day = dropoff.date() - timedelta(days=int(dropoff.hour < hour))
            bins[day][microseconds] += 1
        counts["valid"] += 1
    return batches, {
        "url": SOURCE_URL,
        "blob": blob,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        **counts,
    }


def take_batch(batches, start, days):
    result = Counter()
    for offset in range(days):
        result.update(batches.get(start + timedelta(days=offset), ()))
    return result


def offset_geometry(archive, first, second):
    """Count candidates by assigning each whole slice to its only valid pointer offset."""
    positions = [0, 0]
    rows_per_page = archive.ROWS_PER_PAGE
    min_pages = archive.MIN_EXTENT_BYTES // archive.PAGE_BYTES
    amounts = [0] * rows_per_page
    for side, rows in archive.grouped_slices(first, second):
        source = positions[side]
        destination = sum(positions)
        output_offset = (source - destination) % rows_per_page
        first_page = ((source + rows_per_page - 1) // rows_per_page) * rows_per_page
        pages = max(0, source + rows - first_page) // rows_per_page
        if pages >= min_pages:
            amounts[output_offset] += pages * archive.PAGE_BYTES
        positions[side] += rows
    return amounts


def reference_offsets(archive, first, second):
    """Enumerate complete pages in the stable row-by-row merge for each output offset."""
    page_rows = archive.ROWS_PER_PAGE
    min_pages = archive.MIN_EXTENT_BYTES // archive.PAGE_BYTES
    row_sides = list(archive.stable_row_sides(first, second))
    amounts = []
    for output_offset in range(page_rows):
        positions = [0, 0]
        destination = total_pages = 0
        for side, group in groupby(row_sides):
            size = sum(1 for _ in group)
            source = positions[side]
            pages = 0
            for i in range(size - page_rows + 1):
                if (source + i) % page_rows == (destination + i + output_offset) % page_rows == 0:
                    pages += 1
            if pages >= min_pages:
                total_pages += pages
            positions[side] += size
            destination += size
        amounts.append(total_pages * archive.PAGE_BYTES)
    return amounts


def measure_pair(archive, batches, boundary, days, hour):
    first = take_batch(batches, boundary - timedelta(days=days), days)
    second = take_batch(batches, boundary, days)
    base = archive.page_geometry(first, second)
    offsets = offset_geometry(archive, first, second)
    if offsets[0] != base["mappable_bytes"] or offsets != reference_offsets(archive, first, second):
        raise ValueError(f"page eligibility mismatch at {boundary}, {days}-day batches")
    overlap_us = overlap_rows = 0
    if first and second:
        start = max(min(first), min(second))
        end = min(max(first), max(second))
        if end > start:
            overlap_us = end - start
            overlap_rows = sum(
                count for run in (first, second) for tick, count in run.items()
                if start <= tick <= end
            )
    output_bytes = (base["rows_a"] + base["rows_b"]) * archive.ROW_BYTES
    best = max(range(len(offsets)), key=offsets.__getitem__)
    aligned_fraction = Fraction(offsets[0], output_bytes) if output_bytes else Fraction(0)
    best_fraction = Fraction(offsets[best], output_bytes) if output_bytes else Fraction(0)
    total_rows = base["rows_a"] + base["rows_b"]
    overlap_fraction = Fraction(overlap_rows, total_rows) if total_rows else Fraction(0)
    return {
        "boundary": datetime.combine(boundary, time(hour)).isoformat(timespec="minutes"),
        "days_per_batch": days,
        "pickup_overlap_seconds": overlap_us / 1_000_000,
        "overlapping_rows": overlap_rows,
        "overlapping_fraction": float(overlap_fraction),
        "output_bytes": output_bytes,
        **base,
        "aligned_fraction": float(aligned_fraction),
        "best_output_offset_bytes": best * archive.ROW_BYTES,
        "best_offset_mappable_bytes": offsets[best],
        "best_fraction": float(best_fraction),
        "aligned_gate": int(overlap_us > 0 and aligned_fraction >= MIN_COVERAGE),
        "best_offset_gate": int(overlap_us > 0 and best_fraction >= MIN_COVERAGE),
        "aligned_substantive_gate": int(
            overlap_fraction >= MIN_OVERLAP_FRACTION and aligned_fraction >= MIN_COVERAGE
        ),
        "best_offset_substantive_gate": int(
            overlap_fraction >= MIN_OVERLAP_FRACTION and best_fraction >= MIN_COVERAGE
        ),
    }


def run(archive, input_path, output_directory):
    by_hour, source = load_trips(input_path)
    rows = [
        measure_pair(archive, batches, boundary, days, hour)
        for hour, batches in by_hour.items()
        for days in (7, 1)
        for boundary in BOUNDARIES
    ]
    output_directory.mkdir(parents=True, exist_ok=True)
    with (output_directory / "coverage.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    gate_columns = ("aligned_gate", "best_offset_gate", "aligned_substantive_gate",
                    "best_offset_substantive_gate")
    weekly = {
        str(hour): {
            name: sum(row[name] for row in rows
                      if row["days_per_batch"] == 7 and row["boundary"].endswith(f"T{hour:02d}:00"))
            for name in gate_columns
        }
        for hour in by_hour
    }
    metadata = {
        "source": source,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "row_bytes": archive.ROW_BYTES,
        "page_bytes": archive.PAGE_BYTES,
        "minimum_extent_bytes": archive.MIN_EXTENT_BYTES,
        "weekly_passes_by_hour": weekly,
    }
    (output_directory / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--archive-probe", type=Path, default=ARCHIVE_PROBE)
    args = parser.parse_args()
    run(load_archive_probe(args.archive_probe), args.input, args.output_directory)


if __name__ == "__main__":
    main()
