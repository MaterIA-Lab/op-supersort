# Direct-span comparison with cache-buffered merges

The benchmark applies sparse key corrections to 128-byte records in a
contiguous sorted array. It reuses the original apply-and-sort implementation
and verifies its blob hash. The registered synthetic workload varies array
size and rank displacement. The flight workload reconciles reported elapsed
minutes and measures both supplied positions and lookup by record ID.
[Protocol, results and samples](../../../runs/2026-11-24-key-correction-decision/README.md)

The buffered control saves the replacements and sorts their keys separately.
It reads original blocks into a contiguous scratch queue, omits deleted
rows and merges surviving ranges and replacements into the original array.
Before the write cursor could overwrite an unread input, it refills that
queue. At that point any pending survivors are bounded by the number of
replacements. The queue capacity is therefore the tile size plus one row
per correction. Tests cover empty edits, duplicates, full replacements and
input sizes at tile boundaries.

## Reproduce

Use x86-64 Rust 1.96.0, Python 3.11 or newer, and an available logical CPU.
Fetch the [unchanged DeltaSort library at the pinned revision](https://github.com/shudv/deltasort/blob/89322c7bfb8d5b28b179650d08249398cbe0a977/src/lib.rs)
into `lab/deltasort/lib.rs` with LF line endings. Download the [BTS January
2024 reporting-carrier archive](https://www.transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_1.zip)
to `lab/bts-january.zip`. Keep the extracted flight observations local.
Use a new work directory for each independent reproduction.

```powershell
$work = 'lab/direct-span-comparison'
python -X utf8 prototypes/agents/key-correction-decision/prepare_flights.py january lab/bts-january.zip $work
python -X utf8 prototypes/agents/key-correction-decision/run.py synthetic $work lab/deltasort/lib.rs --cpu 8
python -X utf8 prototypes/agents/key-correction-decision/run.py january $work lab/deltasort/lib.rs --cpu 8
python -X utf8 runs/2026-11-24-key-correction-decision/analyze.py synthetic $work
python -X utf8 runs/2026-11-24-key-correction-decision/analyze.py january $work
```

The analysis script also accepts the published timing archives. Omit the
work directory to read them from the run folder. The phase probe is generated
from the frozen source. Its samples include extra timestamps and are
excluded from choosing the fastest method.
