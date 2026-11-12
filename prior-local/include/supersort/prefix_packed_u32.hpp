#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>
#include <limits>
#include <memory>
#include <numeric>
#include <type_traits>

void vq_sort_u32(std::uint32_t*, std::size_t);
void vq_sort_u16(std::uint16_t*, std::size_t);

namespace supersort {
namespace prefix_detail {

using Key = std::uint32_t;
constexpr std::size_t fanout = 256;

inline void scatter_coarse(const Key* input, Key* groups, std::size_t n, const Key* offsets) {
    constexpr unsigned line_keys = 16;
    alignas(64) std::array<std::array<Key, line_keys>, fanout> lines;
    std::array<unsigned, fanout> used{};
    std::array<std::size_t, fanout> next;
    for (std::size_t p = 0; p < fanout; ++p) next[p] = offsets[p * fanout];
    for (std::size_t i = 0; i < n; ++i) {
        const Key key = input[i];
        const auto p = key >> 24;
        auto& length = used[p];
        lines[p][length++] = key;
        if (length == line_keys) {
            std::copy_n(lines[p].data(), line_keys, groups + next[p]);
            next[p] += line_keys;
            length = 0;
        }
    }
    for (std::size_t p = 0; p < fanout; ++p) {
        if (used[p]) std::copy_n(lines[p].data(), used[p], groups + next[p]);
    }
}

inline void expand(const std::uint16_t* suffixes, Key* output, std::size_t n, Key prefix) {
    const auto head = _mm256_set1_epi32(static_cast<int>(prefix));
    std::size_t i = 0;
    for (; n - i >= 8; i += 8) {
        const auto words = _mm_loadu_si128(reinterpret_cast<const __m128i*>(suffixes + i));
        const auto keys = _mm256_or_si256(_mm256_cvtepu16_epi32(words), head);
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(output + i), keys);
    }
    for (; i < n; ++i) output[i] = prefix | suffixes[i];
}

template<bool Packed>
using LeafKey = std::conditional_t<Packed, std::uint16_t, Key>;

template<bool Packed>
inline void finish_coarse(const Key* input, Key* output, LeafKey<Packed>* scratch,
                          const Key* offsets, std::size_t p) {
    const std::size_t base = p * fanout;
    const auto begin = offsets[base];
    const auto end = offsets[base + fanout];
    std::array<Key, fanout> next;
    for (std::size_t q = 0; q < fanout; ++q) next[q] = offsets[base + q] - begin;
    for (std::size_t i = begin; i < end; ++i) {
        const Key key = input[i];
        scratch[next[(key >> 16) & 255]++] = static_cast<LeafKey<Packed>>(key);
    }
    for (std::size_t q = 0; q < fanout; ++q) {
        const auto first = offsets[base + q];
        const auto length = offsets[base + q + 1] - first;
        if (!length) continue;
        auto* leaf = scratch + (first - begin);
        if constexpr (Packed) {
            if (length > 1) vq_sort_u16(leaf, length);
            expand(leaf, output + first, length, static_cast<Key>(base + q) << 16);
        } else {
            if (length > 1) vq_sort_u32(leaf, length);
            std::copy_n(leaf, length, output + first);
        }
    }
}

}  // namespace prefix_detail

template<bool Packed>
inline void prefix_leaf_sort(std::uint32_t* data, std::size_t n) {
    using namespace prefix_detail;
    if (n < 2) return;
    if (n > std::numeric_limits<Key>::max()) {
        vq_sort_u32(data, n);
        return;
    }
    constexpr auto leaves = fanout * fanout;
    const auto offsets = std::make_unique<Key[]>(leaves + 1);
    for (std::size_t i = 0; i < n; ++i) ++offsets[(data[i] >> 16) + 1];
    std::partial_sum(offsets.get(), offsets.get() + leaves + 1, offsets.get());
    Key largest = 0;
    for (std::size_t p = 0; p < fanout; ++p) {
        largest = std::max(largest, offsets[(p + 1) * fanout] - offsets[p * fanout]);
    }

    std::unique_ptr<Key[]> groups;
    const Key* input = data;
    if (largest != n) {
        groups.reset(new Key[n]);
        scatter_coarse(data, groups.get(), n, offsets.get());
        input = groups.get();
    }
    const std::unique_ptr<LeafKey<Packed>[]> scratch(new LeafKey<Packed>[largest]);
    for (std::size_t p = 0; p < fanout; ++p) {
        if (offsets[p * fanout] != offsets[(p + 1) * fanout]) {
            finish_coarse<Packed>(input, data, scratch.get(), offsets.get(), p);
        }
    }
}

}  // namespace supersort
