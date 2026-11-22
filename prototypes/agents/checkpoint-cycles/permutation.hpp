#pragma once

#include <array>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>

namespace checkpoint_cycles {
using Tag = std::uint64_t;
constexpr Tag visited = Tag{1} << 31;
constexpr std::uint32_t index_mask = 0x7fffffffu;
constexpr unsigned checkpoint_budget = 64;

struct alignas(64) Row {
    std::uint32_t key;
    std::uint32_t ordinal;
    std::array<std::uint64_t, 15> payload;
};
static_assert(sizeof(Row) == 128);

inline std::uint32_t source_index(Tag tag) {
    return static_cast<std::uint32_t>(tag) & index_mask;
}

inline void prefetch_row(const Row* row) {
    _mm_prefetch(reinterpret_cast<const char*>(row), _MM_HINT_T0);
    _mm_prefetch(reinterpret_cast<const char*>(row) + 64, _MM_HINT_T0);
}

template <bool Streaming = false>
inline void copy_row(Row* destination, const Row* source) {
    const auto* src = reinterpret_cast<const __m256i*>(source);
    auto* dst = reinterpret_cast<__m256i*>(destination);
    const auto a = _mm256_load_si256(src);
    const auto b = _mm256_load_si256(src + 1);
    const auto c = _mm256_load_si256(src + 2);
    const auto d = _mm256_load_si256(src + 3);
    if constexpr (Streaming) {
        _mm256_stream_si256(dst, a);
        _mm256_stream_si256(dst + 1, b);
        _mm256_stream_si256(dst + 2, c);
        _mm256_stream_si256(dst + 3, d);
    } else {
        _mm256_store_si256(dst, a);
        _mm256_store_si256(dst + 1, b);
        _mm256_store_si256(dst + 2, c);
        _mm256_store_si256(dst + 3, d);
    }
}

inline void scalar_cycles(Row* rows, Tag* order, std::size_t size) {
    for (std::size_t first = 0; first < size; ++first) {
        if (order[first] & visited) continue;
        const Row saved = rows[first];
        std::size_t current = first;
        auto next = source_index(order[current]);
        prefetch_row(rows + next);
        while (next != first) {
            prefetch_row(rows + source_index(order[next]));
            copy_row(rows + current, rows + next);
            order[current] |= visited;
            current = next;
            next = source_index(order[current]);
        }
        copy_row(rows + current, &saved);
        order[current] |= visited;
    }
}

inline void checkpoint_permute(Row* rows, Tag* order, std::size_t size) {
    if (!size) return;
    const auto stride = std::bit_ceil((size + checkpoint_budget - 1) / checkpoint_budget);
    const auto stride_mask = stride - 1;
    const auto stride_shift = std::countr_zero(stride);
    const auto count = static_cast<unsigned>((size + stride - 1) / stride);
    std::array<Row, checkpoint_budget> saved;
    std::array<std::uint32_t, checkpoint_budget> current;
    std::array<std::uint32_t, checkpoint_budget> next;

    for (unsigned lane = 0; lane < count; ++lane) {
        current[lane] = static_cast<std::uint32_t>(lane * stride);
        copy_row(&saved[lane], rows + current[lane]);
    }

    // Saved vertices cut every touched cycle into vertex-disjoint open paths.
    // A path closes at any saved vertex, so no walker reads overwritten rows.
    unsigned active = count;
    while (active) {
        for (unsigned lane = 0; lane < active; ++lane) {
            next[lane] = source_index(order[current[lane]]);
            if (next[lane] & stride_mask) prefetch_row(rows + next[lane]);
        }
        unsigned lane = 0;
        while (lane < active) {
            const auto destination = current[lane];
            const auto source = next[lane];
            const bool closes_path = (source & stride_mask) == 0;
            if (closes_path) copy_row(rows + destination, &saved[source >> stride_shift]);
            else copy_row(rows + destination, rows + source);
            order[destination] |= visited;
            if (closes_path) {
                --active;
                current[lane] = current[active];
                next[lane] = next[active];
            } else {
                current[lane] = source;
                ++lane;
            }
        }
    }
    // Cycles with no checkpoint are still untouched and must also be moved.
    scalar_cycles(rows, order, size);
}

template <bool Streaming>
inline void gather_and_copy_back(Row* rows, const Tag* order, Row* scratch,
                                 std::size_t size) {
    for (std::size_t destination = 0; destination < size; ++destination) {
        if (destination + 32 < size) prefetch_row(rows + source_index(order[destination + 32]));
        copy_row<Streaming>(scratch + destination, rows + source_index(order[destination]));
    }
    if constexpr (Streaming) {
        _mm_sfence();
        for (std::size_t destination = 0; destination < size; ++destination) {
            copy_row<true>(rows + destination, scratch + destination);
        }
        _mm_sfence();
    } else {
        if (size) __builtin_memcpy(rows, scratch, size * sizeof(Row));
    }
}
}  // namespace checkpoint_cycles
