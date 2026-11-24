use super::{key, Edit, Row};

pub fn merge(rows: &mut [Row], edits: &[Edit], block_rows: usize) -> usize {
    if edits.is_empty() {
        return 0;
    }
    assert!(block_rows > 0);
    let mut removed = edits.to_vec();
    removed.sort_unstable_by_key(|edit| edit.position);
    let mut replacements = Vec::with_capacity(edits.len());
    let mut by_key = Vec::with_capacity(edits.len());
    for edit in &removed {
        let mut row = rows[edit.position];
        row.key = edit.key;
        by_key.push((key(&row), replacements.len()));
        replacements.push(row);
    }
    by_key.sort_unstable_by_key(|&(order, _)| order);
    let mut insertion = by_key.iter().peekable();
    let mut deletion = removed.iter().peekable();

    let mut staged = Vec::<Row>::with_capacity(block_rows + edits.len());
    let (mut read, mut write, mut head) = (0, 0, 0);
    let mut clean_writes = 0;
    while write < rows.len() {
        if read == write && head == staged.len() {
            let clean_end = deletion.peek().map_or(rows.len(), |edit| edit.position);
            let clean = &rows[read..clean_end];
            let unchanged = insertion.peek().map_or(clean.len(), |&&(order, _)| {
                clean.partition_point(|row| key(row) < order)
            });
            read += unchanged;
            write += unchanged;
            if write == rows.len() {
                break;
            }
        }

        if read < rows.len() && (head == staged.len() || read == write) {
            // At read == write the pending survivors equal inserted rows minus
            // skipped deletions, so at most edits.len() survive the refill.
            staged.copy_within(head.., 0);
            staged.truncate(staged.len() - head);
            head = 0;
            let end = (read + block_rows).min(rows.len());
            while let Some(edit) = deletion.next_if(|edit| edit.position < end) {
                staged.extend_from_slice(&rows[read..edit.position]);
                read = edit.position + 1;
            }
            staged.extend_from_slice(&rows[read..end]);
            read = end;
            if staged.is_empty() && read < rows.len() {
                continue;
            }
        }

        // A store at or beyond read would overwrite an unbuffered original.
        let available = (staged.len() - head).min(read - write);
        let clean = &staged[head..head + available];
        let count = insertion.peek().map_or(available, |&&(order, _)| {
            clean.partition_point(|row| key(row) < order)
        });
        if count != 0 {
            rows[write..write + count].copy_from_slice(&clean[..count]);
            head += count;
            write += count;
            clean_writes += count;
        } else {
            let &(_, replacement) = insertion.next().expect("output has an unfilled slot");
            rows[write] = replacements[replacement];
            write += 1;
        }
    }
    debug_assert!(insertion.next().is_none());
    clean_writes
}
