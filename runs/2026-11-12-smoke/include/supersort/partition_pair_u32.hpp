// Adapted from Highway's hwy/contrib/sort/vqsort-inl.h, Copyright 2021 Google
// LLC and Copyright 2024 Arm Limited and/or its affiliates.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

// Include after the static Highway vqsort-inl.h for the selected SIMD target.
namespace supersort::e059 {
namespace hn = hwy::HWY_NAMESPACE;
using Tag = hn::SortTag<std::uint32_t>;
using Vec = hn::Vec<Tag>;
using Traits = hn::detail::MakeTraits<std::uint32_t, hwy::SortAscending>;

namespace partition_detail {

using Key = std::uint32_t;
constexpr auto unroll = hwy::SortConstants::kPartitionUnroll;
static_assert(unroll == 4, "Match the four-vector Highway partition block");

class PartitionState {
public:
    HWY_INLINE PartitionState(Key* keys, std::size_t size, Vec pivot, Key* buf)
        : keys_(keys), buf_(buf), pivot_(pivot), read_left_(keys) {
        const Tag d;
        const auto lanes = hn::Lanes(d);
        const auto block = unroll * lanes;
        const Traits traits;
        const auto main = hn::detail::PartitionRightmost(
            d, traits, keys_, size, pivot_, buffered_left_, remaining_, buf_);
        HWY_DASSERT(main + buffered_left_ == remaining_);
        read_right_ = keys_ + main;
        if (HWY_LIKELY(main != 0)) {
            HWY_DASSERT(main >= 2 * block && main % block == 0);
            left_edge_[0] = hn::LoadU(d, read_left_ + 0 * lanes);
            left_edge_[1] = hn::LoadU(d, read_left_ + 1 * lanes);
            left_edge_[2] = hn::LoadU(d, read_left_ + 2 * lanes);
            left_edge_[3] = hn::LoadU(d, read_left_ + 3 * lanes);
            read_left_ += block;
            read_right_ -= block;
            right_edge_[0] = hn::LoadU(d, read_right_ + 0 * lanes);
            right_edge_[1] = hn::LoadU(d, read_right_ + 1 * lanes);
            right_edge_[2] = hn::LoadU(d, read_right_ + 2 * lanes);
            right_edge_[3] = hn::LoadU(d, read_right_ + 3 * lanes);
        }
    }

    HWY_INLINE bool pending() const { return read_left_ != read_right_; }

    HWY_INLINE void step() {
        const Tag d;
        const auto lanes = hn::Lanes(d);
        const auto block = unroll * lanes;
        const auto prefetch_bytes = 3 * block * sizeof(Key);
        const auto capacity_left = static_cast<std::size_t>(
            (read_left_ - keys_) - static_cast<std::ptrdiff_t>(write_left_));
        HWY_DASSERT(pending() && capacity_left <= 2 * block);

        // The two holes total two blocks. Read from the end with less space.
        // Form prefetch addresses as integers because a hint can pass an edge.
        Vec v0, v1, v2, v3;
        if (capacity_left > block) {
            read_right_ -= block;
            v0 = hn::LoadU(d, read_right_ + 0 * lanes);
            v1 = hn::LoadU(d, read_right_ + 1 * lanes);
            v2 = hn::LoadU(d, read_right_ + 2 * lanes);
            v3 = hn::LoadU(d, read_right_ + 3 * lanes);
            hwy::Prefetch(reinterpret_cast<const Key*>(
                reinterpret_cast<std::uintptr_t>(read_right_) - prefetch_bytes));
        } else {
            v0 = hn::LoadU(d, read_left_ + 0 * lanes);
            v1 = hn::LoadU(d, read_left_ + 1 * lanes);
            v2 = hn::LoadU(d, read_left_ + 2 * lanes);
            v3 = hn::LoadU(d, read_left_ + 3 * lanes);
            read_left_ += block;
            hwy::Prefetch(reinterpret_cast<const Key*>(
                reinterpret_cast<std::uintptr_t>(read_left_) + prefetch_bytes));
        }
        hn::detail::StoreLeftRight4(d, Traits{}, v0, v1, v2, v3, pivot_,
                                    keys_, write_left_, remaining_);
    }

    HWY_INLINE std::size_t finish() {
        HWY_DASSERT(!pending());
        const Tag d;
        const Traits traits;
        auto write_right = remaining_;
        if (HWY_LIKELY(read_left_ != keys_)) {
            hn::detail::StoreLeftRight4(d, traits, left_edge_[0], left_edge_[1],
                                        left_edge_[2], left_edge_[3], pivot_,
                                        keys_, write_left_, remaining_);
            hn::detail::StoreLeftRight(d, traits, right_edge_[0], pivot_,
                                       keys_, write_left_, remaining_);
            hn::detail::StoreLeftRight(d, traits, right_edge_[1], pivot_,
                                       keys_, write_left_, remaining_);
            HWY_DASSERT(remaining_ == buffered_left_ + 2 * hn::Lanes(d));
            write_right = write_left_ + remaining_;
            hn::detail::StoreRightAndBuf(d, traits, right_edge_[2], pivot_,
                                         keys_, write_right, buf_, buffered_left_);
            hn::detail::StoreRightAndBuf(d, traits, right_edge_[3], pivot_,
                                         keys_, write_right, buf_, buffered_left_);
        }
        HWY_DASSERT(write_left_ + buffered_left_ == write_right);
        hwy::CopyBytes(buf_, keys_ + write_left_, buffered_left_ * sizeof(Key));
        return write_left_ + buffered_left_;
    }

    HWY_INLINE std::size_t drain() {
        while (pending()) step();
        return finish();
    }

private:
    Key* keys_;
    Key* buf_;
    Vec pivot_;
    const Key* read_left_;
    const Key* read_right_;
    std::size_t write_left_ = 0;
    std::size_t remaining_;
    std::size_t buffered_left_;
    Vec left_edge_[4];
    Vec right_edge_[4];
};

}  // namespace partition_detail

// Ranges must be disjoint, each longer than two vectors. Both pivots are
// broadcast. Supply two disjoint Highway partition buffers with their usual
// size and alignment, separate from the keys.
template <bool Alternate>
HWY_INLINE std::array<std::size_t, 2> partition_pair(
    std::uint32_t* left, std::size_t nl, Vec pl,
    std::uint32_t* right, std::size_t nr, Vec pr,
    std::uint32_t* left_buf, std::uint32_t* right_buf) {
    using partition_detail::PartitionState;
    if constexpr (Alternate) {
        PartitionState first(left, nl, pl, left_buf);
        PartitionState second(right, nr, pr, right_buf);
        while (first.pending() && second.pending()) {
            first.step();
            second.step();
        }
        if (!first.pending()) {
            const auto left_bound = first.finish();
            return {left_bound, second.drain()};
        }
        const auto right_bound = second.finish();
        return {first.drain(), right_bound};
    } else {
        const auto left_bound = PartitionState(left, nl, pl, left_buf).drain();
        const auto right_bound = PartitionState(right, nr, pr, right_buf).drain();
        return {left_bound, right_bound};
    }
}

}  // namespace supersort::e059
