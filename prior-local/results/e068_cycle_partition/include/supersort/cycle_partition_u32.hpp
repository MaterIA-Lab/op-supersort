#pragma once

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

namespace supersort {

// map has one entry per 16-bit prefix, with values in [0, 512). bounds has
// 513 entries starting at zero and is the exclusive scan of the exact counts.
template<bool Track = false>
std::size_t cycle_partition_u32(std::uint32_t* data, const std::uint16_t* map,
                                const std::size_t* bounds) {
    constexpr std::size_t bucket_count = 512;
    if (bounds[bucket_count] == 0) return 0;

    std::array<std::uint32_t*, bucket_count> next;
    for (std::size_t bucket = 0; bucket < bucket_count; ++bucket) {
        next[bucket] = data + bounds[bucket];
    }

    std::size_t writes = 0;
    for (std::size_t bucket = 0; bucket < bucket_count; ++bucket) {
        auto* cursor = next[bucket];
        auto* const end = data + bounds[bucket + 1];
        while (cursor != end) {
            auto* const hole = cursor++;
            auto key = *hole;
            auto destination = map[key >> 16];
            if (destination == bucket) continue;

            // A completed bucket cannot be a destination. A different bucket
            // with an incoming key still has an incorrect unresolved position.
            // Keep that displaced key and its classification for the next step.
            while (destination != bucket) {
                auto* slot = next[destination];
                std::uint32_t displaced;
                std::uint16_t displaced_bucket;
                do {
                    assert(slot < data + bounds[destination + 1]);
                    displaced = *slot++;
                    displaced_bucket = map[displaced >> 16];
                } while (displaced_bucket == destination);
                next[destination] = slot;
                slot[-1] = key;
                if constexpr (Track) ++writes;
                key = displaced;
                destination = displaced_bucket;
            }
            *hole = key;
            if constexpr (Track) ++writes;
        }
        next[bucket] = end;
    }
    return writes;
}

}  // namespace supersort
