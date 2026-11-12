#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string_view>
#include <type_traits>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;
using Key = std::uint32_t;

std::int64_t ns(Clock::duration elapsed) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count();
}
}  // namespace

#ifdef SUPERSORT_TRACE_LEAVES
namespace e061 {

struct Leaf {
    std::uint32_t offset, size;
    std::int64_t ns;
};

std::vector<Leaf> trace;
const Key* base;
std::uint64_t sampling_seed;
std::size_t count;

std::uint64_t mix(std::uint64_t value) {
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

void reset(const Key* data, std::uint64_t seed, int round) {
    base = data;
    sampling_seed = mix(seed ^ (0xd1b54a32d192ed03ULL * std::uint64_t(round + 2)));
    count = 0;
}

template <class SortLeaf>
inline void trace_leaf(const Key* keys, std::size_t size, SortLeaf&& sort_leaf) {
    const auto offset = std::uint32_t(keys - base);
    std::int64_t elapsed = -1;
    if ((mix(sampling_seed ^ offset) & 15) == 0) {
        const auto start = Clock::now();
        sort_leaf();
        elapsed = ns(Clock::now() - start);
    } else {
        sort_leaf();
    }
    if (count < trace.size()) trace[count] = {offset, std::uint32_t(size), elapsed};
    ++count;
}

void check_capacity() {
    if (count > trace.size()) throw std::runtime_error("leaf trace storage exhausted");
}

void write_trace() {
    for (int i = 0; i < 2048; ++i) {
        const auto first = Clock::now();
        const auto second = Clock::now();
        std::cout << "clock," << ns(second - first) << '\n';
    }
    for (std::size_t i = 0; i < count; ++i) {
        const auto& leaf = trace[i];
        std::cout << "leaf," << leaf.offset << ',' << leaf.size << ',' << leaf.ns << '\n';
    }
}

}  // namespace e061
#endif

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

namespace {
namespace hn = hwy::HWY_NAMESPACE;
using Keys = std::vector<Key>;
constexpr std::size_t alignment = 64;

// The two distributions and pivot progression match E058.
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

void seed_vq(std::mt19937_64& pivots) {
    auto* state = hwy::detail::GetGeneratorStateStatic();
    state[0] = pivots();
    state[1] = pivots();
    state[2] = 1;
}

HWY_NOINLINE void sort(Key* data, std::size_t n) {
    hn::VQSortStatic(data, n, hwy::SortAscending());
}

void check(const Keys& expected, const Key* data) {
    if (!std::equal(expected.begin(), expected.end(), data))
        throw std::runtime_error("output differs from std::sort");
#ifdef SUPERSORT_TRACE_LEAVES
    e061::check_capacity();
#endif
}

void run(std::size_t n, std::string_view family, std::uint64_t seed, int round) {
    const auto source = generate(n, family, seed);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys storage(n + alignment / sizeof(Key) - 1);
    const auto misalignment = reinterpret_cast<std::uintptr_t>(storage.data()) % alignment;
    const auto padding = ((alignment - misalignment) % alignment) / sizeof(Key);
    auto* data = storage.data() + padding;
    const auto alignment_mod64 = reinterpret_cast<std::uintptr_t>(data) % alignment;
    if (alignment_mod64) throw std::runtime_error("failed to align work array");

    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
#ifdef SUPERSORT_TRACE_LEAVES
    e061::trace.resize(n / 16 + 1);
    e061::reset(data, seed, -1);
#endif
    seed_vq(pivots);
    std::copy(source.begin(), source.end(), data);
    sort(data, n);
    check(expected, data);

    pivots.discard(2 * round);
    seed_vq(pivots);
#ifdef SUPERSORT_TRACE_LEAVES
    e061::reset(data, seed, round);
#endif
    std::copy(source.begin(), source.end(), data);
    const auto start = Clock::now();
    sort(data, n);
    const auto elapsed = Clock::now() - start;
    check(expected, data);

    const auto lanes = hn::Lanes(hn::SortTag<Key>{});
    const auto max_leaf = hwy::SortConstants::BaseCaseNumLanes(lanes);
    std::cout << "total," << ns(elapsed) << '\n';
    std::cout << "layout," << lanes << ',' << max_leaf << ',' << alignment_mod64 << '\n';
#ifdef SUPERSORT_TRACE_LEAVES
    e061::write_trace();
#endif
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 5) throw std::invalid_argument("usage: n distribution seed round");
        const auto n = std::stoull(argv[1]);
        const auto round = std::stoi(argv[4]);
        if (n <= 1024 || n > UINT32_MAX || round < 0 || round >= 7)
            throw std::invalid_argument("invalid size or round");
        run(n, argv[2], std::stoull(argv[3]), round);
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
