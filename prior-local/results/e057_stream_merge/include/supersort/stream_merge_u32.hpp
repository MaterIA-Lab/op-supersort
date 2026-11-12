#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>

namespace supersort {
namespace stream_merge_detail {

using Key = std::uint32_t;
constexpr std::size_t lanes = 8;
constexpr std::size_t block_keys = 2048;

inline __m256i sort_bitonic(__m256i keys) {
    auto opposite = _mm256_permute2x128_si256(keys, keys, 1);
    keys = _mm256_blend_epi32(_mm256_min_epu32(keys, opposite), _mm256_max_epu32(keys, opposite), 0xf0);
    opposite = _mm256_shuffle_epi32(keys, _MM_SHUFFLE(1, 0, 3, 2));
    keys = _mm256_blend_epi32(_mm256_min_epu32(keys, opposite), _mm256_max_epu32(keys, opposite), 0xcc);
    opposite = _mm256_shuffle_epi32(keys, _MM_SHUFFLE(2, 3, 0, 1));
    return _mm256_blend_epi32(_mm256_min_epu32(keys, opposite), _mm256_max_epu32(keys, opposite), 0xaa);
}

// The two ascending inputs split into the lowest eight keys and a sorted carry.
inline __m256i merge_vector(__m256i& carry, __m256i incoming) {
    const auto reversed = _mm256_permutevar8x32_epi32(incoming, _mm256_setr_epi32(7, 6, 5, 4, 3, 2, 1, 0));
    const auto low = _mm256_min_epu32(carry, reversed);
    carry = sort_bitonic(_mm256_max_epu32(carry, reversed));
    return sort_bitonic(low);
}

struct Slice {
    const Key* next;
    const Key* end;

    std::size_t size() const { return end - next; }

    __m256i take_vector() {
        const auto result = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(next));
        next += lanes;
        return result;
    }
};

struct Run : Slice {
    Run(const Key* first, const Key* last) : Slice{first, last} {}

    bool ready() const { return next != end; }
};

template<class Input>
class Merge {
public:
    Merge(Input& left, Input& right) : left_(left), right_(right) {}

    // Repeated writes resume the same merge. The caller supplies exact counts.
    void write(Key* out, std::size_t count) {
        if (count == 0) return;
        const auto limit = out + count;
        if (!started_) {
            started_ = true;
            if (count >= lanes && left_.ready() && right_.ready() && left_.size() >= lanes && right_.size() >= lanes) {
                carry_ = left_.take_vector();
                _mm256_storeu_si256(reinterpret_cast<__m256i*>(out), merge_vector(carry_, right_.take_vector()));
                out += lanes;
                vector_ = true;
            }
        }

        if (vector_) {
            auto carry = carry_;
            while (limit - out >= lanes) {
                auto* input = first();
                if (!input || input->size() < lanes) break;
                _mm256_storeu_si256(reinterpret_cast<__m256i*>(out), merge_vector(carry, input->take_vector()));
                out += lanes;
            }
            if (out == limit) {
                carry_ = carry;
                return;
            }
            _mm256_storeu_si256(reinterpret_cast<__m256i*>(tail_.data()), carry);
            tail_next_ = 0;
            vector_ = false;
        }

        // Only the final slice can have fewer than eight keys. Once a short
        // slice participates, finish with exact comparisons against the carry.
        while (out != limit) {
            auto* input = first();
            if (tail_next_ != lanes && (!input || tail_[tail_next_] <= *input->next)) {
                *out++ = tail_[tail_next_++];
            } else if (tail_next_ == lanes && (left_.size() == 0 || right_.size() == 0)) {
                const auto take = std::min(std::size_t(limit - out), input->size());
                std::copy_n(input->next, take, out);
                input->next += take;
                out += take;
            } else {
                *out++ = *input->next++;
            }
        }
    }

private:
    Input* first() {
        const bool has_left = left_.ready();
        const bool has_right = right_.ready();
        if (!has_left) return has_right ? &right_ : nullptr;
        if (!has_right || *left_.next <= *right_.next) return &left_;
        return &right_;
    }

    Input& left_;
    Input& right_;
    __m256i carry_;
    std::array<Key, lanes> tail_;
    std::size_t tail_next_ = lanes;
    bool started_ = false;
    bool vector_ = false;
};

class BlockRun : public Slice {
public:
    BlockRun(const Key* first, const Key* middle, const Key* last, Key* block)
        : Slice{block, block}, left_(first, middle), right_(middle, last), producer_(left_, right_),
          block_(block), remaining_(last - first) {}

    BlockRun(const BlockRun&) = delete;
    BlockRun& operator=(const BlockRun&) = delete;

    bool ready() {
        if (next != end) return true;
        if (remaining_ == 0) return false;
        refill();
        return true;
    }

private:
    // Keep the producer and its vector carry off the consumer's hot path.
    [[gnu::noinline]] void refill() {
        const auto count = std::min(remaining_, block_keys);
        producer_.write(block_, count);
        remaining_ -= count;
        next = block_;
        end = block_ + count;
    }

    Run left_;
    Run right_;
    Merge<Run> producer_;
    Key* block_;
    std::size_t remaining_;
};

inline void merge_two(const Key* first, const Key* middle, const Key* last, Key* dest) {
    Run left(first, middle), right(middle, last);
    Merge(left, right).write(dest, last - first);
}

}  // namespace stream_merge_detail

// Source and destination must be disjoint. Bounds are monotone with bounds[0]
// equal to zero. Scratch has bounds[4] keys in bulk or 4096 in streamed mode.
inline void merge_four_u32(const std::uint32_t* source, std::uint32_t* dest,
                           const std::array<std::size_t, 5>& bounds, std::uint32_t* scratch,
                           bool streamed) {
    using namespace stream_merge_detail;
    const auto n = bounds[4];
    if (n == 0) return;

    const auto a = source + bounds[1];
    const auto b = source + bounds[2];
    const auto c = source + bounds[3];
    const auto d = source + n;
    if (streamed) {
        BlockRun left(source, a, b, scratch), right(b, c, d, scratch + block_keys);
        Merge(left, right).write(dest, n);
    } else {
        const auto middle = scratch + bounds[2];
        merge_two(source, a, b, scratch);
        merge_two(b, c, d, middle);
        merge_two(scratch, middle, scratch + n, dest);
    }
}

}  // namespace supersort
