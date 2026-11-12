#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace frontier_filter {
using Key = std::uint32_t;
using State = std::array<std::uint64_t, 3>;

struct Span {
    std::size_t offset, size, levels;
    State state;
};

struct Capture {
    const Key* base;
    Key* prepared;
    std::size_t size;
    std::vector<Span>& spans;
    std::size_t covered = 0;
};

Capture* active = nullptr;

void capture(const Key* keys, std::size_t size, const std::uint64_t* state, std::size_t levels) {
    auto& ctx = *active;
    const auto offset = static_cast<std::size_t>(keys - ctx.base);
    if (offset < ctx.covered) return;  // Already inside a captured subtree.
    if (offset != ctx.covered || offset > ctx.size || size > ctx.size - offset) {
        throw std::runtime_error("frontier has a gap or invalid span");
    }
    ctx.spans.push_back({offset, size, levels, {state[0], state[1], state[2]}});
    std::copy_n(keys, size, ctx.prepared + offset);
    ctx.covered += size;
}
}  // namespace frontier_filter

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

#include FRONTIER_KERNEL

namespace {
namespace hn = hwy::HWY_NAMESPACE;
using frontier_filter::Key;
using frontier_filter::State;
using frontier_filter::Span;
using Keys = std::vector<Key>;
using Clock = std::chrono::steady_clock;
using Tag = hn::SortTag<Key>;
using Traits = hn::detail::MakeTraits<Key, hwy::SortAscending>;
constexpr auto sort_mode = hn::detail::RecurseMode::kSort;
constexpr std::size_t scratch_size = hwy::SortConstants::BufBytes<Key>(HWY_MAX_BYTES) / sizeof(Key);
constexpr std::size_t cutoff = FRONTIER_CUTOFF;
constexpr Key guard = 0xdeadbeefu;

enum class Arm { replay, candidate, vq };
constexpr std::array arms{Arm::replay, Arm::candidate, Arm::vq};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::replay: return "replay";
        case Arm::candidate: return "candidate";
        case Arm::vq: return "vq";
    }
    throw std::logic_error("unknown arm");
}

Key* align64(Keys& storage) {
    const auto mod64 = reinterpret_cast<std::uintptr_t>(storage.data()) % 64;
    return storage.data() + ((64 - mod64) % 64) / sizeof(Key);
}

// Same inputs and initial states as E064.
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

void capture_tree(frontier_filter::Capture& ctx, Key* data, State state) {
    HWY_ALIGN Key scratch[scratch_size];
    frontier_filter::active = &ctx;
    hn::detail::Recurse<sort_mode, true>(Tag{}, Traits{}, data, ctx.size, scratch, state.data(), 50);
    frontier_filter::active = nullptr;
    if (ctx.covered != ctx.size) throw std::runtime_error("frontier does not cover the complete array");
}

HWY_NOINLINE void direct(Key* data, std::size_t n, const State& state) {
    std::copy(state.begin(), state.end(), hwy::detail::GetGeneratorStateStatic());
    if (n > 1) hn::VQSortStatic(data, n, hwy::SortAscending());
}

struct Used {
    std::size_t spans = 0;
    std::size_t keys = 0;
};

struct ReplayKernel {
    bool sort(Key*, std::size_t) const { return false; }
};

template<class Kernel>
HWY_NOINLINE Used finalize(Key* data, const std::vector<Span>& spans) {
    HWY_ALIGN Key scratch[scratch_size];
    Kernel kernel;
    Used used;
    for (const auto& span : spans) {
        auto* first = data + span.offset;
        if (kernel.sort(first, span.size)) {
            ++used.spans;
            used.keys += span.size;
        } else {
            auto state = span.state;
            hn::detail::Recurse<sort_mode>(Tag{}, Traits{}, first, span.size, scratch, state.data(), span.levels);
        }
    }
    return used;
}

void verify_all() {
    std::mt19937_64 rng(82573);
    supersort::FrontierKernel kernel;
    std::size_t checked = 0;
    std::size_t accepted = 0;
    std::vector<std::size_t> sizes;
    for (std::size_t n = 0; n <= std::min(cutoff, std::size_t{530}); ++n) sizes.push_back(n);
    for (const auto n : {cutoff / 2, cutoff - 1, cutoff}) sizes.push_back(n);
    for (const auto n : sizes) {
        for (unsigned pattern = 0; pattern < 9; ++pattern) {
            const auto margin = 16 + (n + pattern) % 16;
            Keys storage(margin + n + 16, guard);
            auto* keys = storage.data() + margin;
            for (std::size_t i = 0; i < n; ++i) {
                const Key draw = Key(rng());
                switch (pattern) {
                    case 0: keys[i] = draw; break;
                    case 1: keys[i] = 0x00fffff0u + (draw & 0xfffu); break;
                    case 2: keys[i] = 0x80808080u + (draw & 0xffffffu); break;
                    case 3: keys[i] = i % 2 ? UINT32_MAX : UINT32_MAX - 0xffffffu; break;
                    case 4: keys[i] = i % 2 ? UINT32_MAX : UINT32_MAX - 0x1000000u; break;
                    case 5: keys[i] = draw & 0xffu; break;
                    case 6: keys[i] = 0xcafebabeu; break;
                    case 7: keys[i] = Key(n - i); break;
                    case 8: keys[i] = Key(i); break;
                }
            }
            auto expected = storage;
            std::sort(expected.begin() + margin, expected.begin() + margin + n);
            const Keys original(keys, keys + n);
            if (kernel.sort(keys, n)) {
                ++accepted;
            } else {
                if (!std::equal(original.begin(), original.end(), keys)) throw std::runtime_error("fallback touched input");
                direct(keys, n, {271, 811, 1});
            }
            if (storage != expected) throw std::runtime_error("kernel differs from std::sort or touched guards");
            ++checked;
        }
    }
    if (!accepted) throw std::runtime_error("no candidate route exercised");
    std::cout << "verified," << checked << '\n';
}

void timed(std::size_t n, std::string_view family, std::uint64_t seed, int repeats) {
    const auto source = generate(n, family, seed);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys work_storage(n + 15), prepared_storage(n + 15);
    auto* data = align64(work_storage);
    auto* prepared = align64(prepared_storage);
    std::vector<Span> spans;
    auto order = arms;
    std::mt19937_64 order_rng(seed ^ 0x09bcac24ce2fa4a1ULL);
    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
        const State initial{pivots(), pivots(), 1};
        std::copy(source.begin(), source.end(), data);
        spans.clear();
        frontier_filter::Capture capture{data, prepared, n, spans};
        capture_tree(capture, data, initial);
        check(expected, data);

        for (const auto arm : order) {
            const auto* input = arm == Arm::vq ? source.data() : prepared;
            std::copy_n(input, n, data);
            Used used;
            const auto start = Clock::now();
            if (arm == Arm::vq) direct(data, n, initial);
            else if (arm == Arm::replay) finalize<ReplayKernel>(data, spans);
            else used = finalize<supersort::FrontierKernel>(data, spans);
            const auto stop = Clock::now();
            check(expected, data);
            if (round >= 0) {
                const auto ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << (arm == Arm::vq ? 0 : spans.size())
                          << ',' << (arm == Arm::vq ? 0 : n) << ',' << used.spans << ',' << used.keys << '\n';
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
            if (n <= cutoff || n > UINT32_MAX || repeats < 1) throw std::invalid_argument("invalid size or repeats");
            timed(n, argv[2], std::stoull(argv[3]), repeats);
        } else {
            throw std::invalid_argument("usage: n distribution seed repetitions | --verify");
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
