#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <immintrin.h>
#include <memory>

void vq_sort_u32(std::uint32_t*, std::size_t);

namespace supersort {

struct CellWork {
    std::size_t skipped = 0;
    std::size_t aborted = 0;
    std::size_t completed = 0;
    std::size_t attempt_reads = 0;
    std::size_t residual = 0;
};

namespace cell_detail {

constexpr std::size_t cell_count = 1 << 16;
constexpr std::size_t cell_capacity = 3 * cell_count;

inline void copy_sort(const std::uint32_t* src, std::uint32_t* dst, std::size_t n) {
    std::memcpy(dst, src, n * sizeof(*src));
    if (n > 1) vq_sort_u32(dst, n);
}

inline void emit(const std::uint32_t* table, unsigned epoch, std::uint32_t prefix,
                 const std::uint32_t* spill, std::size_t spill_size, std::uint32_t* dst) {
    const auto epoch_mask = _mm256_set1_epi32(0xfc);
    const auto count_mask = _mm256_set1_epi32(3);
    const auto tag = _mm256_set1_epi32(epoch << 2);
    const auto zero = _mm256_setzero_si256();
    std::size_t r = 0;
    for (std::size_t first = 0; first < cell_count; first += 8) {
        const auto words = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(table + first));
        const auto headers = _mm256_srli_epi32(words, 24);
        const auto current = _mm256_cmpeq_epi32(_mm256_and_si256(headers, epoch_mask), tag);
        const auto occupied = _mm256_cmpgt_epi32(_mm256_and_si256(headers, count_mask), zero);
        unsigned active = _mm256_movemask_ps(_mm256_castsi256_ps(_mm256_and_si256(current, occupied)));
        while (active) {
            const auto q = first + __builtin_ctz(active);
            active &= active - 1;
            const auto word = table[q];
            const auto count = (word >> 24) & 3;
            const auto base = prefix | (static_cast<std::uint32_t>(q) << 8);
            auto a = base | (word & 255);
            auto b = base | ((word >> 8) & 255);
            auto c = base | ((word >> 16) & 255);
            if (count >= 2 && a > b) std::swap(a, b);
            if (count == 3) {
                if (b > c) std::swap(b, c);
                if (a > b) std::swap(a, b);
            }
            const std::uint32_t values[] = {a, b, c};
            for (unsigned slot = 0; slot < count; ++slot) {
                while (r < spill_size && spill[r] < values[slot]) *dst++ = spill[r++];
                *dst++ = values[slot];
            }
        }
    }
    while (r < spill_size) *dst++ = spill[r++];
}

inline bool try_group(const std::uint32_t* src, std::uint32_t* dst, std::size_t n,
                      std::uint32_t* table, unsigned epoch, CellWork& work) {
    const auto limit = n / 32;
    const std::unique_ptr<std::uint32_t[]> spill(new std::uint32_t[limit]);
    std::size_t spill_size = 0;
    const std::uint32_t tag = epoch << 26;
    for (std::size_t i = 0; i < n; ++i) {
        const auto key = src[i];
        auto& entry = table[(key >> 8) & 65535];
        const auto word = (entry >> 26) == epoch ? entry : tag;
        const auto count = (word >> 24) & 3;
        if (count < 3) {
            entry = (word | ((key & 255) << (8 * count))) + (1u << 24);
        } else {
            if (spill_size == limit) {
                work.attempt_reads += i + 1;
                return false;
            }
            spill[spill_size++] = key;
        }
    }
    work.attempt_reads += n;
    work.residual += spill_size;
    if (spill_size > 1) vq_sort_u32(spill.get(), spill_size);
    emit(table, epoch, src[0] & 0xff000000u, spill.get(), spill_size, dst);
    return true;
}

}  // namespace cell_detail

// The disjoint source contains stable high-byte buckets specified by offsets.
inline void leaf_vq_u32(const std::uint32_t* prepared, std::uint32_t* dst,
                        const std::array<std::size_t, 257>& offsets) {
    for (std::size_t b = 0; b < 256; ++b) {
        const auto first = offsets[b];
        const auto n = offsets[b + 1] - first;
        if (n) cell_detail::copy_sort(prepared + first, dst + first, n);
    }
}

inline CellWork cells_u32(const std::uint32_t* prepared, std::uint32_t* dst,
                          const std::array<std::size_t, 257>& offsets) {
    CellWork work;
    std::unique_ptr<std::uint32_t[]> table;
    unsigned attempts = 0;
    for (std::size_t b = 0; b < 256; ++b) {
        const auto first = offsets[b];
        const auto n = offsets[b + 1] - first;
        if (!n) continue;
        if (n < 4096 || (n > cell_detail::cell_capacity && n - cell_detail::cell_capacity > n / 32)) {
            ++work.skipped;
        } else {
            const auto epoch = attempts++ % 64;
            if (!table) table = std::make_unique<std::uint32_t[]>(cell_detail::cell_count);
            else if (epoch == 0) std::fill_n(table.get(), cell_detail::cell_count, 0);
            if (cell_detail::try_group(prepared + first, dst + first, n, table.get(), epoch, work)) {
                ++work.completed;
                continue;
            }
            ++work.aborted;
        }
        cell_detail::copy_sort(prepared + first, dst + first, n);
    }
    return work;
}

}  // namespace supersort
