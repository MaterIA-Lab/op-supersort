#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>

namespace supersort {

class FrontierKernel {
    using Key = std::uint32_t;
    static constexpr std::size_t max_keys = 32768;
    static constexpr unsigned digit_bits = 12;
    static constexpr std::size_t digits = std::size_t{1} << digit_bits;
    static constexpr Key digit_mask = digits - 1;
    static constexpr Key max_range = (Key{1} << (2 * digit_bits)) - 1;
    using Histogram = std::array<Key, digits>;

public:
    // A rejected span is untouched so the caller can reuse its original sorter.
    bool sort(Key* keys, std::size_t n) {
        if (n < 256 || n > max_keys) return false;

        const auto bounds = minmax(keys, n);
        const Key base = bounds[0];
        const Key range = bounds[1] - base;
        if (range > max_range) return false;
        if (range == 0) return true;

        const auto low_digits = std::min(digits, std::size_t(range) + 1);
        const auto high_digits = std::size_t(range >> digit_bits) + 1;
        std::fill_n(low_.begin(), low_digits, 0);
        if (high_digits == 1) {
            for (std::size_t i = 0; i < n; ++i) ++low_[keys[i] - base];
            to_offsets(low_, low_digits);
            for (std::size_t i = 0; i < n; ++i) {
                const Key key = keys[i];
                scratch_[low_[key - base]++] = key;
            }
            std::copy_n(scratch_.begin(), n, keys);
            return true;
        }

        std::fill_n(high_.begin(), high_digits, 0);
        for (std::size_t i = 0; i < n; ++i) {
            const Key delta = keys[i] - base;
            ++low_[delta & digit_mask];
            ++high_[delta >> digit_bits];
        }
        to_offsets(low_, low_digits);
        to_offsets(high_, high_digits);
        for (std::size_t i = 0; i < n; ++i) {
            const Key delta = keys[i] - base;
            scratch_[low_[delta & digit_mask]++] = delta;
        }
        for (std::size_t i = 0; i < n; ++i) {
            const Key delta = scratch_[i];
            keys[high_[delta >> digit_bits]++] = base + delta;
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

    static void to_offsets(Histogram& counts, std::size_t count) {
        Key offset = 0;
        for (std::size_t d = 0; d < count; ++d) {
            const Key size = counts[d];
            counts[d] = offset;
            offset += size;
        }
    }

    alignas(64) std::array<Key, max_keys> scratch_;
    Histogram low_;
    Histogram high_;
};

}  // namespace supersort
