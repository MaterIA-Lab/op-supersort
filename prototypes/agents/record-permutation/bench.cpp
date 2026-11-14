#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <iterator>
#include <limits>
#include <memory>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <immintrin.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <sched.h>
#endif

#if defined(RECORD_BENCH_WITH_IPS)
#include <ips2ra.hpp>
#include <ips4o.hpp>
#endif
#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>
#include <ska_sort.hpp>
#include <x86simdsort-static-incl.h>

namespace {

using Clock = std::chrono::steady_clock;
using Word = std::uint64_t;
constexpr unsigned band_bits = 12;
constexpr unsigned slot_bits = 16;
constexpr std::size_t band_size = std::size_t{1} << band_bits;
constexpr std::size_t window_size = std::size_t{1} << slot_bits;
constexpr std::size_t eviction_bytes = 96 * 1024 * 1024;

template <std::size_t Bytes>
struct alignas(Bytes) Row {
    std::uint32_t key;
    std::uint32_t ordinal;
    std::array<Word, (Bytes - 8) / sizeof(Word)> payload;
};

static_assert(sizeof(Row<16>) == 16 && sizeof(Row<64>) == 64);

std::uint64_t nanoseconds(Clock::duration elapsed) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count();
}

void pin_thread(unsigned cpu) {
#ifdef _WIN32
    if (cpu >= std::numeric_limits<DWORD_PTR>::digits ||
        !SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << cpu)) {
        throw std::runtime_error("cannot pin benchmark thread to the requested CPU");
    }
#else
    cpu_set_t set;
    CPU_ZERO(&set);
    if (cpu >= CPU_SETSIZE) throw std::invalid_argument("CPU number exceeds CPU_SETSIZE");
    CPU_SET(cpu, &set);
    if (sched_setaffinity(0, sizeof(set), &set) != 0) {
        throw std::runtime_error("cannot pin benchmark thread to the requested CPU");
    }
#endif
}

void evict_cache(const std::vector<Word>& buffer) {
    const volatile Word* lines = buffer.data();
    for (std::size_t i = 0; i < buffer.size(); i += 64 / sizeof(Word)) {
        (void)lines[i];
    }
}

template <std::size_t Bytes>
void fill_input(Row<Bytes>* source, std::size_t n, Word seed) {
    std::mt19937_64 random(seed);
    for (std::size_t i = 0; i < n; ++i) {
        source[i].key = static_cast<std::uint32_t>(random());
        source[i].ordinal = static_cast<std::uint32_t>(i);
        for (std::size_t field = 0; field < source[i].payload.size(); ++field) {
            source[i].payload[field] = (i + 1) * Word{0x9e3779b97f4a7c15} ^
                                       (field + 1) * Word{0xbf58476d1ce4e5b9};
        }
    }
}

template <std::size_t Bytes>
bool stable_order(const Row<Bytes>& left, const Row<Bytes>& right) {
    return left.key == right.key ? left.ordinal < right.ordinal : left.key < right.key;
}

template <std::size_t Bytes>
void build_expected(const Row<Bytes>* source, Row<Bytes>* expected, std::size_t n) {
    auto order = std::make_unique<std::pair<std::uint32_t, std::uint32_t>[]>(n);
    for (std::size_t i = 0; i < n; ++i) order[i] = {source[i].key, source[i].ordinal};
    std::sort(order.get(), order.get() + n);
    for (std::size_t i = 0; i < n; ++i) expected[i] = source[order[i].second];
}

void set_vq_pivots(Word seed, unsigned round) {
    std::mt19937_64 random(seed ^ 0xe7037ed1a0b428dbULL ^ round);
    auto* state = hwy::detail::GetGeneratorStateStatic();
    state[0] = random();
    state[1] = random();
    state[2] = 1;
}

template <bool Streaming, std::size_t Bytes>
void store_row(const Row<Bytes>* source, Row<Bytes>* dest) {
    if constexpr (Streaming) {
        const auto* input = reinterpret_cast<const __m128i*>(source);
        auto* output = reinterpret_cast<__m128i*>(dest);
        for (std::size_t lane = 0; lane < Bytes / sizeof(__m128i); ++lane) {
            _mm_stream_si128(output + lane, _mm_load_si128(input + lane));
        }
    } else {
        *dest = *source;
    }
}

template <unsigned Distance, bool Streaming = false, std::size_t Bytes>
void gather(const Word* order, const Row<Bytes>* source, Row<Bytes>* dest, std::size_t n) {
    std::size_t i = 0;
    if constexpr (Distance != 0) {
        for (; i + Distance < n; ++i) {
            __builtin_prefetch(source + static_cast<std::uint32_t>(order[i + Distance]), 0, 1);
            store_row<Streaming>(source + static_cast<std::uint32_t>(order[i]), dest + i);
        }
    }
    for (; i < n; ++i) {
        store_row<Streaming>(source + static_cast<std::uint32_t>(order[i]), dest + i);
    }
    if constexpr (Streaming) _mm_sfence();
}

template <std::size_t Bytes>
void grouped_gather(const Word* order, const Row<Bytes>* source, Row<Bytes>* dest,
                    std::size_t n) {
    const auto bands = (n + band_size - 1) / band_size;
    auto cursor = std::make_unique_for_overwrite<std::uint32_t[]>(bands);
    auto requests = std::make_unique_for_overwrite<std::uint32_t[]>(std::min(n, window_size));
    for (std::size_t begin = 0; begin < n; begin += window_size) {
        const auto window = std::min(window_size, n - begin);
        const auto* ranks = order + begin;
        auto* output = dest + begin;
        std::fill_n(cursor.get(), bands, 0u);
        for (std::size_t slot = 0; slot < window; ++slot) {
            const auto original = static_cast<std::uint32_t>(ranks[slot]);
            ++cursor[original >> band_bits];
        }
        std::uint32_t prefix = 0;
        for (std::size_t band = 0; band < bands; ++band) {
            const auto count = cursor[band];
            cursor[band] = prefix;
            prefix += count;
        }
        for (std::size_t slot = 0; slot < window; ++slot) {
            const auto original = static_cast<std::uint32_t>(ranks[slot]);
            const auto offset = original & (band_size - 1);
            requests[cursor[original >> band_bits]++] =
                static_cast<std::uint32_t>((offset << slot_bits) | slot);
        }
        // Grouping advances each cursor to the end of its band's request range.
        std::size_t request_index = 0;
        for (std::size_t band = 0; band < bands; ++band) {
            const auto* input = source + band * band_size;
            for (; request_index < cursor[band]; ++request_index) {
                const auto request = requests[request_index];
                output[request & (window_size - 1)] = input[request >> slot_bits];
            }
        }
    }
}

enum class Algorithm {
    copy, vq_plain, vq_prefetch16, vq_prefetch32, vq_prefetch64, vq_stream32, xss_prefetch32,
    ska_direct, ips2ra_prefetch32, ips4o_direct, grouped
};

struct Method {
    Algorithm algorithm;
    std::string_view name;
};

constexpr Method methods[] = {
    {Algorithm::copy, "copy"},
    {Algorithm::vq_plain, "vq_plain"},
    {Algorithm::vq_prefetch16, "vq_prefetch16"},
    {Algorithm::vq_prefetch32, "vq_prefetch32"},
    {Algorithm::vq_prefetch64, "vq_prefetch64"},
    {Algorithm::vq_stream32, "vq_stream32"},
    {Algorithm::xss_prefetch32, "xss_prefetch32"},
    {Algorithm::ska_direct, "ska_direct"},
#if defined(RECORD_BENCH_WITH_IPS)
    {Algorithm::ips2ra_prefetch32, "ips2ra_prefetch32"},
    {Algorithm::ips4o_direct, "ips4o_direct"},
#endif
    {Algorithm::grouped, "grouped"},
};

struct Timings {
    std::uint64_t total;
    std::uint64_t encode;
    std::uint64_t sort;
    std::uint64_t materialize;
};

template <std::size_t Bytes>
Timings measure(Algorithm algorithm, const Row<Bytes>* source, Row<Bytes>* dest, std::size_t n) {
    const auto start = Clock::now();
    if (algorithm == Algorithm::copy) {
        std::memcpy(dest, source, n * Bytes);
        const auto elapsed = nanoseconds(Clock::now() - start);
        return {elapsed, 0, 0, elapsed};
    }

    if (algorithm == Algorithm::ska_direct || algorithm == Algorithm::ips4o_direct) {
        std::memcpy(dest, source, n * Bytes);
        const auto copied = Clock::now();
        if (algorithm == Algorithm::ska_direct) {
            ska_sort(dest, dest + n, [](const Row<Bytes>& row) {
                return (Word{row.key} << 32) | row.ordinal;
            });
        }
#if defined(RECORD_BENCH_WITH_IPS)
        else {
            ips4o::sort(dest, dest + n, stable_order<Bytes>);
        }
#endif
        const auto sorted = Clock::now();
        return {nanoseconds(sorted - start), 0, nanoseconds(sorted - copied),
                nanoseconds(copied - start)};
    }
    auto order = std::make_unique_for_overwrite<Word[]>(n);
    for (std::size_t i = 0; i < n; ++i) {
        order[i] = (Word{source[i].key} << 32) | i;
    }
    const auto encoded = Clock::now();
    if (algorithm == Algorithm::xss_prefetch32) {
        x86simdsortStatic::qsort(order.get(), n);
#if defined(RECORD_BENCH_WITH_IPS)
    } else if (algorithm == Algorithm::ips2ra_prefetch32) {
        ips2ra::sort(order.get(), order.get() + n);
#endif
    } else {
        hwy::HWY_NAMESPACE::VQSortStatic(order.get(), n, hwy::SortAscending());
    }
    const auto sorted = Clock::now();

    switch (algorithm) {
        case Algorithm::vq_plain:
            gather<0>(order.get(), source, dest, n);
            break;
        case Algorithm::vq_prefetch16:
            gather<16>(order.get(), source, dest, n);
            break;
        case Algorithm::vq_prefetch32:
            gather<32>(order.get(), source, dest, n);
            break;
        case Algorithm::vq_prefetch64:
            gather<64>(order.get(), source, dest, n);
            break;
        case Algorithm::vq_stream32:
            gather<32, true>(order.get(), source, dest, n);
            break;
        case Algorithm::xss_prefetch32:
        case Algorithm::ips2ra_prefetch32:
            gather<32>(order.get(), source, dest, n);
            break;
        case Algorithm::grouped:
            grouped_gather(order.get(), source, dest, n);
            break;
        default:
            throw std::logic_error("invalid indirect sort");
    }
    const auto materialized = Clock::now();
    order.reset();
    const auto end = Clock::now();
    return {nanoseconds(end - start), nanoseconds(encoded - start), nanoseconds(sorted - encoded),
            nanoseconds(materialized - sorted)};
}

template <std::size_t Bytes>
void run(std::size_t n, Word seed, unsigned repeats) {
    auto input = std::make_unique_for_overwrite<Row<Bytes>[]>(n);
    auto output = std::make_unique_for_overwrite<Row<Bytes>[]>(n);
    auto expected = std::make_unique_for_overwrite<Row<Bytes>[]>(n);
    fill_input(input.get(), n, seed);
    build_expected(input.get(), expected.get(), n);
    const std::vector<Word> eviction(eviction_bytes / sizeof(Word), seed);
    std::vector<Method> shuffled(std::begin(methods), std::end(methods));
    std::mt19937_64 shuffler(seed ^ 0x8ebc6af09c88c6e3ULL);

    std::cout << "rows,row_bytes,seed,round,method,total_ns,encode_ns,sort_ns,materialize_ns\n";
    for (unsigned round = 0; round <= repeats; ++round) {
        std::shuffle(shuffled.begin(), shuffled.end(), shuffler);
        for (const auto& method : shuffled) {
            std::memset(output.get(), 0xff, n * Bytes);
            evict_cache(eviction);
            set_vq_pivots(seed, round);
            const auto times = measure(method.algorithm, input.get(), output.get(), n);
            const auto* correct = method.algorithm == Algorithm::copy ? input.get() : expected.get();
            if (std::memcmp(output.get(), correct, n * Bytes) != 0) {
                throw std::runtime_error("bytewise output mismatch in " + std::string(method.name));
            }
            std::cout << n << ',' << Bytes << ',' << seed << ',' << round << ',' << method.name
                      << ',' << times.total << ',' << times.encode << ',' << times.sort << ','
                      << times.materialize << '\n';
        }
        std::cout.flush();
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 6) {
            throw std::invalid_argument("usage: bench ROWS ROW_BYTES SEED REPEATS LOGICAL_CPU");
        }
        const auto n = std::stoull(argv[1]);
        const auto bytes = std::stoull(argv[2]);
        const auto seed = std::stoull(argv[3]);
        const auto repeats = std::stoull(argv[4]);
        const auto cpu = std::stoull(argv[5]);
        if (n == 0 || n > UINT32_MAX || (bytes != 16 && bytes != 64) || repeats > 1000 ||
            cpu > std::numeric_limits<unsigned>::max()) {
            throw std::invalid_argument("expected positive 32-bit ROWS, 16 or 64 ROW_BYTES, "
                                        "REPEATS <= 1000, and a valid LOGICAL_CPU");
        }
        pin_thread(static_cast<unsigned>(cpu));
        if (bytes == 16) {
            run<16>(n, seed, static_cast<unsigned>(repeats));
        } else {
            run<64>(n, seed, static_cast<unsigned>(repeats));
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
