"""Extract anonymous Blitz rating snapshots from the pinned Lichess archive."""

import argparse
import csv
import hashlib
import json
from bisect import bisect_left, bisect_right
from collections import Counter
from compression.zstd import ZstdFile
from itertools import product
from pathlib import Path
from statistics import median


ARCHIVE_URL = "https://database.lichess.org/standard/lichess_db_standard_rated_2015-01.pgn.zst"
ARCHIVE_BYTES = 285_559_460
CUTOFF_DAY = 22
DAYS = (22, 25, 28, 31)
HOURS = (6, 12, 18)
WIDTHS = (60, 600)
TAGS = {b"UTCDate", b"UTCTime", b"White", b"Black", b"WhiteElo", b"BlackElo"}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def windows():
    for day, hour, width in product(DAYS, HOURS, WIDTHS):
        yield f"2015-01-{day}T{hour:02d}:00Z/{width}s", day * 86_400 + hour * 3600, width


def blitz_headers(path):
    fields = None
    with ZstdFile(path) as stream:
        for line in stream:
            if line.startswith(b'[Event "'):
                if fields is not None:
                    yield fields
                event = line.rstrip(b"\r\n")
                blitz = event == b'[Event "Rated Blitz"]' or event.startswith(b'[Event "Rated Blitz ')
                fields = {} if blitz else None
            elif fields is not None:
                line = line.rstrip(b"\r\n")
                if not line:
                    yield fields
                    fields = None
                elif line.startswith(b"[") and line.endswith(b'"]'):
                    tag, separator, value = line[1:-2].partition(b' "')
                    if separator and tag in TAGS:
                        fields[tag] = value
    if fields is not None:
        yield fields


def timestamp(fields):
    date = fields.get(b"UTCDate", b"")
    time = fields.get(b"UTCTime", b"")
    if len(date) != 10 or not date.startswith(b"2015.01.") or len(time) != 8:
        return None
    try:
        day = int(date[-2:])
        hour, minute, second = map(int, time.split(b":"))
    except ValueError:
        return None
    if 1 <= day <= 31 and 0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60:
        return day * 86_400 + hour * 3600 + minute * 60 + second
    return None


def replay(path):
    cutoff = CUTOFF_DAY * 86_400
    initial = {}
    observed = []
    counts = Counter()
    for game_number, fields in enumerate(blitz_headers(path)):
        counts["rated_blitz_games"] += 1
        moment = timestamp(fields)
        if moment is None:
            counts["invalid_or_out_of_month_game_timestamps"] += 1
            continue
        for side, seat in enumerate((b"White", b"Black")):
            account = fields.get(seat, b"").lower()
            try:
                rating = int(fields[seat + b"Elo"])
            except (KeyError, ValueError):
                rating = 0
            if not account or account == b"?" or not 0 < rating <= 65535:
                counts["invalid_account_rating_observations"] += 1
                continue
            order = 2 * game_number + side
            if moment < cutoff:
                current = (moment, order, rating)
                old = initial.get(account)
                if old is None or current > old:
                    initial[account] = current
                counts["pre_cutoff_observations"] += 1
            else:
                observed.append((moment, order, account, rating))
                counts["post_cutoff_observations"] += 1

    roster = sorted(initial)
    positions = {account: index for index, account in enumerate(roster)}
    ratings = [initial[account][2] for account in roster]
    counts["roster"] = len(roster)
    schedule = list(windows())
    endpoints = sorted({endpoint for _, start, width in schedule for endpoint in (start, start + width)})
    snapshots = {}
    observed.sort()
    cursor = 0
    for end in endpoints:
        while cursor < len(observed) and observed[cursor][0] < end:
            _, _, account, rating = observed[cursor]
            index = positions.get(account)
            if index is None:
                counts["outside_roster_observations_before_last_endpoint"] += 1
            else:
                ratings[index] = rating
                counts["roster_observations_before_last_endpoint"] += 1
            cursor += 1
        snapshots[end] = ratings.copy()
    return counts, snapshots


def rank_positions(ordered):
    positions = [0] * len(ordered)
    for rank, (_, index) in enumerate(ordered):
        positions[index] = rank
    return positions


def geometry(before, after):
    old_order = sorted((rating, index) for index, rating in enumerate(before))
    new_order = sorted((rating, index) for index, rating in enumerate(after))
    old_positions = rank_positions(old_order)
    new_positions = rank_positions(new_order)
    changed = [index for index in range(len(before)) if before[index] != after[index]]
    distances = sorted(abs(old_positions[index] - new_positions[index]) for index in changed)
    if changed:
        first = min(old_positions[index] for index in changed)
        last = max(old_positions[index] for index in changed)
        replacements = [(after[index], index) for index in changed]
        begin = bisect_left(old_order, min(replacements), 0, first)
        end = bisect_right(old_order, max(replacements), lo=last + 1)
    else:
        begin = end = 0
    return {
        "edits": len(changed),
        "median_edited_displacement": median(distances) if distances else 0,
        "p95_edited_displacement": distances[(95 * len(distances) - 1) // 100] if distances else 0,
        "maximum_edited_displacement": max(distances, default=0),
        "affected_interval_rows": end - begin,
        "minimum_unchanged_writes": sum(
            first != last and before[index] == after[index]
            for index, (first, last) in enumerate(zip(old_positions, new_positions, strict=True))
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path, help="local directory for anonymous fixtures and aggregate geometry")
    args = parser.parse_args()
    if args.archive.stat().st_size != ARCHIVE_BYTES:
        raise SystemExit("unexpected January 2015 archive length")
    args.output.mkdir(parents=True, exist_ok=True)
    fixture_directory = args.output / "fixtures"
    fixture_directory.mkdir()
    source_digest = sha256(args.archive)
    counts, snapshots = replay(args.archive)
    result = {"archive_url": ARCHIVE_URL, "archive_bytes": ARCHIVE_BYTES,
              "archive_sha256": source_digest, "extraction_counts": dict(counts), "windows": []}
    if not counts["roster"]:
        raise SystemExit("no valid rated Blitz observations before the cutoff")
    for number, (label, start, width) in enumerate(windows()):
        before, after = snapshots[start], snapshots[start + width]
        path = fixture_directory / f"{number:02d}.csv"
        with path.open("x", encoding="ascii", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("id", "before", "after"))
            writer.writerows((index, first, last) for index, (first, last) in enumerate(zip(before, after, strict=True)))
        result["windows"].append({"label": label, "seconds": width, "fixture_sha256": sha256(path),
                                  **geometry(before, after)})
    with (args.output / "geometry.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(f"Prepared {len(result['windows'])} windows on a fixed roster of {counts['roster']:,} accounts")


if __name__ == "__main__":
    main()
