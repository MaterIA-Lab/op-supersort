# Lichess Blitz rating refresh benchmark

Replay the latest reported pre-game Blitz rating of each account in a fixed
roster. Compare nine implementations of the same in-place refresh.
[Protocol and measurements](../../../runs/2026-11-23-lichess-rating-replay/README.md)

## Reproduce

Use Python 3.14 or newer for its standard-library Zstandard reader and
Rust 1.96.0 on an x86-64 machine. The recorded build uses `znver3`.
Download the [January 2015 Lichess standard games archive](https://database.lichess.org/standard/lichess_db_standard_rated_2015-01.pgn.zst)
and the [pinned DeltaSort library](https://github.com/shudv/deltasort/blob/89322c7bfb8d5b28b179650d08249398cbe0a977/src/lib.rs).
Keep the archive and generated fixtures local. The extraction uses account
handles to construct dense numeric IDs. Use LF line endings for the Rust
sources so the Git blob hashes match.

```powershell
python -X utf8 prototypes/agents/lichess-rating-replay/prepare.py lab/lichess_db_standard_rated_2015-01.pgn.zst lab/lichess-replay
python -X utf8 prototypes/agents/lichess-rating-replay/run.py lab/lichess-replay lab/deltasort/lib.rs --cpu 8
python -X utf8 runs/2026-11-23-lichess-rating-replay/analyze.py lab/lichess-replay
```

Use an available logical CPU. Omit the directory from the last command
to analyze the published samples. The Rust harness is shared with the
[FIDE benchmark](../fide-rating-updates/README.md).
