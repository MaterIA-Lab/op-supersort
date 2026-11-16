#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace placement {

constexpr std::size_t row_bytes = 128;
constexpr std::size_t page_bytes = 4096;
constexpr std::size_t page_rows = page_bytes / row_bytes;
constexpr std::size_t minimum_extent_rows = 64 * 1024 / row_bytes;

constexpr std::size_t page_floor(std::size_t rows) { return rows / page_rows * page_rows; }
constexpr std::size_t page_ceil(std::size_t rows) { return page_floor(rows + page_rows - 1); }

struct Run {
    const std::byte* data;
    std::size_t size;

    const std::byte* row(std::size_t i) const { return i ? data + i * row_bytes : data; }

    std::uint64_t key(std::size_t i) const {
        std::uint64_t result;
        std::memcpy(&result, row(i), sizeof(result));
        return result;
    }

    Run range(std::size_t begin, std::size_t end) const { return {row(begin), end - begin}; }
};

using Runs = std::array<Run, 2>;

struct Slice {
    std::size_t side = 0;
    std::size_t source = 0;
    std::size_t output = 0;
    std::size_t size = 0;
};

struct Edges {
    Slice prefix;
    Slice suffix;
};

inline std::size_t bound(Run run, std::uint64_t pivot, bool include_equal) {
    std::size_t low = 0;
    std::size_t high = run.size;
    while (low < high) {
        const auto mid = low + (high - low) / 2;
        const auto key = run.key(mid);
        if (key < pivot || (include_equal && key == pivot)) {
            low = mid + 1;
        } else {
            high = mid;
        }
    }
    return low;
}

inline Edges outer_slices(const Runs& runs) {
    const auto [a, b] = runs;
    if (a.size == 0) return {{1, 0, 0, b.size}, {}};
    if (b.size == 0) return {{0, 0, 0, a.size}, {}};
    const auto total = a.size + b.size;
    const std::size_t first = a.key(0) <= b.key(0) ? 0 : 1;
    const auto first_end = bound(runs[first], runs[1 - first].key(0), first == 0);
    const std::size_t last = a.key(a.size - 1) <= b.key(b.size - 1) ? 1 : 0;
    const auto last_begin = bound(runs[last], runs[1 - last].key(runs[1 - last].size - 1),
                                 last == 0);
    const auto last_size = runs[last].size - last_begin;
    return {{first, 0, 0, first_end}, {last, last_begin, total - last_size, last_size}};
}

inline Slice full_pages(Slice slice) {
    const auto begin = page_ceil(slice.output);
    const auto end = page_floor(slice.output + slice.size);
    if (end < begin + minimum_extent_rows) return {};
    return {slice.side, slice.source + begin - slice.output, begin, end - begin};
}

constexpr std::size_t required_phase(Slice slice) {
    return (slice.output % page_rows + page_rows - slice.source % page_rows) % page_rows;
}

struct Plan {
    Edges mapped;
    std::array<std::size_t, 2> phase{};
};

inline Plan plan_edges(Edges edges, bool shift_inputs) {
    Plan plan{{full_pages(edges.prefix), full_pages(edges.suffix)}};
    auto& [head, tail] = plan.mapped;
    if (shift_inputs) {
        if (head.size) plan.phase[head.side] = required_phase(head);
        if (tail.size && (head.side != tail.side || tail.size > head.size)) {
            plan.phase[tail.side] = required_phase(tail);
        }
    }
    if (head.size && plan.phase[head.side] != required_phase(head)) head = {};
    if (tail.size && plan.phase[tail.side] != required_phase(tail)) tail = {};
    return plan;
}

// Emit source spans in stable output order, copying the two outer stretches in bulk.
template <typename Emit>
void visit_merge(const Runs& runs, Edges edges, Emit emit) {
    const auto [head, tail] = edges;
    std::array<std::size_t, 2> cursor{};
    std::array<std::size_t, 2> end{runs[0].size, runs[1].size};
    if (head.size) {
        emit(head.side, head.source, head.size);
        cursor[head.side] = head.size;
    }
    if (tail.size) end[tail.side] = tail.source;

    while (cursor[0] < end[0] && cursor[1] < end[1]) {
        const auto side = runs[0].key(cursor[0]) <= runs[1].key(cursor[1]) ? 0 : 1;
        emit(side, cursor[side], 1);
        ++cursor[side];
    }
    for (std::size_t side = 0; side < 2; ++side) {
        if (cursor[side] < end[side]) emit(side, cursor[side], end[side] - cursor[side]);
    }
    if (tail.size) emit(tail.side, tail.source, tail.size);
}

}  // namespace placement
