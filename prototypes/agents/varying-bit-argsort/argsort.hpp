#pragma once

#include <algorithm>
#include <bit>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>
#include <memory>
#include <numeric>
#include <span>
#include <utility>

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>
#include <pdqsort.h>

namespace varying_bit_argsort {

using Clock = std::chrono::steady_clock;
using Word = std::uint64_t;
using Index = std::uint32_t;

struct alignas(16) Key {
    Word high;
    Word low;
};
static_assert(sizeof(Key) == 16);

inline std::uint64_t nanoseconds(Clock::time_point start, Clock::time_point end) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
}

inline std::uint64_t low_mask(unsigned bits) {
    return bits == 64 ? ~Word{0} : (Word{1} << bits) - 1;
}

inline bool key_less(const Key& left, const Key& right) {
    return left.high == right.high ? left.low < right.low : left.high < right.high;
}

inline Key variation(std::span<const Key> keys) {
    Key changed{};
    if (!keys.empty()) {
        const Key first = keys.front();
        for (const Key& key : keys) {
            changed.high |= key.high ^ first.high;
            changed.low |= key.low ^ first.low;
        }
    }
    return changed;
}

enum class Method { varying, ranges, leading, pairs, indirect };

struct Projection {
    Word high;
    Word low;
    unsigned low_bits;
    unsigned bits;
    bool exact;
};

inline Word keep_top(Word mask, unsigned bits) {
    const unsigned present = std::popcount(mask);
    return present <= bits ? mask : mask & ~_pdep_u64(low_mask(present - bits), mask);
}

inline Word range_for_32(std::uint32_t bits) {
    return low_mask(std::bit_width(bits)) & ~low_mask(std::countr_zero(bits));
}

inline Word field_ranges(Word bits) {
    return (range_for_32(static_cast<std::uint32_t>(bits >> 32)) << 32)
           | range_for_32(static_cast<std::uint32_t>(bits));
}

inline Projection choose_projection(Key changed, unsigned budget, Method method) {
    Key chosen = changed;
    if (method == Method::ranges) {
        chosen = {field_ranges(changed.high), field_ranges(changed.low)};
    } else if (method == Method::leading) {
        chosen = changed.high
            ? Key{low_mask(std::bit_width(changed.high)), ~Word{0}}
            : Key{0, low_mask(std::bit_width(changed.low))};
    }
    const Word high = keep_top(chosen.high, budget);
    const unsigned high_bits = std::popcount(high);
    const Word low = keep_top(chosen.low, budget - high_bits);
    const unsigned low_bits = std::popcount(low);
    const bool exact = !(changed.high & ~high) && !(changed.low & ~low);
    return {high, low, low_bits, high_bits + low_bits, exact};
}

struct Stats {
    std::uint64_t prepare_ns = 0;
    std::uint64_t sort_ns = 0;
    std::uint64_t finish_ns = 0;
    std::size_t repaired = 0;
    std::size_t largest_repair = 0;
    std::size_t scratch_bytes = 0;
    unsigned prefix_bits = 0;
};

struct Result {
    std::unique_ptr<Index[]> indices;
    Stats stats;
};

inline void sort_indices(std::span<const Key> keys, Index* begin, Index* end) {
    pdqsort(begin, end, [keys](Index i, Index j) {
        const Key& a = keys[i];
        const Key& b = keys[j];
        if (a.high != b.high) return a.high < b.high;
        if (a.low != b.low) return a.low < b.low;
        return i < j;
    });
}

template<class GetPrefix, class GetIndex>
void finish_groups(std::span<const Key> keys, Index* indices, GetPrefix prefix,
                   GetIndex index, Stats& stats) {
    const std::size_t size = keys.size();
    std::size_t begin = 0;
    while (begin < size) {
        indices[begin] = index(begin);
        const Word group = prefix(begin);
        std::size_t end = begin + 1;
        while (end < size && prefix(end) == group) {
            indices[end] = index(end);
            ++end;
        }
        const auto count = end - begin;
        if (count > 1) {
            stats.repaired += count;
            stats.largest_repair = std::max(stats.largest_repair, count);
            sort_indices(keys, indices + begin, indices + end);
        }
        begin = end;
    }
}

inline void encode_tags(std::span<const Key> keys, Word* tags, Projection plan,
                        unsigned index_bits, Method method) {
    if (method == Method::leading) {
        const unsigned high_shift = std::countr_zero(plan.high) & 63;
        const unsigned low_shift = std::countr_zero(plan.low) & 63;
        for (std::size_t i = 0; i < keys.size(); ++i) {
            const Key& key = keys[i];
            const Word high = ((key.high & plan.high) >> high_shift) << plan.low_bits;
            const Word low = (key.low & plan.low) >> low_shift;
            tags[i] = ((high | low) << index_bits) | i;
        }
    } else {
        for (std::size_t i = 0; i < keys.size(); ++i) {
            const Key& key = keys[i];
            const Word prefix = (_pext_u64(key.high, plan.high) << plan.low_bits)
                                | _pext_u64(key.low, plan.low);
            tags[i] = (prefix << index_bits) | i;
        }
    }
}

// The returned uint32 indices require at most 2^32 input keys.
inline Result argsort(std::span<const Key> keys, Method method) {
    const auto start = Clock::now();
    const auto size = keys.size();
    auto indices = std::make_unique_for_overwrite<Index[]>(size);
    if (size < 2) {
        if (size == 1) indices[0] = 0;
        return {std::move(indices), {}};
    }

    Stats stats;
    if (method == Method::indirect) {
        std::iota(indices.get(), indices.get() + size, Index{0});
        const auto prepared = Clock::now();
        sort_indices(keys, indices.get(), indices.get() + size);
        stats.prepare_ns = nanoseconds(start, prepared);
        stats.sort_ns = nanoseconds(prepared, Clock::now());
    } else if (method == Method::pairs) {
        auto pairs = std::make_unique_for_overwrite<hwy::K64V64[]>(size);
        for (std::size_t i = 0; i < size; ++i) pairs[i] = {i, keys[i].high};
        const auto prepared = Clock::now();
        hwy::HWY_NAMESPACE::VQSortStatic(pairs.get(), size, hwy::SortAscending());
        const auto sorted = Clock::now();
        finish_groups(keys, indices.get(), [&](auto i) { return pairs[i].key; },
                      [&](auto i) { return static_cast<Index>(pairs[i].value); }, stats);
        pairs.reset();
        stats.finish_ns = nanoseconds(sorted, Clock::now());
        stats.prepare_ns = nanoseconds(start, prepared);
        stats.sort_ns = nanoseconds(prepared, sorted);
        stats.prefix_bits = 64;
        stats.scratch_bytes = size * sizeof(hwy::K64V64);
    } else {
        const unsigned index_bits = std::bit_width(size - 1);
        const auto plan = choose_projection(variation(keys), 64 - index_bits, method);
        auto tags = std::make_unique_for_overwrite<Word[]>(size);
        encode_tags(keys, tags.get(), plan, index_bits, method);
        const auto prepared = Clock::now();
        hwy::HWY_NAMESPACE::VQSortStatic(tags.get(), size, hwy::SortAscending());
        const auto sorted = Clock::now();
        const Word index_mask = low_mask(index_bits);
        const auto index = [&](auto i) { return static_cast<Index>(tags[i] & index_mask); };
        if (plan.exact) {
            for (std::size_t i = 0; i < size; ++i) indices[i] = index(i);
        } else {
            finish_groups(keys, indices.get(), [&](auto i) { return tags[i] >> index_bits; },
                          index, stats);
        }
        tags.reset();
        stats.finish_ns = nanoseconds(sorted, Clock::now());
        stats.prepare_ns = nanoseconds(start, prepared);
        stats.sort_ns = nanoseconds(prepared, sorted);
        stats.prefix_bits = plan.bits;
        stats.scratch_bytes = size * sizeof(Word);
    }
    return {std::move(indices), stats};
}

}  // namespace varying_bit_argsort
