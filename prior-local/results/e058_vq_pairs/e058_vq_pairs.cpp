#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string_view>
#include <vector>

#ifdef SUPERSORT_TRACE
namespace e058 {
using Clock = std::chrono::steady_clock;
using Key = std::uint32_t;

struct Partition {
    std::uint32_t offset, size, bound, levels;
    Key pivot;
    std::int64_t ns;
};

std::vector<Partition> trace;
const Key* base;
std::size_t count;

void record(const Key* keys, std::size_t num, std::size_t bound,
            std::size_t levels, Key pivot, Clock::duration elapsed) {
    if (count < trace.size()) {
        trace[count] = {std::uint32_t(keys - base), std::uint32_t(num),
                        std::uint32_t(bound), std::uint32_t(levels), pivot,
                        std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count()};
    }
    ++count;
}
}  // namespace e058
#endif

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

namespace {
namespace hn = hwy::HWY_NAMESPACE;
using Clock = std::chrono::steady_clock;
using Key = std::uint32_t;
using Keys = std::vector<Key>;

// The two generators and pivot seed progression are those of E057.
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

std::int64_t ns(Clock::duration elapsed) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count();
}

HWY_NOINLINE void sort(Key* data, std::size_t n) {
    hn::VQSortStatic(data, n, hwy::SortAscending());
}

void run(std::size_t n, std::string_view family, std::uint64_t seed, int round) {
    const auto source = generate(n, family, seed);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys data(n);
    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
    auto* state = hwy::detail::GetGeneratorStateStatic();
    for (int i = -1; i <= round; ++i) {
        state[0] = pivots();
        state[1] = pivots();
    }
    state[2] = 1;

#ifdef SUPERSORT_TRACE
    e058::base = data.data();
    e058::trace.resize(n / 16 + 1);
#endif
    std::copy(source.begin(), source.end(), data.begin());
    const auto start = Clock::now();
    sort(data.data(), n);
    const auto elapsed = Clock::now() - start;
    if (data != expected) throw std::runtime_error("output differs from std::sort");

    std::cout << "total," << ns(elapsed) << '\n';
#ifdef SUPERSORT_TRACE
    if (e058::count > e058::trace.size()) throw std::runtime_error("trace storage exhausted");
    for (int i = 0; i < 2048; ++i) {
        const auto first = Clock::now();
        const auto second = Clock::now();
        std::cout << "clock," << ns(second - first) << '\n';
    }
    for (std::size_t i = 0; i < e058::count; ++i) {
        const auto& p = e058::trace[i];
        std::cout << "partition," << p.offset << ',' << p.size << ',' << p.bound << ','
                  << p.levels << ',' << p.pivot << ',' << p.ns << '\n';
    }
#endif
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 5) throw std::invalid_argument("usage: n distribution seed round");
        const auto n = std::stoull(argv[1]);
        const auto round = std::stoi(argv[4]);
        if (n <= 1024 || n > UINT32_MAX || round < -1) throw std::invalid_argument("size or round");
        run(n, argv[2], std::stoull(argv[3]), round);
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
