#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <numeric>
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

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>
#include <pdqsort.h>
#include <x86simdsort-static-incl.h>

#include "permutation.hpp"

namespace {
using namespace checkpoint_cycles;
using Clock = std::chrono::steady_clock;

std::uint64_t elapsed_ns(Clock::time_point begin, Clock::time_point end) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(end - begin).count();
}

void pin_thread(unsigned cpu) {
#ifdef _WIN32
    if (cpu >= std::numeric_limits<DWORD_PTR>::digits ||
        !SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << cpu)) {
        throw std::runtime_error("cannot pin benchmark thread");
    }
#else
    cpu_set_t set;
    CPU_ZERO(&set);
    if (cpu >= CPU_SETSIZE) throw std::runtime_error("CPU exceeds CPU_SETSIZE");
    CPU_SET(cpu, &set);
    if (sched_setaffinity(0, sizeof(set), &set)) throw std::runtime_error("cannot pin benchmark thread");
#endif
}

enum class Algorithm { checkpoint, cycle, cached, streaming, x86_streaming, pdq };
struct Method {
    const char* name;
    Algorithm algorithm;
};
constexpr std::array methods{
    Method{"checkpoint64_vqsort", Algorithm::checkpoint},
    Method{"scalar_cycle_vqsort", Algorithm::cycle},
    Method{"cached_gather_vqsort", Algorithm::cached},
    Method{"stream_gather_vqsort", Algorithm::streaming},
    Method{"stream_gather_x86", Algorithm::x86_streaming},
    Method{"pdqsort_rows", Algorithm::pdq},
};

struct Phases {
    std::uint64_t index_ns;
    std::uint64_t materialize_ns;
};

bool row_less(const Row& left, const Row& right) {
    return left.key < right.key || (left.key == right.key && left.ordinal < right.ordinal);
}

Phases sort_rows(Row* rows, std::size_t size, Tag* tags, Row* scratch, Algorithm algorithm) {
    const auto begin = Clock::now();
    if (algorithm == Algorithm::pdq) {
        pdqsort(rows, rows + size, row_less);
        return {elapsed_ns(begin, Clock::now()), 0};
    }
    for (std::size_t index = 0; index < size; ++index) {
        tags[index] = (Tag{rows[index].key} << 32) | static_cast<std::uint32_t>(index);
    }
    if (algorithm == Algorithm::x86_streaming) {
        x86simdsortStatic::qsort(tags, size);
    } else {
        hwy::HWY_NAMESPACE::VQSortStatic(tags, size, hwy::SortAscending());
    }
    const auto materialize_begin = Clock::now();
    switch (algorithm) {
        case Algorithm::checkpoint: checkpoint_permute(rows, tags, size); break;
        case Algorithm::cycle: scalar_cycles(rows, tags, size); break;
        case Algorithm::cached: gather_and_copy_back<false>(rows, tags, scratch, size); break;
        case Algorithm::streaming:
        case Algorithm::x86_streaming: gather_and_copy_back<true>(rows, tags, scratch, size); break;
        case Algorithm::pdq: break;
    }
    return {elapsed_ns(begin, materialize_begin), elapsed_ns(materialize_begin, Clock::now())};
}

void fill_rows(std::vector<Row>& rows, std::uint64_t seed, std::string_view distribution) {
    std::mt19937_64 random(seed);
    for (std::size_t index = 0; index < rows.size(); ++index) {
        auto& row = rows[index];
        row.key = static_cast<std::uint32_t>(random());
        if (distribution == "eight") row.key &= 7;
        row.ordinal = static_cast<std::uint32_t>(index);
        for (auto& value : row.payload) value = random();
    }
}

std::vector<std::uint32_t> oracle(const std::vector<Row>& original) {
    std::vector<std::uint32_t> order(original.size());
    std::iota(order.begin(), order.end(), 0u);
    std::sort(order.begin(), order.end(), [&](auto left, auto right) {
        return row_less(original[left], original[right]);
    });
    return order;
}

void verify(const std::vector<Row>& rows, const std::vector<Row>& original,
            const std::vector<std::uint32_t>& order, const char* method) {
    for (std::size_t index = 0; index < rows.size(); ++index) {
        if (std::memcmp(&rows[index], &original[order[index]], sizeof(Row))) {
            throw std::runtime_error(std::string(method) + " row mismatch at " + std::to_string(index));
        }
    }
}

void verify_permutation(const std::vector<std::uint32_t>& order) {
    const std::size_t size = order.size();
    std::vector<Row> original(size), rows(size), scratch(size);
    fill_rows(original, 271 + size, "uniform");
    std::vector<Tag> tags(size);
    for (unsigned method = 0; method < 4; ++method) {
        rows = original;
        for (std::size_t index = 0; index < size; ++index) tags[index] = order[index];
        if (method == 0) checkpoint_permute(rows.data(), tags.data(), size);
        else if (method == 1) scalar_cycles(rows.data(), tags.data(), size);
        else if (method == 2) gather_and_copy_back<false>(rows.data(), tags.data(), scratch.data(), size);
        else gather_and_copy_back<true>(rows.data(), tags.data(), scratch.data(), size);
        verify(rows, original, order, "permutation primitive");
    }
}

void correctness_screen() {
    std::uint64_t cases = 0;
    for (unsigned size = 0; size <= 8; ++size) {
        std::vector<std::uint32_t> order(size);
        std::iota(order.begin(), order.end(), 0u);
        do {
            verify_permutation(order);
            ++cases;
        } while (std::next_permutation(order.begin(), order.end()));
    }
    constexpr std::array<std::size_t, 11> sizes{3, 63, 64, 65, 127, 128, 129, 257, 511, 1023, 4097};
    std::mt19937_64 random(1601);
    for (const auto size : sizes) {
        std::vector<std::uint32_t> order(size);
        std::iota(order.begin(), order.end(), 0u);
        verify_permutation(order);
        std::reverse(order.begin(), order.end());
        verify_permutation(order);
        std::iota(order.begin(), order.end(), 0u);
        std::rotate(order.begin(), order.begin() + 1, order.end());
        verify_permutation(order);
        std::iota(order.begin(), order.end(), 0u);
        if (size > 5) {
            order[1] = 3;
            order[3] = 5;
            order[5] = 1;
        }
        verify_permutation(order);
        cases += 4;
        for (unsigned trial = 0; trial < 12; ++trial) {
            std::shuffle(order.begin(), order.end(), random);
            verify_permutation(order);
            ++cases;
        }
        std::vector<Row> original(size), rows(size), scratch(size);
        fill_rows(original, 271 + size, "eight");
        const auto expected = oracle(original);
        std::vector<Tag> tags(size);
        for (const auto& method : methods) {
            rows = original;
            sort_rows(rows.data(), size, tags.data(), scratch.data(), method.algorithm);
            verify(rows, original, expected, method.name);
        }
    }
    std::cout << "Verified " << cases << " supplied permutations with all four movers; "
              << sizes.size() * methods.size() << " complete sorts also passed\n";
}

void flush_bytes(const void* address, std::size_t size) {
    auto begin = reinterpret_cast<std::uintptr_t>(address) & ~std::uintptr_t{63};
    const auto end = reinterpret_cast<std::uintptr_t>(address) + size;
    for (; begin < end; begin += 64) _mm_clflush(reinterpret_cast<const void*>(begin));
}

void run(std::size_t size, std::string_view distribution, std::uint64_t seed, unsigned repeats) {
    std::vector<Row> original(size), rows(size), scratch(size);
    std::vector<Tag> tags(size);
    fill_rows(original, seed, distribution);
    const auto expected = oracle(original);
    std::mt19937_64 random(seed ^ 0xd0b053a3ull);
    auto shuffled = methods;
    std::cout << "records,distribution,seed,round,method,index_ns,materialize_ns,total_ns,verified\n";
    for (unsigned round = 0; round <= repeats; ++round) {
        std::shuffle(shuffled.begin(), shuffled.end(), random);
        for (const auto& method : shuffled) {
            std::memcpy(rows.data(), original.data(), size * sizeof(Row));
            if (size >= 1048576) {
                flush_bytes(rows.data(), size * sizeof(Row));
                flush_bytes(scratch.data(), size * sizeof(Row));
                flush_bytes(tags.data(), size * sizeof(Tag));
                _mm_mfence();
            }
            const auto begin = Clock::now();
            const auto phases = sort_rows(rows.data(), size, tags.data(), scratch.data(), method.algorithm);
            const auto total = elapsed_ns(begin, Clock::now());
            verify(rows, original, expected, method.name);
            std::cout << size << ',' << distribution << ',' << seed << ',' << round << ','
                      << method.name << ',' << phases.index_ns << ',' << phases.materialize_ns
                      << ',' << total << ",true\n";
        }
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") {
            correctness_screen();
            return 0;
        }
        if (argc != 6) throw std::invalid_argument("usage: bench N uniform|eight SEED REPEATS CPU");
        const auto size = std::stoull(argv[1]);
        const std::string_view distribution(argv[2]);
        const auto seed = std::stoull(argv[3]);
        const auto repeats = std::stoul(argv[4]);
        const auto cpu = std::stoul(argv[5]);
        if (!size || size > (std::size_t{1} << 24) || repeats < 1 || repeats > 1000 || cpu > 1023 ||
            (distribution != "uniform" && distribution != "eight")) {
            throw std::invalid_argument("invalid benchmark argument");
        }
        pin_thread(static_cast<unsigned>(cpu));
        run(size, distribution, seed, static_cast<unsigned>(repeats));
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
