#[allow(dead_code)]
mod registered {
    include!("../key-correction-spans/bench.rs");

    use std::arch::x86_64::{_mm_prefetch, _MM_HINT_T0};
    use std::error::Error;
    use std::fs::File;
    use std::io::{BufRead, BufReader};
    use std::ops::Range;

    const WARMUPS: usize = 3;
    const MEASURED: usize = 11;

    #[derive(Clone, Copy)]
    enum RatingMethod {
        Unchanged(Method),
        DriftSort,
        RegionalEsmLeft,
        RegionalEsmRight,
        Counting,
    }

    const RATING_METHODS: [RatingMethod; 9] = [
        RatingMethod::Unchanged(Method::DirectSpans),
        RatingMethod::Unchanged(Method::BulkEsmLeft),
        RatingMethod::Unchanged(Method::BulkEsmRight),
        RatingMethod::Unchanged(Method::DeltaSort),
        RatingMethod::Unchanged(Method::FullSort),
        RatingMethod::DriftSort,
        RatingMethod::RegionalEsmLeft,
        RatingMethod::RegionalEsmRight,
        RatingMethod::Counting,
    ];

    impl RatingMethod {
        fn name(self) -> &'static str {
            match self {
                Self::Unchanged(method) => method.name(),
                Self::DriftSort => "drift_sort",
                Self::RegionalEsmLeft => "regional_esm_left",
                Self::RegionalEsmRight => "regional_esm_right",
                Self::Counting => "counting_gather",
            }
        }

        fn run(self, rows: &mut [Row], edits: &[Edit]) -> Option<usize> {
            match self {
                Self::Unchanged(method) => method.run(rows, edits),
                Self::DriftSort => {
                    sort::change_keys(rows, edits);
                    rows.sort_by(sort::compare_rows);
                    None
                }
                Self::RegionalEsmLeft => Some(regional_esm(rows, edits, bulk_esm_left)),
                Self::RegionalEsmRight => Some(regional_esm(rows, edits, bulk_esm_right)),
                Self::Counting => {
                    counting_gather(rows, edits);
                    None
                }
            }
        }
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
            let key = (edit.key, rows[edit.position].id);
            min_key = min_key.min(key);
            max_key = max_key.max(key);
        }
        let begin = rows[..first_position].partition_point(|row| (row.key, row.id) < min_key);
        let after_edited = last_position + 1;
        let end =
            after_edited + rows[after_edited..].partition_point(|row| (row.key, row.id) <= max_key);
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

    // Ratings must fit u16 and IDs must be dense, both checked at fixture ingestion.
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
        for (key, source) in by_id {
            let next = &mut buckets[key as usize];
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

    struct RatingFixture {
        initial: Vec<Row>,
        expected: Vec<Row>,
        edits: Vec<Edit>,
        minimum_writes: usize,
    }

    fn load_fixture(path: &str) -> Result<RatingFixture, Box<dyn Error>> {
        let mut lines = BufReader::new(File::open(path)?).lines();
        if lines.next().ok_or("missing fixture header")?? != "id,before,after" {
            return Err("expected id,before,after header".into());
        }
        let mut random = SplitMix64(271);
        let mut initial = Vec::new();
        let mut expected = Vec::new();
        let mut changes = Vec::new();
        for (index, line) in lines.enumerate() {
            let line = line?;
            let mut columns = line.split(',');
            let id: u32 = columns.next().ok_or("missing id")?.parse()?;
            let before: u16 = columns.next().ok_or("missing before rating")?.parse()?;
            let after: u16 = columns.next().ok_or("missing after rating")?.parse()?;
            if index != id as usize || columns.next().is_some() {
                return Err("expected dense ids and exactly two ratings per row".into());
            }
            let row = Row {
                id,
                key: before.into(),
                payload: std::array::from_fn(|_| random.next()),
            };
            initial.push(row);
            expected.push(Row {
                key: after.into(),
                ..row
            });
            if before != after {
                changes.push((index, after.into()));
            }
        }
        if initial.len() < 100_000 || changes.is_empty() {
            return Err("fixture did not pass the size and edit requirements".into());
        }
        initial.sort_by_key(|row| (row.key, row.id));
        expected.sort_by_key(|row| (row.key, row.id));
        let mut sources = vec![0; initial.len()];
        let mut destinations = vec![0; expected.len()];
        for (position, (&source, &target)) in initial.iter().zip(&expected).enumerate() {
            sources[source.id as usize] = position;
            destinations[target.id as usize] = position;
        }
        let edits: Vec<_> = changes
            .into_iter()
            .map(|(id, key)| Edit {
                position: sources[id],
                key,
            })
            .collect();
        let mut edited = vec![false; initial.len()];
        for edit in &edits {
            edited[edit.position] = true;
        }
        let minimum_writes = initial
            .iter()
            .enumerate()
            .filter(|&(position, row)| {
                !edited[position] && destinations[row.id as usize] != position
            })
            .count();
        Ok(RatingFixture {
            initial,
            expected,
            edits,
            minimum_writes,
        })
    }

    pub fn benchmark() -> Result<(), Box<dyn Error>> {
        let args: Vec<_> = env::args().skip(1).collect();
        let [path, minimum_writes, cpu] = args.as_slice() else {
            return Err("usage: bench FIXTURE.csv MINIMUM_UNCHANGED_WRITES CPU".into());
        };
        let cpu: usize = cpu.parse()?;
        if cpu >= 1024 {
            return Err("invalid logical CPU".into());
        }
        pin(cpu)?;
        let fixture = load_fixture(path)?;
        if fixture.minimum_writes != minimum_writes.parse()? {
            return Err("fixture differs from the independent write-count oracle".into());
        }
        let interval_rows = affected_interval(&fixture.initial, &fixture.edits).len();
        let mut working = fixture.initial.clone();
        let mut random = SplitMix64(0x8a78718a4dabe913);
        let mut output = io::BufWriter::new(io::stdout().lock());
        writeln!(
            output,
            "rows,edits,interval_rows,cache,round,method,total_ns,unchanged_rows_written,verified"
        )?;
        for round in 0..(WARMUPS + MEASURED) {
            let mut cache_order = [false, true];
            random.shuffle(&mut cache_order);
            for cold in cache_order {
                let cache = if cold { "flushed" } else { "copy_reset" };
                let mut order = RATING_METHODS;
                random.shuffle(&mut order);
                for method in order {
                    working.copy_from_slice(&fixture.initial);
                    if cold {
                        flush(&working);
                    }
                    let start = Instant::now();
                    let moved =
                        black_box(method.run(black_box(&mut working), black_box(&fixture.edits)));
                    let elapsed = start.elapsed().as_nanos();
                    let is_candidate =
                        matches!(method, RatingMethod::Unchanged(Method::DirectSpans));
                    let valid_writes = if is_candidate {
                        moved == Some(fixture.minimum_writes)
                    } else {
                        moved.is_none_or(|count| count >= fixture.minimum_writes)
                    };
                    if working != fixture.expected || !valid_writes {
                        return Err(format!("{cache} {round}: {} failed", method.name()).into());
                    }
                    let moved = moved.map(|count| count.to_string()).unwrap_or_default();
                    writeln!(
                        output,
                        "{},{},{interval_rows},{cache},{round},{},{elapsed},{moved},true",
                        working.len(),
                        fixture.edits.len(),
                        method.name()
                    )?;
                }
            }
        }
        output.flush()?;
        Ok(())
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    registered::benchmark()
}
