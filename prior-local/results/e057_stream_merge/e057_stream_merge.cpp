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
#include <string>
#include <string_view>
#include <vector>

#include "include/supersort/stream_merge_u32.hpp"

void vq_sort_u32(std::uint32_t*, std::size_t);
void seed_vq_for_benchmark(std::uint64_t, std::uint64_t);

namespace {

using Key = std::uint32_t;
using Keys = std::vector<Key>;
using Bounds = std::array<std::size_t, 5>;
constexpr std::size_t run_size = 65536;
constexpr std::size_t stream_scratch = 4096;
constexpr Key last_key = std::numeric_limits<Key>::max();
constexpr Key guard = 0xdeadbeefu;

enum class Arm { bulk, stream, vq };
constexpr std::array arms{Arm::bulk, Arm::stream, Arm::vq};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::bulk: return "bulk";
        case Arm::stream: return "stream";
        case Arm::vq: return "vq";
    }
    throw std::logic_error("unknown arm");
}

template <bool Streamed>
bool sort_runs(Key* data, std::size_t n) {
    const std::unique_ptr<Key[]> aux(new (std::nothrow) Key[n]);
    const std::unique_ptr<Key[]> scratch(new (std::nothrow) Key[Streamed ? stream_scratch : n]);
    if (!aux || !scratch) return false;

    for (std::size_t first = 0; first < n; first += run_size) {
        const auto size = std::min(run_size, n - first);
        if (size > 1) vq_sort_u32(data + first, size);
    }

    auto* src = data;
    auto* dst = aux.get();
    for (std::size_t run = run_size; run < n; run = std::min(n, 4 * run)) {
        for (std::size_t first = 0; first < n;) {
            Bounds bounds{};
            for (std::size_t i = 1; i < bounds.size(); ++i) {
                bounds[i] = bounds[i - 1] + std::min(run, n - first - bounds[i - 1]);
            }
            if (bounds[1] == bounds[4]) std::copy_n(src + first, bounds[4], dst + first);
            else supersort::merge_four_u32(src + first, dst + first, bounds, scratch.get(), Streamed);
            first += bounds[4];
        }
        std::swap(src, dst);
    }
    if (src != data) std::copy_n(src, n, data);
    return true;
}

bool run(Arm arm, Key* data, std::size_t n) {
    if (n > run_size && n <= last_key) {
        if (arm == Arm::bulk && sort_runs<false>(data, n)) return true;
        if (arm == Arm::stream && sort_runs<true>(data, n)) return true;
    }
    if (n > 1) vq_sort_u32(data, n);
    return false;
}

// Same draws and construction as E054 for the four filter families.
Keys generate(std::size_t n, std::string_view family, std::uint64_t seed) {
    std::mt19937_64 rng(seed);
    constexpr Key dense = 0x54880000u;
    Keys source(n);
    if (family == "uniform") {
        for (auto& key : source) key = Key(rng());
    } else if (family == "mixed") {
        for (auto& key : source) key = rng() & 1u ? dense | (Key(rng()) & 4095u) : Key(rng());
    } else if (family == "dense16") {
        for (auto& key : source) key = dense | (Key(rng()) & 65535u);
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

void check(const Keys& expected, const Key* data, const char* label) {
    if (!std::equal(expected.begin(), expected.end(), data)) {
        throw std::runtime_error(std::string(label) + " differs from std::sort");
    }
}

void check_guards(const Keys& storage, const Key* data, std::size_t n) {
    const auto untouched = [](Key key) { return key == guard; };
    if (!std::all_of(storage.data(), data, untouched) ||
        !std::all_of(data + n, storage.data() + storage.size(), untouched)) {
        throw std::runtime_error("output touched guard keys");
    }
}

void verify_merge(const std::array<std::size_t, 4>& sizes, std::size_t offset,
                  unsigned pattern, std::mt19937_64& rng, std::size_t& checked) {
    Bounds bounds{};
    for (std::size_t i = 0; i < sizes.size(); ++i) bounds[i + 1] = bounds[i] + sizes[i];
    const auto n = bounds.back();
    const auto margin = 16 + offset;
    Keys source(margin + n + 16, guard);
    auto* input = source.data() + margin;
    for (std::size_t i = 0; i < sizes.size(); ++i) {
        for (auto j = bounds[i]; j < bounds[i + 1]; ++j) {
            if (pattern == 0) input[j] = Key(rng());
            else if (pattern == 1) input[j] = rng() & 1u ? 0 : last_key;
            else input[j] = Key(i) << 30 | (Key(rng()) & 0x3fffffffu);
        }
        std::sort(input + bounds[i], input + bounds[i + 1]);
    }
    const auto original = source;
    Keys expected(input, input + n);
    std::sort(expected.begin(), expected.end());
    for (const auto streamed : {false, true}) {
        const auto scratch_size = streamed ? stream_scratch : n;
        Keys storage(margin + n + 16, guard), scratch(margin + scratch_size + 16, guard);
        auto* output = storage.data() + margin;
        auto* work = scratch.data() + margin;
        supersort::merge_four_u32(input, output, bounds, work, streamed);
        check(expected, output, streamed ? "streamed merge" : "materialized merge");
        check_guards(storage, output, n);
        check_guards(scratch, work, scratch_size);
        if (source != original) throw std::runtime_error("merge changed input");
        ++checked;
    }
}

void verify_all() {
    std::size_t checked = 0;
    std::mt19937_64 rng(54403);
    for (const std::size_t offset : {0, 1, 7, 15}) {
        for (unsigned pattern = 0; pattern < 3; ++pattern) {
            for (std::size_t n = 0; n < 33; ++n) {
                verify_merge({n, n % 9, n / 2, n % 11}, offset, pattern, rng, checked);
            }
            for (const std::size_t n : {2047, 2048, 2049, 4095, 4096, 4097}) {
                verify_merge({n, n + 1, n - 1, n / 3}, offset, pattern, rng, checked);
                verify_merge({n, 3, 0, 0}, offset, pattern, rng, checked);
                verify_merge({3, 0, 0, n}, offset, pattern, rng, checked);
            }
        }
        for (const auto n : {std::size_t{0}, std::size_t{1}, run_size - 1, run_size, run_size + 1,
                             2 * run_size + 7, 3 * run_size, 4 * run_size + 9}) {
            const auto source = generate(n, "mixed", 36767);
            auto expected = source;
            std::sort(expected.begin(), expected.end());
            for (const auto arm : arms) {
                Keys storage(32 + offset + n, guard);
                auto* data = storage.data() + 16 + offset;
                std::copy(source.begin(), source.end(), data);
                const auto merged = run(arm, data, n);
                if (merged != (arm != Arm::vq && n > run_size)) {
                    throw std::runtime_error("wrong verification route");
                }
                check(expected, data, name(arm));
                check_guards(storage, data, n);
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
            const auto start = std::chrono::steady_clock::now();
            const auto merged = run(arm, data.data(), n);
            const auto stop = std::chrono::steady_clock::now();
            check(expected, data.data(), name(arm));
            if (round >= 0) {
                const auto ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << (merged ? "merge" : "vq") << '\n';
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
            if (n <= run_size || n > last_key || repeats < 1) throw std::invalid_argument("invalid size or repeats");
            timed(n, argv[2], std::stoull(argv[3]), repeats);
        } else {
            throw std::invalid_argument("usage: n distribution seed repetitions | --verify");
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
