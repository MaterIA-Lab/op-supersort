#pragma once

#include "windows_compact_u32.hpp"

namespace supersort::window_detail {

struct SplitWork {
    std::size_t low;
    std::size_t high;
};

constexpr std::array<std::array<int, 8>, 256> right_permutations() {
    std::array<std::array<int, 8>, 256> table{};
    for (unsigned mask = 0; mask < table.size(); ++mask) {
        unsigned position = 8;
        for (int lane = 7; lane >= 0; --lane) {
            if (mask & (1u << lane)) table[mask][--position] = lane;
        }
    }
    return table;
}

alignas(32) inline constexpr auto right_lanes = right_permutations();

inline unsigned lane_mask(__m256i comparison) {
    return static_cast<unsigned>(_mm256_movemask_ps(_mm256_castsi256_ps(comparison)));
}

inline __m256i pack_side(__m256i keys, unsigned mask,
                         const std::array<std::array<int, 8>, 256>& order) {
    if (mask == 255) return keys;
    const auto indices = _mm256_load_si256(reinterpret_cast<const __m256i*>(order[mask].data()));
    return _mm256_permutevar8x32_epi32(keys, indices);
}

inline void split_block(const Key* block, Key* a, __m256i prefix, Key* counts,
                        std::size_t& left, std::size_t& right) {
    const auto keys = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(block));
    const auto highs = _mm256_srli_epi32(keys, 16);
    const unsigned low = lane_mask(_mm256_cmpgt_epi32(prefix, highs));
    const unsigned high = lane_mask(_mm256_cmpgt_epi32(highs, prefix));
    unsigned inside = 255 ^ (low | high);

    // Count before stores. Only the vector register is still needed afterwards.
    if (inside == 255) {
        for (unsigned lane = 0; lane < 8; ++lane) ++counts[block[lane] & 65535];
    } else {
        while (inside) {
            ++counts[block[__builtin_ctz(inside)] & 65535];
            inside &= inside - 1;
        }
    }
    if (low) {
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(a + left), pack_side(keys, low, external_lanes));
        left += __builtin_popcount(low);
    }
    if (high) {
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(a + right - 8), pack_side(keys, high, right_lanes));
        right -= __builtin_popcount(high);
    }
}

inline SplitWork split_window(Key* a, std::size_t n, Key prefix, Key* counts) {
    constexpr std::size_t lanes = 8;
    std::array<Key, 3 * lanes - 1> pending;
    std::size_t pending_size = n;
    std::size_t left = 0, right = n;

    if (n >= 2 * lanes) {
        std::copy_n(a, lanes, pending.data());
        std::copy_n(a + n - lanes, lanes, pending.data() + lanes);
        std::size_t read_left = lanes, read_right = n - lanes;
        const auto high_prefix = _mm256_set1_epi32(prefix);
        while (read_right - read_left >= lanes) {
            const Key* block;
            // At least one gap is already large enough for a full-width store.
            // Reading from the other side makes both stores safe.
            if (read_left - left <= right - read_right) {
                block = a + read_left;
                read_left += lanes;
            } else {
                read_right -= lanes;
                block = a + read_right;
            }
            split_block(block, a, high_prefix, counts, left, right);
        }
        const auto tail = read_right - read_left;
        std::copy_n(a + read_left, tail, pending.data() + 2 * lanes);
        pending_size = 2 * lanes + tail;
    } else if (n) {
        std::copy_n(a, n, pending.data());
    }

    for (std::size_t i = 0; i < pending_size; ++i) {
        const auto key = pending[i];
        const auto high = key >> 16;
        if (high < prefix) a[left++] = key;
        else if (high > prefix) a[--right] = key;
        else ++counts[key & 65535];
    }
    return {left, n - right};
}

inline void emit_window_counts(Key* dst, Key prefix, const Key* counts) {
    const Key base = prefix << 16;
    for (Key offset = 0; offset < width; ++offset) {
        const auto multiplicity = counts[offset];
        std::fill_n(dst, multiplicity, base | offset);
        dst += multiplicity;
    }
}

// One known window with an unshifted 16-bit prefix and n <= UINT32_MAX.
inline SplitWork sort_window_split(Key* a, std::size_t n, Key prefix) {
    if (!n) return {0, 0};
    const auto counts = std::make_unique<Key[]>(width);
    const auto work = split_window(a, n, prefix, counts.get());
    if (work.low > 1) vq_sort_u32(a, work.low);
    if (work.high > 1) vq_sort_u32(a + n - work.high, work.high);
    emit_window_counts(a + work.low, prefix, counts.get());
    return work;
}

}  // namespace supersort::window_detail
