#pragma once

#include "windows_split_u32.hpp"

namespace supersort {
namespace four_split_detail {

constexpr std::size_t lanes = 8;

template<bool Right>
inline void store(__m256i keys, unsigned mask, std::uint32_t* dst, std::size_t& cursor) {
    if (!mask) return;
    const auto count = static_cast<std::size_t>(__builtin_popcount(mask));
    if constexpr (Right) {
        const auto packed = window_detail::pack_side(keys, mask, window_detail::right_lanes);
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(dst + cursor - lanes), packed);
        cursor -= count;
    } else {
        const auto packed = window_detail::pack_side(keys, mask, window_detail::external_lanes);
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(dst + cursor), packed);
        cursor += count;
    }
}

}  // namespace four_split_detail

// shift is in [0, 30]. The disjoint scratch holds at least n + 16 keys.
inline std::array<std::size_t, 4> four_split_u32(std::uint32_t* a, std::size_t n,
                                               unsigned shift, std::uint32_t* scratch) {
    using four_split_detail::lanes;
    using four_split_detail::store;
    if (!n) return {};

    std::array<std::uint32_t, 3 * lanes - 1> pending;
    std::size_t pending_size = n;
    std::size_t left = 0, right = n;
    const std::size_t scratch_end = n + 2 * lanes;
    std::size_t center_left = 0, center_right = scratch_end;

    if (n >= 2 * lanes) {
        std::copy_n(a, lanes, pending.data());
        std::copy_n(a + n - lanes, lanes, pending.data() + lanes);
        std::size_t read_left = lanes, read_right = n - lanes;
        const auto to_sign = _mm_cvtsi32_si128(static_cast<int>(30 - shift));
        while (read_right - read_left >= lanes) {
            // The two gaps total at least 16 slots. Reading from the smaller
            // gap's side leaves at least 8 slots on each side for full stores.
            const std::uint32_t* block;
            if (read_left - left <= right - read_right) {
                block = a + read_left;
                read_left += lanes;
            } else {
                read_right -= lanes;
                block = a + read_right;
            }
            const auto keys = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(block));
            const auto digits = _mm256_sll_epi32(keys, to_sign);
            const auto high = window_detail::lane_mask(digits);
            const auto low = window_detail::lane_mask(_mm256_slli_epi32(digits, 1));
            store<false>(keys, (high | low) ^ 255u, a, left);
            // At most n keys can enter scratch, so its cursors stay at least
            // 16 slots apart and both full-width stores fit.
            store<false>(keys, low & ~high, scratch, center_left);
            store<true>(keys, high & ~low, scratch, center_right);
            store<true>(keys, high & low, a, right);
        }
        const auto tail = read_right - read_left;
        std::copy_n(a + read_left, tail, pending.data() + 2 * lanes);
        pending_size = 2 * lanes + tail;
    } else {
        std::copy_n(a, n, pending.data());
    }

    for (std::size_t i = 0; i < pending_size; ++i) {
        const auto key = pending[i];
        switch ((key >> shift) & 3u) {
            case 0: a[left++] = key; break;
            case 1: scratch[center_left++] = key; break;
            case 2: scratch[--center_right] = key; break;
            case 3: a[--right] = key; break;
        }
    }

    const auto second_middle = scratch_end - center_right;
    if (center_left) std::copy_n(scratch, center_left, a + left);
    if (second_middle) std::copy_n(scratch + center_right, second_middle, a + left + center_left);
    return {left, center_left, second_middle, n - right};
}

}  // namespace supersort
