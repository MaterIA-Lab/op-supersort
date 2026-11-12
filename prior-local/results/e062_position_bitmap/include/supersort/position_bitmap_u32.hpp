#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>

namespace supersort {
namespace position_bitmap_detail {

using Key = std::uint32_t;
using Word = std::uint64_t;
constexpr std::size_t max_keys = 512;
constexpr std::size_t word_bits = 64;
constexpr std::size_t max_words = max_keys / word_bits;
constexpr std::size_t max_planes = 8;
constexpr std::size_t lanes = 8;
using Planes = std::array<std::array<Word, max_words>, max_planes>;

struct Positions {
    // Only words selected by live can be read.
    std::array<Word, max_words> words;
    unsigned live = 0;
    std::size_t count = 0;
};

inline Key varying_bits(const Key* data, std::size_t n) {
    auto any = _mm256_setzero_si256();
    auto all = _mm256_set1_epi32(-1);
    std::size_t i = 0;
    for (; n - i >= lanes; i += lanes) {
        const auto keys = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(data + i));
        any = _mm256_or_si256(any, keys);
        all = _mm256_and_si256(all, keys);
    }
    alignas(32) std::array<Key, lanes> any_lane, all_lane;
    _mm256_store_si256(reinterpret_cast<__m256i*>(any_lane.data()), any);
    _mm256_store_si256(reinterpret_cast<__m256i*>(all_lane.data()), all);
    Key any_bits = 0, all_bits = ~Key{0};
    for (std::size_t lane = 0; lane < lanes; ++lane) {
        any_bits |= any_lane[lane];
        all_bits &= all_lane[lane];
    }
    for (; i < n; ++i) {
        any_bits |= data[i];
        all_bits &= data[i];
    }
    return any_bits ^ all_bits;
}

inline std::size_t build_planes(const Key* data, std::size_t n, Key varying, Planes& planes) {
    std::array<Key, max_planes> bits;
    __m128i shifts[max_planes];
    std::size_t plane_count = 0;
    while (varying && plane_count < max_planes) {
        // Align the highest remaining varying bit with movemask's sign bit.
        const auto shift = __builtin_clz(varying);
        const auto bit = Key{1} << (31 - shift);
        bits[plane_count] = bit;
        shifts[plane_count++] = _mm_cvtsi32_si128(shift);
        varying ^= bit;
    }

    for (std::size_t offset = 0; offset < n; offset += word_bits) {
        const auto count = std::min(word_bits, n - offset);
        std::array<Word, max_planes> words{};
        std::size_t i = 0;
        for (; count - i >= lanes; i += lanes) {
            const auto keys = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(data + offset + i));
            for (std::size_t p = 0; p < plane_count; ++p) {
                const auto shifted = _mm256_sll_epi32(keys, shifts[p]);
                const auto mask = _mm256_movemask_ps(_mm256_castsi256_ps(shifted));
                words[p] |= static_cast<Word>(mask) << i;
            }
        }
        for (; i < count; ++i) {
            for (std::size_t p = 0; p < plane_count; ++p) {
                words[p] |= static_cast<Word>((data[offset + i] & bits[p]) != 0) << i;
            }
        }
        for (std::size_t p = 0; p < plane_count; ++p) planes[p][offset / word_bits] = words[p];
    }
    return plane_count;
}

template<class Finish>
void emit(const Key* data, const Planes& planes, std::size_t plane_count, std::size_t depth,
          const Positions& positions, Key*& output, Finish& finish) {
    if (positions.count > 4 && depth < plane_count) {
        Positions zeros, ones;
        for (unsigned live = positions.live; live; live &= live - 1) {
            const auto word = __builtin_ctz(live);
            const Word group = positions.words[word];
            const Word one = group & planes[depth][word];
            const Word zero = group ^ one;
            zeros.words[word] = zero;
            ones.words[word] = one;
            zeros.live |= static_cast<unsigned>(zero != 0) << word;
            ones.live |= static_cast<unsigned>(one != 0) << word;
            ones.count += __builtin_popcountll(one);
        }
        zeros.count = positions.count - ones.count;
        // Higher bits are fixed within this group, so every zero precedes every one.
        if (zeros.live) emit(data, planes, plane_count, depth + 1, zeros, output, finish);
        if (ones.live) emit(data, planes, plane_count, depth + 1, ones, output, finish);
        return;
    }

    Key* const begin = output;
    for (unsigned live = positions.live; live; live &= live - 1) {
        const auto word = __builtin_ctz(live);
        for (Word pending = positions.words[word]; pending; pending &= pending - 1) {
            *output++ = data[word * word_bits + __builtin_ctzll(pending)];
        }
    }
    if (positions.count > 4) {
        finish(begin, positions.count);
        return;
    }
    for (auto* key = begin + 1; key < output; ++key) {
        const auto value = *key;
        auto* hole = key;
        while (hole != begin && value < hole[-1]) {
            *hole = hole[-1];
            --hole;
        }
        *hole = value;
    }
}

}  // namespace position_bitmap_detail

// True when maps (or their all-equal certificate) handled the input.
template<class Finish>
bool position_bitmap_u32(std::uint32_t* data, std::size_t n, Finish&& finish) {
    using namespace position_bitmap_detail;
    if (n <= 128 || n > max_keys) {
        if (n > 1) finish(data, n);
        return false;
    }

    const auto varying = varying_bits(data, n);
    if (!varying) return true;
    Planes planes;
    const auto plane_count = build_planes(data, n, varying, planes);

    Positions root;
    root.count = n;
    const auto word_count = (n + word_bits - 1) / word_bits;
    root.live = (1u << word_count) - 1;
    for (std::size_t word = 0; word < word_count; ++word) {
        const auto count = std::min(word_bits, n - word * word_bits);
        root.words[word] = ~Word{0} >> (word_bits - count);
    }

    alignas(64) std::array<Key, max_keys> result;
    Key* output = result.data();
    emit(data, planes, plane_count, 0, root, output, finish);
    std::copy_n(result.data(), n, data);
    return true;
}

}  // namespace supersort
