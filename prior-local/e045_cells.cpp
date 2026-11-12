#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include "include/supersort/cells_u32.hpp"

namespace {

using Key = uint32_t;
using Keys = std::vector<Key>;
using Work = supersort::CellWork;

struct Prepared {
    std::array<size_t, 257> offsets{};
    Keys keys;
};

Prepared prepare(const Keys& source) {
    Prepared result;
    result.keys.resize(source.size());
    for (Key x : source) ++result.offsets[(x >> 24) + 1];
    for (size_t p = 1; p < result.offsets.size(); ++p) {
        result.offsets[p] += result.offsets[p - 1];
    }
    auto cursor = result.offsets;
    for (Key x : source) result.keys[cursor[x >> 24]++] = x;
    return result;
}

void append_late_overflow(Keys& keys, size_t count, Key prefix, std::mt19937_64& rng) {
    if (count == 0) return;
    const size_t colliding_cells = count / 32 + 1;
    if (count > 65536 || 4 * colliding_cells > count) {
        throw std::invalid_argument("late_overflow requires 4 to 65536 keys per group");
    }
    const size_t singletons = count - 4 * colliding_cells;
    const Key stride = Key(rng()) | 1u;
    const Key offset = Key(rng());
    auto append = [&](size_t cell, Key suffix) {
        const Key q = (stride * Key(cell) + offset) & 65535u;
        keys.push_back(prefix | (q << 8) | (suffix & 255u));
    };
    for (size_t i = 0; i < singletons; ++i) append(i, Key(rng()));
    for (size_t i = 0; i < colliding_cells; ++i) {
        const Key suffix = Key(rng());
        for (Key j = 0; j < 4; ++j) append(singletons + i, suffix + j);
    }
}

Keys generate(size_t n, std::string_view distribution, uint64_t seed) {
    std::mt19937_64 rng(seed);
    Keys keys;
    keys.reserve(n);
    if (distribution == "late_overflow") {
        for (Key p = 0; p < 256; ++p) {
            append_late_overflow(keys, n / 256 + (p < n % 256), p << 24, rng);
        }
        return keys;
    }
    if (distribution == "prefix_distinct") {
        if (n / 4 + (n % 4 != 0) > (size_t{1} << 24)) {
            throw std::invalid_argument("prefix_distinct exhausted its four prefixes");
        }
        constexpr std::array<Key, 4> prefixes{0x00u, 0x23u, 0xa7u, 0xffu};
        std::array<Key, 4> stride, offset;
        for (size_t p = 0; p < prefixes.size(); ++p) {
            stride[p] = Key(rng()) | 1u;
            offset[p] = Key(rng());
        }
        for (size_t i = 0; i < n; ++i) {
            const size_t p = i % 4;
            const Key suffix = (stride[p] * Key(i / 4) + offset[p]) & 0xffffffu;
            keys.push_back((prefixes[p] << 24) | suffix);
        }
        return keys;
    }
    if (distribution != "uniform" && distribution != "near_sorted" &&
        distribution != "dense16" && distribution != "skew" &&
        distribution != "bimodal" && distribution != "mixed" && distribution != "few") {
        throw std::invalid_argument("unknown distribution");
    }
    for (size_t i = 0; i < n; ++i) {
        const Key x = Key(rng());
        if (distribution == "dense16") {
            keys.push_back(0x7f120000u | (x & 65535u));
        } else if (distribution == "skew") {
            keys.push_back(x % 100 < 95 ? 0x54882000u | (Key(rng()) & 4095u) : Key(rng()));
        } else if (distribution == "bimodal") {
            const Key base = x & 4096u ? 0x18012000u : 0xd8203000u;
            keys.push_back(base | (x & 4095u));
        } else if (distribution == "mixed") {
            keys.push_back(x & 1u ? 0x54882000u | (Key(rng()) & 4095u) : Key(rng()));
        } else if (distribution == "few") {
            keys.push_back((x & 15u) * 2654435761u);
        } else {
            keys.push_back(x);
        }
    }
    if (distribution == "near_sorted" && n != 0) {
        std::sort(keys.begin(), keys.end());
        for (unsigned k = 0; k < 20; ++k) {
            const size_t left = rng() % n;
            const size_t right = rng() % n;
            std::swap(keys[left], keys[right]);
        }
    }
    return keys;
}

Work run_leaf(bool cells, const Key* source, Key* destination,
              const std::array<size_t, 257>& offsets) {
    if (cells) return supersort::cells_u32(source, destination, offsets);
    supersort::leaf_vq_u32(source, destination, offsets);
    return {};
}

int run_timed(size_t n, std::string_view distribution, uint64_t seed, int repeats) {
    auto expected = generate(n, distribution, seed);
    const auto prepared = prepare(expected);
    std::sort(expected.begin(), expected.end());
    Keys destination(n);
    std::mt19937_64 order(seed ^ 0x4e72b115c56351f3ULL);
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        const bool cells_first = (order() & 1u) != 0;
        for (bool cells : {cells_first, !cells_first}) {
            std::fill(destination.begin(), destination.end(), 0xdeadbeefu);
            const auto start = std::chrono::steady_clock::now();
            const Work work = run_leaf(cells, prepared.keys.data(), destination.data(), prepared.offsets);
            const auto stop = std::chrono::steady_clock::now();
            const char* algorithm = cells ? "leaf_cells" : "leaf_vq";
            if (destination != expected) {
                throw std::runtime_error(std::string(algorithm) + " differs from std::sort");
            }
            if (round >= 0) {
                const double ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << algorithm << ',' << ms << ',' << work.skipped << ','
                          << work.aborted << ',' << work.completed << ',' << work.attempt_reads
                          << ',' << work.residual << '\n';
            }
        }
    }
    return 0;
}

void verify(const Keys& input, std::string_view label, Work expected_work, size_t& checked) {
    constexpr Key guard = 0xdeadbeefu;
    const auto prepared = prepare(input);
    auto expected = input;
    std::sort(expected.begin(), expected.end());
    for (size_t offset : {0, 1, 7, 15}) {
        const size_t margin = 16 + offset;
        Keys source(input.size() + margin + 32, guard);
        std::copy(prepared.keys.begin(), prepared.keys.end(), source.begin() + margin);
        const auto saved = source;
        for (bool cells : {false, true}) {
            Keys destination(source.size(), guard);
            Key* output = destination.data() + margin;
            const Work work = run_leaf(cells, source.data() + margin, output, prepared.offsets);
            const auto is_guard = [](Key x) { return x == guard; };
            if (source != saved || !std::equal(expected.begin(), expected.end(), output) ||
                !std::all_of(destination.data(), output, is_guard) ||
                !std::all_of(output + input.size(), destination.data() + destination.size(), is_guard)) {
                throw std::runtime_error(std::string(label) + " failed exactness or guards");
            }
            if (cells && (work.skipped != expected_work.skipped ||
                          work.aborted != expected_work.aborted ||
                          work.completed != expected_work.completed ||
                          work.attempt_reads != expected_work.attempt_reads ||
                          work.residual != expected_work.residual)) {
                throw std::runtime_error(std::string(label) + " failed branch work counts");
            }
            ++checked;
        }
    }
}

int verify_all() {
    size_t checked = 0;
    verify({}, "empty", {}, checked);
    verify({0xffffffffu}, "singleton", {1, 0, 0, 0, 0}, checked);
    verify({0xffffffffu, 0, 0, 0xffffffffu}, "extremes and duplicates", {2, 0, 0, 0, 0}, checked);
    std::mt19937_64 rng(0x98a7d3c1ULL);
    for (size_t n : {15, 16, 17, 127, 128, 129, 4095, 4096, 4097}) {
        Keys keys(n);
        for (size_t i = 0; i < n; ++i) {
            keys[i] = 0xff000000u | (Key(i) << 8) | (Key(rng()) & 255u);
        }
        std::shuffle(keys.begin(), keys.end(), rng);
        const Work expected = n < 4096 ? Work{1, 0, 0, 0, 0} : Work{0, 0, 1, n, 0};
        verify(keys, "minimum group size", expected, checked);
    }

    Keys duplicates(4096, 0xffffffffu);
    verify(duplicates, "early overflow", {0, 1, 0, 4096 / 32 + 4, 0}, checked);
    Keys late;
    append_late_overflow(late, 4096, 0u, rng);
    verify(late, "last-key overflow", {0, 1, 0, 4096, 0}, checked);
    late.pop_back();
    std::array<bool, 65536> seen{};
    for (Key x : late) seen[x >> 8] = true;
    const Key unused = Key(std::find(seen.begin(), seen.end(), false) - seen.begin());
    late.push_back((unused << 8) | 255u);
    verify(late, "full residual budget", {0, 0, 1, 4096, 4096 / 32}, checked);

    constexpr size_t capacity = 3 * 65536;
    constexpr size_t largest_possible_group = capacity + capacity / 31;
    Keys dense(largest_possible_group);
    for (size_t i = 0; i < dense.size(); ++i) dense[i] = Key(i % 65536) << 8;
    verify(dense, "maximum admissible group", {0, 0, 1, dense.size(), dense.size() / 32}, checked);
    dense.push_back(0);
    verify(dense, "size bound skip", {1, 0, 0, 0, 0}, checked);

    Keys epochs;
    for (Key p = 0; p < 256; ++p) {
        if (p % 63 == 0) {
            append_late_overflow(epochs, 4096, p << 24, rng);
        } else {
            for (Key q = 0; q < 4096; ++q) {
                const Key varying_cell = q + (p % 3) * 1024;
                epochs.push_back((p << 24) | (varying_cell << 8) | p);
            }
        }
    }
    verify(epochs, "epochs wrap across completed and aborted attempts", {0, 5, 251, 256 * 4096, 0}, checked);
    std::cout << "verified," << checked << '\n';
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") return verify_all();
        if (argc != 5) throw std::invalid_argument("usage: e045_cells n distribution seed repetitions | --verify");
        const int repeats = std::stoi(argv[4]);
        if (repeats < 1) throw std::invalid_argument("repetitions must be positive");
        return run_timed(std::stoull(argv[1]), argv[2], std::stoull(argv[3]), repeats);
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
