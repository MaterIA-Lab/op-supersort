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

#include "include/supersort/windows_u32.hpp"
#include "vendor/x86-simd-sort/src/x86simdsort-static-incl.h"

void vq_sort_u32(uint32_t*, size_t);
void ips2ra_sort_u32(uint32_t*, size_t);

namespace {

using Key = uint32_t;
using Keys = std::vector<Key>;
using Work = supersort::WindowWork;
using Route = supersort::WindowRoute;

enum class Algorithm { window, cert_vq, vq, simd, ips2ra };

constexpr Key dense_base = 0x54880000u;
constexpr Key narrow_base = dense_base | 0x2000u;
constexpr Key left_base = 0x18010000u;
constexpr Key right_base = 0xd8200000u;
constexpr size_t minimum_size = size_t{1} << 18;

Keys make_late(size_t n, uint64_t seed, bool exceed_budget) {
    if (n < minimum_size) throw std::invalid_argument("late_reject requires the probe to be enabled");
    std::mt19937_64 rng(seed);
    Keys keys(n);
    for (Key& x : keys) x = dense_base | (Key(rng()) & 65535u);
    const size_t stride = n / 256;
    size_t external = n / 8 + exceed_budget;
    for (size_t i = n; external != 0; --external) {
        do { --i; } while (i % stride == 0 && i / stride < 256);
        const Key x = Key(rng());
        keys[i] = (x >> 16) == (dense_base >> 16) ? (x ^ 0x80000000u) : x;
    }
    return keys;
}

Keys make_pair(size_t n, uint64_t seed, bool shuffled) {
    std::mt19937_64 left(seed ^ 0xb57ac30519bf498eULL);
    std::mt19937_64 right(seed ^ 0x712b054ff4a3bc68ULL);
    std::mt19937_64 order(seed ^ 0x3dca58221669cf35ULL);
    size_t left_remaining = n / 2;
    size_t right_remaining = n - left_remaining;
    Keys keys(n);
    for (Key& x : keys) {
        const bool next_left = left_remaining != 0 &&
            (right_remaining == 0 || !shuffled || (order() & 1u));
        if (next_left) {
            x = left_base | (Key(left()) & 4095u);
            --left_remaining;
        } else {
            x = right_base | (Key(right()) & 4095u);
            --right_remaining;
        }
    }
    return keys;
}

Keys generate(size_t n, std::string_view distribution, uint64_t seed) {
    if (distribution == "late_reject") return make_late(n, seed, true);
    if (distribution == "window_pair_grouped") return make_pair(n, seed, false);
    if (distribution == "window_pair_shuffled") return make_pair(n, seed, true);
    if (distribution == "equal") return Keys(n, 0xffffffffu);
    std::mt19937_64 rng(seed);
    Keys keys(n);
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
            keys[i] = (prefixes[p] << 24) | suffix;
        }
        return keys;
    }
    if (distribution == "uniform" || distribution == "near_sorted") {
        for (Key& x : keys) x = Key(rng());
        if (distribution == "near_sorted" && n != 0) {
            std::sort(keys.begin(), keys.end());
            for (unsigned k = 0; k < 20; ++k) {
                const size_t left = rng() % n;
                const size_t right = rng() % n;
                std::swap(keys[left], keys[right]);
            }
        }
    } else if (distribution == "dense16") {
        for (Key& x : keys) x = dense_base | (Key(rng()) & 65535u);
    } else if (distribution == "skew") {
        for (Key& x : keys) {
            const bool dense = Key(rng()) % 100 < 95;
            x = dense ? narrow_base | (Key(rng()) & 4095u) : Key(rng());
        }
    } else if (distribution == "bimodal") {
        for (Key& x : keys) {
            const Key sample = Key(rng());
            x = (sample & 4096u ? left_base : right_base) | (sample & 4095u);
        }
    } else if (distribution == "mixed") {
        for (Key& x : keys) {
            const bool dense = (rng() & 1u) != 0;
            x = dense ? narrow_base | (Key(rng()) & 4095u) : Key(rng());
        }
    } else if (distribution == "few") {
        for (Key& x : keys) x = (Key(rng()) & 15u) * 2654435761u;
    } else {
        throw std::invalid_argument("unknown distribution");
    }
    return keys;
}

const char* name(Algorithm algorithm) {
    switch (algorithm) {
        case Algorithm::window: return "window";
        case Algorithm::cert_vq: return "cert_vq";
        case Algorithm::vq: return "vq";
        case Algorithm::simd: return "simd";
        case Algorithm::ips2ra: return "ips2ra";
    }
    throw std::logic_error("unknown algorithm");
}

const char* name(Route route) {
    switch (route) {
        case Route::bypass: return "bypass";
        case Route::reject: return "reject";
        case Route::constant: return "constant";
        case Route::one: return "one";
        case Route::two: return "two";
    }
    throw std::logic_error("unknown route");
}

Work run(Algorithm algorithm, Key* data, size_t n) {
    switch (algorithm) {
        case Algorithm::window: return supersort::window_u32(data, n);
        case Algorithm::cert_vq: return supersort::cert_vq_u32(data, n);
        case Algorithm::vq:
            if (n != 0) vq_sort_u32(data, n);
            break;
        case Algorithm::simd:
            if (n != 0) x86simdsortStatic::qsort(data, n);
            break;
        case Algorithm::ips2ra:
            if (n != 0) ips2ra_sort_u32(data, n);
            break;
    }
    return {Route::bypass, 0, 0};
}

bool same_work(Work a, Work b) {
    return a.route == b.route && a.examined == b.examined && a.residual == b.residual;
}

bool late_rejection(Work work, size_t n) {
    return work.route == Route::reject && work.examined > n - n / 10 && work.examined <= n;
}

int run_timed(bool filter, size_t n, std::string_view distribution, uint64_t seed, int repeats) {
    const auto source = generate(n, distribution, seed);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys data(n);
    std::vector<Algorithm> algorithms{Algorithm::window, Algorithm::vq};
    if (filter) algorithms.push_back(Algorithm::cert_vq);
    else {
        algorithms.push_back(Algorithm::simd);
        algorithms.push_back(Algorithm::ips2ra);
    }
    std::mt19937_64 order(seed ^ 0x77d4512db17ab1c7ULL);
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(algorithms.begin(), algorithms.end(), order);
        Work window{}, certified{};
        for (Algorithm algorithm : algorithms) {
            std::copy(source.begin(), source.end(), data.begin());
            const auto start = std::chrono::steady_clock::now();
            const Work work = run(algorithm, data.data(), n);
            const auto stop = std::chrono::steady_clock::now();
            if (data != expected) {
                throw std::runtime_error(std::string(name(algorithm)) + " differs from std::sort");
            }
            if (algorithm == Algorithm::window) window = work;
            if (algorithm == Algorithm::cert_vq) certified = work;
            if (round >= 0) {
                const double ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << name(algorithm) << ',' << ms << ',' << name(work.route)
                          << ',' << work.examined << ',' << work.residual << '\n';
            }
        }
        if (filter && !same_work(window, certified)) {
            throw std::runtime_error("window and cert_vq classified the same input differently");
        }
        if (distribution == "late_reject" && !late_rejection(window, n)) {
            throw std::runtime_error("late_reject did not reject in the final tenth of the input");
        }
    }
    return 0;
}

void verify(const Keys& input, std::string_view label, Work expected_work,
            size_t offset, size_t& checked) {
    constexpr Key guard = 0xdeadbeefu;
    const size_t margin = 16 + offset;
    auto expected = input;
    std::sort(expected.begin(), expected.end());
    Work first{};
    for (Algorithm algorithm : {Algorithm::window, Algorithm::cert_vq}) {
        Keys storage(input.size() + margin + 32, guard);
        Key* data = storage.data() + margin;
        std::copy(input.begin(), input.end(), data);
        const Work work = run(algorithm, data, input.size());
        const auto is_guard = [](Key x) { return x == guard; };
        if (!std::equal(expected.begin(), expected.end(), data) ||
            !std::all_of(storage.data(), data, is_guard) ||
            !std::all_of(data + input.size(), storage.data() + storage.size(), is_guard)) {
            throw std::runtime_error(std::string(label) + " failed exactness or guards");
        }
        const bool classified = expected_work.route == Route::reject
            ? late_rejection(work, input.size()) : same_work(work, expected_work);
        if (!classified || (algorithm == Algorithm::cert_vq && !same_work(work, first))) {
            throw std::runtime_error(std::string(label) + " failed route or work counts");
        }
        first = work;
        ++checked;
    }
}

int verify_all() {
    size_t checked = 0;
    constexpr Work bypass{Route::bypass, 0, 0};
    for (size_t offset : {0, 1, 7, 15}) {
        verify({}, "empty", bypass, offset, checked);
        verify({0xffffffffu}, "singleton", bypass, offset, checked);
        verify({0xffffffffu, 0, 0, 0xffffffffu}, "extremes and duplicates", bypass, offset, checked);
        verify(generate(129 + offset, "uniform", 65203), "small uniform", bypass, offset, checked);
    }
    verify(Keys(minimum_size - 1, 7), "below size threshold", bypass, 1, checked);
    verify(Keys(minimum_size, 0), "constant at lower extreme", {Route::constant, minimum_size, 0}, 0, checked);
    verify(Keys(minimum_size + 7, 0xffffffffu), "constant at upper extreme", {Route::constant, minimum_size + 7, 0}, 7, checked);
    verify(generate(minimum_size, "uniform", 6083), "no proposal", bypass, 15, checked);

    const size_t n = minimum_size + 17;
    auto one = generate(n, "dense16", 54013);
    one[n - 4] = 0;
    one[n - 3] = dense_base;
    one[n - 2] = dense_base | 65535u;
    one[n - 1] = 0xffffffffu;
    verify(one, "one window and both extremes", {Route::one, n, 2}, 7, checked);
    verify(make_late(n, 13103, false), "outside budget inclusive", {Route::one, n, n / 8}, 15, checked);
    verify(make_late(n, 13103, true), "last key rejection", {Route::reject, 0, 0}, 1, checked);

    std::mt19937_64 rng(75103);
    Keys adjacent(n);
    for (size_t i = 0; i < n; ++i) {
        const Key base = (i + i / (n / 256)) & 1u ? 0xfffe0000u : 0xffff0000u;
        adjacent[i] = base | (Key(rng()) & 65535u);
    }
    adjacent[n - 2] = 0;
    adjacent[n - 1] = 0xffffffffu;
    verify(adjacent, "adjacent windows at upper extreme", {Route::two, n, 1}, 15, checked);

    auto two = make_pair(n, 12379, true);
    two[n - 3] = 0;
    two[n - 2] = 0x6f00ffffu;
    two[n - 1] = 0xffffffffu;
    verify(two, "two windows with external keys on three sides", {Route::two, n, 3}, 7, checked);
    std::cout << "verified," << checked << '\n';
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") return verify_all();
        if (argc != 6) {
            throw std::invalid_argument("usage: e046_windows filter|full n distribution seed repetitions | --verify");
        }
        const std::string_view mode(argv[1]);
        if (mode != "filter" && mode != "full") throw std::invalid_argument("unknown stage");
        const int repeats = std::stoi(argv[5]);
        if (repeats < 1) throw std::invalid_argument("repetitions must be positive");
        return run_timed(mode == "filter", std::stoull(argv[2]), argv[3], std::stoull(argv[4]), repeats);
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
