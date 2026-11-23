mod sort;

use std::arch::x86_64::{_mm_clflush, _mm_mfence};
use std::env;
use std::hint::black_box;
use std::io::{self, Write};
use std::time::Instant;

use sort::{bulk_esm_left, bulk_esm_right, delta_sort, direct_spans, full_sort, Edit, Row};

#[derive(Clone, Copy, Debug)]
enum Method {
    DirectSpans,
    BulkEsmLeft,
    BulkEsmRight,
    DeltaSort,
    FullSort,
}

const METHODS: [Method; 5] = [
    Method::DirectSpans,
    Method::BulkEsmLeft,
    Method::BulkEsmRight,
    Method::DeltaSort,
    Method::FullSort,
];

impl Method {
    fn name(self) -> &'static str {
        match self {
            Self::DirectSpans => "direct_spans",
            Self::BulkEsmLeft => "bulk_esm_left",
            Self::BulkEsmRight => "bulk_esm_right",
            Self::DeltaSort => "delta_sort",
            Self::FullSort => "full_sort",
        }
    }

    fn run(self, rows: &mut [Row], edits: &[Edit]) -> Option<usize> {
        match self {
            Self::DirectSpans => Some(direct_spans(rows, edits)),
            Self::BulkEsmLeft => Some(bulk_esm_left(rows, edits)),
            Self::BulkEsmRight => Some(bulk_esm_right(rows, edits)),
            Self::DeltaSort => {
                delta_sort(rows, edits);
                None
            }
            Self::FullSort => {
                full_sort(rows, edits);
                None
            }
        }
    }
}

struct SplitMix64(u64);

impl SplitMix64 {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e3779b97f4a7c15);
        let mut value = self.0;
        value = (value ^ (value >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        value = (value ^ (value >> 27)).wrapping_mul(0x94d049bb133111eb);
        value ^ (value >> 31)
    }

    fn below(&mut self, limit: usize) -> usize {
        let bound = limit as u64;
        let threshold = bound.wrapping_neg() % bound;
        loop {
            let product = u128::from(self.next()) * u128::from(bound);
            if (product as u64) >= threshold {
                return (product >> 64) as usize;
            }
        }
    }

    fn shuffle<T>(&mut self, items: &mut [T]) {
        for i in (1..items.len()).rev() {
            items.swap(i, self.below(i + 1));
        }
    }
}

fn fixture(size: usize, edit_count: usize, seed: u64, local: bool) -> (Vec<Row>, Vec<Edit>) {
    let mut random = SplitMix64(seed);
    let mut original: Vec<_> = (0..size)
        .map(|id| Row {
            key: random.next() as u32,
            id: id as u32,
            payload: std::array::from_fn(|_| random.next()),
        })
        .collect();
    original.sort_unstable_by_key(|row| (row.key, row.id));

    // A partial Fisher-Yates draw selects distinct positions without sorting them.
    let mut indices: Vec<_> = (0..size).collect();
    let mut edits = Vec::with_capacity(edit_count);
    for edit in 0..edit_count {
        let next = edit + random.below(size - edit);
        indices.swap(edit, next);
        let position = indices[edit];
        let key = if local {
            let offset = random.below(513) as isize - 256;
            let neighbor = position.saturating_add_signed(offset).min(size - 1);
            original[neighbor].key
        } else {
            random.next() as u32
        };
        edits.push(Edit { position, key });
    }
    (original, edits)
}

fn expected_rows(original: &[Row], edits: &[Edit]) -> Vec<Row> {
    let mut expected = original.to_vec();
    for edit in edits {
        expected[edit.position].key = edit.key;
    }
    expected.sort_by(|a, b| a.key.cmp(&b.key).then(a.id.cmp(&b.id)));
    expected
}

fn check_fixture(original: &[Row], edits: &[Edit]) {
    let expected = expected_rows(original, edits);
    let mut working = original.to_vec();
    let mut changed = vec![false; original.len()];
    for edit in edits {
        changed[edit.position] = true;
    }
    // IDs are unique even when the physical order differs from their arrival order.
    let mut destinations = vec![0; original.len()];
    for (position, row) in expected.iter().enumerate() {
        destinations[row.id as usize] = position;
    }
    let minimum_moves = original
        .iter()
        .enumerate()
        .filter(|&(source, row)| !changed[source] && destinations[row.id as usize] != source)
        .count();
    for method in METHODS {
        working.copy_from_slice(original);
        let moved = method.run(&mut working, edits);
        assert_eq!(working, expected, "fixture failed for {}", method.name());
        if let Some(moved) = moved {
            if matches!(method, Method::DirectSpans) {
                assert_eq!(moved, minimum_moves);
            } else {
                assert!(moved >= minimum_moves);
            }
        }
    }
}

fn verify() {
    let mut checks = 0;
    let mut random = SplitMix64(271);
    for size in 0..=5 {
        let mut original: Vec<_> = (0..size)
            .map(|id| Row {
                key: [1, 1, 3, 0, 4][id],
                id: id as u32,
                payload: std::array::from_fn(|_| random.next()),
            })
            .collect();
        original.sort_unstable_by_key(|row| (row.key, row.id));
        for assignment in 0..4_usize.pow(size as u32) {
            let mut edits: Vec<_> = (0..size)
                .filter_map(|position| {
                    let replacement = (assignment >> (2 * position)) & 3;
                    (replacement != 0).then(|| Edit {
                        position,
                        key: [0, 0, 1, u32::MAX][replacement],
                    })
                })
                .collect();
            random.shuffle(&mut edits);
            check_fixture(&original, &edits);
            checks += 1;
        }
    }
    for size in [6, 7, 17, 63, 64, 65, 127, 257, 1023] {
        for count in [0, 1, size / 3, size - 1, size] {
            for local in [false, true] {
                let (original, edits) = fixture(size, count, random.next(), local);
                check_fixture(&original, &edits);
                checks += 1;
            }
        }
    }
    println!("Verified {checks} fixtures for all five methods and checked the minimum unchanged-row writes");
}

#[cfg(windows)]
fn pin(cpu: usize) -> io::Result<()> {
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetCurrentThread() -> *mut core::ffi::c_void;
        fn SetThreadAffinityMask(thread: *mut core::ffi::c_void, mask: usize) -> usize;
    }
    let mask = 1_usize
        .checked_shl(cpu as u32)
        .ok_or(io::ErrorKind::InvalidInput)?;
    // The current-thread pseudohandle needs no close. A zero return indicates failure.
    if unsafe { SetThreadAffinityMask(GetCurrentThread(), mask) } == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

#[cfg(target_os = "linux")]
fn pin(cpu: usize) -> io::Result<()> {
    unsafe extern "C" {
        fn sched_setaffinity(pid: i32, size: usize, mask: *const u64) -> i32;
    }
    let mut mask = [0_u64; 16];
    mask[cpu / 64] = 1_u64 << (cpu % 64);
    // pid=0 sets the calling thread's affinity. Pass the whole Linux cpu_set_t.
    if unsafe { sched_setaffinity(0, std::mem::size_of_val(&mask), mask.as_ptr()) } != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

fn flush(rows: &[Row]) {
    let first = rows.as_ptr().cast::<u8>();
    // Row alignment and size make both cache lines valid within each row.
    unsafe {
        for offset in (0..std::mem::size_of_val(rows)).step_by(64) {
            _mm_clflush(first.add(offset));
        }
        _mm_mfence();
    }
}

fn run(size: usize, count: usize, distribution: &str, seed: u64, repeats: usize) -> io::Result<()> {
    let (original, edits) = fixture(size, count, seed, distribution == "local");
    let expected = expected_rows(&original, &edits);
    let mut working = original.clone();
    let mut random = SplitMix64(seed ^ 0xbd7782dcf475078f);
    let mut output = io::BufWriter::new(io::stdout().lock());
    writeln!(
        output,
        "rows,edits,distribution,seed,round,method,total_ns,unchanged_rows_written,verified"
    )?;

    for round in 0..=repeats {
        let mut order = METHODS;
        random.shuffle(&mut order);
        for method in order {
            working.copy_from_slice(&original);
            if size > 4096 {
                flush(&working);
            }
            let start = Instant::now();
            let moved = black_box(method.run(black_box(&mut working), black_box(&edits)));
            let elapsed = start.elapsed().as_nanos();
            if working != expected {
                let bad = working
                    .iter()
                    .zip(&expected)
                    .position(|(a, b)| a != b)
                    .unwrap();
                return Err(io::Error::other(format!(
                    "{} output mismatch at row {bad}",
                    method.name()
                )));
            }
            let moved = moved.map(|n| n.to_string()).unwrap_or_default();
            writeln!(
                output,
                "{size},{count},{distribution},{seed},{round},{},{elapsed},{moved},true",
                method.name()
            )?;
        }
    }
    output.flush()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().skip(1).collect();
    if args == ["--verify"] {
        verify();
        return Ok(());
    }
    let [size, count, distribution, seed, repeats, cpu] = args.as_slice() else {
        return Err("usage: bench --verify | ROWS EDITS uniform|local SEED REPEATS CPU".into());
    };
    let (size, count, seed, repeats, cpu) = (
        size.parse()?,
        count.parse()?,
        seed.parse()?,
        repeats.parse()?,
        cpu.parse()?,
    );
    if size == 0
        || size > u32::MAX as usize
        || count > size
        || repeats == 0
        || cpu >= 1024
        || !matches!(distribution.as_str(), "uniform" | "local")
    {
        return Err("invalid benchmark argument".into());
    }
    pin(cpu)?;
    run(size, count, distribution, seed, repeats)?;
    Ok(())
}
