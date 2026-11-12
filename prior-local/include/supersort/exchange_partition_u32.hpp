#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>
#include <limits>
#include <utility>

namespace supersort {
namespace exchange_partition_detail {

constexpr std::size_t lanes = 8;

constexpr std::array<std::uint64_t, 256> byte_masks() {
    std::array<std::uint64_t, 256> table{};
    for (unsigned mask = 0; mask < table.size(); ++mask) {
        for (unsigned lane = 0; lane < lanes; ++lane) {
            if (mask & (1u << lane)) table[mask] |= std::uint64_t{0xff} << (8 * lane);
        }
    }
    return table;
}

inline constexpr auto lane_bytes = byte_masks();

inline unsigned greater_mask(__m256i keys, __m256i sign_bit, __m256i pivot) {
    const auto greater = _mm256_cmpgt_epi32(_mm256_xor_si256(keys, sign_bit), pivot);
    return static_cast<unsigned>(_mm256_movemask_ps(_mm256_castsi256_ps(greater)));
}

inline __m256i replace_lanes(__m256i dst, __m256i src, std::uint64_t dst_mask,
                            std::uint64_t src_mask) {
    constexpr std::uint64_t lane_ids = 0x0706050403020100;
    constexpr std::uint64_t signs = 0x8080808080808080;
    const auto packed = _pext_u64(lane_ids, src_mask);
    const auto scattered = _pdep_u64(packed, dst_mask);
    // Selected bytes hold source indices. The other bytes keep their original
    // destination lanes by setting the sign bit used by blendv.
    const auto index_bytes = scattered | (~dst_mask & signs);
    const auto indices = _mm256_cvtepi8_epi32(_mm_cvtsi64_si128(static_cast<long long>(index_bytes)));
    const auto permuted = _mm256_permutevar8x32_epi32(src, indices);
    return _mm256_castps_si256(_mm256_blendv_ps(_mm256_castsi256_ps(permuted),
                                              _mm256_castsi256_ps(dst),
                                              _mm256_castsi256_ps(indices)));
}

}  // namespace exchange_partition_detail

// Moves keys <= pivot before keys > pivot and returns the first right index.
template<bool Track = false>
std::size_t exchange_partition_u32(std::uint32_t* data, std::size_t n, std::uint32_t pivot,
                                   std::size_t* written_keys = nullptr) {
    using namespace exchange_partition_detail;
    constexpr auto min_i32 = std::numeric_limits<std::int32_t>::min();
    const auto sign_bit = _mm256_set1_epi32(min_i32);
    const auto signed_pivot = _mm256_set1_epi32(static_cast<std::int32_t>(std::int64_t{pivot} + min_i32));
    std::size_t left = 0, right = n;
    __m256i left_keys, right_keys;
    unsigned left_bad = 0, right_bad = 0;
    bool left_dirty = false, right_dirty = false;
    std::size_t written = 0;
    const auto flush = [&](std::size_t offset, __m256i keys) {
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(data + offset), keys);
        if constexpr (Track) written += lanes;
    };

    // Each nonempty mask denotes an active vector held at its original index.
    // Load a new vector only when that side has no work pending.
    while (right - left >= 2 * lanes) {
        if (!left_bad) {
            left_keys = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(data + left));
            left_bad = greater_mask(left_keys, sign_bit, signed_pivot);
            left_dirty = false;
            if (!left_bad) {
                left += lanes;
                continue;
            }
        }
        if (!right_bad) {
            right_keys = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(data + right - lanes));
            right_bad = greater_mask(right_keys, sign_bit, signed_pivot) ^ 255u;
            right_dirty = false;
            if (!right_bad) {
                right -= lanes;
                continue;
            }
        }

        const auto left_count = __builtin_popcount(left_bad);
        const auto right_count = __builtin_popcount(right_bad);
        const auto count = left_count < right_count ? left_count : right_count;
        const auto prefix = (1u << count) - 1;
        const auto take_left = _pdep_u32(prefix, left_bad);
        const auto take_right = _pdep_u32(prefix, right_bad);
        const auto left_bytes = lane_bytes[take_left];
        const auto right_bytes = lane_bytes[take_right];
        const auto new_left = replace_lanes(left_keys, right_keys, left_bytes, right_bytes);
        right_keys = replace_lanes(right_keys, left_keys, right_bytes, left_bytes);
        left_keys = new_left;
        left_bad ^= take_left;
        right_bad ^= take_right;
        left_dirty = right_dirty = true;

        if (!left_bad) {
            flush(left, left_keys);
            left += lanes;
        }
        if (!right_bad) {
            flush(right - lanes, right_keys);
            right -= lanes;
        }
    }

    // The unfinished interval has at most 15 keys and contains at most one
    // active vector. Restore it if modified before the exact scalar finish.
    if (left_bad && left_dirty) flush(left, left_keys);
    if (right_bad && right_dirty) flush(right - lanes, right_keys);
    while (left < right) {
        while (left < right && data[left] <= pivot) ++left;
        while (left < right && data[right - 1] > pivot) --right;
        if (left == right) break;
        std::swap(data[left], data[right - 1]);
        ++left;
        --right;
        if constexpr (Track) written += 2;
    }
    if constexpr (Track) {
        if (written_keys) *written_keys = written;
    }
    return left;
}

}  // namespace supersort
