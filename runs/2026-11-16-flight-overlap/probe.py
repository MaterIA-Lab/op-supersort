"""Calculate verified page reuse when merging real flight schedules."""

import argparse
from bisect import bisect_left
import csv
from datetime import date
from heapq import merge
from itertools import combinations, groupby
import json
from pathlib import Path
import platform

from flight_sample import AIRPORTS, DAY, YEAR_START, load_flights


ROW_BYTES = 128
PAGE_BYTES = 4096
MIN_EXTENT_BYTES = 64 * 1024
PAGE_ROWS = PAGE_BYTES // ROW_BYTES
EXTENT_PAGES = MIN_EXTENT_BYTES // PAGE_BYTES
MONTHS = range(1, 13)


def merge_slices(left, right):
    def tagged(run, source):
        for key, row_number in run:
            yield key, source, row_number

    merged = merge(tagged(left, 0), tagged(right, 1))
    return [(side, sum(1 for _ in rows)) for side, rows in groupby(merged, key=lambda row: row[1])]


def extent_bytes(start, length):
    prefix = (-start) % PAGE_ROWS
    pages = max(0, length - prefix) // PAGE_ROWS
    return pages * PAGE_BYTES if pages >= EXTENT_PAGES else 0


def slice_geometry(slices):
    source_rows = [0, 0]
    output_rows = 0
    output_phases = [0] * PAGE_ROWS
    input_phases = [[0] * PAGE_ROWS for _ in range(2)]
    long_slice_bytes = 0
    for side, length in slices:
        position = source_rows[side]
        phase = (position - output_rows) % PAGE_ROWS
        output_phases[phase] += extent_bytes(position, length)
        input_phase = (output_rows - position) % PAGE_ROWS
        input_phases[side][input_phase] += extent_bytes(output_rows, length)
        if length >= EXTENT_PAGES * PAGE_ROWS:
            long_slice_bytes += length * ROW_BYTES
        source_rows[side] += length
        output_rows += length
    return output_phases, input_phases, long_slice_bytes


def explicit_page_bytes(merged, output_phase, input_phase):
    """Enumerate full contiguous pages of same-source records, grouped as extents."""
    def mapped_pages():
        for start in range((-output_phase) % PAGE_ROWS, len(merged) - PAGE_ROWS + 1, PAGE_ROWS):
            page = merged[start : start + PAGE_ROWS]
            _, side, _, rank = page[0]
            if (rank + input_phase) % PAGE_ROWS == 0 and all(
                record[1] == side and record[3] == rank + index
                for index, record in enumerate(page)
            ):
                yield side
            else:
                yield None

    total = [0, 0]
    for side, pages in groupby(mapped_pages()):
        if side is not None:
            count = sum(1 for _ in pages)
            if count >= EXTENT_PAGES:
                total[side] += count * PAGE_BYTES
    return total


def verify_geometry(left, right, slices, output_phases, input_phases):
    ordered = sorted(
        (key, side, row_number, rank)
        for side, run in enumerate((left, right))
        for rank, (key, row_number) in enumerate(run)
    )
    planned_order = (side for side, count in slices for _ in range(count))
    if not all(side == row[1] for side, row in zip(planned_order, ordered, strict=True)):
        raise ValueError("merge disagrees with stable reference order")
    for phase in range(PAGE_ROWS):
        if output_phases[phase] != sum(explicit_page_bytes(ordered, phase, 0)):
            raise ValueError(f"output shift disagrees with explicit pages for phase {phase}")
        reference = explicit_page_bytes(ordered, 0, phase)
        if [totals[phase] for totals in input_phases] != reference:
            raise ValueError(f"input alignment disagrees with explicit pages for phase {phase}")


def check_boundary_geometry():
    minimum = EXTENT_PAGES * PAGE_ROWS
    for left_size in (minimum - 1, minimum, minimum + 1, minimum * 2 + 1):
        for right_size in (minimum - 1, minimum, minimum + 1, minimum * 2 + 1):
            # Equal keys exercise the stable left-first policy and unaligned boundaries.
            left = [(0, i) for i in range(left_size)]
            right = [(0, left_size + i) for i in range(right_size)]
            slices = merge_slices(left, right)
            out, source, _ = slice_geometry(slices)
            verify_geometry(left, right, slices, out, source)
            fixed_left = left_size // PAGE_ROWS * PAGE_BYTES if left_size >= minimum else 0
            if left_size % PAGE_ROWS:
                assert out[0] == fixed_left
            else:
                expected_right = right_size // PAGE_ROWS * PAGE_BYTES if right_size >= minimum else 0
                assert out[0] == fixed_left + expected_right


def wall_clock(month, day, hour=0):
    return (date(2013, month, day) - YEAR_START).days * DAY + hour * 60


def cases(flights):
    by_actual_time = sorted(flights, key=lambda flight: flight.actual)
    clock = [flight.actual for flight in by_actual_time]

    def window(start, end):
        return by_actual_time[bisect_left(clock, start):bisect_left(clock, end)]

    for days in (7, 1):
        width = days * DAY
        for month in MONTHS:
            for day in (8, 15, 22):
                boundary = wall_clock(month, day, 12)
                yield (
                    f"adjacent_{days}d", f"2013-{month:02}-{day:02}T12:00",
                    window(boundary - width, boundary), window(boundary, boundary + width),
                )
    for month in MONTHS:
        start = wall_clock(month, 1)
        end = wall_clock(month + 1, 1) if month < 12 else 365 * DAY
        airports = {airport: [] for airport in AIRPORTS}
        for flight in window(start, end):
            airports[flight.airport].append(flight)
        for a, b in combinations(AIRPORTS, 2):
            yield "parallel_month", f"2013-{month:02} {a}/{b}", airports[a], airports[b]


def ordered_keys(flights):
    return sorted((flight.scheduled, flight.row_number) for flight in flights)


def measure(regime, case, left_flights, right_flights):
    left, right = ordered_keys(left_flights), ordered_keys(right_flights)
    total = len(left) + len(right)
    slices = merge_slices(left, right)
    out, source, long_slice_bytes = slice_geometry(slices)
    verify_geometry(left, right, slices, out, source)

    overlap_minutes = overlap_rows = 0
    if left and right:
        start = max(left[0][0], right[0][0])
        end = min(left[-1][0], right[-1][0])
        if end > start:
            overlap_minutes = end - start
            overlap_rows = sum(start <= key <= end for run in (left, right) for key, _ in run)

    out_phase = max(range(PAGE_ROWS), key=out.__getitem__)
    input_a, input_b = [max(range(PAGE_ROWS), key=totals.__getitem__) for totals in source]
    fixed_bytes, output_bytes = out[0], out[out_phase]
    independent_bytes = source[0][input_a] + source[1][input_b]
    if not (fixed_bytes <= min(output_bytes, independent_bytes)
            and max(output_bytes, independent_bytes) <= long_slice_bytes <= total * ROW_BYTES):
        raise ValueError("page estimates violated the measured slice upper bound")

    return {
        "regime": regime,
        "case": case,
        "rows_a": len(left),
        "rows_b": len(right),
        "overlap_minutes": overlap_minutes,
        "overlap_rows": overlap_rows,
        "same_source_slices": len(slices),
        "longest_slice_rows": max((length for _, length in slices), default=0),
        "unaligned_slice_upper_bytes": long_slice_bytes,
        "fixed_mappable_bytes": fixed_bytes,
        "best_output_offset_bytes": out_phase * ROW_BYTES,
        "best_output_mappable_bytes": output_bytes,
        "best_input_a_offset_bytes": input_a * ROW_BYTES,
        "best_input_b_offset_bytes": input_b * ROW_BYTES,
        "best_inputs_mappable_bytes": independent_bytes,
    }


def analyze(rows):
    result = {}
    for regime, cases_by_regime in groupby(rows, key=lambda row: row["regime"]):
        group = list(cases_by_regime)
        substantial = [
            row for row in group
            if row["overlap_rows"] * 20 >= row["rows_a"] + row["rows_b"]
            and row["overlap_minutes"] > 0
        ]
        counts = {"cases": len(group), "positive_overlap": sum(
            row["overlap_minutes"] > 0 for row in group
        ), "substantial_overlap": len(substantial)}
        for name in ("fixed", "best_output", "best_inputs"):
            passes = [
                row["case"] for row in substantial
                if row[f"{name}_mappable_bytes"] * 8 >= (row["rows_a"] + row["rows_b"]) * ROW_BYTES * 3
            ]
            counts[f"{name}_gate"] = passes
        result[regime] = counts
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rda_file", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    check_boundary_geometry()
    flights, source = load_flights(args.rda_file)
    rows = [measure(*case) for case in cases(flights)]
    if len(rows) != 108:
        raise ValueError("the registered matrix requires 108 cases")

    args.output_directory.mkdir(parents=True, exist_ok=True)
    with (args.output_directory / "coverage.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "source": source,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "record_bytes": ROW_BYTES,
        "page_bytes": PAGE_BYTES,
        "minimum_extent": MIN_EXTENT_BYTES,
        "geometry_verification": "stable reference order and all 32 offsets checked per case",
        "regimes": analyze(rows),
    }
    (args.output_directory / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
