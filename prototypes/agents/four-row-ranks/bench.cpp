#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
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

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>
#include <x86simdsort-static-incl.h>

namespace {

using Row = std::uint32_t;
using Clock = std::chrono::steady_clock;
constexpr std::size_t large_group_count = 1'048'576;

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

constexpr Row key(Row row) { return row >> 16; }

void insertion_sort4(Row* rows) {
    for (unsigned i = 1; i < 4; ++i) {
        const Row current = rows[i];
        unsigned j = i;
        while (j > 0 && key(current) < key(rows[j - 1])) {
            rows[j] = rows[j - 1];
            --j;
        }
        rows[j] = current;
    }
}

__m256i load_rows(const Row* rows) {
    return _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows));
}

void store_rows(Row* rows, __m256i packed) {
    _mm256_storeu_si256(reinterpret_cast<__m256i*>(rows), packed);
}

__m256i lanes() { return _mm256_setr_epi32(0, 1, 2, 3, 4, 5, 6, 7); }

__m256i tagged_keys(__m256i rows) {
    // Replace each low 16-bit payload with its array slot as a tie breaker.
    return _mm256_blend_epi16(rows, lanes(), 0x55);
}

template <int PartnerLanes, int UseMax>
__m256i exchange_keys(__m256i tagged) {
    const auto other = _mm256_shuffle_epi32(tagged, PartnerLanes);
    return _mm256_blend_epi32(_mm256_min_epu32(tagged, other),
                             _mm256_max_epu32(tagged, other), UseMax);
}

void network_sort2x4(Row* rows) {
    const auto packed = load_rows(rows);
    auto tags = tagged_keys(packed);
    tags = exchange_keys<_MM_SHUFFLE(2, 3, 0, 1), 0xaa>(tags);
    tags = exchange_keys<_MM_SHUFFLE(1, 0, 3, 2), 0xcc>(tags);
    tags = exchange_keys<_MM_SHUFFLE(3, 1, 2, 0), 0x44>(tags);
    // VPERMD takes only the low three index bits from each lane.
    store_rows(rows, _mm256_permutevar8x32_epi32(packed, tags));
}

struct alignas(16) ShuffleMask {
    std::array<std::uint8_t, 16> bytes;
};

constexpr auto make_lookup() {
    std::array<ShuffleMask, 64> table{};
    std::array<unsigned, 4> order{0, 1, 2, 3};
    do {
        std::array<unsigned, 4> rank{};
        for (unsigned slot = 0; slot < 4; ++slot) rank[order[slot]] = slot;
        // Compare the four adjacent cyclic pairs followed by the two opposite pairs.
        unsigned mask = 0;
        for (unsigned i = 0; i < 4; ++i) {
            mask |= (rank[i] > rank[(i + 1) % 4]) << i;
        }
        mask |= (rank[0] > rank[2]) << 4;
        mask |= (rank[1] > rank[3]) << 5;
        for (unsigned result_byte = 0; result_byte < 16; ++result_byte) {
            table[mask].bytes[result_byte] =
                static_cast<std::uint8_t>(4 * order[result_byte / 4] + result_byte % 4);
        }
    } while (std::next_permutation(order.begin(), order.end()));
    return table;
}

constexpr auto lookup = make_lookup();

__m256i as_signed_order(__m256i tags) {
    return _mm256_xor_si256(tags, _mm256_set1_epi32(std::numeric_limits<std::int32_t>::min()));
}

void lookup_sort2x4(Row* rows) {
    const auto packed = load_rows(rows);
    const auto ordered = as_signed_order(tagged_keys(packed));
    const auto cycle = _mm256_cmpgt_epi32(
        ordered, _mm256_shuffle_epi32(ordered, _MM_SHUFFLE(0, 3, 2, 1)));
    const auto opposite = _mm256_cmpgt_epi32(
        ordered, _mm256_shuffle_epi32(ordered, _MM_SHUFFLE(3, 2, 3, 2)));
    const unsigned adjacent_bits = _mm256_movemask_ps(_mm256_castsi256_ps(cycle));
    const unsigned opposite_bits = _mm256_movemask_ps(_mm256_castsi256_ps(opposite));
    const auto low = (adjacent_bits & 15) | ((opposite_bits & 3) << 4);
    const auto high = (adjacent_bits >> 4) | (opposite_bits & 0x30);
    const auto shuffle_low = _mm_load_si128(reinterpret_cast<const __m128i*>(&lookup[low]));
    const auto shuffle_high = _mm_load_si128(reinterpret_cast<const __m128i*>(&lookup[high]));
    store_rows(rows, _mm256_shuffle_epi8(packed, _mm256_set_m128i(shuffle_high, shuffle_low)));
}

void rank_sort2x4(Row* rows) {
    const auto packed = load_rows(rows);
    const auto ordered = as_signed_order(tagged_keys(packed));
    const auto a = _mm256_cmpgt_epi32(
        ordered, _mm256_shuffle_epi32(ordered, _MM_SHUFFLE(0, 3, 2, 1)));
    const auto b = _mm256_cmpgt_epi32(
        ordered, _mm256_shuffle_epi32(ordered, _MM_SHUFFLE(1, 0, 3, 2)));
    const auto c = _mm256_cmpgt_epi32(
        ordered, _mm256_shuffle_epi32(ordered, _MM_SHUFFLE(2, 1, 0, 3)));
    const auto wins = _mm256_add_epi32(_mm256_add_epi32(a, b), c);
    const auto rank = _mm256_sub_epi32(_mm256_setzero_si256(), wins);

    // Write the source lane numbers to non-overlapping byte positions using their ranks.
    const auto shifted = _mm256_sllv_epi32(lanes(), _mm256_slli_epi32(rank, 3));
    const auto pairs = _mm256_or_si256(
        shifted, _mm256_shuffle_epi32(shifted, _MM_SHUFFLE(2, 3, 0, 1)));
    const auto merged = _mm256_or_si256(
        pairs, _mm256_shuffle_epi32(pairs, _MM_SHUFFLE(1, 0, 3, 2)));
    const auto offsets = _mm256_setr_epi32(0, 8, 16, 24, 0, 8, 16, 24);
    const auto indices = _mm256_srlv_epi32(merged, offsets);
    store_rows(rows, _mm256_permutevar8x32_epi32(packed, indices));
}

template <void (*Sort)(Row*)>
void paired_sort(Row* rows, std::size_t groups) {
    const auto paired = groups & ~std::size_t{1};
    for (std::size_t i = 0; i < paired; i += 2) Sort(rows + 4 * i);
    if (paired != groups) insertion_sort4(rows + 4 * paired);
}

template <bool Highway>
void individual_sort(Row* rows, std::size_t groups) {
    for (std::size_t i = 0; i < groups; ++i) {
        auto* group = rows + 4 * i;
        std::array<Row, 4> tags;
        for (unsigned slot = 0; slot < 4; ++slot) tags[slot] = (group[slot] & 0xffff0000u) | slot;
        if constexpr (Highway) {
            hwy::HWY_NAMESPACE::VQSortStatic(tags.data(), tags.size(), hwy::SortAscending());
        } else {
            x86simdsortStatic::qsort(tags.data(), tags.size());
        }
        const std::array<Row, 4> sorted{group[tags[0] & 3], group[tags[1] & 3],
                                         group[tags[2] & 3], group[tags[3] & 3]};
        std::copy(sorted.begin(), sorted.end(), group);
    }
}

struct Method {
    const char* name;
    void (*sort)(Row*, std::size_t);
};

constexpr std::array methods{
    Method{"vqsort", individual_sort<true>},
    Method{"x86_simd_sort", individual_sort<false>},
    Method{"avx2_network", paired_sort<network_sort2x4>},
    Method{"avx2_lookup", paired_sort<lookup_sort2x4>},
    Method{"avx2_rank", paired_sort<rank_sort2x4>},
};

std::vector<Row> make_expected(const std::vector<Row>& input) {
    auto expected = input;
    for (auto row = expected.begin(); row != expected.end(); row += 4) {
        std::stable_sort(row, row + 4, [](Row a, Row b) { return key(a) < key(b); });
    }
    return expected;
}

void verify(const Method& method, const std::vector<Row>& output,
            const std::vector<Row>& expected) {
    if (output != expected) throw std::runtime_error(std::string(method.name) + " output mismatch");
}

void verify_exhaustively() {
    constexpr std::array<Row, 4> alphabet{0, 1, 32768, 65535};
    std::vector<Row> input;
    for (unsigned i = 0; i < 257; ++i) {
        for (unsigned slot = 0; slot < 4; ++slot) {
            const Row value = alphabet[(i >> (2 * slot)) & 3];
            input.push_back((value << 16) | (0xf010 - slot));
        }
    }
    const auto expected = make_expected(input);
    for (const auto& method : methods) {
        auto output = input;
        method.sort(output.data(), output.size() / 4);
        verify(method, output, expected);
    }
}

void evict_cache(const std::vector<std::uint64_t>& lines) {
    const volatile auto* data = lines.data();
    for (std::size_t i = 0; i < lines.size(); i += 64 / sizeof(std::uint64_t)) (void)data[i];
}

void run(std::size_t groups, std::string_view distribution, std::uint64_t seed, unsigned repeats) {
    std::mt19937_64 random(seed);
    std::vector<Row> input(groups * 4);
    const auto key_mask = distribution == "uniform" ? 0xffffu : 7u;
    for (Row& row : input) {
        const auto word = random();
        const Row key_bits = static_cast<Row>(word >> 32) & key_mask;
        row = (key_bits << 16) | (static_cast<Row>(word) & 0xffffu);
    }
    const auto expected = make_expected(input);
    auto output = input;
    const std::size_t eviction_words =
        groups >= large_group_count ? 96 * 1024 * 1024 / sizeof(std::uint64_t) : 0;
    const std::vector<std::uint64_t> eviction(eviction_words, seed);
    auto shuffled = methods;

    std::cout << "groups,distribution,seed,round,method,total_ns\n";
    for (unsigned round = 0; round <= repeats; ++round) {
        std::shuffle(shuffled.begin(), shuffled.end(), random);
        for (const auto& method : shuffled) {
            std::copy(input.begin(), input.end(), output.begin());
            evict_cache(eviction);
            const auto start = Clock::now();
            method.sort(output.data(), groups);
            const auto elapsed = Clock::now() - start;
            verify(method, output, expected);
            std::cout << groups << ',' << distribution << ',' << seed << ',' << round << ','
                      << method.name << ','
                      << std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count()
                      << '\n';
        }
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") {
            verify_exhaustively();
            std::cout << "Verified all five methods on 257 groups\n";
            return 0;
        }
        if (argc != 6) {
            throw std::invalid_argument("usage: bench GROUPS uniform|eight SEED REPEATS LOGICAL_CPU");
        }
        const auto groups = std::stoull(argv[1]);
        const std::string_view distribution(argv[2]);
        const auto seed = std::stoull(argv[3]);
        const auto repeats = std::stoull(argv[4]);
        const auto cpu = std::stoull(argv[5]);
        if (groups == 0 || groups > std::numeric_limits<std::size_t>::max() / sizeof(Row) / 4 ||
            (distribution != "uniform" && distribution != "eight") || repeats > 1000 ||
            cpu > std::numeric_limits<unsigned>::max()) {
            throw std::invalid_argument("invalid group count, distribution, repeats or CPU");
        }
        pin_thread(static_cast<unsigned>(cpu));
        run(groups, distribution, seed, static_cast<unsigned>(repeats));
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
