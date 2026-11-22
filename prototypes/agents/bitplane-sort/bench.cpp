#include <algorithm>
#include <array>
#include <bit>
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

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>
#include <x86simdsort-static-incl.h>

namespace {
constexpr std::size_t width = 32;
using Clock = std::chrono::steady_clock;

struct Buffers {
    std::vector<std::uint8_t> keys;
    std::vector<std::uint32_t> payloads;
    explicit Buffers(std::size_t groups) : keys(groups * width), payloads(groups * width) {}
};

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

void flush_bytes(const void* address, std::size_t size) {
    auto begin = reinterpret_cast<std::uintptr_t>(address) & ~std::uintptr_t{63};
    const auto end = reinterpret_cast<std::uintptr_t>(address) + size;
    for (; begin < end; begin += 64) _mm_clflush(reinterpret_cast<const void*>(begin));
}

void flush_buffers(const Buffers& input, const Buffers& output) {
    flush_bytes(input.keys.data(), input.keys.size());
    flush_bytes(input.payloads.data(), input.payloads.size() * sizeof(std::uint32_t));
    flush_bytes(output.keys.data(), output.keys.size());
    flush_bytes(output.payloads.data(), output.payloads.size() * sizeof(std::uint32_t));
    _mm_mfence();
}

struct Destination {
    const std::uint8_t* keys;
    const std::uint32_t* payloads;
    std::uint8_t* out_keys;
    std::uint32_t* out_payloads;
    unsigned used = 0;

    void emit(unsigned source) {
        out_keys[used] = keys[source];
        out_payloads[used++] = payloads[source];
    }

    void emit_mask(std::uint32_t mask) {
        while (mask) {
            emit(std::countr_zero(mask));
            mask &= mask - 1;
        }
    }
};

template <std::size_t... Bits>
std::array<std::uint32_t, 8> make_planes(__m256i keys, std::index_sequence<Bits...>) {
    return {static_cast<std::uint32_t>(_mm256_movemask_epi8(
        _mm256_slli_epi16(keys, static_cast<int>(7 - Bits))))...};
}

template <int Bit>
void refine(std::uint32_t members, const std::array<std::uint32_t, 8>& planes,
            Destination& destination) {
    if ((members & (members - 1)) == 0) {
        destination.emit(std::countr_zero(members));
        return;
    }
    const auto ones = members & planes[Bit];
    const auto zeros = members ^ ones;
    if constexpr (Bit == 0) {
        destination.emit_mask(zeros);
        destination.emit_mask(ones);
    } else {
        if (zeros) refine<Bit - 1>(zeros, planes, destination);
        if (ones) refine<Bit - 1>(ones, planes, destination);
    }
}

void bitplane_group(const std::uint8_t* keys, const std::uint32_t* payloads,
                    std::uint8_t* out_keys, std::uint32_t* out_payloads) {
    const auto packed = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(keys));
    const auto planes = make_planes(packed, std::make_index_sequence<8>{});
    Destination destination{keys, payloads, out_keys, out_payloads};
    refine<7>(0xffffffffu, planes, destination);
}

template <int Distance>
__m256i partner(__m256i value) {
    if constexpr (Distance == 8) return _mm256_permute2x128_si256(value, value, 1);
    if constexpr (Distance == 4) return _mm256_shuffle_epi32(value, _MM_SHUFFLE(1, 0, 3, 2));
    if constexpr (Distance == 2) return _mm256_shuffle_epi32(value, _MM_SHUFFLE(2, 3, 0, 1));
    if constexpr (Distance == 1) {
        const auto swaps = _mm256_setr_epi8(2, 3, 0, 1, 6, 7, 4, 5,
                                          10, 11, 8, 9, 14, 15, 12, 13,
                                          2, 3, 0, 1, 6, 7, 4, 5,
                                          10, 11, 8, 9, 14, 15, 12, 13);
        return _mm256_shuffle_epi8(value, swaps);
    }
    return value;
}

template <int Size, int Distance, int Base, std::size_t... Slots>
__m256i choose_mask(std::index_sequence<Slots...>) {
    return _mm256_setr_epi16(static_cast<short>(
        (((((Base + Slots) & Distance) != 0) ^ (((Base + Slots) & Size) != 0))) ? -1 : 0)...);
}

template <int Size, int Distance>
void network_pass(__m256i& low, __m256i& high) {
    const auto other_low = Distance == 16 ? high : partner<Distance>(low);
    const auto other_high = Distance == 16 ? low : partner<Distance>(high);
    const auto next_low = _mm256_blendv_epi8(
        _mm256_min_epu16(low, other_low), _mm256_max_epu16(low, other_low),
        choose_mask<Size, Distance, 0>(std::make_index_sequence<16>{}));
    const auto next_high = _mm256_blendv_epi8(
        _mm256_min_epu16(high, other_high), _mm256_max_epu16(high, other_high),
        choose_mask<Size, Distance, 16>(std::make_index_sequence<16>{}));
    low = next_low;
    high = next_high;
    if constexpr (Distance > 1) network_pass<Size, Distance / 2>(low, high);
}

template <int Size = 2>
void network_sort(__m256i& low, __m256i& high) {
    network_pass<Size, Size / 2>(low, high);
    if constexpr (Size < 32) network_sort<Size * 2>(low, high);
}

void network_group(const std::uint8_t* keys, const std::uint32_t* payloads,
                   std::uint8_t* out_keys, std::uint32_t* out_payloads) {
    const auto packed = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(keys));
    auto low = _mm256_cvtepu8_epi16(_mm256_castsi256_si128(packed));
    auto high = _mm256_cvtepu8_epi16(_mm256_extracti128_si256(packed, 1));
    low = _mm256_or_si256(_mm256_slli_epi16(low, 5),
        _mm256_setr_epi16(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15));
    high = _mm256_or_si256(_mm256_slli_epi16(high, 5),
        _mm256_setr_epi16(16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31));
    network_sort(low, high);
    alignas(32) std::uint16_t tags[width];
    _mm256_store_si256(reinterpret_cast<__m256i*>(tags), low);
    _mm256_store_si256(reinterpret_cast<__m256i*>(tags + 16), high);
    for (unsigned slot = 0; slot < width; ++slot) {
        out_keys[slot] = static_cast<std::uint8_t>(tags[slot] >> 5);
        out_payloads[slot] = payloads[tags[slot] & 31];
    }
}

template <bool Highway>
void library_group(const std::uint8_t* keys, const std::uint32_t* payloads,
                   std::uint8_t* out_keys, std::uint32_t* out_payloads) {
    alignas(64) std::uint32_t tags[width];
    for (unsigned slot = 0; slot < width; ++slot) tags[slot] = (keys[slot] << 5) | slot;
    if constexpr (Highway) {
        hwy::HWY_NAMESPACE::VQSortStatic(tags, width, hwy::SortAscending());
    } else {
        x86simdsortStatic::qsort(tags, width);
    }
    for (unsigned slot = 0; slot < width; ++slot) {
        out_keys[slot] = static_cast<std::uint8_t>(tags[slot] >> 5);
        out_payloads[slot] = payloads[tags[slot] & 31];
    }
}

void counting_group(const std::uint8_t* keys, const std::uint32_t* payloads,
                    std::uint8_t* out_keys, std::uint32_t* out_payloads) {
    std::uint16_t positions[256]{};
    for (unsigned slot = 0; slot < width; ++slot) ++positions[keys[slot]];
    unsigned total = 0;
    for (auto& position : positions) {
        const auto count = position;
        position = static_cast<std::uint16_t>(total);
        total += count;
    }
    for (unsigned slot = 0; slot < width; ++slot) {
        const unsigned output = positions[keys[slot]]++;
        out_keys[output] = keys[slot];
        out_payloads[output] = payloads[slot];
    }
}

using GroupSort = void (*)(const std::uint8_t*, const std::uint32_t*, std::uint8_t*, std::uint32_t*);

template <GroupSort Sort>
void batch(const Buffers& input, Buffers& output) {
    for (std::size_t first = 0; first < input.keys.size(); first += width) {
        Sort(input.keys.data() + first, input.payloads.data() + first,
             output.keys.data() + first, output.payloads.data() + first);
    }
}

struct Method {
    const char* name;
    void (*sort)(const Buffers&, Buffers&);
};
constexpr std::array methods{
    Method{"bitplane_membership", batch<bitplane_group>},
    Method{"avx2_network16", batch<network_group>},
    Method{"vqsort32", batch<library_group<true>>},
    Method{"x86_simd_sort32", batch<library_group<false>>},
    Method{"stable_counting256", batch<counting_group>},
};

Buffers expected_output(const Buffers& input) {
    Buffers result(input.keys.size() / width);
    for (std::size_t first = 0; first < input.keys.size(); first += width) {
        std::array<unsigned, width> slots;
        std::iota(slots.begin(), slots.end(), 0);
        std::stable_sort(slots.begin(), slots.end(), [&](unsigned a, unsigned b) {
            return input.keys[first + a] < input.keys[first + b];
        });
        for (unsigned slot = 0; slot < width; ++slot) {
            result.keys[first + slot] = input.keys[first + slots[slot]];
            result.payloads[first + slot] = input.payloads[first + slots[slot]];
        }
    }
    return result;
}

void verify(const Buffers& output, const Buffers& expected, const char* method) {
    if (output.keys != expected.keys || output.payloads != expected.payloads) {
        throw std::runtime_error(std::string(method) + " output mismatch");
    }
}

void correctness_screen() {
    constexpr std::array<std::uint8_t, 4> alphabet{0, 1, 128, 255};
    Buffers input(1024);
    std::mt19937_64 random(271);
    for (std::size_t group = 0; group < 1024; ++group) {
        for (unsigned slot = 0; slot < width; ++slot) {
            const auto at = group * width + slot;
            std::uint8_t key = static_cast<std::uint8_t>(random());
            if (group < 256) key = slot < 4 ? alphabet[(group >> (2 * slot)) & 3] : 128;
            else if (group < 384) key = static_cast<std::uint8_t>(group);
            else if (group < 512) key = static_cast<std::uint8_t>(slot * 8);
            else if (group < 640) key = static_cast<std::uint8_t>(255 - slot * 8);
            else if (group < 768) key = slot & 1 ? 255 : 0;
            else if (group < 896) key &= 7;
            else if (group < 928) key = slot == group - 896 ? 0 : 255;
            else if (group < 960) key = slot == group - 928 ? 255 : 0;
            input.keys[at] = key;
            input.payloads[at] = static_cast<std::uint32_t>(at);
        }
    }
    const auto expected = expected_output(input);
    Buffers output(1024);
    for (const auto& method : methods) {
        std::fill(output.keys.begin(), output.keys.end(), 0xa5);
        std::fill(output.payloads.begin(), output.payloads.end(), 0xdeadbeefu);
        method.sort(input, output);
        verify(output, expected, method.name);
    }
    std::cout << "Verified 1024 adversarial groups for all five methods\n";
}

void run(std::size_t groups, std::string_view distribution, std::uint64_t seed, unsigned repeats) {
    Buffers input(groups), output(groups);
    std::mt19937_64 random(seed);
    for (std::size_t at = 0; at < input.keys.size(); ++at) {
        const auto word = random();
        input.keys[at] = static_cast<std::uint8_t>((word >> 32) & (distribution == "uniform" ? 255 : 7));
        input.payloads[at] = static_cast<std::uint32_t>(word);
    }
    const auto expected = expected_output(input);
    std::mt19937_64 order_random(seed ^ 0xb690b9c5ull);
    auto shuffled = methods;
    std::cout << "groups,distribution,seed,round,method,total_ns,verified\n";
    for (unsigned round = 0; round <= repeats; ++round) {
        std::shuffle(shuffled.begin(), shuffled.end(), order_random);
        for (const auto& method : shuffled) {
            std::fill(output.keys.begin(), output.keys.end(), 0xa5);
            std::fill(output.payloads.begin(), output.payloads.end(), 0xdeadbeefu);
            if (groups >= 65536) flush_buffers(input, output);
            const auto begin = Clock::now();
            method.sort(input, output);
            const auto duration = std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - begin).count();
            verify(output, expected, method.name);
            std::cout << groups << ',' << distribution << ',' << seed << ',' << round << ','
                      << method.name << ',' << duration << ",true\n";
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
        if (argc != 6) throw std::invalid_argument("usage: bench GROUPS uniform|eight SEED REPEATS CPU");
        const auto groups = std::stoull(argv[1]);
        const std::string_view distribution(argv[2]);
        const auto seed = std::stoull(argv[3]);
        const auto repeats = std::stoul(argv[4]);
        const auto cpu = std::stoul(argv[5]);
        if (!groups || groups > 1048576 || repeats < 1 || repeats > 1000 || cpu > 1023 ||
            (distribution != "uniform" && distribution != "eight")) {
            throw std::invalid_argument("invalid argument");
        }
        pin_thread(static_cast<unsigned>(cpu));
        run(groups, distribution, seed, static_cast<unsigned>(repeats));
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
