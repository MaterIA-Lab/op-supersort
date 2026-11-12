#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace e062 {
using Key = std::uint32_t;
using State = std::array<std::uint64_t, 3>;

struct Span {
    std::size_t offset, size, levels;
    State state;
};

struct Capture {
    const Key* base;
    Key* snapshot;
    std::size_t size;
    std::vector<Span> spans;
    std::size_t end = 0;
    std::size_t covered = 0;
};

Capture* active = nullptr;

void capture(const Key* keys, std::size_t size, const std::uint64_t* state, std::size_t levels) {
    auto& ctx = *active;
    const auto offset = static_cast<std::size_t>(keys - ctx.base);
    if (offset < ctx.end) return;  // A captured ancestor contains this subtree.
    if (offset > ctx.size || size > ctx.size - offset) throw std::runtime_error("invalid capture range");
    ctx.spans.push_back({offset, size, levels, {state[0], state[1], state[2]}});
    std::copy_n(keys, size, ctx.snapshot + offset);
    ctx.end = offset + size;
    ctx.covered += size;
}
}  // namespace e062

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

#include "include/supersort/position_bitmap_u32.hpp"

namespace {
namespace hn = hwy::HWY_NAMESPACE;
using e062::Key;
using e062::State;
using Keys = std::vector<Key>;
using Clock = std::chrono::steady_clock;
using Tag = hn::SortTag<Key>;
using Traits = hn::detail::MakeTraits<Key, hwy::SortAscending>;
constexpr auto sort_mode = hn::detail::RecurseMode::kSort;
constexpr std::size_t max_levels = 50;
constexpr std::size_t scratch_size = hwy::SortConstants::BufBytes<Key>(HWY_MAX_BYTES) / sizeof(Key);
constexpr Key guard = 0xdeadbeefu;

enum class Arm { replay, bitmap, vq };
constexpr std::array arms{Arm::replay, Arm::bitmap, Arm::vq};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::replay: return "replay";
        case Arm::bitmap: return "bitmap";
        case Arm::vq: return "vq";
    }
    throw std::logic_error("unknown arm");
}

// Same generators as E061.
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
    } else {
        throw std::invalid_argument("unknown distribution");
    }
    return source;
}

void check(const Keys& expected, const Key* data) {
    if (!std::equal(expected.begin(), expected.end(), data)) throw std::runtime_error("output differs from std::sort");
}

void capture_tree(e062::Capture& ctx, Key* data, State state) {
    HWY_ALIGN Key scratch[scratch_size];
    e062::active = &ctx;
    hn::detail::Recurse<sort_mode, true>(Tag{}, Traits{}, data, ctx.size, scratch, state.data(), max_levels);
    e062::active = nullptr;
}

HWY_NOINLINE void direct(Key* data, std::size_t n, const State& state) {
    std::copy(state.begin(), state.end(), hwy::detail::GetGeneratorStateStatic());
    if (n > 1) hn::VQSortStatic(data, n, hwy::SortAscending());
}

template <bool Bitmap>
HWY_NOINLINE std::size_t replay(Key* data, const std::vector<e062::Span>& spans) {
    HWY_ALIGN Key scratch[scratch_size];
    std::size_t used = 0;
    for (const auto& span : spans) {
        auto state = span.state;
        auto* keys = data + span.offset;
        if constexpr (Bitmap) {
            const auto finish = [&](Key* group, std::size_t n) {
                hn::detail::Recurse<sort_mode>(Tag{}, Traits{}, group, n, scratch, state.data(), span.levels);
            };
            used += supersort::position_bitmap_u32(keys, span.size, finish);
        } else {
            hn::detail::Recurse<sort_mode>(Tag{}, Traits{}, keys, span.size, scratch, state.data(), span.levels);
        }
    }
    return used;
}

void verify_all() {
    std::mt19937_64 rng(82573);
    std::size_t checked = 0;
    constexpr Key last = std::numeric_limits<Key>::max();
    for (std::size_t n = 0; n <= 520; ++n) {
        for (unsigned pattern = 0; pattern < 8; ++pattern) {
            const auto margin = 16 + (n + pattern) % 16;
            Keys data(margin + n + 16, guard);
            auto* keys = data.data() + margin;
            for (std::size_t i = 0; i < n; ++i) {
                const auto draw = Key(rng());
                switch (pattern) {
                    case 0: keys[i] = draw; break;
                    case 1: keys[i] = 0x816f0000u | (draw & 65535u); break;
                    case 2: keys[i] = i == n / 2 ? last : 0x816f0000u | (draw & 65535u); break;
                    case 3: keys[i] = draw & 0x80400201u; break;
                    case 4: keys[i] = last; break;
                    case 5: keys[i] = Key(i) << 23; break;
                    case 6: keys[i] = Key(n - 1 - i) << 23; break;
                    case 7: keys[i] = i % 3 ? 0 : last; break;
                }
            }
            auto expected = data;
            std::sort(expected.begin() + margin, expected.begin() + margin + n);
            const auto finish = [](Key* group, std::size_t count) { direct(group, count, {271, 811, 1}); };
            const bool used = supersort::position_bitmap_u32(keys, n, finish);
            if (data != expected || used != (n > 128 && n <= 512)) {
                throw std::runtime_error("bitmap differs from std::sort, touched guards or used the wrong route");
            }
            ++checked;
        }
    }
    std::cout << "verified," << checked << '\n';
}

void timed(std::size_t n, std::string_view family, std::uint64_t seed, int repeats) {
    const auto source = generate(n, family, seed);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys storage(n + 15), snapshot(n);
    const auto mod64 = reinterpret_cast<std::uintptr_t>(storage.data()) % 64;
    auto* data = storage.data() + ((64 - mod64) % 64) / sizeof(Key);
    auto order = arms;
    std::mt19937_64 order_rng(seed ^ 0x09bcac24ce2fa4a1ULL);
    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
        const State initial{pivots(), pivots(), 1};
        std::copy(source.begin(), source.end(), data);
        // Gaps resolved above the capture threshold are already in final order.
        std::copy(expected.begin(), expected.end(), snapshot.begin());
        e062::Capture ctx{data, snapshot.data(), n, {}};
        capture_tree(ctx, data, initial);
        check(expected, data);
        if (!ctx.covered) throw std::runtime_error("capture has no subtrees");

        for (const auto arm : order) {
            const auto& input = arm == Arm::vq ? source : snapshot;
            std::copy(input.begin(), input.end(), data);
            std::size_t used = 0;
            const auto start = Clock::now();
            if (arm == Arm::vq) direct(data, n, initial);
            else if (arm == Arm::replay) replay<false>(data, ctx.spans);
            else used = replay<true>(data, ctx.spans);
            const auto stop = Clock::now();
            check(expected, data);
            if (round >= 0) {
                const auto ms = std::chrono::duration<double, std::milli>(stop - start).count();
                const auto spans = arm == Arm::vq ? 0 : ctx.spans.size();
                const auto covered = arm == Arm::vq ? 0 : ctx.covered;
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << spans << ',' << covered << ',' << used << '\n';
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
            if (n <= 512 || n > UINT32_MAX || repeats < 1) throw std::invalid_argument("invalid size or repeats");
            timed(n, argv[2], std::stoull(argv[3]), repeats);
        } else {
            throw std::invalid_argument("usage: n distribution seed repetitions | --verify");
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
