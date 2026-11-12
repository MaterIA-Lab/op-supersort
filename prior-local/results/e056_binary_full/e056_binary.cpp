#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <new>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include "include/supersort/windows_split_u32.hpp"

#ifdef SUPERSORT_E056_FULL
#include "vendor/x86-simd-sort/src/x86simdsort-static-incl.h"
void ips2ra_sort_u32(std::uint32_t*, std::size_t);
#endif

void seed_vq_for_benchmark(std::uint64_t, std::uint64_t);
std::size_t vq_partition_le_u32(std::uint32_t*, std::size_t, std::uint32_t);

namespace {

namespace window = supersort::window_detail;
using window::Key;
using window::SplitWork;
using Keys = std::vector<Key>;
constexpr std::size_t minimum_size = 1u << 18;
constexpr Key last_key = std::numeric_limits<Key>::max();
constexpr Key dense = 0x54880000u;
constexpr Key guard = 0xdeadbeefu;

enum class Arm {
    binary, split, vq,
#ifdef SUPERSORT_E056_FULL
    simd, ips2ra,
#endif
};
#ifdef SUPERSORT_E056_FULL
constexpr std::array arms{Arm::binary, Arm::split, Arm::vq, Arm::simd, Arm::ips2ra};
#else
constexpr std::array arms{Arm::binary, Arm::split, Arm::vq};
#endif

constexpr bool uses_window(Arm arm) { return arm == Arm::binary || arm == Arm::split; }

const char* name(Arm arm) {
    switch (arm) {
        case Arm::binary: return "binary";
        case Arm::split: return "split";
        case Arm::vq: return "vq";
#ifdef SUPERSORT_E056_FULL
        case Arm::simd: return "simd";
        case Arm::ips2ra: return "ips2ra";
#endif
    }
    throw std::logic_error("unknown arm");
}

std::optional<Key> propose(const Key* data, std::size_t n) {
    constexpr std::size_t min_matches = 96;
    if (n < minimum_size || n > last_key) return {};
    std::array<Key, window::samples> prefixes;
    const auto stride = n / prefixes.size();
    for (std::size_t i = 0; i < prefixes.size(); ++i) prefixes[i] = data[i * stride] >> 16;
    std::sort(prefixes.begin(), prefixes.end());
    std::size_t largest = 0;
    Key best = 0;
    for (std::size_t first = 0; first < prefixes.size();) {
        auto end = first + 1;
        while (end < prefixes.size() && prefixes[first] == prefixes[end]) ++end;
        if (end - first > largest) {
            largest = end - first;
            best = prefixes[first];
        }
        first = end;
    }
    if (largest >= min_matches) return best;
    return {};
}

SplitWork binary_window(Key* data, std::size_t n, Key prefix, Key* counts) {
    const Key base = prefix << 16;
    const Key upper = base | 65535u;
    const auto end = upper == last_key ? n : vq_partition_le_u32(data, n, upper);
    const auto begin = base == 0 ? 0 : vq_partition_le_u32(data, end, base - 1);
    for (std::size_t i = begin; i < end; ++i) ++counts[data[i] - base];
    return {begin, n - end};
}

struct Work {
    std::optional<Key> prefix;
    std::size_t lower;
    std::size_t middle;
};

Work run(Arm arm, Key* data, std::size_t n) {
    if (uses_window(arm)) {
        const auto prefix = propose(data, n);
        if (prefix) {
            const std::unique_ptr<Key[]> counts(new (std::nothrow) Key[window::width]{});
            if (counts) {
                const auto work = arm == Arm::binary ? binary_window(data, n, *prefix, counts.get())
                                                     : window::split_window(data, n, *prefix, counts.get());
                if (work.low > 1) vq_sort_u32(data, work.low);
                if (work.high > 1) vq_sort_u32(data + n - work.high, work.high);
                window::emit_window_counts(data + work.low, *prefix, counts.get());
                return {prefix, work.low, n - work.low - work.high};
            }
        }
    }
#ifdef SUPERSORT_E056_FULL
    if (arm == Arm::simd) {
        if (n > 1) x86simdsortStatic::qsort(data, n);
        return {{}, 0, 0};
    }
    if (arm == Arm::ips2ra) {
        if (n > 1) ips2ra_sort_u32(data, n);
        return {{}, 0, 0};
    }
#endif
    if (n > 1) vq_sort_u32(data, n);
    return {{}, 0, 0};
}

// The main families use the same draws and key construction as E054.
Keys generate(std::size_t n, std::string_view family, std::uint64_t seed) {
    std::mt19937_64 rng(seed);
    Keys source(n);
    if (family == "uniform") {
        for (auto& key : source) key = Key(rng());
    } else if (family == "mixed") {
        for (auto& key : source) key = rng() & 1u ? dense | (Key(rng()) & 4095u) : Key(rng());
    } else if (family == "dense16") {
        for (auto& key : source) key = dense | (Key(rng()) & 65535u);
    } else if (family == "late_miss") {
        if (n < minimum_size) throw std::invalid_argument("late_miss requires an active probe");
        for (auto& key : source) key = 0xf2370000u | (Key(rng()) & 65535u);
        const auto stride = n / window::samples;
        for (std::size_t i = 0; i < window::samples; ++i) source[i * stride] = dense | (Key(rng()) & 4095u);
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

void check_sorted(const Keys& expected, const Key* data, Work work, Arm arm) {
    if (!std::equal(expected.begin(), expected.end(), data)) {
        throw std::runtime_error(std::string(name(arm)) + " differs from std::sort");
    }
    if (!work.prefix) {
        if (work.lower != 0 || work.middle != 0) throw std::runtime_error("unexpected fallback telemetry");
        return;
    }
    const Key base = *work.prefix << 16;
    const auto first = std::lower_bound(expected.begin(), expected.end(), base);
    const auto end = std::upper_bound(first, expected.end(), base | 65535u);
    if (work.lower != std::size_t(first - expected.begin()) || work.middle != std::size_t(end - first)) {
        throw std::runtime_error(std::string(name(arm)) + " reported wrong window bounds");
    }
}

void check_guards(const Keys& storage, const Key* data, std::size_t n) {
    const auto untouched = [](Key key) { return key == guard; };
    if (!std::all_of(storage.data(), data, untouched) ||
        !std::all_of(data + n, storage.data() + storage.size(), untouched)) {
        throw std::runtime_error("output touched guard keys");
    }
}

void verify_partition(const Keys& source, Key pivot, std::size_t offset, std::size_t& checked) {
    const auto n = source.size();
    Keys storage(32 + offset + n, guard);
    auto* data = storage.data() + 16 + offset;
    std::copy(source.begin(), source.end(), data);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    const auto bound = vq_partition_le_u32(data, n, pivot);
    const auto left = [pivot](Key key) { return key <= pivot; };
    if (bound != std::size_t(std::upper_bound(expected.begin(), expected.end(), pivot) - expected.begin()) ||
        !std::is_partitioned(data, data + n, left)) {
        throw std::runtime_error("binary partition returned wrong boundary");
    }
    check_guards(storage, data, n);
    std::sort(data, data + n);
    if (!std::equal(expected.begin(), expected.end(), data)) {
        throw std::runtime_error("binary partition changed key multiplicity");
    }
    ++checked;
}

void verify_sort(const Keys& source, std::size_t offset, std::optional<Key> prefix, std::size_t& checked) {
    const auto n = source.size();
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    for (const auto arm : arms) {
        Keys storage(32 + offset + n, guard);
        auto* data = storage.data() + 16 + offset;
        std::copy(source.begin(), source.end(), data);
        const auto work = run(arm, data, n);
        if (work.prefix != (uses_window(arm) ? prefix : std::nullopt)) {
            throw std::runtime_error(std::string(name(arm)) + " chose wrong route");
        }
        check_sorted(expected, data, work, arm);
        check_guards(storage, data, n);
        ++checked;
    }
}

void verify_all() {
    std::size_t checked = 0;
    std::mt19937_64 rng(54403);
    constexpr Key pivot = 0x83729e01u;
    for (const std::size_t offset : {0, 1, 7, 15}) {
        for (std::size_t n = 0; n <= 263; ++n) {
            Keys data(n);
            for (auto& key : data) key = rng() & 1u ? Key(rng()) : pivot;
            verify_partition(data, pivot, offset, checked);
            verify_partition(data, 0, offset, checked);
            verify_partition(data, last_key, offset, checked);
        }
        verify_sort({}, offset, {}, checked);
        verify_sort({0, last_key, last_key, 0, 65535u, 65536u}, offset, {}, checked);
        for (const Key prefix : {0u, dense >> 16, 65535u}) {
            const Key base = prefix << 16;
            Keys data(minimum_size + 1);
            for (std::size_t i = 0; i < data.size(); ++i) {
                data[i] = i % 4 < 3 ? base | (Key(rng()) & 65535u) : Key(rng());
            }
            data[1] = base;
            data[2] = base | 65535u;
            verify_sort(data, offset, prefix, checked);
        }
    }
    verify_sort(Keys(minimum_size - 1, dense), 1, {}, checked);
    verify_sort(Keys(minimum_size, dense), 1, dense >> 16, checked);
    verify_sort(generate(minimum_size + 1, "late_miss", 36767), 7, dense >> 16, checked);
    verify_sort(generate(minimum_size + 1, "mixed", 36767), 15, dense >> 16, checked);
    verify_sort(generate(minimum_size + 1, "uniform", 36767), 1, {}, checked);
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
            const auto work = run(arm, data.data(), n);
            const auto stop = std::chrono::steady_clock::now();
            check_sorted(expected, data.data(), work, arm);
            if (round >= 0) {
                const auto ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << (work.prefix ? "window" : "vq")
                          << ',' << work.lower << ',' << work.middle << '\n';
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
            if (n < minimum_size || n > last_key || repeats < 1) {
                throw std::invalid_argument("unsupported size or repetition count");
            }
            timed(n, argv[2], std::stoull(argv[3]), repeats);
        } else {
            throw std::invalid_argument("usage: n distribution seed repetitions | --verify");
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
