"""Extract flight duration observations from a registered BTS monthly archive."""

import argparse
import csv
import hashlib
import io
import json
import struct
from collections import Counter
from datetime import date
from pathlib import Path
from zipfile import ZipFile


BASE = "https://www.transtats.bts.gov/PREZIP/"
SOURCES = {
    "january": (1, "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_1.zip"),
    "april": (4, "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_4.zip"),
}
FIELDS = ("FlightDate", "CRSDepTime", "Cancelled", "Diverted", "CRSElapsedTime", "ActualElapsedTime")
RECORD = struct.Struct("<IHH")


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def whole(text):
    integer, _, fraction = text.partition(".")
    if fraction.strip("0"):
        raise ValueError("expected a whole number")
    return int(integer)


def minute_of_day(clock):
    hour, minute = divmod(whole(clock), 100)
    if hour == 24 and minute == 0:
        return 24 * 60
    if not 0 <= hour < 24 or minute >= 60:
        raise ValueError("invalid local departure clock")
    return hour * 60 + minute


def extract(source, month, output):
    counts = Counter()
    with ZipFile(source) as archive:
        names = [x for x in archive.namelist() if x.lower().endswith(".csv")]
        if len(names) != 1 or not names[0].endswith(f"_2024_{month}.csv"):
            raise ValueError("unexpected monthly CSV member")
        member = names[0]
        with io.TextIOWrapper(archive.open(member), encoding="utf-8-sig", newline="") as stream:
            rows = csv.reader(stream)
            columns = next(rows)
            indexes = [columns.index(name) for name in FIELDS]
            with output.open("xb") as binary:
                for row in rows:
                    counts["source_rows"] += 1
                    day, clock, cancelled, diverted, scheduled, actual = [row[index] for index in indexes]
                    try:
                        if whole(cancelled) or whole(diverted):
                            counts["cancelled_or_diverted"] += 1
                            continue
                        flight_date = date.fromisoformat(day)
                        if (flight_date.year, flight_date.month) != (2024, month):
                            raise ValueError("unexpected monthly flight date")
                        when = flight_date.day * 1440 + minute_of_day(clock)
                        before, after = whole(scheduled), whole(actual)
                        if not (0 < before < 65536 and 0 < after < 65536):
                            raise ValueError("invalid duration")
                    except ValueError:
                        counts["invalid_or_incomplete"] += 1
                        continue
                    counts["roster_rows"] += 1
                    counts["different_durations"] += before != after
                    binary.write(RECORD.pack(when, before, after))
    return member, dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=SOURCES)
    parser.add_argument("archive", type=Path)
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    output = args.work / f"{args.stage}-observations.bin"
    month, archive_name = SOURCES[args.stage]
    member, counts = extract(args.archive, month, output)
    data = {
        "archive_url": BASE + archive_name,
        "archive_sha256": digest(args.archive),
        "archive_bytes": args.archive.stat().st_size,
        "member": member,
        "counts": counts,
        "observations_sha256": digest(output),
        "observation_bytes": RECORD.size,
        "row_bytes_in_benchmark": 128,
    }
    with (args.work / f"{args.stage}-source.json").open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    print(f"Extracted {counts['roster_rows']:,} eligible flights from {counts['source_rows']:,} reports")


if __name__ == "__main__":
    main()
