#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>

namespace record_permutation {

template <unsigned SourceShift, bool Prefetch, class Row>
void materialize(const Row* input, Row* output, const uint64_t* indexes, size_t count) {
    constexpr size_t prefetch_distance = 32;
    for (size_t index = 0; index < count; ++index) {
        if constexpr (Prefetch) {
            if (index + prefetch_distance < count) {
                const auto next_source = static_cast<uint32_t>(indexes[index + prefetch_distance] >> SourceShift);
                const auto* next_row = reinterpret_cast<const char*>(input + next_source);
                __builtin_prefetch(next_row, 0, 3);
                if constexpr (sizeof(Row) > 64) {
                    __builtin_prefetch(next_row + 64, 0, 3);
                }
            }
        }
        const uint64_t entry = indexes[index];
        const auto source = static_cast<uint32_t>(entry >> SourceShift);
        if constexpr (SourceShift == 0) {
            output[index] = input[source];
        } else {
            output[static_cast<uint32_t>(entry)] = input[source];
        }
    }
}

template <class Row, class IndexSorter>
void blocked(const Row* input, Row* output, uint64_t* indexes, size_t count, IndexSorter sort_indexes) {
    constexpr size_t rows_per_tile = 256 * 1024 / sizeof(Row);
    static_assert(rows_per_tile > 0);
    for (size_t start = 0; start < count; start += rows_per_tile) {
        const size_t end = std::min(start + rows_per_tile, count);
        for (size_t rank = start; rank < end; ++rank) {
            const auto source = static_cast<uint32_t>(indexes[rank]);
            indexes[rank] = (uint64_t{source} << 32) | rank;
        }
        sort_indexes(indexes + start, end - start);
        materialize<32, true>(input, output, indexes + start, end - start);
    }
}

}  // namespace record_permutation
