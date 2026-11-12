#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string_view>
#include <vector>

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

#include "include/supersort/partition_pair_u32.hpp"

namespace {
namespace hn = hwy::HWY_NAMESPACE;
using supersort::e059::partition_pair;
using supersort::e059::Tag;
using supersort::e059::Traits;
using supersort::e059::Vec;
using hn::detail::PivotResult;
using Key = std::uint32_t;
using Keys = std::vector<Key>;
using Clock = std::chrono::steady_clock;

constexpr std::size_t scratch_size = hwy::SortConstants::BufBytes<Key>(HWY_MAX_BYTES) / sizeof(Key);
constexpr Key max_key = std::numeric_limits<Key>::max();
constexpr Key guard = 0xdeadbeefu;

struct Scratch {
    HWY_ALIGN Key left[scratch_size];
    HWY_ALIGN Key right[scratch_size];
};

struct Node {
    Key* keys;
    std::size_t size;
    Vec pivot;
    PivotResult result;
    bool ready = false;
};

void prepare(Node& node, Key* buffer, std::uint64_t* state, std::size_t levels) {
    node.ready = hn::detail::PreparePairPivot(Tag{}, Traits{}, node.keys, node.size,
                                             buffer, state, levels, node.pivot, node.result);
}

std::size_t partition_one(const Node& node, Key* buffer) {
    return hn::detail::Partition(Tag{}, Traits{}, node.keys, node.size, node.pivot, buffer);
}

template <bool Alternate>
void descend(const Node& parent, std::size_t bound, std::size_t child_levels,
             Scratch& scratch, std::uint64_t* state) {
    Node left{parent.keys, bound, {}, PivotResult::kNormal};
    Node right{parent.keys + bound, parent.size - bound, {}, PivotResult::kNormal};
    if (left.size && parent.result != PivotResult::kIsFirst) {
        prepare(left, scratch.left, state, child_levels);
    }
    if (right.size && parent.result != PivotResult::kWasLast) {
        prepare(right, scratch.left, state, child_levels);
    }

    std::array<std::size_t, 2> cuts{};
    if (left.ready && right.ready) {
        cuts = partition_pair<Alternate>(left.keys, left.size, left.pivot,
                                         right.keys, right.size, right.pivot,
                                         scratch.left, scratch.right);
    } else if (left.ready) {
        cuts[0] = partition_one(left, scratch.left);
    } else if (right.ready) {
        cuts[1] = partition_one(right, scratch.left);
    }
    if (left.ready) descend<Alternate>(left, cuts[0], child_levels - 1, scratch, state);
    if (right.ready) descend<Alternate>(right, cuts[1], child_levels - 1, scratch, state);
}

template <bool Alternate>
HWY_NOINLINE void schedule(Key* data, std::size_t n) {
    if (n <= 1) return;
    Scratch scratch;
    if (hn::detail::HandleSpecialCases(Tag{}, Traits{}, data, n, scratch.left)) return;
    auto* state = hwy::detail::GetGeneratorStateStatic();
    constexpr std::size_t max_levels = 50;
    Node root{data, n, {}, PivotResult::kNormal};
    prepare(root, scratch.left, state, max_levels);
    if (root.ready) descend<Alternate>(root, partition_one(root, scratch.left), max_levels - 1, scratch, state);
}

HWY_NOINLINE void direct(Key* data, std::size_t n) {
    if (n > 1) hn::VQSortStatic(data, n, hwy::SortAscending());
}

struct Arm {
    const char* name;
    void (*sort)(Key*, std::size_t);
};

constexpr std::array arms{Arm{"serial", schedule<false>}, Arm{"alternate", schedule<true>}, Arm{"vq", direct}};

// Same draws and construction as E058, plus an all-equal control.
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
    } else if (family == "equal") {
        std::fill(source.begin(), source.end(), 0x5488f13bu);
    } else {
        throw std::invalid_argument("unknown distribution");
    }
    return source;
}

void seed_vq(std::uint64_t first, std::uint64_t second) {
    auto* state = hwy::detail::GetGeneratorStateStatic();
    state[0] = first;
    state[1] = second;
    state[2] = 1;
}

std::size_t verify_pair(std::size_t nl, std::size_t nr, std::size_t offset,
                        unsigned pattern, Key pl, Key pr, std::mt19937_64& rng) {
    const auto margin = 32 + offset;
    Keys source(margin + nl + nr + 32, guard);
    auto* data = source.data() + margin;
    for (std::size_t i = 0; i < nl + nr; ++i) {
        const Key value = Key(rng());
        if (pattern == 0) data[i] = value;
        else if (pattern == 1) data[i] = value & 1 ? max_key : 0;
        else data[i] = i < nl ? pl : pr;
    }
    auto expected = source;
    auto* left = expected.data() + margin;
    const auto pleft = hn::Set(Tag{}, pl);
    const auto pright = hn::Set(Tag{}, pr);
    Scratch scratch;
    const std::array cuts{
        hn::detail::Partition(Tag{}, Traits{}, left, nl, pleft, scratch.left),
        hn::detail::Partition(Tag{}, Traits{}, left + nl, nr, pright, scratch.right),
    };
    for (const bool alternate : {false, true}) {
        auto actual = source;
        auto* first = actual.data() + margin;
        const auto pair = alternate ? partition_pair<true>(first, nl, pleft, first + nl, nr, pright,
                                                            scratch.left, scratch.right)
                                    : partition_pair<false>(first, nl, pleft, first + nl, nr, pright,
                                                             scratch.left, scratch.right);
        if (pair != cuts || actual != expected) throw std::runtime_error("pair differs from Highway Partition");
    }
    return 2;
}

void verify_all() {
    std::size_t checked = 0;
    std::mt19937_64 rng(82573);
    constexpr std::array<std::size_t, 15> sizes{17, 31, 32, 33, 63, 64, 65, 95, 96, 97,
                                                127, 128, 129, 513, 16397};
    for (std::size_t i = 0; i < sizes.size(); ++i) {
        for (std::size_t j = 0; j < sizes.size(); ++j) {
            const auto offset = (i + 3 * j) % 16;
            checked += verify_pair(sizes[i], sizes[j], offset, 0, Key(rng()), Key(rng()), rng);
            checked += verify_pair(sizes[i], sizes[j], offset, 1, 0, max_key, rng);
            checked += verify_pair(sizes[i], sizes[j], offset, 2, max_key, 0, rng);
        }
    }
    const auto leaf = hwy::SortConstants::BaseCaseNumLanes(hn::Lanes(Tag{}));
    for (const auto n : {std::size_t{0}, std::size_t{1}, leaf - 1, leaf, leaf + 1, 2 * leaf - 1,
                         2 * leaf, 2 * leaf + 1, 4 * leaf + 3, std::size_t{32777}}) {
        for (unsigned pattern = 0; pattern < 8; ++pattern) {
            auto source = generate(n, pattern == 1 ? "prefix_distinct" : "uniform", 82573);
            for (std::size_t i = 0; i < n; ++i) {
                if (pattern == 2) source[i] = i & 1 ? 0 : max_key;
                if (pattern == 3) source[i] = Key(i);
                if (pattern == 4) source[i] = Key(n - i);
                if (pattern == 5) source[i] = 0;
                if (pattern == 6) source[i] &= 15;
                if (pattern == 7 && i > 2) source[i] = max_key;
            }
            Keys data(32 + n + 32, guard);
            auto expected = data;
            std::copy(source.begin(), source.end(), expected.begin() + 32);
            std::sort(expected.begin() + 32, expected.begin() + 32 + n);
            for (const auto arm : arms) {
                std::copy(source.begin(), source.end(), data.begin() + 32);
                seed_vq(271, 811);
                arm.sort(data.data() + 32, n);
                if (data != expected) throw std::runtime_error("sort differs from std::sort or touched guards");
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
            seed_vq(first, second);
            const auto start = Clock::now();
            arm.sort(data.data(), n);
            const auto stop = Clock::now();
            if (data != expected) throw std::runtime_error("sort differs from std::sort");
            if (round >= 0) {
                const auto ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << arm.name << ',' << ms << '\n';
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
            if (n <= 1024 || n > max_key || repeats < 1) throw std::invalid_argument("invalid size or repeats");
            timed(n, argv[2], std::stoull(argv[3]), repeats);
        } else {
            throw std::invalid_argument("usage: n distribution seed repetitions | --verify");
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
