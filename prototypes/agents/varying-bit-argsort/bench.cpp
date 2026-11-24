#include "argsort.hpp"

#include <array>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <sched.h>
#endif

namespace {
using namespace varying_bit_argsort;

struct NamedMethod {
    Method method;
    const char* name;
};

constexpr std::array methods{
    NamedMethod{Method::varying, "varying_bits"},
    NamedMethod{Method::ranges, "field_ranges"},
    NamedMethod{Method::leading, "leading_prefix"},
    NamedMethod{Method::pairs, "high_word_pairs"},
    NamedMethod{Method::indirect, "pdqsort_indices"},
};

void pin(unsigned cpu) {
#ifdef _WIN32
    if (cpu >= std::numeric_limits<DWORD_PTR>::digits ||
        !SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << cpu)) {
        throw std::runtime_error("cannot pin benchmark thread");
    }
#else
    cpu_set_t cpus;
    CPU_ZERO(&cpus);
    if (cpu >= CPU_SETSIZE) throw std::runtime_error("CPU exceeds supported affinity mask");
    CPU_SET(cpu, &cpus);
    if (sched_setaffinity(0, sizeof(cpus), &cpus)) throw std::runtime_error("cannot pin benchmark thread");
#endif
}

void flush(std::span<const Key> keys) {
    const auto bytes = std::as_bytes(keys);
    for (std::size_t offset = 0; offset < bytes.size(); offset += 64) {
        _mm_clflush(bytes.data() + offset);
    }
    if (!bytes.empty()) _mm_clflush(&bytes.back());
    _mm_mfence();
}

struct SplitMix64 {
    Word state;

    Word next() {
        Word value = (state += 0x9e3779b97f4a7c15ULL);
        value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
        value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
        return value ^ (value >> 31);
    }

    Word below(Word bound) {
        const Word threshold = -bound % bound;
        Word value;
        do {
            value = next();
        } while (value < threshold);
        return value % bound;
    }
};

Word morton_code(Word x, Word y, Word z) {
    constexpr Word x_mask = 0x1249249249249249ULL;
    return _pdep_u64(x, x_mask) | _pdep_u64(y, x_mask << 1) | _pdep_u64(z, x_mask << 2);
}

std::vector<Key> make_keys(std::size_t size, std::string_view shape, Word seed) {
    constexpr Word epoch_us = 1'730'000'000'000'000ULL;
    constexpr Word day_us = 86'400'000'000ULL;
    SplitMix64 rng{seed};
    std::vector<Key> keys(size);
    for (Key& key : keys) {
        if (shape == "composite") {
            const Word tenant = rng.below(1024);
            const Word sensor = rng.below(64);
            key = {(tenant << 32) | (sensor << 8) | 0x5a, epoch_us + rng.below(day_us)};
        } else if (shape == "morton") {
            const Word x = (rng.below(128) << 8) | 17;
            const Word y = (rng.below(128) << 8) | 53;
            key = {morton_code(x, y, 25), epoch_us + rng.below(day_us)};
        } else if (shape == "uniform") {
            key = {rng.next(), rng.next()};
        } else {
            throw std::invalid_argument("unregistered input shape");
        }
    }
    return keys;
}

std::vector<Index> stable_order(std::span<const Key> keys) {
    std::vector<Index> indices(keys.size());
    std::iota(indices.begin(), indices.end(), Index{0});
    std::stable_sort(indices.begin(), indices.end(), [&](Index i, Index j) {
        return key_less(keys[i], keys[j]);
    });
    return indices;
}

void verify_result(std::span<const Index> expected, const Result& result, const NamedMethod& method) {
    if (!std::equal(expected.begin(), expected.end(), result.indices.get())) {
        throw std::runtime_error(std::string("verification failed for ") + method.name);
    }
}

void verify_fixture(std::span<const Key> keys) {
    const auto expected = stable_order(keys);
    for (const auto& method : methods) {
        verify_result(expected, argsort(keys, method.method), method);
    }
}

void verify() {
    constexpr std::array universe{
        Key{0, 0}, Key{~Word{0}, 0}, Key{0, Word{1} << 63}, Key{0, 1},
    };
    std::size_t verified = 0;
    for (unsigned size = 0; size <= 6; ++size) {
        std::vector<Key> keys(size);
        for (unsigned state = 0; state < (1U << (size * 2)); ++state) {
            for (unsigned i = 0; i < size; ++i) keys[i] = universe[(state >> (i * 2)) & 3];
            verify_fixture(keys);
            ++verified;
        }
    }
    for (std::size_t size : {7, 31, 255, 256, 257, 1023, 1024, 1025, 8193}) {
        for (std::string_view shape : {"uniform", "composite", "morton"}) {
            verify_fixture(make_keys(size, shape, 72431));
            ++verified;
        }
        std::vector<Key> keys(size, Key{~Word{0}, ~Word{0}});
        verify_fixture(keys);
        SplitMix64 rng{521};
        for (Key& key : keys) key = {Word{1} << 63, rng.next()};
        keys.back().high = 0;
        verify_fixture(keys);
        verified += 2;
    }
    std::cout << "Verified " << verified << " fixtures for all five methods\n";
}

void measure(std::size_t size, std::string_view shape, Word seed, unsigned cpu) {
    pin(cpu);
    const auto keys = make_keys(size, shape, seed);
    const auto expected = stable_order(keys);
    const auto changed = variation(keys);
    const auto varying = std::popcount(changed.high) + std::popcount(changed.low);
    std::mt19937_64 order_rng(seed ^ 0x258a71e365c4906dULL);
    auto order = methods;
    std::cout << "rows,shape,seed,round,method,total_ns,prepare_ns,sort_ns,finish_ns,"
                 "variable_bits,prefix_bits,repaired,largest_repair,scratch_bytes,verified\n";
    for (unsigned round = 0; round < 7; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
        for (const auto& method : order) {
            flush(keys);
            const auto start = Clock::now();
            const auto result = argsort(keys, method.method);
            const auto elapsed = nanoseconds(start, Clock::now());
            verify_result(expected, result, method);
            const auto& s = result.stats;
            std::cout << size << ',' << shape << ',' << seed << ',' << round << ','
                      << method.name << ',' << elapsed << ',' << s.prepare_ns << ','
                      << s.sort_ns << ',' << s.finish_ns << ',' << varying << ',' << s.prefix_bits
                      << ',' << s.repaired << ',' << s.largest_repair << ',' << s.scratch_bytes
                      << ",true\n";
        }
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") {
            verify();
            return 0;
        }
        if (argc != 5) throw std::invalid_argument("usage: bench --verify | ROWS SHAPE SEED CPU");
        const auto size = std::stoull(argv[1]);
        const std::string_view shape = argv[2];
        if ((size != 1048576 && size != 4194304)
            || (shape != "uniform" && shape != "composite" && shape != "morton")) {
            throw std::invalid_argument("unregistered size or shape");
        }
        measure(size, shape, std::stoull(argv[3]), std::stoul(argv[4]));
        return 0;
    } catch (const std::exception& problem) {
        std::cerr << problem.what() << '\n';
        return 1;
    }
}
