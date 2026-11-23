use std::cmp::Ordering;

#[repr(C, align(64))]
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Row {
    pub key: u32,
    pub id: u32,
    pub payload: [u64; 15],
}

const _: () = assert!(std::mem::size_of::<Row>() == 128);

impl Row {
    fn order_key(&self) -> u64 {
        (u64::from(self.key) << 32) | u64::from(self.id)
    }
}

#[derive(Clone, Copy, Debug)]
pub struct Edit {
    pub position: usize,
    pub key: u32,
}

struct Batch {
    by_position: Vec<Edit>,
    replacements: Vec<Row>,
    by_key: Vec<(u64, usize)>,
}

impl Batch {
    fn from_edits(rows: &[Row], edits: &[Edit]) -> Self {
        let mut by_position = edits.to_vec();
        by_position.sort_unstable_by_key(|edit| edit.position);
        debug_assert!(by_position
            .windows(2)
            .all(|w| w[0].position < w[1].position));

        let mut replacements = Vec::with_capacity(edits.len());
        let mut by_key = Vec::with_capacity(edits.len());
        for edit in &by_position {
            let mut row = rows[edit.position];
            row.key = edit.key;
            by_key.push((row.order_key(), replacements.len()));
            replacements.push(row);
        }
        by_key.sort_unstable_by_key(|&(key, _)| key);
        Self {
            by_position,
            replacements,
            by_key,
        }
    }
}

struct Move {
    source: usize,
    destination: usize,
    count: usize,
}

struct Insertion {
    old_gap: usize,
    replacement: usize,
    destination: usize,
}

fn move_rows(rows: &mut [Row], source: usize, destination: usize, count: usize) -> usize {
    if source == destination || count == 0 {
        return 0;
    }
    rows.copy_within(source..source + count, destination);
    count
}

pub fn direct_spans(rows: &mut [Row], edits: &[Edit]) -> usize {
    if edits.is_empty() {
        return 0;
    }
    let batch = Batch::from_edits(rows, edits);
    let mut insertions = Vec::with_capacity(edits.len());
    for &(key, replacement) in &batch.by_key {
        let old_gap = rows.partition_point(|row| row.order_key() < key);
        insertions.push(Insertion {
            old_gap,
            replacement,
            destination: 0,
        });
    }

    let mut moves = Vec::with_capacity(2 * edits.len() + 1);
    let mut deletion = 0;
    let mut insertion = 0;
    let mut source = 0;
    let mut destination = 0;
    loop {
        let delete_at = batch
            .by_position
            .get(deletion)
            .map_or(rows.len(), |edit| edit.position);
        let insert_at = insertions
            .get(insertion)
            .map_or(rows.len(), |edit| edit.old_gap);
        let event = delete_at.min(insert_at);
        let count = event - source;
        if count != 0 && source != destination {
            moves.push(Move {
                source,
                destination,
                count,
            });
        }
        source = event;
        destination += count;

        // A gap at index i comes before the original row at i, even if that row is deleted.
        while let Some(edit) = insertions.get_mut(insertion) {
            if edit.old_gap != event {
                break;
            }
            edit.destination = destination;
            destination += 1;
            insertion += 1;
        }
        if event == rows.len() {
            break;
        }
        if delete_at == event {
            source += 1;
            deletion += 1;
        }
    }
    debug_assert_eq!(destination, rows.len());

    // Final destinations of unchanged rows increase with their source positions.
    // A left move cannot overwrite a pending right mover to its left: that row
    // has a final destination farther left than the destination of this move.
    // Moving left spans forwards and right spans backwards preserves all other sources.
    let mut moved = 0;
    for span in moves.iter().filter(|span| span.destination < span.source) {
        moved += move_rows(rows, span.source, span.destination, span.count);
    }
    for span in moves
        .iter()
        .rev()
        .filter(|span| span.destination > span.source)
    {
        moved += move_rows(rows, span.source, span.destination, span.count);
    }
    for edit in insertions {
        rows[edit.destination] = batch.replacements[edit.replacement];
    }
    moved
}

pub fn bulk_esm_left(rows: &mut [Row], edits: &[Edit]) -> usize {
    if edits.is_empty() {
        return 0;
    }
    let batch = Batch::from_edits(rows, edits);
    let mut source = 0;
    let mut target = 0;
    let mut moved = 0;
    for edit in &batch.by_position {
        let count = edit.position - source;
        moved += move_rows(rows, source, target, count);
        source = edit.position + 1;
        target += count;
    }
    moved += move_rows(rows, source, target, rows.len() - source);

    let mut clean_end = rows.len() - edits.len();
    let mut output_end = rows.len();
    for &(key, replacement) in batch.by_key.iter().rev() {
        let cut = rows[..clean_end].partition_point(|row| row.order_key() < key);
        let count = clean_end - cut;
        output_end -= count;
        moved += move_rows(rows, cut, output_end, count);
        clean_end = cut;
        output_end -= 1;
        rows[output_end] = batch.replacements[replacement];
    }
    debug_assert_eq!(clean_end, output_end);
    moved
}

pub fn bulk_esm_right(rows: &mut [Row], edits: &[Edit]) -> usize {
    if edits.is_empty() {
        return 0;
    }
    let batch = Batch::from_edits(rows, edits);
    let mut source_end = rows.len();
    let mut target_end = rows.len();
    let mut moved = 0;
    for edit in batch.by_position.iter().rev() {
        let source_begin = edit.position + 1;
        let count = source_end - source_begin;
        target_end -= count;
        moved += move_rows(rows, source_begin, target_end, count);
        source_end = edit.position;
    }
    moved += move_rows(rows, 0, target_end - source_end, source_end);

    let mut clean_begin = edits.len();
    let mut output_begin = 0;
    for &(key, replacement) in &batch.by_key {
        let count = rows[clean_begin..].partition_point(|row| row.order_key() < key);
        moved += move_rows(rows, clean_begin, output_begin, count);
        clean_begin += count;
        output_begin += count;
        rows[output_begin] = batch.replacements[replacement];
        output_begin += 1;
    }
    debug_assert_eq!(clean_begin, output_begin);
    moved
}

pub fn change_keys(rows: &mut [Row], edits: &[Edit]) {
    for edit in edits {
        rows[edit.position].key = edit.key;
    }
}

pub fn compare_rows(a: &Row, b: &Row) -> Ordering {
    a.order_key().cmp(&b.order_key())
}

pub fn delta_sort(rows: &mut [Row], edits: &[Edit]) {
    change_keys(rows, edits);
    let mut dirty: Vec<_> = edits.iter().map(|edit| edit.position).collect();
    deltasort::delta_sort_by(rows, &mut dirty, compare_rows);
}

pub fn full_sort(rows: &mut [Row], edits: &[Edit]) {
    change_keys(rows, edits);
    rows.sort_unstable_by_key(Row::order_key);
}
