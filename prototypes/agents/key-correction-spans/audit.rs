#[allow(dead_code)]
mod registered {
    include!("bench.rs");

    #[derive(Clone, Copy)]
    enum AuditMethod {
        Registered(Method),
        DriftSort,
    }

    impl AuditMethod {
        fn name(self) -> &'static str {
            match self {
                Self::Registered(method) => method.name(),
                Self::DriftSort => "drift_sort",
            }
        }

        fn run(self, rows: &mut [Row], edits: &[Edit]) -> Option<usize> {
            match self {
                Self::Registered(method) => method.run(rows, edits),
                Self::DriftSort => {
                    sort::change_keys(rows, edits);
                    rows.sort_by(sort::compare_rows);
                    None
                }
            }
        }
    }

    pub fn run_with_driftsort() -> Result<(), Box<dyn std::error::Error>> {
        let args: Vec<_> = env::args().skip(1).collect();
        let [size, count, seed, repeats, cpu] = args.as_slice() else {
            return Err("usage: audit ROWS EDITS SEED REPEATS CPU".into());
        };
        let (size, count, seed, repeats, cpu) = (
            size.parse()?,
            count.parse()?,
            seed.parse()?,
            repeats.parse()?,
            cpu.parse()?,
        );
        if size == 0 || size > u32::MAX as usize || count > size || repeats == 0 || cpu >= 1024 {
            return Err("invalid benchmark argument".into());
        }
        pin(cpu)?;

        let (original, edits) = fixture(size, count, seed, false);
        let expected = expected_rows(&original, &edits);
        let mut working = original.clone();
        let mut random = SplitMix64(seed ^ 0xbd7782dcf475078f);
        let mut order = [
            AuditMethod::Registered(Method::DirectSpans),
            AuditMethod::Registered(Method::BulkEsmLeft),
            AuditMethod::Registered(Method::BulkEsmRight),
            AuditMethod::Registered(Method::DeltaSort),
            AuditMethod::Registered(Method::FullSort),
            AuditMethod::DriftSort,
        ];
        let mut output = io::BufWriter::new(io::stdout().lock());
        writeln!(
            output,
            "rows,edits,distribution,seed,round,method,total_ns,unchanged_rows_written,verified"
        )?;
        for round in 0..=repeats {
            random.shuffle(&mut order);
            for method in order {
                working.copy_from_slice(&original);
                flush(&working);
                let start = Instant::now();
                let moved = black_box(method.run(black_box(&mut working), black_box(&edits)));
                let elapsed = start.elapsed().as_nanos();
                if working != expected {
                    return Err(format!("{} output mismatch", method.name()).into());
                }
                let moved = moved.map(|n| n.to_string()).unwrap_or_default();
                writeln!(
                    output,
                    "{size},{count},uniform,{seed},{round},{},{elapsed},{moved},true",
                    method.name()
                )?;
            }
        }
        output.flush()?;
        Ok(())
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    registered::run_with_driftsort()
}
