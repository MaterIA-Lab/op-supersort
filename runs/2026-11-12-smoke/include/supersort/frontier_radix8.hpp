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
    static constexpr unsigned digit_bits = 8;
    static constexpr std::size_t digits = std::size_t{1} << digit_bits;
    static constexpr Key digit_mask = digits - 1;
    static constexpr Key max_range = (Key{1} << (3 * digit_bits)) - 1;
    using Histogram = std::array<Key, digits>;

public:
    bool sort(Key* keys, std::size_t n) {
        if (n < 256 || n > max_keys) return false;
        const auto bounds = minmax(keys, n);
        const Key base = bounds[0];
        const Key range = bounds[1] - base;
        if (range > max_range) return false;
        if (range == 0) return true;
        if (range <= digit_mask) radix<1>(keys, n, base, range);
        else if (range <= (Key{1} << (2 * digit_bits)) - 1) radix<2>(keys, n, base, range);
        else radix<3>(keys, n, base, range);
        return true;
    }

private:
    template<unsigned Passes>
    void radix(Key* keys, std::size_t n, Key base, Key range) {
        const auto last_digits = std::size_t(range >> ((Passes - 1) * digit_bits)) + 1;
        for (unsigned pass = 0; pass < Passes; ++pass) {
            const auto count = pass + 1 == Passes ? last_digits : digits;
            std::fill_n(histograms_[pass].begin(), count, 0);
        }
        for (std::size_t i = 0; i < n; ++i) {
            const Key delta = keys[i] - base;
            ++histograms_[0][delta & digit_mask];
            if constexpr (Passes >= 2) ++histograms_[1][(delta >> digit_bits) & digit_mask];
            if constexpr (Passes == 3) ++histograms_[2][delta >> (2 * digit_bits)];
        }
        for (unsigned pass = 0; pass < Passes; ++pass) {
            const auto count = pass + 1 == Passes ? last_digits : digits;
            to_offsets(histograms_[pass], count);
        }

        for (std::size_t i = 0; i < n; ++i) {
            const Key key = keys[i];
            const Key delta = key - base;
            first_[histograms_[0][delta & digit_mask]++] = Passes == 1 ? key : delta;
        }
        if constexpr (Passes == 1) {
            std::copy_n(first_.begin(), n, keys);
        } else if constexpr (Passes == 2) {
            scatter<digit_bits>(first_.data(), keys, n, histograms_[1], base);
        } else {
            scatter<digit_bits>(first_.data(), second_.data(), n, histograms_[1], 0);
            scatter<2 * digit_bits>(second_.data(), keys, n, histograms_[2], base);
        }
    }

    template<unsigned Shift>
    static void scatter(const Key* input, Key* output, std::size_t n, Histogram& offsets, Key base) {
        for (std::size_t i = 0; i < n; ++i) {
            const Key delta = input[i];
            output[offsets[(delta >> Shift) & digit_mask]++] = delta + base;
        }
    }

    static void to_offsets(Histogram& counts, std::size_t count) {
        Key offset = 0;
        for (std::size_t d = 0; d < count; ++d) {
            const Key size = counts[d];
            counts[d] = offset;
            offset += size;
        }
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

    alignas(64) std::array<Key, max_keys> first_;
    alignas(64) std::array<Key, max_keys> second_;
    std::array<Histogram, 3> histograms_;
};

}  // namespace supersort
