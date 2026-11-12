#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>

namespace supersort {

// Include after the static Highway vqsort implementation.
class FrontierKernel {
    using Key = std::uint32_t;
    using Suffix = std::uint16_t;
    static constexpr std::size_t max_keys = 32768;
    static constexpr unsigned suffix_bits = 16;
    static constexpr std::size_t buckets = 256;
    static constexpr Key max_range = (Key{1} << 24) - 1;

public:
    bool sort(Key* keys, std::size_t n) {
        if (n < 256 || n > max_keys) return false;
        const auto bounds = minmax(keys, n);
        const Key base = bounds[0];
        const Key range = bounds[1] - base;
        if (range > max_range) return false;
        if (range == 0) return true;

        const auto active = std::size_t(range >> suffix_bits) + 1;
        std::fill_n(ends_.begin(), active, 0);
        for (std::size_t i = 0; i < n; ++i) ++ends_[(keys[i] - base) >> suffix_bits];
        Key offset = 0;
        for (std::size_t bucket = 0; bucket < active; ++bucket) {
            const Key size = ends_[bucket];
            ends_[bucket] = offset;
            offset += size;
        }
        for (std::size_t i = 0; i < n; ++i) {
            const Key delta = keys[i] - base;
            scratch_[ends_[delta >> suffix_bits]++] = static_cast<Suffix>(delta);
        }

        // Advancing the insertion cursors leaves each one at its bucket end.
        std::size_t begin = 0;
        for (std::size_t bucket = 0; bucket < active; ++bucket) {
            const auto end = ends_[bucket];
            const auto count = end - begin;
            auto* leaf = scratch_.data() + begin;
            if (count > 1) hwy::HWY_NAMESPACE::VQSortStatic(leaf, count, hwy::SortAscending{});
            expand(leaf, keys + begin, count, base + (Key(bucket) << suffix_bits));
            begin = end;
        }
        return true;
    }

private:
    static std::array<Key, 2> minmax(const Key* keys, std::size_t n) {
        auto minimum = _mm256_set1_epi32(-1);
        auto maximum = _mm256_setzero_si256();
        std::size_t i = 0;
        for (; n - i >= 8; i += 8) {
            const auto block = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(keys + i));
            minimum = _mm256_min_epu32(minimum, block);
            maximum = _mm256_max_epu32(maximum, block);
        }
        alignas(32) std::array<Key, 8> mins, maxs;
        _mm256_store_si256(reinterpret_cast<__m256i*>(mins.data()), minimum);
        _mm256_store_si256(reinterpret_cast<__m256i*>(maxs.data()), maximum);
        Key lo = *std::min_element(mins.begin(), mins.end());
        Key hi = *std::max_element(maxs.begin(), maxs.end());
        for (; i < n; ++i) {
            lo = std::min(lo, keys[i]);
            hi = std::max(hi, keys[i]);
        }
        return {lo, hi};
    }

    static void expand(const Suffix* suffixes, Key* keys, std::size_t n, Key base) {
        const auto head = _mm256_set1_epi32(static_cast<int>(base));
        std::size_t i = 0;
        for (; n - i >= 8; i += 8) {
            const auto words = _mm_loadu_si128(reinterpret_cast<const __m128i*>(suffixes + i));
            const auto block = _mm256_add_epi32(head, _mm256_cvtepu16_epi32(words));
            _mm256_storeu_si256(reinterpret_cast<__m256i*>(keys + i), block);
        }
        for (; i < n; ++i) keys[i] = base + suffixes[i];
    }

    alignas(64) std::array<Suffix, max_keys> scratch_;
    std::array<Key, buckets> ends_;
};

}  // namespace supersort
