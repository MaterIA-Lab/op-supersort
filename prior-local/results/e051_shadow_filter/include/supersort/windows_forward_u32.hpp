#pragma once

#include "windows_split_u32.hpp"

namespace supersort::window_detail {

inline std::size_t compact_window_forward(Key* a, std::size_t n, Key prefix, Key* counts) {
    const auto high_prefix = _mm256_set1_epi32(prefix);
    std::size_t read = 0, used = 0;
    for (; n - read >= 8; read += 8) {
        const auto keys = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(a + read));
        const auto highs = _mm256_srli_epi32(keys, 16);
        unsigned inside = lane_mask(_mm256_cmpeq_epi32(high_prefix, highs));
        const unsigned outside = inside ^ 255;
        if (inside == 255) {
            for (unsigned lane = 0; lane < 8; ++lane) ++counts[a[read + lane] & 65535];
        } else {
            while (inside) {
                ++counts[a[read + __builtin_ctz(inside)] & 65535];
                inside &= inside - 1;
            }
            // The destination is never ahead of the current block. Its keys
            // are already counted or saved in the register before this store.
            if (outside != 255 || used != read) {
                _mm256_storeu_si256(reinterpret_cast<__m256i*>(a + used), pack_side(keys, outside, external_lanes));
            }
            used += __builtin_popcount(outside);
        }
    }
    for (; read < n; ++read) {
        const auto key = a[read];
        if ((key >> 16) == prefix) ++counts[key & 65535];
        else a[used++] = key;
    }
    return used;
}

inline SplitWork restore_window_forward(Key* a, std::size_t n, Key prefix,
                                        const Key* counts, std::size_t residual) {
    if (!n) return {0, 0};
    const Key end_of_window = (prefix << 16) | 65535;
    const auto* first_high = std::upper_bound(a, a + residual, end_of_window);
    const auto low = static_cast<std::size_t>(first_high - a);
    const auto high = residual - low;
    if (residual != n) {
        if (high) std::memmove(a + n - high, first_high, high * sizeof(Key));
        emit_window_counts(a + low, prefix, counts);
    }
    return {low, high};
}

// One known window with an unshifted 16-bit prefix and n <= UINT32_MAX.
inline SplitWork sort_window_forward(Key* a, std::size_t n, Key prefix) {
    if (!n) return {0, 0};
    const auto counts = std::make_unique<Key[]>(width);
    const auto residual = compact_window_forward(a, n, prefix, counts.get());
    if (residual > 1) vq_sort_u32(a, residual);
    return restore_window_forward(a, n, prefix, counts.get(), residual);
}

}  // namespace supersort::window_detail
