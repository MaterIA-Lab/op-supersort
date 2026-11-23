#[allow(dead_code)]
mod frozen {
    include!("../key-correction-spans/bench.rs");

    use std::error::Error;
    use std::fs;

    const DAY_MINUTES: u32 = 1440;
    const REPEATS: usize = 7;
    const ORDER_SEED: u64 = 0x8a78718a4dabe913;
    const PAYLOAD_SEED: u64 = 271;

    #[derive(Clone, Copy)]
    enum ReplayMethod {
        Original(Method),
        DriftSort,
        RegionalEsmLeft,
        RegionalEsmRight,
    }

    const REPLAY_METHODS: [ReplayMethod; 8] = [
        ReplayMethod::Original(Method::DirectSpans),
        ReplayMethod::Original(Method::BulkEsmLeft),
        ReplayMethod::Original(Method::BulkEsmRight),
        ReplayMethod::Original(Method::DeltaSort),
        ReplayMethod::Original(Method::FullSort),
        ReplayMethod::DriftSort,
        ReplayMethod::RegionalEsmLeft,
        ReplayMethod::RegionalEsmRight,
    ];

    impl ReplayMethod {
        fn name(self) -> &'static str {
            match self {
                Self::Original(method) => method.name(),
                Self::DriftSort => "drift_sort",
                Self::RegionalEsmLeft => "regional_esm_left",
                Self::RegionalEsmRight => "regional_esm_right",
            }
        }

        fn run(self, rows: &mut [Row], edits: &[Edit]) -> Option<usize> {
            match self {
                Self::Original(method) => method.run(rows, edits),
                Self::DriftSort => {
                    sort::change_keys(rows, edits);
                    rows.sort_by(sort::compare_rows);
                    None
                }
                Self::RegionalEsmLeft => Some(regional_esm(rows, edits, bulk_esm_left)),
                Self::RegionalEsmRight => Some(regional_esm(rows, edits, bulk_esm_right)),
            }
        }
    }

    fn affected_interval(rows: &[Row], edits: &[Edit]) -> std::ops::Range<usize> {
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
        // Rows strictly outside the interval precede or follow both the old
        // and the new versions of all edited rows, so their ranks stay fixed.
        let begin = rows[..first_position].partition_point(|row| (row.key, row.id) < min_key);
        let end_after_edited = last_position + 1;
        let end = end_after_edited
            + rows[end_after_edited..].partition_point(|row| (row.key, row.id) <= max_key);
        begin..end
    }

    fn regional_esm(
        rows: &mut [Row],
        edits: &[Edit],
        merge: fn(&mut [Row], &[Edit]) -> usize,
    ) -> usize {
        let interval = affected_interval(rows, edits);
        let local_edits: Vec<_> = edits
            .iter()
            .map(|edit| Edit {
                position: edit.position - interval.start,
                key: edit.key,
            })
            .collect();
        merge(&mut rows[interval], &local_edits)
    }

    struct Flight {
        scheduled: u32,
        actual: u32,
        id: u32,
        payload: [u64; 15],
    }

    fn load_input(path: &str) -> Result<Vec<Flight>, Box<dyn Error>> {
        let source = fs::read_to_string(path)?;
        let mut lines = source.lines();
        if lines.next() != Some("id,scheduled,actual") {
            return Err("unexpected replay input header".into());
        }
        let mut random = SplitMix64(PAYLOAD_SEED);
        let mut flights = Vec::new();
        for line in lines {
            let fields: Vec<_> = line.split(',').collect();
            let [id, scheduled, actual] = fields.as_slice() else {
                return Err("invalid flight row".into());
            };
            let id: u32 = id.parse()?;
            if id as usize != flights.len() {
                return Err("expected consecutive source row numbers".into());
            }
            flights.push(Flight {
                scheduled: scheduled.parse()?,
                actual: actual.parse()?,
                id,
                payload: std::array::from_fn(|_| random.next()),
            });
        }
        Ok(flights)
    }

    fn snapshot(flights: &[Flight], boundary: u32) -> Vec<Row> {
        let mut rows: Vec<_> = flights
            .iter()
            .map(|flight| Row {
                key: if flight.actual < boundary {
                    flight.actual
                } else {
                    flight.scheduled
                },
                id: flight.id,
                payload: flight.payload,
            })
            .collect();
        rows.sort_by(|a, b| a.key.cmp(&b.key).then(a.id.cmp(&b.id)));
        rows
    }

    fn positions(rows: &[Row]) -> Vec<usize> {
        let mut positions = vec![0; rows.len()];
        for (position, row) in rows.iter().enumerate() {
            positions[row.id as usize] = position;
        }
        positions
    }

    fn benchmark_day(
        output: &mut impl Write,
        geometry: &mut impl Write,
        flights: &[Flight],
        day: &str,
        start_minute: u32,
    ) -> Result<(), Box<dyn Error>> {
        let end_minute = start_minute + DAY_MINUTES;
        let original = snapshot(flights, start_minute);
        let expected = snapshot(flights, end_minute);
        let sources = positions(&original);
        let destinations = positions(&expected);
        let mut arrivals: Vec<_> = flights
            .iter()
            .filter(|flight| {
                (start_minute..end_minute).contains(&flight.actual)
                    && flight.actual != flight.scheduled
            })
            .collect();
        arrivals.sort_unstable_by_key(|flight| (flight.actual, flight.id));
        let edits: Vec<_> = arrivals
            .iter()
            .map(|flight| Edit {
                position: sources[flight.id as usize],
                key: flight.actual,
            })
            .collect();
        if edits.is_empty() {
            return Err(format!("no corrections for {day}").into());
        }
        let mut edited = vec![false; original.len()];
        let mut distances = Vec::with_capacity(edits.len());
        for edit in &edits {
            edited[edit.position] = true;
            let id = original[edit.position].id as usize;
            distances.push(edit.position.abs_diff(destinations[id]));
        }
        distances.sort_unstable();
        let p50 = distances[distances.len().div_ceil(2) - 1];
        let p95 = distances[(95 * distances.len()).div_ceil(100) - 1];
        let maximum = distances[distances.len() - 1];
        let minimum_writes = original
            .iter()
            .enumerate()
            .filter(|&(from, row)| !edited[from] && from != destinations[row.id as usize])
            .count();
        let rows_in_interval = affected_interval(&original, &edits).len();
        writeln!(
            geometry,
            "{day},{},{},{rows_in_interval},{p50},{p95},{maximum},{minimum_writes}",
            original.len(),
            edits.len()
        )?;

        let mut working = original.clone();
        let mut random = SplitMix64(ORDER_SEED ^ u64::from(start_minute));
        for round in 0..=REPEATS {
            let mut cache_order = [false, true];
            random.shuffle(&mut cache_order);
            for cold in cache_order {
                let cache = if cold { "cold" } else { "resident" };
                let mut order = REPLAY_METHODS;
                random.shuffle(&mut order);
                for method in order {
                    working.copy_from_slice(&original);
                    if cold {
                        flush(&working);
                    }
                    let start = Instant::now();
                    let moved = black_box(method.run(black_box(&mut working), black_box(&edits)));
                    let elapsed = start.elapsed().as_nanos();
                    let valid_writes = match (method, moved) {
                        (ReplayMethod::Original(Method::DirectSpans), count) => {
                            count == Some(minimum_writes)
                        }
                        (_, Some(count)) => count >= minimum_writes,
                        (_, None) => true,
                    };
                    if working != expected || !valid_writes {
                        return Err(
                            format!("{day} {cache} {round}: {} failed", method.name()).into()
                        );
                    }
                    let moved = moved.map(|count| count.to_string()).unwrap_or_default();
                    writeln!(
                        output,
                        "{day},{cache},{round},{},{elapsed},{moved},true",
                        method.name()
                    )?;
                }
            }
        }
        Ok(())
    }

    pub fn replay() -> Result<(), Box<dyn Error>> {
        let args: Vec<_> = env::args().skip(1).collect();
        let [input, geometry_path, cpu, days @ ..] = args.as_slice() else {
            return Err("usage: bench INPUT.csv GEOMETRY.csv CPU DATE:MINUTE...".into());
        };
        let cpu: usize = cpu.parse()?;
        if days.is_empty() || cpu >= 1024 {
            return Err("invalid replay argument".into());
        }
        pin(cpu)?;
        let flights = load_input(input)?;
        let mut output = io::BufWriter::new(io::stdout().lock());
        let mut geometry = io::BufWriter::new(fs::File::create(geometry_path)?);
        writeln!(
            output,
            "day,cache,round,method,total_ns,unchanged_rows_written,verified"
        )?;
        writeln!(
            geometry,
            "day,rows,edits,interval_rows,rank_p50,rank_p95,rank_max,minimum_unchanged_writes"
        )?;
        for specification in days {
            let (day, minute) = specification
                .split_once(':')
                .ok_or("expected DATE:MINUTE")?;
            benchmark_day(&mut output, &mut geometry, &flights, day, minute.parse()?)?;
        }
        geometry.flush()?;
        output.flush()?;
        Ok(())
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    frozen::replay()
}
