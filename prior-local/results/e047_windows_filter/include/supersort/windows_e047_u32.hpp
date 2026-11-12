#pragma once

#include "windows_u32.hpp"

namespace supersort {
namespace window_detail {

inline std::size_t constant_prefix_blocks(const Key* a, std::size_t n, Key key) {
    const auto initial = _mm256_set1_epi32(static_cast<int>(key));
    std::size_t i = 0;
    for (; n - i >= 32; i += 32) {
        const auto d0 = _mm256_xor_si256(_mm256_loadu_si256(reinterpret_cast<const __m256i*>(a + i)), initial);
        const auto d1 = _mm256_xor_si256(_mm256_loadu_si256(reinterpret_cast<const __m256i*>(a + i + 8)), initial);
        const auto d2 = _mm256_xor_si256(_mm256_loadu_si256(reinterpret_cast<const __m256i*>(a + i + 16)), initial);
        const auto d3 = _mm256_xor_si256(_mm256_loadu_si256(reinterpret_cast<const __m256i*>(a + i + 24)), initial);
        const auto diff = _mm256_or_si256(_mm256_or_si256(d0, d1), _mm256_or_si256(d2, d3));
        if (!_mm256_testz_si256(diff, diff)) return i;
    }
    while (i < n && a[i] == key) ++i;
    return i;
}

inline WindowWork certify_blocks(const Key* a, std::size_t n, Proposal windows) {
    if (!windows.count) return {WindowRoute::bypass, 0, 0};

    std::size_t i = 0;
    const auto high0 = a[0] >> 16;
    if (high0 == windows.first || high0 == windows.second) {
        i = constant_prefix_blocks(a, n, a[0]);
        if (i == n) return {WindowRoute::constant, n, 0};
    }

    const auto first = _mm256_set1_epi32(windows.first);
    const auto second = _mm256_set1_epi32(windows.second);
    const auto budget = n / 8;
    std::size_t outside = 0;
    // Earlier blocks are known to contain only the first key, inside a window.
    for (; n - i >= 8; i += 8) {
        const auto values = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(a + i));
        const auto high = _mm256_srli_epi32(values, 16);
        const auto matches = _mm256_or_si256(_mm256_cmpeq_epi32(high, first),
                                            _mm256_cmpeq_epi32(high, second));
        const auto mask = _mm256_movemask_ps(_mm256_castsi256_ps(matches));
        outside += 8 - __builtin_popcount(static_cast<unsigned>(mask));
        if (outside > budget) return {WindowRoute::reject, i + 8, outside};
    }
    for (; i < n; ++i) {
        const auto high = a[i] >> 16;
        outside += high != windows.first && high != windows.second;
        if (outside > budget) return {WindowRoute::reject, i + 1, outside};
    }
    return {windows.count == 1 ? WindowRoute::one : WindowRoute::two, n, outside};
}

}  // namespace window_detail

inline WindowWork cert_vq_e047_u32(std::uint32_t* a, std::size_t n) {
    const auto work = window_detail::certify_blocks(a, n, window_detail::propose(a, n));
    if (n > 1) vq_sort_u32(a, n);
    return work;
}

inline WindowWork window_e047_u32(std::uint32_t* a, std::size_t n) {
    using namespace window_detail;
    const auto proposal = propose(a, n);
    const auto work = certify_blocks(a, n, proposal);
    apply(a, n, proposal, work);
    return work;
}

}  // namespace supersort
