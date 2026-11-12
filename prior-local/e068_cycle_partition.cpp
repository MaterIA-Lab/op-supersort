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

#include "include/supersort/cycle_partition_u32.hpp"

void vq_sort_u32(std::uint32_t*, std::size_t);
void seed_vq_for_benchmark(std::uint64_t, std::uint64_t);
bool ips_block_partition_u32(std::uint32_t*, std::size_t, const std::uint16_t*, std::size_t*, bool);

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

enum class Arm { cycles, blocks, vq };
constexpr std::array arms{Arm::cycles, Arm::blocks, Arm::vq};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::cycles: return "cycles";
        case Arm::blocks: return "blocks";
        case Arm::vq: return "vq";
    }
    throw std::logic_error("unknown arm");
}

struct Work {
    double split_ms, finish_ms;
    std::size_t bins, largest;
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

// Same stratified sample and rounded quantile boundaries as E066.
void choose_ranges(const Key* data, std::size_t n, Map& map) {
    std::array<Key, sample_size> sample;
    std::uint64_t state = 0xa471d58cb369f206ULL;
    std::size_t begin = 0;
    for (std::size_t i = 0; i < sample_size; ++i) {
        const auto end = (i + 1) * n / sample_size;
        sample[i] = data[begin + next_draw(state) % (end - begin)];
        begin = end;
    }
    vq_sort_u32(sample.data(), sample.size());
    if ((sample.front() >> 16) == (sample.back() >> 16)) {
        map.fill(0);
        return;
    }
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
}

Bounds exact_bounds(const Keys& input, const Map& map) {
    Bounds bounds{};
    for (const Key key : input) ++bounds[map[key >> 16] + 1];
    for (std::size_t i = 0; i < bins; ++i) bounds[i + 1] += bounds[i];
    return bounds;
}

std::size_t misplaced_count(const Key* input, const Map& map, const Bounds& bounds) {
    std::size_t misplaced = 0;
    for (std::size_t i = 0; i < bins; ++i) {
        for (auto j = bounds[i]; j < bounds[i + 1]; ++j) misplaced += map[input[j] >> 16] != i;
    }
    return misplaced;
}

Keys group_stably(const Keys& input, const Map& map, Bounds next) {
    Keys grouped(input.size());
    for (const Key key : input) grouped[next[map[key >> 16]]++] = key;
    return grouped;
}

Work whole(Key* data, std::size_t n, double split_ms, const char* route) {
    const auto start = Clock::now();
    finish(data, n);
    return {split_ms, ms(Clock::now() - start), 0, 0, route};
}

Work run(Arm arm, Key* data, std::size_t n, const Map& map, const Bounds& prepared, Bounds& actual) {
    if (arm == Arm::vq) return whole(data, n, 0, "vq");
    const auto start = Clock::now();
    if (arm == Arm::cycles) {
        supersort::cycle_partition_u32(data, map.data(), prepared.data());
    } else if (!ips_block_partition_u32(data, n, map.data(), actual.data(), false)) {
        return whole(data, n, ms(Clock::now() - start), "reserve");
    }
    const auto split = Clock::now();
    const auto& bounds = arm == Arm::cycles ? prepared : actual;
    Work work{ms(split - start), 0, 0, 0, name(arm)};
    for (std::size_t i = 0; i < bins; ++i) {
        const auto count = bounds[i + 1] - bounds[i];
        work.bins += count != 0;
        work.largest = std::max(work.largest, count);
        finish(data + bounds[i], count);
    }
    work.finish_ms = ms(Clock::now() - split);
    return work;
}

// Same E066 inputs, with grouped derived after preparing the uniform table.
Keys generate(std::size_t n, std::string_view family, std::uint64_t seed) {
    std::mt19937_64 rng(seed);
    Keys source(n);
    if (family == "uniform" || family == "grouped") {
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
    } else {
        throw std::invalid_argument("unknown distribution");
    }
    return source;
}

void check_partition(Key* data, const Map& map, const Bounds& bounds, const Keys& expected) {
    for (std::size_t i = 0; i < bins; ++i) {
        const auto in_bin = [&](Key key) { return map[key >> 16] == i; };
        if (!std::all_of(data + bounds[i], data + bounds[i + 1], in_bin)) {
            throw std::runtime_error("wrong cycle range");
        }
        std::sort(data + bounds[i], data + bounds[i + 1]);
    }
    if (!std::equal(expected.begin(), expected.end(), data)) throw std::runtime_error("cycle differs from std::sort");
}

void verify_all() {
    std::mt19937_64 rng(82573);
    std::size_t checked = 0;
    for (unsigned geometry = 0; geometry < 3; ++geometry) {
        Map map;
        for (std::size_t p = 0; p < map.size(); ++p) {
            map[p] = geometry == 0 ? p >> 7 : geometry == 1 ? (p < 32768 ? p >> 8 : 511) : 511;
        }
        for (std::size_t n = 0; n <= 260; ++n) {
            for (unsigned pattern = 0; pattern < 5; ++pattern) {
                auto source = generate(n, pattern == 3 ? "dominant" : "uniform", rng());
                if (pattern == 1) {
                    for (std::size_t i = 0; i < n; ++i) source[i] = i & 1 ? 0 : UINT32_MAX;
                }
                if (pattern == 2) std::sort(source.rbegin(), source.rend());
                const auto bounds = exact_bounds(source, map);
                if (pattern == 4) source = group_stably(source, map, bounds);
                const auto misplaced = misplaced_count(source.data(), map, bounds);
                auto expected = source;
                std::sort(expected.begin(), expected.end());
                const auto margin = 16 + (n + pattern) % 16;
                for (const bool track : {false, true}) {
                    Keys storage(margin + n + 16, guard);
                    auto* data = storage.data() + margin;
                    std::copy(source.begin(), source.end(), data);
                    if (track) {
                        if (supersort::cycle_partition_u32<true>(data, map.data(), bounds.data()) != misplaced) {
                            throw std::runtime_error("write count differs from initial misplaced positions");
                        }
                    } else {
                        supersort::cycle_partition_u32(data, map.data(), bounds.data());
                    }
                    check_partition(data, map, bounds, expected);
                    const auto clean = [](Key key) { return key == guard; };
                    if (!std::all_of(storage.data(), data, clean) ||
                        !std::all_of(data + n, storage.data() + storage.size(), clean)) throw std::runtime_error("touched guards");
                    ++checked;
                }
            }
        }
    }
    std::cout << "verified," << checked << '\n';
}

void timed(std::size_t n, std::string_view family, std::uint64_t seed, int repeats) {
    auto source = generate(n, family, seed);
    seed_vq_for_benchmark(seed ^ 0xe441a769fe90d12bULL, 811);
    Map map;
    choose_ranges(source.data(), n, map);
    const auto prepared = exact_bounds(source, map);
    if (family == "grouped") source = group_stably(source, map, prepared);
    const auto misplaced = misplaced_count(source.data(), map, prepared);
    if (family == "grouped" && misplaced != 0) throw std::runtime_error("grouped input has misplaced keys");
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys storage(n + 15);
    const auto mod64 = reinterpret_cast<std::uintptr_t>(storage.data()) % 64;
    auto* data = storage.data() + ((64 - mod64) % 64) / sizeof(Key);
    std::copy(source.begin(), source.end(), data);
    const auto writes = supersort::cycle_partition_u32<true>(data, map.data(), prepared.data());
    if (writes != misplaced) throw std::runtime_error("write count differs from initial misplaced positions");
    check_partition(data, map, prepared, expected);

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
            Bounds actual;
            const auto start = Clock::now();
            const auto work = run(arm, data, n, map, prepared, actual);
            const auto stop = Clock::now();
            if (!std::equal(expected.begin(), expected.end(), data)) throw std::runtime_error("sort differs from std::sort");
            if (std::string_view(work.route) == "blocks" && actual != prepared) {
                throw std::runtime_error("blocks and cycles have different range boundaries");
            }
            if (round >= 0) {
                std::cout << round << ',' << name(arm) << ',' << ms(stop - start) << ',' << work.split_ms << ','
                          << work.finish_ms << ',' << work.bins << ',' << work.largest << ',' << work.route << ','
                          << (arm == Arm::cycles ? writes : 0) << ',' << misplaced << '\n';
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
