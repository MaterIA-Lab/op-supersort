"""Extract the registered fixed-membership FIDE ranking fixture."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


def read_list(path, month):
    ratings = {}
    repeated = set()
    with ZipFile(path) as archive:
        [member] = archive.infolist()
        if member.filename.lower() != f"standard_{month.lower()}frl.txt":
            raise ValueError(f"unexpected {month} archive member")
        with archive.open(member) as stream:
            header = stream.readline()
            if not header.startswith(b"ID Number "):
                raise ValueError(f"unexpected {month} header")
            id_end = header.index(b"Name")
            rating_start = header.index(month.encode("ascii"))
            rating_end = header.index(b"Gms", rating_start)
            for line_number, line in enumerate(stream, start=2):
                player_id = line[:id_end].strip()
                rating = line[rating_start:rating_end].strip()
                if not player_id.isdigit() or not rating.isdigit():
                    raise ValueError(f"invalid rating row {line_number} in {month}")
                player_id, rating = int(player_id), int(rating)
                if not 0 < rating < 65536:
                    raise ValueError(f"rating outside the benchmark key domain in {month}")
                if player_id in ratings:
                    repeated.add(player_id)
                ratings[player_id] = rating
    metadata = {
        "month": month,
        "filesize": path.stat().st_size,
        "zip_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rated_rows": line_number - 1,
        "unique_ids": len(ratings),
        "repeated_ids": len(repeated),
    }
    return ratings, repeated, metadata


def quantiles(values):
    values = sorted(values)
    if not values:
        return None
    return {
        f"p{percent}": values[(percent * len(values) + 99) // 100 - 1]
        for percent in (1, 25, 50, 75, 95, 99, 100)
    }


def prepare(before_path, after_path, fixture_path):
    before, duplicates_before, meta_before = read_list(before_path, "JUN24")
    after, duplicates_after, meta_after = read_list(after_path, "JUL24")
    matching = before.keys() & after.keys()
    ambiguous = matching & (duplicates_before | duplicates_after)
    players = sorted(matching - ambiguous)
    keys = [(before[player], after[player]) for player in players]
    initial = sorted(range(len(keys)), key=lambda index: (keys[index][0], index))
    final = sorted(range(len(keys)), key=lambda index: (keys[index][1], index))
    destinations = [0] * len(keys)
    for rank, index in enumerate(final):
        destinations[index] = rank

    old_ranks = []
    new_ranks = []
    rating_changes = []
    minimum_writes = 0
    for rank, index in enumerate(initial):
        old_rating, new_rating = keys[index]
        if old_rating != new_rating:
            old_ranks.append(rank)
            new_ranks.append(destinations[index])
            rating_changes.append(new_rating - old_rating)
        else:
            minimum_writes += destinations[index] != rank

    with fixture_path.open("x", encoding="ascii", newline="\n") as stream:
        stream.write("id,before,after\n")
        for index, (old_rating, new_rating) in enumerate(keys):
            stream.write(f"{index},{old_rating},{new_rating}\n")
    return {
        "sources": [meta_before, meta_after],
        "june_only_ids": len(before.keys() - after.keys()),
        "july_only_ids": len(after.keys() - before.keys()),
        "ambiguous_shared_ids_excluded": len(ambiguous),
        "shared_rows": len(keys),
        "array_bytes_at_128_per_row": len(keys) * 128,
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "edits": len(rating_changes),
        "rating_delta": quantiles(rating_changes),
        "absolute_rank_delta": quantiles(abs(old - new) for old, new in zip(old_ranks, new_ranks, strict=True)),
        "edited_old_ranks": quantiles(old_ranks),
        "edited_new_ranks": quantiles(new_ranks),
        "minimum_unchanged_writes": minimum_writes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("june", type=Path)
    parser.add_argument("july", type=Path)
    parser.add_argument("fixture", type=Path, help="local output with one pair of ratings per shared row")
    parser.add_argument("geometry", type=Path, help="aggregate output suitable for publication")
    args = parser.parse_args()
    if args.fixture.exists() or args.geometry.exists():
        raise SystemExit("output already exists")
    result = prepare(args.june, args.july, args.fixture)
    with args.geometry.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(f"{result['shared_rows']:,} shared rated entries, {result['edits']:,} edited ratings")
