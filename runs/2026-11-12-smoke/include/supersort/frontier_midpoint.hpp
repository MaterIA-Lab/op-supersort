#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>

namespace supersort {

// Include after the static Highway vqsort implementation.
namespace frontier_midpoint_detail {
namespace hn = hwy::HWY_NAMESPACE;
}

class FrontierKernel {
    using Key = std::uint32_t;
    using Tag = frontier_midpoint_detail::hn::SortTag<Key>;
    using Traits = frontier_midpoint_detail::hn::detail::MakeTraits<Key, hwy::SortAscending>;
    static constexpr std::size_t max_keys = 32768;
    static constexpr std::size_t scratch_size = hwy::SortConstants::BufBytes<Key>(HWY_MAX_BYTES) / sizeof(Key);

public:
    bool sort(Key* keys, std::size_t n) {
        if (n < 256 || n > max_keys) return false;
        const auto bounds = minmax(keys, n);
        descend(keys, n, bounds[0], bounds[1]);
        return true;
    }

private:
    HWY_NOINLINE void descend(Key* keys, std::size_t n, Key lo, Key hi) {
        namespace hn = frontier_midpoint_detail::hn;
        if (n <= 1 || lo == hi) return;
        const Tag d;
        const Traits traits;
        if (n <= hwy::SortConstants::BaseCaseNumLanes(hn::Lanes(d))) {
            hn::detail::BaseCase(d, traits, keys, n, scratch_);
            return;
        }

        // The interval is inclusive, so the right side starts at midpoint + 1.
        const Key midpoint = lo + (hi - lo) / 2;
        const auto left = hn::detail::Partition(d, traits, keys, n, hn::Set(d, midpoint), scratch_);
        const auto right = n - left;
        if (std::min(left, right) < n / 8) {
            hn::VQSortStatic(keys, n, hwy::SortAscending{});
            return;
        }

        descend(keys, left, lo, midpoint);
        descend(keys + left, right, midpoint + 1, hi);
    }

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

    HWY_ALIGN Key scratch_[scratch_size];
};

}  // namespace supersort
