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

enum class Arm { single, striped, vq };
constexpr std::array arms{Arm::single, Arm::striped, Arm::vq};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::single: return "single";
        case Arm::striped: return "striped";
        case Arm::vq: return "vq";
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
    }
    throw std::logic_error("unknown arm");
}

bool same_work(Work first, Work second) {
    return first.route == second.route && first.examined == second.examined &&
           first.proposals == second.proposals;
}

int run_timed(std::size_t n, std::string_view family, std::uint64_t seed, int repeats) {
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
        const std::uint64_t first = pivots();
        const std::uint64_t second = pivots();
        Work single{}, striped{};
        for (Arm arm : order) {
            std::copy(source.begin(), source.end(), data.begin());
            seed_vq_for_benchmark(first, second);
            const auto start = std::chrono::steady_clock::now();
            const Work work = run(arm, data.data(), n);
            const auto stop = std::chrono::steady_clock::now();
            if (data != expected) throw std::runtime_error(std::string(name(arm)) + " differs from std::sort");
            if (arm == Arm::single) single = work;
            if (arm == Arm::striped) striped = work;
            if (round >= 0) {
                const double ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << name(work.route) << ','
                          << work.examined << ',' << work.proposals << '\n';
            }
        }
        if (!same_work(single, striped)) throw std::runtime_error("counter arms disagree on route or work");
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
