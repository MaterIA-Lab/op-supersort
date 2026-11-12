#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <immintrin.h>
#include <limits>
#include <memory>

void vq_sort_u32(std::uint32_t*, std::size_t);

namespace supersort {

enum class WindowRoute { bypass, reject, constant, one, two };

struct WindowWork {
    WindowRoute route;
    std::size_t examined;
    std::size_t residual;
};

namespace window_detail {

using Key = std::uint32_t;
constexpr std::size_t width = 1 << 16;
constexpr std::size_t samples = 256;

struct Proposal {
    Key first = 0;
    Key second = 0;
    unsigned count = 0;
};

inline Proposal propose(const Key* a, std::size_t n) {
    if (n < (1u << 18) || n > std::numeric_limits<Key>::max()) return {};
    std::array<Key, samples> prefixes;
    for (std::size_t i = 0; i < samples; ++i) prefixes[i] = a[(n / samples) * i] >> 16;
    std::sort(prefixes.begin(), prefixes.end());

    Key first = 0, second = 0;
    std::size_t first_count = 0, second_count = 0;
    for (std::size_t begin = 0; begin < samples;) {
        auto end = begin + 1;
        while (end < samples && prefixes[end] == prefixes[begin]) ++end;
        const auto count = end - begin;
        if (count > first_count) {
            second = first;
            second_count = first_count;
            first = prefixes[begin];
            first_count = count;
        } else if (count > second_count) {
            second = prefixes[begin];
            second_count = count;
        }
        begin = end;
    }
    if (first_count >= 224) return {first, first, 1};
    if (first_count + second_count < 224) return {};
    if (first > second) std::swap(first, second);
    return {first, second, 2};
}

inline WindowWork certify(const Key* a, std::size_t n, Proposal windows) {
    if (windows.count == 0) return {WindowRoute::bypass, 0, 0};
    const auto first = _mm256_set1_epi32(windows.first);
    const auto second = _mm256_set1_epi32(windows.second);
    const auto initial = _mm256_set1_epi32(static_cast<int>(a[0]));
    auto diff = _mm256_setzero_si256();
    std::size_t i = 0, outside = 0;
    const auto budget = n / 8;
    for (; n - i >= 8; i += 8) {
        const auto values = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(a + i));
        const auto high = _mm256_srli_epi32(values, 16);
        const auto matches = _mm256_or_si256(_mm256_cmpeq_epi32(high, first),
                                            _mm256_cmpeq_epi32(high, second));
        const auto mask = _mm256_movemask_ps(_mm256_castsi256_ps(matches));
        outside += 8 - __builtin_popcount(static_cast<unsigned>(mask));
        if (outside > budget) return {WindowRoute::reject, i + 8, outside};
        diff = _mm256_or_si256(diff, _mm256_xor_si256(values, initial));
    }
    bool constant = _mm256_testz_si256(diff, diff);
    for (; i < n; ++i) {
        const auto x = a[i];
        const auto high = x >> 16;
        outside += high != windows.first && high != windows.second;
        if (outside > budget) return {WindowRoute::reject, i + 1, outside};
        constant &= x == a[0];
    }
    if (constant) return {WindowRoute::constant, n, 0};
    return {windows.count == 1 ? WindowRoute::one : WindowRoute::two, n, outside};
}

inline void count_all(const Key* a, std::size_t n, Proposal windows, Key* counts) {
    if (windows.count == 1) {
        for (std::size_t i = 0; i < n; ++i) ++counts[a[i] & 65535];
    } else {
        for (std::size_t i = 0; i < n; ++i) {
            const auto x = a[i];
            const auto offset = (x >> 16) == windows.first ? 0 : width;
            ++counts[offset + (x & 65535)];
        }
    }
}

inline void separate(const Key* a, std::size_t n, Proposal windows, Key* counts, Key* outside) {
    for (std::size_t i = 0; i < n; ++i) {
        const auto x = a[i];
        const auto high = x >> 16;
        if (high == windows.first) ++counts[x & 65535];
        else if (high == windows.second) ++counts[width + (x & 65535)];
        else *outside++ = x;
    }
}

inline void reconstruct(Key* dst, Proposal windows, const Key* counts,
                        const Key* outside, std::size_t residual) {
    std::size_t used = 0;
    for (unsigned w = 0; w < windows.count; ++w) {
        const Key base = (w == 0 ? windows.first : windows.second) << 16;
        if (used < residual) {
            const auto from = outside + used;
            const auto to = std::lower_bound(from, outside + residual, base);
            const std::size_t length = to - from;
            std::memcpy(dst, from, length * sizeof(Key));
            dst += length;
            used += length;
        }
        for (Key offset = 0; offset < width; ++offset) {
            const auto multiplicity = counts[w * width + offset];
            std::fill_n(dst, multiplicity, base | offset);
            dst += multiplicity;
        }
    }
    if (used < residual) std::memcpy(dst, outside + used, (residual - used) * sizeof(Key));
}

}  // namespace window_detail

inline WindowWork cert_vq_u32(std::uint32_t* a, std::size_t n) {
    const auto work = window_detail::certify(a, n, window_detail::propose(a, n));
    if (n > 1) vq_sort_u32(a, n);
    return work;
}

inline WindowWork window_u32(std::uint32_t* a, std::size_t n) {
    using namespace window_detail;
    const auto proposal = propose(a, n);
    const auto work = certify(a, n, proposal);
    if (work.route == WindowRoute::bypass || work.route == WindowRoute::reject) {
        if (n > 1) vq_sort_u32(a, n);
    } else if (work.route != WindowRoute::constant) {
        const auto counts = std::make_unique<Key[]>(width * proposal.count);
        std::unique_ptr<Key[]> outside;
        if (work.residual) {
            outside.reset(new Key[work.residual]);
            separate(a, n, proposal, counts.get(), outside.get());
            if (work.residual > 1) vq_sort_u32(outside.get(), work.residual);
        } else {
            count_all(a, n, proposal, counts.get());
        }
        reconstruct(a, proposal, counts.get(), outside.get(), work.residual);
    }
    return work;
}

}  // namespace supersort
