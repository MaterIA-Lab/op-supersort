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

namespace e064 {
using Key = std::uint32_t;
using State = std::array<std::uint64_t, 3>;
using Clock = std::chrono::steady_clock;

struct Span {
    std::size_t offset, size, levels;
    State state;
};

struct Frontier {
    const Key* base;
    Key* prepared;  // Set during capture, null during live timing.
    std::size_t size;
    std::vector<Span>& spans;
    std::size_t covered = 0;
    std::size_t visited = 0;
    Clock::duration elapsed{};
};

Frontier* active = nullptr;

template <class Sort>
void frontier(const Key* keys, std::size_t size, const std::uint64_t* state,
              std::size_t levels, Sort&& sort) {
    auto& ctx = *active;
    const auto offset = static_cast<std::size_t>(keys - ctx.base);
    if (offset != ctx.covered || offset > ctx.size || size > ctx.size - offset) {
        throw std::runtime_error("frontier has a gap or overlapping spans");
    }
    const State initial{state[0], state[1], state[2]};
    if (ctx.prepared) {
        ctx.spans.push_back({offset, size, levels, initial});
        std::copy_n(keys, size, ctx.prepared + offset);
        sort();
    } else {
        if (ctx.visited >= ctx.spans.size()) throw std::runtime_error("unexpected live span");
        const auto& span = ctx.spans[ctx.visited];
        if (span.offset != offset || span.size != size || span.levels != levels || span.state != initial) {
            throw std::runtime_error("live frontier differs from capture");
        }
        const auto start = Clock::now();
        sort();
        ctx.elapsed += Clock::now() - start;
    }
    ctx.covered += size;
    ++ctx.visited;
}
}  // namespace e064

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

namespace {
namespace hn = hwy::HWY_NAMESPACE;
using e064::Clock;
using e064::Key;
using e064::State;
using Keys = std::vector<Key>;
using Tag = hn::SortTag<Key>;
using Traits = hn::detail::MakeTraits<Key, hwy::SortAscending>;
constexpr auto sort_mode = hn::detail::RecurseMode::kSort;
constexpr std::size_t scratch_size = hwy::SortConstants::BufBytes<Key>(HWY_MAX_BYTES) / sizeof(Key);

enum class Arm { vq, live, replay, oracle };
constexpr std::array arms{Arm::vq, Arm::live, Arm::replay, Arm::oracle};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::vq: return "vq";
        case Arm::live: return "live";
        case Arm::replay: return "replay";
        case Arm::oracle: return "oracle";
    }
    throw std::logic_error("unknown arm");
}

Key* align64(Keys& storage) {
    const auto mod64 = reinterpret_cast<std::uintptr_t>(storage.data()) % 64;
    return storage.data() + ((64 - mod64) % 64) / sizeof(Key);
}

// Same generators and pivot progression as E062.
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

HWY_NOINLINE void visit_tree(e064::Frontier& ctx, Key* data, State state) {
    HWY_ALIGN Key scratch[scratch_size];
    e064::active = &ctx;
    hn::detail::Recurse<sort_mode, true>(Tag{}, Traits{}, data, ctx.size, scratch, state.data(), 50);
    e064::active = nullptr;
}

HWY_NOINLINE void direct(Key* data, std::size_t n, const State& state) {
    std::copy(state.begin(), state.end(), hwy::detail::GetGeneratorStateStatic());
    hn::VQSortStatic(data, n, hwy::SortAscending());
}

HWY_NOINLINE void finalize(Key* data, const std::vector<e064::Span>& spans) {
    HWY_ALIGN Key scratch[scratch_size];
    for (const auto& span : spans) {
        auto state = span.state;
        hn::detail::Recurse<sort_mode>(Tag{}, Traits{}, data + span.offset, span.size,
                                      scratch, state.data(), span.levels);
    }
}

double ms(Clock::duration elapsed) {
    return std::chrono::duration<double, std::milli>(elapsed).count();
}

void check_coverage(const e064::Frontier& ctx) {
    if (ctx.covered != ctx.size || ctx.visited != ctx.spans.size()) {
        throw std::runtime_error("frontier does not cover the complete array");
    }
}

void timed(std::size_t n, std::string_view family, std::uint64_t seed, int repeats) {
    const auto source = generate(n, family, seed);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys work_storage(n + 15), prepared_storage(n + 15);
    auto* data = align64(work_storage);
    auto* prepared = align64(prepared_storage);
    std::vector<e064::Span> spans;
    auto order = arms;
    std::mt19937_64 order_rng(seed ^ 0x09bcac24ce2fa4a1ULL);
    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
        const State initial{pivots(), pivots(), 1};
        std::copy(source.begin(), source.end(), data);
        spans.clear();
        e064::Frontier capture{data, prepared, n, spans};
        visit_tree(capture, data, initial);
        check_coverage(capture);
        check(expected, data);

        for (const auto arm : order) {
            const auto* input = arm == Arm::replay ? prepared : source.data();
            std::copy_n(input, n, data);
            e064::Frontier live{data, nullptr, n, spans};
            const auto start = Clock::now();
            if (arm == Arm::vq) direct(data, n, initial);
            else if (arm == Arm::live) visit_tree(live, data, initial);
            else {
                if (arm == Arm::oracle) std::copy_n(prepared, n, data);
                finalize(data, spans);
            }
            const auto stop = Clock::now();
            if (arm == Arm::live) check_coverage(live);
            check(expected, data);
            if (round >= 0) {
                const auto count = arm == Arm::vq ? 0 : spans.size();
                const auto covered = arm == Arm::vq ? 0 : n;
                std::cout << round << ',' << name(arm) << ',' << ms(stop - start) << ',' << ms(live.elapsed)
                          << ',' << count << ',' << covered << '\n';
            }
        }
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 5) throw std::invalid_argument("usage: n distribution seed repetitions");
        const auto n = std::stoull(argv[1]);
        const auto repeats = std::stoi(argv[4]);
        if (n <= 32768 || n > UINT32_MAX || repeats < 1) throw std::invalid_argument("invalid size or repeats");
        timed(n, argv[2], std::stoull(argv[3]), repeats);
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
