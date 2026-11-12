#pragma once

#include "windows_u32.hpp"

namespace supersort::window_detail {

constexpr std::array<std::array<int, 8>, 256> external_permutations() {
    std::array<std::array<int, 8>, 256> table{};
    for (unsigned mask = 0; mask < table.size(); ++mask) {
        unsigned position = 0;
        for (int lane = 0; lane < 8; ++lane) {
            if (mask & (1u << lane)) table[mask][position++] = lane;
        }
    }
    return table;
}

alignas(32) inline constexpr auto external_lanes = external_permutations();

template<bool Two>
inline void increment_inside(Key key, Key first, Key* counts) {
    auto index = static_cast<std::size_t>(key & 65535);
    if constexpr (Two) index += (key >> 16) == first ? 0 : width;
    ++counts[index];
}

template<bool Two>
inline void separate_compact_impl(const Key* a, std::size_t n, Proposal windows,
                                  Key* counts, Key* outside, std::size_t residual) {
    const auto first = _mm256_set1_epi32(windows.first);
    const auto second = _mm256_set1_epi32(windows.second);
    std::size_t i = 0;
    std::size_t used = 0;
    for (; n - i >= 8; i += 8) {
        const auto values = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(a + i));
        const auto high = _mm256_srli_epi32(values, 16);
        auto matches = _mm256_cmpeq_epi32(high, first);
        if constexpr (Two) matches = _mm256_or_si256(matches, _mm256_cmpeq_epi32(high, second));
        unsigned inside = static_cast<unsigned>(_mm256_movemask_ps(_mm256_castsi256_ps(matches)));
        if (inside == 255) {
            for (unsigned lane = 0; lane < 8; ++lane) increment_inside<Two>(a[i + lane], windows.first, counts);
        } else if (inside == 0) {
            _mm256_storeu_si256(reinterpret_cast<__m256i*>(outside + used), values);
            used += 8;
        } else {
            const unsigned external = inside ^ 255;
            const auto order = _mm256_load_si256(reinterpret_cast<const __m256i*>(external_lanes[external].data()));
            const auto packed = _mm256_permutevar8x32_epi32(values, order);
            const auto kept = static_cast<unsigned>(__builtin_popcount(external));
            if (residual - used >= 8) {
                _mm256_storeu_si256(reinterpret_cast<__m256i*>(outside + used), packed);
            } else {
                alignas(32) Key tail[8];
                _mm256_store_si256(reinterpret_cast<__m256i*>(tail), packed);
                std::memcpy(outside + used, tail, kept * sizeof(Key));
            }
            used += kept;
            do {
                const auto lane = __builtin_ctz(inside);
                increment_inside<Two>(a[i + lane], windows.first, counts);
                inside &= inside - 1;
            } while (inside);
        }
    }
    if (i < n) separate(a + i, n - i, windows, counts, used ? outside + used : outside);
}

// Source and outputs are disjoint. The certificate supplies the exact outside capacity.
inline void separate_compact(const Key* a, std::size_t n, Proposal windows,
                             Key* counts, Key* outside, std::size_t residual) {
    if (windows.count == 1) separate_compact_impl<false>(a, n, windows, counts, outside, residual);
    else separate_compact_impl<true>(a, n, windows, counts, outside, residual);
}

}  // namespace supersort::window_detail
