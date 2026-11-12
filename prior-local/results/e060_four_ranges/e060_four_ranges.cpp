#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <new>
#include <random>
#include <stdexcept>
#include <string_view>
#include <vector>

#include "include/supersort/four_split_u32.hpp"

void vq_sort_u32(std::uint32_t*, std::size_t);
void seed_vq_for_benchmark(std::uint64_t, std::uint64_t);
std::size_t vq_partition_le_u32(std::uint32_t*, std::size_t, std::uint32_t);

namespace {
using Key = std::uint32_t;
using Keys = std::vector<Key>;
using Counts = std::array<std::size_t, 4>;
using Clock = std::chrono::steady_clock;
constexpr Key guard = 0xdeadbeefu;
constexpr std::size_t leaf = 32768;
constexpr unsigned digits = 6;
constexpr std::size_t scratch_padding = 16;

struct Work {
    std::size_t classified = 0;
    std::size_t copied = 0;
    std::size_t fallbacks = 0;
};

Counts binary_split(Key* data, std::size_t n, unsigned shift, Key prefix) {
    const Key low_bits = (Key{1} << shift) - 1;
    const Key first_cut = prefix | low_bits;
    const Key middle_cut = first_cut | (Key{1} << shift);
    const Key last_cut = first_cut | (Key{2} << shift);
    const auto middle = vq_partition_le_u32(data, n, middle_cut);
    const auto first = vq_partition_le_u32(data, middle, first_cut);
    const auto third = vq_partition_le_u32(data + middle, n - middle, last_cut);
    return {first, middle - first, third, n - middle - third};
}

void finish(Key* data, std::size_t n) {
    if (n > 1) vq_sort_u32(data, n);
}

template <bool Four>
void sort_node(Key* data, std::size_t n, Key prefix, unsigned depth, Key* scratch, Work& work) {
    if (n <= leaf || depth == digits) {
        finish(data, n);
        return;
    }

    const unsigned shift = 30 - 2 * depth;
    Counts counts;
    if constexpr (Four) {
        counts = supersort::four_split_u32(data, n, shift, scratch);
        work.classified += n;
        work.copied += counts[1] + counts[2];
    } else {
        counts = binary_split(data, n, shift, prefix);
        work.classified += 2 * n;
    }
    if (std::find(counts.begin(), counts.end(), n) != counts.end()) {
        ++work.fallbacks;
        finish(data, n);
        return;
    }

    auto* first = data;
    for (unsigned bucket = 0; bucket < counts.size(); ++bucket) {
        sort_node<Four>(first, counts[bucket], prefix | (Key(bucket) << shift), depth + 1, scratch, work);
        first += counts[bucket];
    }
}

template <bool Four>
Work sort(Key* data, std::size_t n, bool fail_reserve = false) {
    Work work;
    std::unique_ptr<Key[]> scratch;
    if constexpr (Four) {
        if (n > leaf) {
            constexpr auto max_n = std::numeric_limits<std::size_t>::max() / sizeof(Key) - scratch_padding;
            if (!fail_reserve && n <= max_n) scratch.reset(new (std::nothrow) Key[n + scratch_padding]);
            if (!scratch) {
                ++work.fallbacks;
                finish(data, n);
                return work;
            }
        }
    }
    sort_node<Four>(data, n, 0, 0, scratch.get(), work);
    return work;
}

enum class Arm { binary, four, vq };
constexpr std::array arms{Arm::binary, Arm::four, Arm::vq};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::binary: return "binary";
        case Arm::four: return "four";
        case Arm::vq: return "vq";
    }
    throw std::logic_error("unknown arm");
}

Work run(Arm arm, Key* data, std::size_t n) {
    if (arm == Arm::binary) return sort<false>(data, n);
    if (arm == Arm::four) return sort<true>(data, n);
    finish(data, n);
    return {};
}

// The first two generators match E058 and E059.
Keys generate(std::size_t n, std::string_view family, std::uint64_t seed) {
    std::mt19937_64 rng(seed);
    Keys source(n);
    if (family == "uniform") {
        for (auto& key : source) key = Key(rng());
    } else if (family == "prefix_distinct") {
        constexpr std::array<Key, 4> prefixes{0x00u, 0x23u, 0xa7u, 0xffu};
        if (n > (std::size_t{1} << 26)) throw std::invalid_argument("prefix_distinct exhausted");
        std::array<Key, 4> stride, offset;
        for (std::size_t p = 0; p < prefixes.size(); ++p) {
            stride[p] = Key(rng()) | 1u;
            offset[p] = Key(rng());
        }
        for (std::size_t i = 0; i < n; ++i) {
            const auto p = i % 4;
            const auto suffix = (stride[p] * Key(i / 4) + offset[p]) & 0xffffffu;
            source[i] = (prefixes[p] << 24) | suffix;
        }
    } else if (family == "center") {
        for (auto& key : source) {
            const Key draw = Key(rng());
            key = ((1u + (draw >> 31)) << 30) | (draw & 0x3fffffffu);
        }
    } else if (family == "equal") {
        std::fill(source.begin(), source.end(), 0x5488f13bu);
    } else {
        throw std::invalid_argument("unknown distribution");
    }
    return source;
}

void verify_split(std::size_t n, unsigned shift, std::size_t offset, unsigned pattern, std::mt19937_64& rng) {
    const auto margin = 16 + offset;
    Keys data(margin + n + 16, guard), scratch(margin + n + scratch_padding + 16, guard);
    auto* keys = data.data() + margin;
    std::array<Keys, 4> expected;
    const Key digit_mask = Key{3} << shift;
    for (std::size_t i = 0; i < n; ++i) {
        Key key = Key(rng());
        if (pattern == 1) key = (key & ~digit_mask) | ((1u + (key & 1u)) << shift);
        if (pattern == 2) key = (key & ~digit_mask) | ((key & 1u ? 3u : 0u) << shift);
        if (pattern >= 3) key = (key & ~digit_mask) | (Key(pattern - 3) << shift);
        if (pattern == 7) key = i & 1u ? 0 : std::numeric_limits<Key>::max();
        keys[i] = key;
        expected[(key >> shift) & 3].push_back(key);
    }
    const auto counts = supersort::four_split_u32(keys, n, shift, scratch.data() + margin);
    auto* first = keys;
    for (unsigned bucket = 0; bucket < counts.size(); ++bucket) {
        auto& want = expected[bucket];
        if (counts[bucket] != want.size()) throw std::runtime_error("incorrect four-way count");
        std::sort(want.begin(), want.end());
        std::sort(first, first + counts[bucket]);
        if (!std::equal(want.begin(), want.end(), first)) throw std::runtime_error("incorrect four-way contents");
        first += counts[bucket];
    }
    const auto clean = [](Key key) { return key == guard; };
    if (!std::all_of(data.data(), keys, clean) || !std::all_of(keys + n, data.data() + data.size(), clean) ||
        !std::all_of(scratch.begin(), scratch.begin() + margin, clean) ||
        !std::all_of(scratch.begin() + margin + n + scratch_padding, scratch.end(), clean)) {
        throw std::runtime_error("four-way split touched guards");
    }
}

void verify_all() {
    std::size_t checked = 0;
    std::mt19937_64 rng(82573);
    for (const auto shift : {0u, 2u, 8u, 18u, 28u, 30u}) {
        for (std::size_t n = 0; n <= 96; ++n) {
            for (unsigned pattern = 0; pattern < 8; ++pattern) {
                verify_split(n, shift, (n + pattern) % 8, pattern, rng);
                ++checked;
            }
        }
        for (const auto n : {1023u, 1024u, 1025u, 16397u}) {
            for (unsigned pattern = 0; pattern < 8; ++pattern) {
                verify_split(n, shift, (n + pattern) % 8, pattern, rng);
                ++checked;
            }
        }
    }
    for (const auto n : {std::size_t{0}, std::size_t{1}, leaf - 1, leaf, leaf + 1, 4 * leaf + 3, 16 * leaf + 1}) {
        for (const auto family : {"uniform", "prefix_distinct", "center", "equal"}) {
            const auto source = generate(n, family, 82573);
            Keys data(32 + n + 32, guard);
            auto expected = data;
            std::copy(source.begin(), source.end(), expected.begin() + 32);
            std::sort(expected.begin() + 32, expected.begin() + 32 + n);
            for (const auto arm : arms) {
                std::copy(source.begin(), source.end(), data.begin() + 32);
                seed_vq_for_benchmark(271, 811);
                run(arm, data.data() + 32, n);
                if (data != expected) throw std::runtime_error("sort differs from std::sort or touched guards");
                ++checked;
            }
            if (n > leaf) {
                std::copy(source.begin(), source.end(), data.begin() + 32);
                seed_vq_for_benchmark(271, 811);
                const auto work = sort<true>(data.data() + 32, n, true);
                if (data != expected || work.fallbacks != 1 || work.classified || work.copied) {
                    throw std::runtime_error("incorrect allocation fallback");
                }
                ++checked;
            }
        }
    }
    std::cout << "verified," << checked << '\n';
}

void timed(std::size_t n, std::string_view family, std::uint64_t seed, int repeats) {
    const auto source = generate(n, family, seed);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys data(n);
    auto order = arms;
    std::mt19937_64 order_rng(seed ^ 0x09bcac24ce2fa4a1ULL);
    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
        const auto first = pivots();
        const auto second = pivots();
        for (const auto arm : order) {
            std::copy(source.begin(), source.end(), data.begin());
            seed_vq_for_benchmark(first, second);
            const auto start = Clock::now();
            const auto work = run(arm, data.data(), n);
            const auto stop = Clock::now();
            if (data != expected) throw std::runtime_error("sort differs from std::sort");
            if (round >= 0) {
                const auto ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << work.classified << ','
                          << work.copied << ',' << work.fallbacks << '\n';
            }
        }
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") verify_all();
        else if (argc == 5) {
            const auto n = std::stoull(argv[1]);
            const auto repeats = std::stoi(argv[4]);
            if (n <= leaf || n > UINT32_MAX || repeats < 1) throw std::invalid_argument("invalid size or repeats");
            timed(n, argv[2], std::stoull(argv[3]), repeats);
        } else {
            throw std::invalid_argument("usage: n distribution seed repetitions | --verify");
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
