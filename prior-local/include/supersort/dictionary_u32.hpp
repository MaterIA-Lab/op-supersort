#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>
#include <limits>

void vq_sort_u32(std::uint32_t*, std::size_t);

namespace supersort {

enum class DictionaryRoute { bypass, collision, reject, counted };

struct DictionaryWork {
    DictionaryRoute route;
    std::size_t examined;
    std::size_t proposals;
};

namespace dictionary_detail {

using Key = std::uint32_t;
constexpr std::size_t max_keys = 16;
constexpr std::size_t table_size = 256;
using Keys = std::array<Key, max_keys>;

inline std::size_t propose(const Key* a, std::size_t n, Keys& keys) {
    std::size_t count = 0;
    const auto stride = n / 256;
    for (std::size_t i = 0; i < 256; ++i) {
        const auto key = a[i * stride];
        if (std::find(keys.data(), keys.data() + count, key) != keys.data() + count) continue;
        if (count == max_keys) return max_keys + 1;
        keys[count++] = key;
    }
    return count;
}

inline std::size_t distinct_projections(const Keys& keys, std::size_t count, Key mask) {
    Keys projections;
    std::size_t distinct = 0;
    for (std::size_t i = 0; i < count; ++i) {
        const auto projected = keys[i] & mask;
        if (std::find(projections.data(), projections.data() + distinct, projected) ==
            projections.data() + distinct) {
            projections[distinct++] = projected;
        }
    }
    return distinct;
}

inline Key distinguish(const Keys& keys, std::size_t count) {
    Key mask = 0;
    std::size_t best = 1;
    for (unsigned step = 0; step < 8; ++step) {
        Key chosen = 0;
        for (unsigned bit = 0; bit < 32; ++bit) {
            const Key flag = Key{1} << bit;
            if (mask & flag) continue;
            const auto unique = distinct_projections(keys, count, mask | flag);
            if (unique == count) return mask | flag;
            if (unique > best) {
                best = unique;
                chosen = flag;
            }
        }
        if (!chosen) break;
        mask |= chosen;
    }
    return 0;
}

template<unsigned Banks>
inline DictionaryWork count_keys(Key* a, std::size_t n, const Keys& keys,
                                 std::size_t count, Key mask) {
    std::array<Key, table_size> witness;
    witness.fill(keys[0]);
    for (std::size_t j = 0; j < count; ++j) witness[_pext_u32(keys[j], mask)] = keys[j];
    std::array<std::array<Key, table_size>, Banks> counts{};
    std::size_t i = 0;
    for (; n - i >= 4; i += 4) {
        const auto a0 = a[i];
        const auto a1 = a[i + 1];
        const auto a2 = a[i + 2];
        const auto a3 = a[i + 3];
        const auto p0 = _pext_u32(a0, mask);
        const auto p1 = _pext_u32(a1, mask);
        const auto p2 = _pext_u32(a2, mask);
        const auto p3 = _pext_u32(a3, mask);
        if ((a0 ^ witness[p0]) | (a1 ^ witness[p1]) | (a2 ^ witness[p2]) | (a3 ^ witness[p3])) {
            return {DictionaryRoute::reject, i + 4, count};
        }
        ++counts[0][p0];
        ++counts[1 % Banks][p1];
        ++counts[2 % Banks][p2];
        ++counts[3 % Banks][p3];
    }
    for (; i < n; ++i) {
        const auto key = a[i];
        const auto slot = _pext_u32(key, mask);
        if (witness[slot] != key) return {DictionaryRoute::reject, i + 1, count};
        ++counts[0][slot];
    }
    for (std::size_t j = 0; j < count; ++j) {
        const auto key = keys[j];
        const auto slot = _pext_u32(key, mask);
        Key multiplicity = 0;
        for (const auto& bank : counts) multiplicity += bank[slot];
        std::fill_n(a, multiplicity, key);
        a += multiplicity;
    }
    return {DictionaryRoute::counted, n, count};
}

}  // namespace dictionary_detail

template<unsigned Banks>
inline DictionaryWork dictionary_u32(std::uint32_t* a, std::size_t n) {
    static_assert(Banks == 1 || Banks == 4);
    using namespace dictionary_detail;
    DictionaryWork work{DictionaryRoute::bypass, 0, 0};
    if (n >= (1u << 18) && n <= std::numeric_limits<Key>::max()) {
        Keys keys;
        work.proposals = propose(a, n, keys);
        if (work.proposals >= 2 && work.proposals <= max_keys) {
            std::sort(keys.data(), keys.data() + work.proposals);
            const auto mask = distinguish(keys, work.proposals);
            if (mask) {
                work = count_keys<Banks>(a, n, keys, work.proposals, mask);
                if (work.route == DictionaryRoute::counted) return work;
            } else {
                work.route = DictionaryRoute::collision;
            }
        }
    }
    if (n > 1) vq_sort_u32(a, n);
    return work;
}

}  // namespace supersort
