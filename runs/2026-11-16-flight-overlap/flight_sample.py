"""Read the pinned OpenIntro flight sample without requiring R."""

from dataclasses import dataclass
from datetime import date
from hashlib import sha1, sha256
from io import BytesIO
from pathlib import Path
from struct import calcsize, unpack
import bz2
import math


COMMIT = "b37b235dd702363d5ad87af68dff9533cc148160"
BLOB = "7ae458bb4baa4b32523ac495f6e96431413cb323"
SOURCE = f"https://raw.githubusercontent.com/openintrostat/openintro/{COMMIT}/data/nycflights.rda"
AIRPORTS = ("EWR", "JFK", "LGA")
DAY = 24 * 60
YEAR_START = date(2013, 1, 1)


@dataclass(frozen=True)
class Flight:
    scheduled: int
    actual: int
    row_number: int
    airport: str


class DataFrameReader:
    """Read the RDX2 XDR types present in the pinned data frame."""

    def __init__(self, raw):
        self.stream = BytesIO(bz2.decompress(raw))
        self.symbols = []
        if self.stream.read(7) != b"RDX2\nX\n" or self.value(">i") != 2:
            raise ValueError("expected RDX2 XDR serialization")
        self.stream.read(8)

    def value(self, format_string):
        return unpack(format_string, self.stream.read(calcsize(format_string)))[0]

    def size(self):
        size = self.value(">i")
        if not 0 <= size <= 1_000_000:
            raise ValueError("unexpected R vector size")
        return size

    def object(self):
        flags = self.value(">I")
        kind = flags & 255
        has_attributes = bool(flags & (1 << 9))
        has_tag = bool(flags & (1 << 10))

        if kind == 254:
            return None
        if kind == 255:
            index = (flags >> 8) or self.value(">i")
            return self.symbols[index - 1]
        if kind == 1:
            symbol = self.object()
            self.symbols.append(symbol)
            return symbol
        if kind == 2:
            if has_attributes:
                self.object()
            tag = self.object() if has_tag else None
            return (tag, self.object(), self.object())
        if kind == 9:
            size = self.value(">i")
            return None if size == -1 else self.stream.read(size).decode("utf-8")
        if kind in (13, 14):
            size = self.size()
            code = "i" if kind == 13 else "d"
            element_bytes = calcsize(">" + code)
            result = unpack(f">{size}{code}", self.stream.read(size * element_bytes))
        elif kind in (16, 19):
            result = [self.object() for _ in range(self.size())]
        else:
            raise ValueError(f"unexpected R type {kind}")

        attributes = self.object() if has_attributes else None
        return (result, attributes) if kind == 19 else result

    def columns(self):
        tag, value, tail = self.object()
        if tag != "nycflights" or tail is not None or self.stream.read(1):
            raise ValueError("expected one nycflights data frame")
        values, attributes = value
        while attributes is not None:
            name, names, attributes = attributes
            if name == "names":
                return dict(zip(names, values, strict=True))
        raise ValueError("missing data frame column names")


def clock_minutes(hhmm):
    if hhmm == 2400:
        return 0
    hour, minute = divmod(hhmm, 100)
    if 0 <= hour < 24 and 0 <= minute < 60:
        return hour * 60 + minute
    raise ValueError("invalid departure clock")


def complete_integer(value):
    return math.isfinite(value) and int(value) == value and value != -(1 << 31)


def load_flights(path: Path):
    raw = path.read_bytes()
    if sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest() != BLOB:
        raise ValueError("flight sample does not match the pinned Git blob")
    columns = DataFrameReader(raw).columns()
    fields = ("year", "month", "day", "dep_time", "dep_delay", "hour", "minute", "origin")
    flights = []
    invalid = schedule_checks = schedule_matches = same_clock_matches = 0
    for row_number, values in enumerate(zip(*(columns[key] for key in fields), strict=True)):
        year, month, day, departure, delay, hour, minute, airport = values
        if airport not in AIRPORTS or not all(complete_integer(value) for value in values[:5]):
            invalid += 1
            continue
        try:
            published_date = date(int(year), int(month), int(day))
            observed_clock = clock_minutes(int(departure))
        except ValueError:
            invalid += 1
            continue
        if published_date.year != YEAR_START.year:
            invalid += 1
            continue
        scheduled_clock = (observed_clock - int(delay)) % DAY
        scheduled = (published_date - YEAR_START).days * DAY + scheduled_clock
        if complete_integer(hour) and complete_integer(minute) and 0 <= minute < 60:
            fields_clock = int(hour * 60 + minute) % DAY
            schedule_checks += 1
            schedule_matches += fields_clock == scheduled_clock
            same_clock_matches += fields_clock == observed_clock
        flights.append(Flight(scheduled, scheduled + int(delay), row_number, airport))
    return flights, {
        "url": SOURCE,
        "blob": BLOB,
        "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
        "rows": len(flights) + invalid,
        "retained": len(flights),
        "excluded": invalid,
        "schedule_field_checks": schedule_checks,
        "schedule_field_matches": schedule_matches,
        "actual_field_matches": same_clock_matches,
    }
