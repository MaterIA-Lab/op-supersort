#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include "include/supersort/dictionary_u32.hpp"

#ifdef SUPERSORT_E054
#include "include/supersort/combined_u32.hpp"
#include "vendor/x86-simd-sort/src/x86simdsort-static-incl.h"
void ips2ra_sort_u32(std::uint32_t*, std::size_t);
#endif

void vq_sort_u32(std::uint32_t*, std::size_t);
void seed_vq_for_benchmark(std::uint64_t, std::uint64_t);

namespace {

using Key = std::uint32_t;
using Keys = std::vector<Key>;
using Dictionary = std::array<Key, 16>;
using Route = supersort::DictionaryRoute;
using Work = supersort::DictionaryWork;

constexpr std::size_t minimum_size = 1u << 18;
constexpr std::size_t samples = 256;
constexpr Key guard = 0xdeadbeefu;

enum class Arm {
    single, striped, vq,
#ifdef SUPERSORT_E054
    combined, e047, simd, ips2ra,
#endif
};
constexpr std::array arms{Arm::single, Arm::striped, Arm::vq};
#ifdef SUPERSORT_E054
constexpr std::array full_arms{Arm::combined, Arm::e047, Arm::striped, Arm::vq, Arm::simd, Arm::ips2ra};
#endif

const char* name(Arm arm) {
    switch (arm) {
        case Arm::single: return "single";
        case Arm::striped: return "striped";
        case Arm::vq: return "vq";
#ifdef SUPERSORT_E054
        case Arm::combined: return "combined";
        case Arm::e047: return "e047";
        case Arm::simd: return "simd";
        case Arm::ips2ra: return "ips2ra";
#endif
    }
    throw std::logic_error("unknown arm");
}

const char* name(Route route) {
    switch (route) {
        case Route::bypass: return "bypass";
        case Route::collision: return "collision";
        case Route::reject: return "reject";
        case Route::counted: return "counted";
    }
    throw std::logic_error("unknown route");
}

Dictionary multiplicative() {
    Dictionary keys;
    for (Key i = 0; i < keys.size(); ++i) keys[i] = i * 2654435761u;
    return keys;
}

Dictionary permuted(std::mt19937_64& rng) {
    Dictionary keys;
    for (auto next = keys.begin(); next != keys.end(); ++next) {
        Key key;
        do { key = Key(rng()); } while (std::find(keys.begin(), next, key) != next);
        *next = key;
    }
    return keys;
}

Dictionary powers() {
    Dictionary keys{};
    for (std::size_t i = 1; i < keys.size(); ++i) keys[i] = Key{1} << (i - 1);
    return keys;
}

Keys draw_from(std::size_t n, const Dictionary& keys, std::mt19937_64& rng) {
    Keys result(n);
    for (Key& key : result) key = keys[rng() & 15u];
    return result;
}

void cover_samples(Keys& source, const Dictionary& keys) {
    const auto stride = source.size() / samples;
    if (stride < 2) throw std::invalid_argument("coverage cases require disjoint sample positions");
    for (std::size_t i = 0; i < keys.size(); ++i) source[stride * i] = keys[i];
}

Keys dominant(std::size_t n, const Dictionary& keys, std::mt19937_64& rng) {
    const auto stride = n / samples;
    if (stride < 2 || n / 20 < keys.size() - 1) {
        throw std::invalid_argument("dominant case too small for exact sample coverage");
    }
    Keys result(n, keys[0]);
    // Reserve one sampled position for each minor key while fixing the total mixture at 95/5.
    std::size_t minor = n / 20 - (keys.size() - 1);
    std::size_t unsampled = n - samples;
    std::size_t sample = 0;
    for (std::size_t i = 0; i < n; ++i) {
        if (sample < samples && i == sample * stride) {
            if (sample < keys.size()) result[i] = keys[sample];
            ++sample;
        } else {
            if (minor && std::uniform_int_distribution<std::size_t>(0, unsampled - 1)(rng) < minor) {
                result[i] = keys[1 + rng() % (keys.size() - 1)];
                --minor;
            }
            --unsampled;
        }
    }
    return result;
}

#ifdef SUPERSORT_E054
bool generate_windows(Keys& source, std::string_view family, std::mt19937_64& rng) {
    constexpr Key dense = 0x54880000u;
    const auto n = source.size();
    if (family == "prefix_distinct") {
        if (n / 4 + (n % 4 != 0) > (std::size_t{1} << 24)) {
            throw std::invalid_argument("prefix_distinct exhausted its four prefixes");
        }
        constexpr std::array<Key, 4> prefixes{0x00u, 0x23u, 0xa7u, 0xffu};
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
    } else if (family == "dense16" || family == "late_reject") {
        for (auto& key : source) key = dense | (Key(rng()) & 65535u);
        if (family == "late_reject") {
            if (n < minimum_size) throw std::invalid_argument("late_reject requires the probe enabled");
            const auto stride = n / samples;
            for (std::size_t i = n, external = n / 8 + 1; external != 0; --external) {
                do { --i; } while (i % stride == 0 && i / stride < samples);
                const Key draw = Key(rng());
                source[i] = (draw >> 16) == (dense >> 16) ? draw ^ 0x80000000u : draw;
            }
        }
    } else if (family == "skew") {
        for (auto& key : source) {
            key = Key(rng()) % 100 < 95 ? (dense | 0x2000u) | (Key(rng()) & 4095u) : Key(rng());
        }
    } else if (family == "bimodal") {
        for (auto& key : source) {
            const auto draw = Key(rng());
            key = (draw & 4096u ? 0x18010000u : 0xd8200000u) | (draw & 4095u);
        }
    } else if (family == "near_sorted") {
        for (auto& key : source) key = Key(rng());
        std::sort(source.begin(), source.end());
        for (unsigned swap = 0; n != 0 && swap < 20; ++swap) {
            const auto left = rng() % n;
            const auto right = rng() % n;
            std::swap(source[left], source[right]);
        }
    } else {
        return false;
    }
    return true;
}
#endif

Keys generate(std::size_t n, std::string_view family, std::uint64_t seed) {
    std::mt19937_64 rng(seed);
    if (family == "few") return draw_from(n, multiplicative(), rng);
    if (family == "few_permute") {
        const auto dictionary = permuted(rng);
        return draw_from(n, dictionary, rng);
    }
    if (family == "few_dominant") {
        const auto dictionary = permuted(rng);
        return dominant(n, dictionary, rng);
    }
    if (family == "few_powers") {
        const auto dictionary = powers();
        auto source = draw_from(n, dictionary, rng);
        cover_samples(source, dictionary);
        return source;
    }
    if (family == "early_unknown" || family == "late_unknown") {
        const auto dictionary = multiplicative();
        auto source = draw_from(n, dictionary, rng);
        cover_samples(source, dictionary);
        // Swap the same known key with the unknown across the two adversaries.
        const Key known = source[1];
        const Key unknown = 1;
        if (std::find(dictionary.begin(), dictionary.end(), unknown) != dictionary.end()) {
            throw std::logic_error("unknown key in dictionary");
        }
        source[1] = family == "early_unknown" ? unknown : known;
        source.back() = family == "early_unknown" ? known : unknown;
        return source;
    }
    if (family == "equal") return Keys(n, 0xffffffffu);
    Keys source(n);
    if (family == "uniform") {
        for (Key& key : source) key = Key(rng());
    } else if (family == "mixed") {
        for (Key& key : source) key = rng() & 1u ? 0x54880000u | (Key(rng()) & 4095u) : Key(rng());
#ifdef SUPERSORT_E054
    } else if (generate_windows(source, family, rng)) {
        return source;
#endif
    } else {
        throw std::invalid_argument("unknown distribution");
    }
    return source;
}

Work run(Arm arm, Key* a, std::size_t n) {
    switch (arm) {
        case Arm::single: return supersort::dictionary_u32<1>(a, n);
        case Arm::striped: return supersort::dictionary_u32<4>(a, n);
        case Arm::vq:
            if (n > 1) vq_sort_u32(a, n);
            return {Route::bypass, 0, 0};
#ifdef SUPERSORT_E054
        default: break;
#endif
    }
    throw std::logic_error("unknown arm");
}

bool same_work(Work first, Work second) {
    return first.route == second.route && first.examined == second.examined &&
           first.proposals == second.proposals;
}

#ifdef SUPERSORT_E054
supersort::CombinedWork run_full(Arm arm, Key* a, std::size_t n) {
    switch (arm) {
        case Arm::combined: return supersort::combined_u32(a, n);
        case Arm::e047: return {false, {}, supersort::window_e047_u32(a, n)};
        case Arm::striped: return {true, supersort::dictionary_u32<4>(a, n), {}};
        case Arm::vq: if (n > 1) vq_sort_u32(a, n); break;
        case Arm::simd: if (n > 1) x86simdsortStatic::qsort(a, n); break;
        case Arm::ips2ra: if (n > 1) ips2ra_sort_u32(a, n); break;
        case Arm::single: throw std::logic_error("single is not part of the complete comparison");
    }
    return {};
}

struct Telemetry {
    std::string_view route;
    std::size_t examined;
    std::size_t proposals;
};

Telemetry record(Arm arm, supersort::CombinedWork work, std::size_t windows) {
    if (work.used_dictionary) {
        const auto dict = work.dictionary;
        switch (dict.route) {
            case Route::bypass: return {"dict_bypass", dict.examined, dict.proposals};
            case Route::collision: return {"dict_collision", dict.examined, dict.proposals};
            case Route::reject: return {"dict_reject", dict.examined, dict.proposals};
            case Route::counted: return {"dict_counted", dict.examined, dict.proposals};
        }
    }
    if (arm == Arm::combined || arm == Arm::e047) {
        const auto window = work.window;
        using WindowRoute = supersort::WindowRoute;
        switch (window.route) {
            case WindowRoute::bypass: return {"window_bypass", window.examined, windows};
            case WindowRoute::reject: return {"window_reject", window.examined, windows};
            case WindowRoute::constant: return {"window_constant", window.examined, windows};
            case WindowRoute::one: return {"window_one", window.examined, windows};
            case WindowRoute::two: return {"window_two", window.examined, windows};
        }
    }
    return {"bypass", 0, 0};
}
#endif

int run_timed(std::size_t n, std::string_view family, std::uint64_t seed, int repeats) {
    const auto source = generate(n, family, seed);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys data(n);
    std::mt19937_64 order_rng(seed ^ 0x09bcac24ce2fa4a1ULL);
#ifdef SUPERSORT_E054
    auto order = full_arms;
    // Record the deterministic proposal from untouched input. This cannot affect dispatch.
    const auto window_proposals = supersort::window_detail::propose(source.data(), n).count;
#else
    auto order = arms;
    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
#endif
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
#ifndef SUPERSORT_E054
        const std::uint64_t first = pivots();
        const std::uint64_t second = pivots();
        Work single{}, striped{};
#endif
        for (Arm arm : order) {
            std::copy(source.begin(), source.end(), data.begin());
#ifdef SUPERSORT_E054
            const auto start = std::chrono::steady_clock::now();
            const auto work = run_full(arm, data.data(), n);
#else
            seed_vq_for_benchmark(first, second);
            const auto start = std::chrono::steady_clock::now();
            const Work work = run(arm, data.data(), n);
#endif
            const auto stop = std::chrono::steady_clock::now();
            if (data != expected) throw std::runtime_error(std::string(name(arm)) + " differs from std::sort");
#ifndef SUPERSORT_E054
            if (arm == Arm::single) single = work;
            if (arm == Arm::striped) striped = work;
#endif
            if (round >= 0) {
                const double ms = std::chrono::duration<double, std::milli>(stop - start).count();
#ifdef SUPERSORT_E054
                const auto telem = record(arm, work, window_proposals);
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << telem.route << ','
                          << telem.examined << ',' << telem.proposals << '\n';
#else
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << name(work.route) << ','
                          << work.examined << ',' << work.proposals << '\n';
#endif
            }
        }
#ifndef SUPERSORT_E054
        if (!same_work(single, striped)) throw std::runtime_error("counter arms disagree on route or work");
#endif
    }
    return 0;
}

void verify(const Keys& source, std::size_t offset, Work expected_work, std::size_t& checked) {
    const auto margin = 16 + offset;
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    for (Arm arm : arms) {
        Keys storage(margin + source.size() + 16, guard);
        Key* data = storage.data() + margin;
        std::copy(source.begin(), source.end(), data);
        const auto work = run(arm, data, source.size());
        const auto untouched = [](Key key) { return key == guard; };
        if (!std::equal(expected.begin(), expected.end(), data) ||
            !std::all_of(storage.data(), data, untouched) ||
            !std::all_of(data + source.size(), storage.data() + storage.size(), untouched) ||
            !same_work(work, arm == Arm::vq ? Work{Route::bypass, 0, 0} : expected_work)) {
            throw std::runtime_error(std::string(name(arm)) + " failed exactness, guards or work");
        }
        ++checked;
    }
}

#ifdef SUPERSORT_E054
void verify_full(const Keys& source, std::size_t offset, Telemetry combined_expected,
                 std::size_t& checked) {
    const auto margin = 16 + offset;
    const auto windows = supersort::window_detail::propose(source.data(), source.size()).count;
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    for (Arm arm : full_arms) {
        Keys storage(margin + source.size() + 16, guard);
        Key* data = storage.data() + margin;
        std::copy(source.begin(), source.end(), data);
        const auto work = record(arm, run_full(arm, data, source.size()), windows);
        const auto untouched = [](Key key) { return key == guard; };
        if (!std::equal(expected.begin(), expected.end(), data) ||
            !std::all_of(storage.data(), data, untouched) ||
            !std::all_of(data + source.size(), storage.data() + storage.size(), untouched)) {
            throw std::runtime_error(std::string(name(arm)) + " failed exactness or guards");
        }
        if (arm == Arm::combined &&
            (work.route != combined_expected.route || work.examined != combined_expected.examined ||
             work.proposals != combined_expected.proposals)) {
            throw std::runtime_error("combined failed route or work");
        }
        ++checked;
    }
}

void verify_combined(std::size_t& checked) {
    for (std::size_t offset : {0, 1, 7, 15}) {
        for (std::size_t n : {0, 1, 2, 7, 8, 9, 15, 16, 17, 31, 32, 33, 127, 128, 129, 255, 256, 257}) {
            verify_full(generate(n, "uniform", 31147), offset, {"dict_bypass", 0, 0}, checked);
        }
        verify_full({0, 0, 65535u, 65536u, 0xfffffffeu, 0xffffffffu, 0xffffffffu},
                    offset, {"dict_bypass", 0, 0}, checked);
    }
    constexpr auto n = minimum_size + 3;
    verify_full(generate(n, "uniform", 36767), 1, {"dict_bypass", 0, 17}, checked);
    verify_full(generate(n, "dense16", 33851), 7, {"window_one", n, 1}, checked);
    verify_full(generate(n, "bimodal", 34019), 15, {"window_two", n, 2}, checked);
    verify_full(generate(n, "equal", 36809), 1, {"window_constant", n, 1}, checked);
    verify_full(generate(n, "few_powers", 56533), 7, {"window_one", n, 1}, checked);
    verify_full(generate(n, "late_reject", 42853), 15, {"window_reject", n, 1}, checked);
    verify_full(generate(n, "early_unknown", 41719), 1, {"dict_reject", 4, 16}, checked);
    verify_full(generate(n, "late_unknown", 41719), 7, {"dict_reject", n, 16}, checked);
    std::mt19937_64 rng(43391);
    const auto known = multiplicative();
    auto source = draw_from(n, known, rng);
    cover_samples(source, known);
    verify_full(source, 15, {"dict_counted", n, 16}, checked);
    auto sparse_powers = powers();
    for (Key& key : sparse_powers) key <<= 16;
    source = draw_from(n, sparse_powers, rng);
    cover_samples(source, sparse_powers);
    verify_full(source, 15, {"dict_collision", 0, 16}, checked);
}
#endif

int verify_all() {
    std::size_t checked = 0;
    constexpr Work bypass{Route::bypass, 0, 0};
    for (std::size_t offset : {0, 1, 7, 15}) {
        for (std::size_t n : {0, 1, 2, 7, 8, 9, 15, 16, 17, 31, 32, 33, 127, 128, 129, 255, 256, 257}) {
            verify(generate(n, "uniform", 54403), offset, bypass, checked);
        }
        verify({0, 0, 65535u, 65536u, 0xfffffffeu, 0xffffffffu, 0xffffffffu}, offset, bypass, checked);
    }
    verify(Keys(minimum_size - 1, 0), 1, bypass, checked);
    verify(Keys(minimum_size, 0xffffffffu), 7, {Route::bypass, 0, 1}, checked);
    verify(generate(minimum_size, "uniform", 36767), 1, {Route::bypass, 0, 17}, checked);
    verify(generate(minimum_size, "few_powers", 56533), 7, {Route::collision, 0, 16}, checked);
    verify(generate(minimum_size, "early_unknown", 41719), 15, {Route::reject, 4, 16}, checked);
    const auto dictionary = multiplicative();
    std::mt19937_64 rng(43391);
    for (std::size_t tail = 0; tail < 4; ++tail) {
        const auto n = minimum_size + tail;
        auto known = draw_from(n, dictionary, rng);
        cover_samples(known, dictionary);
        verify(known, tail, {Route::counted, n, 16}, checked);
        verify(generate(n, "late_unknown", 41719), tail, {Route::reject, n, 16}, checked);
    }
    Keys extremes(minimum_size + 3, 0);
    for (std::size_t i = 2; i < extremes.size(); i += 3) extremes[i] = 0xffffffffu;
    extremes[extremes.size() / samples] = 0xffffffffu;
    verify(extremes, 15, {Route::counted, extremes.size(), 2}, checked);
#ifdef SUPERSORT_E054
    verify_combined(checked);
#endif
    std::cout << "verified," << checked << '\n';
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") return verify_all();
        if (argc != 5) throw std::invalid_argument("usage: n distribution seed repetitions | --verify");
        const auto n = std::stoull(argv[1]);
        const auto repeats = std::stoi(argv[4]);
        if (!n || n > std::numeric_limits<Key>::max() || repeats < 1) {
            throw std::invalid_argument("unsupported size or repetition count");
        }
        return run_timed(n, argv[2], std::stoull(argv[3]), repeats);
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
