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

void vq_sort_u32(std::uint32_t*, std::size_t);
void seed_vq_for_benchmark(std::uint64_t, std::uint64_t);
bool ips_block_partition_u32(std::uint32_t*, std::size_t, const std::uint16_t*, std::size_t*, bool);

#ifdef SUPERSORT_BLOCK_PHASES
namespace e067 { const double* phase_times(); }
#endif

namespace {
using Key = std::uint32_t;
using Keys = std::vector<Key>;
using Clock = std::chrono::steady_clock;
constexpr std::size_t bins = 512;
constexpr std::size_t sample_size = 32768;
constexpr Key dense = 0x54880000u;
constexpr Key guard = 0xdeadbeefu;
using Map = std::array<std::uint16_t, 65536>;
using Bounds = std::array<std::size_t, bins + 1>;

enum class Arm { fixed, adaptive, vq };
constexpr std::array arms{Arm::fixed, Arm::adaptive, Arm::vq};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::fixed: return "fixed";
        case Arm::adaptive: return "adaptive";
        case Arm::vq: return "vq";
    }
    throw std::logic_error("unknown arm");
}

struct Work {
    double split_ms = 0;
    double finish_ms = 0;
    std::size_t bins = 0;
    std::size_t largest = 0;
    const char* route;
};

double ms(Clock::duration duration) {
    return std::chrono::duration<double, std::milli>(duration).count();
}

void finish(Key* data, std::size_t n) {
    if (n > 1) vq_sort_u32(data, n);
}

std::uint64_t next_draw(std::uint64_t& state) {
    state += 0x9e3779b97f4a7c15ULL;
    auto value = (state ^ (state >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

bool choose_ranges(const Key* data, std::size_t n, Map& map) {
    std::array<Key, sample_size> sample;
    std::uint64_t state = 0xa471d58cb369f206ULL;
    std::size_t begin = 0;
    for (std::size_t i = 0; i < sample_size; ++i) {
        const auto end = (i + 1) * n / sample_size;
        sample[i] = data[begin + next_draw(state) % (end - begin)];
        begin = end;
    }
    vq_sort_u32(sample.data(), sample.size());
    if ((sample.front() >> 16) == (sample.back() >> 16)) return false;

    std::size_t first = 0;
    std::uint16_t bin = 0;
    for (std::size_t i = 1; i < bins; ++i) {
        const auto cut = sample[i * (sample_size / bins)] >> 16;
        if (cut > first) {
            std::fill(map.begin() + first, map.begin() + cut, bin++);
            first = cut;
        }
    }
    std::fill(map.begin() + first, map.end(), bin);
    return true;
}

Work whole(Key* data, std::size_t n, double split_ms, const char* route) {
    const auto start = Clock::now();
    finish(data, n);
    return {split_ms, ms(Clock::now() - start), 0, 0, route};
}

Work run(Arm arm, Key* data, std::size_t n, bool fail_reserve = false) {
    if (arm == Arm::vq) return whole(data, n, 0, "vq");
    const auto start = Clock::now();
    if (n < sample_size) return whole(data, n, ms(Clock::now() - start), "bypass");
    Map map;
    if (arm == Arm::adaptive && !choose_ranges(data, n, map)) {
        return whole(data, n, ms(Clock::now() - start), "bypass");
    }

    Bounds bounds;
    if (!ips_block_partition_u32(data, n, arm == Arm::adaptive ? map.data() : nullptr,
                                 bounds.data(), fail_reserve)) {
        return whole(data, n, ms(Clock::now() - start), "reserve");
    }
    const auto split = Clock::now();
    Work work{ms(split - start), 0, 0, 0, "blocks"};
    for (std::size_t i = 0; i < bins; ++i) {
        const auto count = bounds[i + 1] - bounds[i];
        work.bins += count != 0;
        work.largest = std::max(work.largest, count);
        finish(data + bounds[i], count);
    }
    work.finish_ms = ms(Clock::now() - split);
    return work;
}

// Uniform and prefix_distinct use the E064 draws.
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
    } else if (family == "dominant") {
        for (auto& key : source) {
            const auto draw = Key(rng());
            key = rng() % 20 == 0 ? draw : dense | (draw & 65535u);
        }
    } else if (family == "dense16") {
        for (auto& key : source) key = dense | (Key(rng()) & 65535u);
    } else {
        throw std::invalid_argument("unknown distribution");
    }
    return source;
}

void check_guards(const Keys& data, const Key* keys, std::size_t n) {
    const auto clean = [](Key key) { return key == guard; };
    if (!std::all_of(data.data(), keys, clean) || !std::all_of(keys + n, data.data() + data.size(), clean)) {
        throw std::runtime_error("touched guards");
    }
}

void verify_partition(const Keys& source, const Map* map, std::size_t offset) {
    const auto n = source.size();
    const auto margin = 16 + offset;
    Keys storage(margin + n + 16, guard);
    auto* data = storage.data() + margin;
    std::copy(source.begin(), source.end(), data);
    Bounds bounds;
    if (!ips_block_partition_u32(data, n, map ? map->data() : nullptr, bounds.data(), false)) {
        throw std::runtime_error("unexpected partition fallback");
    }
    if (bounds.front() != 0 || bounds.back() != n || !std::is_sorted(bounds.begin(), bounds.end())) {
        throw std::runtime_error("invalid block partition boundaries");
    }
    for (std::size_t i = 0; i < bins; ++i) {
        const auto in_bin = [&](Key key) { return (map ? (*map)[key >> 16] : key >> 23) == i; };
        if (!std::all_of(data + bounds[i], data + bounds[i + 1], in_bin)) {
            throw std::runtime_error("wrong block partition range");
        }
    }
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    std::sort(data, data + n);
    if (!std::equal(expected.begin(), expected.end(), data)) throw std::runtime_error("lost or changed keys");
    check_guards(storage, data, n);
}

void verify_all() {
    std::size_t checked = 0;
    Map map;
    for (std::size_t p = 0; p < map.size(); ++p) map[p] = p < 32768 ? p >> 8 : 511;
    for (const auto n : {7u, 15u, 63u, 127u, 128u, 129u, 255u, 256u, 257u, 1025u, 32769u, 65535u}) {
        for (const auto family : {"uniform", "prefix_distinct", "dominant", "dense16"}) {
            auto source = generate(n, family, 82573);
            source.front() = 0;
            source.back() = std::numeric_limits<Key>::max();
            for (const auto* table : {static_cast<const Map*>(nullptr), static_cast<const Map*>(&map)}) {
                verify_partition(source, table, n % 16);
                ++checked;
            }
        }
    }
    for (const auto n : {std::size_t{0}, std::size_t{1}, sample_size - 1, sample_size,
                         sample_size + 1, 2 * sample_size + 3}) {
        for (const auto family : {"uniform", "prefix_distinct", "dominant", "dense16"}) {
            const auto source = generate(n, family, 82573);
            Keys storage(16 + n + 16, guard);
            auto* data = storage.data() + 16;
            auto expected = source;
            std::sort(expected.begin(), expected.end());
            for (const auto arm : arms) {
                std::copy(source.begin(), source.end(), data);
                seed_vq_for_benchmark(271, 811);
                const auto work = run(arm, data, n);
                if (!std::equal(expected.begin(), expected.end(), data)) throw std::runtime_error("sort differs from std::sort");
                check_guards(storage, data, n);
                if (arm == Arm::adaptive && std::string_view(family) == "dense16" &&
                    std::string_view(work.route) != "bypass") throw std::runtime_error("incorrect dense bypass");
                ++checked;
            }
        }
    }
    const auto source = generate(sample_size + 1, "uniform", 82573);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    for (const auto arm : {Arm::fixed, Arm::adaptive}) {
        auto data = source;
        const auto work = run(arm, data.data(), data.size(), true);
        if (data != expected || std::string_view(work.route) != "reserve") {
            throw std::runtime_error("incorrect reserve fallback");
        }
        ++checked;
    }
    std::cout << "verified," << checked << '\n';
}

void timed(std::size_t n, std::string_view family, std::uint64_t seed, int repeats) {
    const auto source = generate(n, family, seed);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys storage(n + 15);
    const auto mod64 = reinterpret_cast<std::uintptr_t>(storage.data()) % 64;
    auto* data = storage.data() + ((64 - mod64) % 64) / sizeof(Key);
    auto order = arms;
    std::mt19937_64 order_rng(seed ^ 0x09bcac24ce2fa4a1ULL);
    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
        const auto first = pivots();
        const auto second = pivots();
        for (const auto arm : order) {
            std::copy(source.begin(), source.end(), data);
            seed_vq_for_benchmark(first, second);
            const auto start = Clock::now();
            const auto work = run(arm, data, n);
            const auto stop = Clock::now();
            if (!std::equal(expected.begin(), expected.end(), data)) throw std::runtime_error("sort differs from std::sort");
            if (round >= 0) {
                std::cout << round << ',' << name(arm) << ',' << ms(stop - start) << ',' << work.split_ms << ','
                          << work.finish_ms << ',' << work.bins << ',' << work.largest << ',' << work.route;
#ifdef SUPERSORT_BLOCK_PHASES
                const std::array<double, 3> empty{};
                const auto* phases = std::string_view(work.route) == "blocks" ? e067::phase_times() : empty.data();
                std::cout << ',' << phases[0] << ',' << phases[1] << ',' << phases[2];
#endif
                std::cout << '\n';
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
            if (n < sample_size || n > UINT32_MAX || repeats < 1) throw std::invalid_argument("invalid size or repeats");
            timed(n, argv[2], std::stoull(argv[3]), repeats);
        } else {
            throw std::invalid_argument("usage: n distribution seed repetitions | --verify");
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
