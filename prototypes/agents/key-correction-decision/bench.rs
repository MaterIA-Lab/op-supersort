#[allow(dead_code)]
mod registered {
    include!("../key-correction-spans/bench.rs");

    use std::arch::x86_64::{_mm_prefetch, _MM_HINT_T0};
    use std::error::Error;
    use std::fs;
    use std::ops::Range;

    mod buffered {
        include!("buffered.rs");
    }

    mod phase {
        include!(env!("SUPERSORT_PHASE_RS"));
    }

    const WARMUPS: usize = 2;
    const ROUNDS: usize = 5;

    fn key(row: &Row) -> u64 {
        (u64::from(row.key) << 32) | u64::from(row.id)
    }

    fn affected_interval(rows: &[Row], edits: &[Edit]) -> Range<usize> {
        let Some(first) = edits.first() else {
            return 0..0;
        };
        let mut first_position = first.position;
        let mut last_position = first.position;
        let mut min_key = (first.key, rows[first.position].id);
        let mut max_key = min_key;
        for edit in &edits[1..] {
            first_position = first_position.min(edit.position);
            last_position = last_position.max(edit.position);
            let order = (edit.key, rows[edit.position].id);
            min_key = min_key.min(order);
            max_key = max_key.max(order);
        }
        let begin = rows[..first_position].partition_point(|row| (row.key, row.id) < min_key);
        let after = last_position + 1;
        let end = after + rows[after..].partition_point(|row| (row.key, row.id) <= max_key);
        begin..end
    }

    fn regional_esm(
        rows: &mut [Row],
        edits: &[Edit],
        merge: fn(&mut [Row], &[Edit]) -> usize,
    ) -> usize {
        let interval = affected_interval(rows, edits);
        let local: Vec<_> = edits
            .iter()
            .map(|edit| Edit {
                position: edit.position - interval.start,
                key: edit.key,
            })
            .collect();
        merge(&mut rows[interval], &local)
    }

    // This is the FIDE counting and gather control with a 16-bit key domain.
    fn counting_gather(rows: &mut [Row], edits: &[Edit]) {
        sort::change_keys(rows, edits);
        let mut buckets = vec![0_usize; 1 << 16];
        let mut by_id = vec![(0_u32, 0_u32); rows.len()];
        for (source, row) in rows.iter().enumerate() {
            buckets[row.key as usize] += 1;
            by_id[row.id as usize] = (row.key, source as u32);
        }
        let mut offset = 0;
        for next in &mut buckets {
            let count = *next;
            *next = offset;
            offset += count;
        }
        let mut sources = vec![0_u32; rows.len()];
        for (rating, source) in by_id {
            let next = &mut buckets[rating as usize];
            sources[*next] = source;
            *next += 1;
        }
        let mut ordered = Vec::with_capacity(rows.len());
        for (index, &source) in sources.iter().enumerate() {
            if let Some(&ahead) = sources.get(index + 32) {
                let address = (&rows[ahead as usize] as *const Row).cast::<i8>();
                // Each aligned 128-byte record covers two valid cache lines.
                unsafe {
                    _mm_prefetch(address, _MM_HINT_T0);
                    _mm_prefetch(address.add(64), _MM_HINT_T0);
                }
            }
            ordered.push(rows[source as usize]);
        }
        rows.copy_from_slice(&ordered);
    }

    #[derive(Clone, Copy)]
    enum Comparison {
        Prior(Method),
        Drift,
        RegionalLeft,
        RegionalRight,
        Buffered(usize),
        Counting,
        Phases,
    }

    const COMPARISONS: [Comparison; 11] = [
        Comparison::Prior(Method::DirectSpans),
        Comparison::Prior(Method::BulkEsmLeft),
        Comparison::Prior(Method::BulkEsmRight),
        Comparison::Prior(Method::DeltaSort),
        Comparison::Prior(Method::FullSort),
        Comparison::Drift,
        Comparison::RegionalLeft,
        Comparison::RegionalRight,
        Comparison::Buffered(256),
        Comparison::Buffered(1024),
        Comparison::Phases,
    ];

    impl Comparison {
        fn name(self) -> &'static str {
            match self {
                Self::Prior(method) => method.name(),
                Self::Drift => "drift_sort",
                Self::RegionalLeft => "regional_esm_left",
                Self::RegionalRight => "regional_esm_right",
                Self::Buffered(256) => "buffered_esm_32k",
                Self::Buffered(1024) => "buffered_esm_128k",
                Self::Buffered(_) => unreachable!(),
                Self::Counting => "counting_gather",
                Self::Phases => "direct_spans_phases",
            }
        }

        fn run(self, rows: &mut [Row], edits: &[Edit]) -> Sample {
            let mut result = Sample::default();
            result.writes = match self {
                Self::Prior(method) => method.run(rows, edits),
                Self::Drift => {
                    sort::change_keys(rows, edits);
                    rows.sort_by(sort::compare_rows);
                    None
                }
                Self::RegionalLeft => Some(regional_esm(rows, edits, bulk_esm_left)),
                Self::RegionalRight => Some(regional_esm(rows, edits, bulk_esm_right)),
                Self::Buffered(tile) => Some(buffered::merge(rows, edits, tile)),
                Self::Counting => {
                    counting_gather(rows, edits);
                    None
                }
                Self::Phases => {
                    let (writes, plan, execute) = phase::direct_spans_phases(rows, edits);
                    result.phases = Some((plan, execute));
                    Some(writes)
                }
            };
            result
        }
    }

    #[derive(Default)]
    struct Sample {
        writes: Option<usize>,
        phases: Option<(u128, u128)>,
    }

    #[derive(Clone, Copy)]
    struct IdEdit {
        id: u32,
        key: u32,
    }

    #[derive(Clone, Copy)]
    enum Input {
        Positions,
        Ids,
    }

    impl Input {
        fn name(self) -> &'static str {
            match self {
                Self::Positions => "positions",
                Self::Ids => "id",
            }
        }
    }

    fn locate(rows: &[Row], old_keys: &[u32], edits: &[IdEdit]) -> Vec<Edit> {
        edits
            .iter()
            .map(|edit| {
                let order = (u64::from(old_keys[edit.id as usize]) << 32) | u64::from(edit.id);
                let index = rows.partition_point(|row| key(row) < order);
                assert_eq!(key(&rows[index]), order, "replica state has a stale old key");
                Edit {
                    position: index,
                    key: edit.key,
                }
            })
            .collect()
    }

    struct Fixture {
        initial: Vec<Row>,
        expected: Vec<Row>,
        edits: Vec<Edit>,
        id_edits: Vec<IdEdit>,
        initial_keys: Vec<u32>,
        expected_keys: Vec<u32>,
        real: bool,
    }

    fn synthetic(size: usize, count: usize, distance: &str, seed: u64) -> Fixture {
        let (initial, mut edits) = fixture(size, count, seed, false);
        let bounds = match distance {
            "random" => None,
            "short" => Some((1, 256)),
            "medium" => Some((4096, 8192)),
            _ => unreachable!(),
        };
        if let Some((minimum, maximum)) = bounds {
            let mut rng = SplitMix64(seed ^ 0xb20106c26777fef3);
            for edit in &mut edits {
                let offset = minimum + rng.below(maximum - minimum + 1);
                let neighbor = if rng.below(2) == 0 {
                    edit.position.saturating_sub(offset)
                } else {
                    (edit.position + offset).min(size - 1)
                };
                edit.key = initial[neighbor].key;
            }
        }
        Fixture {
            expected: expected_rows(&initial, &edits),
            initial,
            edits,
            id_edits: Vec::new(),
            initial_keys: Vec::new(),
            expected_keys: Vec::new(),
            real: false,
        }
    }

    fn flights(path: &str, start: u32, width: u32) -> Result<Fixture, Box<dyn Error>> {
        let input = fs::read(path)?;
        if input.is_empty() || input.len() % 8 != 0 || input.len() / 8 > u32::MAX as usize {
            return Err("invalid flight observations file".into());
        }
        let size = input.len() / 8;
        let end = start.checked_add(width).ok_or("invalid window")?;
        let mut initial = Vec::with_capacity(size);
        let mut expected = Vec::with_capacity(size);
        let mut initial_keys = Vec::with_capacity(size);
        let mut expected_keys = Vec::with_capacity(size);
        let mut id_edits = Vec::new();
        let mut rng = SplitMix64(247021);
        for (index, record) in input.chunks_exact(8).enumerate() {
            let when = u32::from_le_bytes(record[0..4].try_into()?);
            let scheduled = u16::from_le_bytes(record[4..6].try_into()?) as u32;
            let actual = u16::from_le_bytes(record[6..8].try_into()?) as u32;
            let old = if when < start { actual } else { scheduled };
            let new = if when < end { actual } else { scheduled };
            let id = index as u32;
            initial_keys.push(old);
            expected_keys.push(new);
            let row = Row {
                key: old,
                id,
                payload: std::array::from_fn(|_| rng.next()),
            };
            initial.push(row);
            expected.push(Row { key: new, ..row });
            if old != new {
                id_edits.push(IdEdit { id, key: new });
            }
        }
        initial.sort_by_key(key);
        expected.sort_by(sort::compare_rows);
        let mut positions = vec![0; size];
        for (position, row) in initial.iter().enumerate() {
            positions[row.id as usize] = position;
        }
        let edits = id_edits
            .iter()
            .map(|edit| Edit {
                position: positions[edit.id as usize],
                key: edit.key,
            })
            .collect();
        Ok(Fixture {
            initial,
            expected,
            edits,
            id_edits,
            initial_keys,
            expected_keys,
            real: true,
        })
    }

    struct Geometry {
        minimum_writes: usize,
        interval: usize,
        p50: f64,
        p95: usize,
        maximum: usize,
    }

    fn geometry(f: &Fixture) -> Geometry {
        let mut destinations = vec![0; f.initial.len()];
        let mut is_edited = vec![false; f.initial.len()];
        for (position, row) in f.expected.iter().enumerate() {
            destinations[row.id as usize] = position;
        }
        let mut distances = Vec::with_capacity(f.edits.len());
        for edit in &f.edits {
            is_edited[edit.position] = true;
            let final_rank = destinations[f.initial[edit.position].id as usize];
            distances.push(edit.position.abs_diff(final_rank));
        }
        distances.sort_unstable();
        let count = distances.len();
        let (p50, p95, maximum) = if count > 0 {
            (
                (distances[(count - 1) / 2] as f64 + distances[count / 2] as f64) / 2.0,
                distances[(95 * count - 1) / 100],
                distances[count - 1],
            )
        } else {
            (0.0, 0, 0)
        };
        Geometry {
            minimum_writes: f
                .initial
                .iter()
                .enumerate()
                .filter(|&(position, row)| {
                    !is_edited[position] && destinations[row.id as usize] != position
                })
                .count(),
            interval: affected_interval(&f.initial, &f.edits).len(),
            p50,
            p95,
            maximum,
        }
    }

    fn check_controls(original: &[Row], edits: &[Edit]) {
        let expected = expected_rows(original, edits);
        let mut working = original.to_vec();
        for size in [1, 2, 4, 256, 1024] {
            buffered::merge(&mut working, edits, size);
            assert_eq!(working, expected, "buffered control mismatch at {size} rows");
            working.copy_from_slice(original);
        }
        let (moves, _, _) = phase::direct_spans_phases(&mut working, edits);
        assert_eq!(working, expected);
        working.copy_from_slice(original);
        assert_eq!(direct_spans(&mut working, edits), moves);
    }

    fn verify_new_controls() {
        verify();
        let mut checks = 0;
        let mut rng = SplitMix64(613);
        for size in 0..=5 {
            let mut rows: Vec<_> = (0..size)
                .map(|id| Row {
                    key: (id % 2) as u32,
                    id: id as u32,
                    payload: [id as u64; 15],
                })
                .collect();
            rows.sort_by_key(key);
            for assignment in 0..4_usize.pow(size as u32) {
                let mut edits: Vec<_> = (0..size)
                    .filter_map(|position| {
                        let replacement = (assignment >> (position * 2)) & 3;
                        (replacement != 0).then(|| Edit {
                            position,
                            key: [0, 0, 1, u32::MAX][replacement],
                        })
                    })
                    .collect();
                rng.shuffle(&mut edits);
                check_controls(&rows, &edits);
                checks += 1;
            }
        }
        for size in [7, 63, 255, 256, 257, 1023, 1024, 1025, 2049] {
            for edit_count in [0, 1, size / 3, size - 1, size] {
                for local in [false, true] {
                    let (rows, edits) = fixture(size, edit_count, rng.next(), local);
                    check_controls(&rows, &edits);
                    checks += 1;
                }
            }
        }
        println!("Verified {checks} additional fixtures with five buffer sizes and the phase probe");
    }

    fn run_fixture(f: Fixture, seed: u64, cpu: usize) -> Result<(), Box<dyn Error>> {
        pin(cpu)?;
        let geometry = geometry(&f);
        let mut methods = COMPARISONS.to_vec();
        let mut inputs = vec![Input::Positions];
        if f.real {
            methods.push(Comparison::Counting);
            inputs.push(Input::Ids);
        }
        let mut working = f.initial.clone();
        let mut state = f.initial_keys.clone();
        let mut rng = SplitMix64(seed ^ 0x3657e8297a9d0e01);
        let mut output = io::BufWriter::new(io::stdout().lock());
        writeln!(
            output,
            "rows,edits,p50,p95,maximum,interval,minimum_writes,mode,cache,round,method,total_ns,writes,plan_ns,execute_ns,verified"
        )?;
        for round in 0..WARMUPS + ROUNDS {
            rng.shuffle(&mut inputs);
            for &input in &inputs {
                let mut cold_first = [false, true];
                rng.shuffle(&mut cold_first);
                for cold in cold_first {
                    let cache = if cold { "flushed" } else { "copy_reset" };
                    rng.shuffle(&mut methods);
                    for &method in &methods {
                        working.copy_from_slice(&f.initial);
                        state.copy_from_slice(&f.initial_keys);
                        if cold {
                            flush(&working);
                        }
                        let start = Instant::now();
                        let result = match input {
                            Input::Positions => {
                                method.run(black_box(&mut working), black_box(&f.edits))
                            }
                            Input::Ids => {
                                let edits = locate(&working, &state, black_box(&f.id_edits));
                                method.run(black_box(&mut working), black_box(&edits))
                            }
                        };
                        for edit in black_box(&f.id_edits) {
                            state[edit.id as usize] = edit.key;
                        }
                        let elapsed = start.elapsed().as_nanos();
                        let exact_writes = matches!(
                            method,
                            Comparison::Prior(Method::DirectSpans) | Comparison::Phases
                        );
                        if working != f.expected
                            || state != f.expected_keys
                            || (exact_writes && result.writes != Some(geometry.minimum_writes))
                            || result.writes.is_some_and(|n| n < geometry.minimum_writes)
                        {
                            return Err(format!("{} failed exact checks", method.name()).into());
                        }
                        let moves = result.writes.map(|n| n.to_string()).unwrap_or_default();
                        let (plan, execute) = result
                            .phases
                            .map(|(a, b)| (a.to_string(), b.to_string()))
                            .unwrap_or_default();
                        writeln!(
                            output,
                            "{},{},{},{},{},{},{},{},{cache},{round},{},{elapsed},{moves},{plan},{execute},true",
                            f.initial.len(), f.edits.len(), geometry.p50, geometry.p95,
                            geometry.maximum, geometry.interval, geometry.minimum_writes,
                            input.name(), method.name()
                        )?;
                    }
                }
            }
        }
        output.flush()?;
        Ok(())
    }

    pub fn decision() -> Result<(), Box<dyn Error>> {
        let args: Vec<_> = env::args().skip(1).collect();
        match args.as_slice() {
            [verify] if verify == "--verify" => verify_new_controls(),
            [shape, rows, distance, seed, cpu] if shape == "synthetic" => {
                let rows: usize = rows.parse()?;
                if ![32768, 262144, 1048576].contains(&rows)
                    || !matches!(distance.as_str(), "short" | "medium" | "random")
                {
                    return Err("unregistered synthetic size or displacement".into());
                }
                let seed = seed.parse()?;
                run_fixture(synthetic(rows, rows / 1024, distance, seed), seed, cpu.parse()?)?;
            }
            [real, path, start, width, cpu] if real == "flights" => {
                let start = start.parse()?;
                let width = width.parse()?;
                let fixture = flights(path, start, width)?;
                run_fixture(fixture, u64::from(start) * 67 + u64::from(width), cpu.parse()?)?;
            }
            _ => return Err("usage: bench --verify | synthetic ROWS DISTANCE SEED CPU | flights OBSERVATIONS START WIDTH CPU".into()),
        }
        Ok(())
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    registered::decision()
}
