#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include "include/supersort/windows_compact_u32.hpp"

namespace {

using namespace supersort::window_detail;
using Keys = std::vector<Key>;

constexpr Proposal one{0x5488u, 0x5488u, 1};
constexpr Proposal two{0x1801u, 0xd820u, 2};
constexpr Key guard = 0xdeadbeefu;

enum class Arm { scalar, compact };
enum class Order { grouped, periodic, random };

struct Case {
    Proposal windows;
    size_t divisor;
    Order order;
};

Case settings(std::string_view name) {
    if (name == "inside") return {one, 0, Order::grouped};
    if (name == "two_half_random") return {two, 2, Order::random};
    if (name == "two_skew_random") return {two, 20, Order::random};
    const size_t split = name.find('_');
    if (split != std::string_view::npos) {
        const auto family = name.substr(0, split);
        const size_t divisor = family == "half" ? 2 : family == "skew" ? 20 : 0;
        if (divisor) {
            const auto order = name.substr(split + 1);
            if (order == "grouped") return {one, divisor, Order::grouped};
            if (order == "periodic") return {one, divisor, Order::periodic};
            if (order == "random") return {one, divisor, Order::random};
        }
    }
    throw std::invalid_argument("unknown distribution");
}

bool external(Key key, Proposal windows) {
    const Key high = key >> 16;
    return high != windows.first && high != windows.second;
}

Keys generate(size_t n, Case spec, uint64_t seed) {
    // The order stream affects positions only, never the two value streams.
    std::mt19937_64 internal_rng(seed ^ 0x927c6187d823731bULL);
    std::mt19937_64 external_rng(seed ^ 0x764d2fb231c924d7ULL);
    std::mt19937_64 order_rng(seed ^ 0xcbd165b19987e37fULL);
    size_t outside = spec.divisor ? n / spec.divisor : 0;
    size_t inside = n - outside;
    Keys source(n);
    for (size_t i = 0; i < n; ++i) {
        bool take_outside = false;
        if (outside) {
            if (!inside) take_outside = true;
            else if (spec.order == Order::periodic) take_outside = (i + 1) % spec.divisor == 0;
            else if (spec.order == Order::random) {
                take_outside = std::uniform_int_distribution<size_t>(0, inside + outside - 1)(order_rng) < outside;
            }
        }
        if (take_outside) {
            Key key;
            do { key = static_cast<Key>(external_rng()); } while (!external(key, spec.windows));
            source[i] = key;
            --outside;
        } else {
            const Key draw = static_cast<Key>(internal_rng());
            const Key high = draw & 4096u ? spec.windows.first : spec.windows.second;
            source[i] = (high << 16) | (draw & 4095u);
            --inside;
        }
    }
    return source;
}

struct Expected {
    Keys sorted;
    Keys counts;
    Keys outside;
};

Expected make_expected(const Keys& source, Proposal windows, size_t residual) {
    Expected expected{source, Keys(width * windows.count), {}};
    expected.outside.reserve(residual);
    for (Key key : source) {
        const Key high = key >> 16;
        if (high == windows.first) ++expected.counts[key & 65535u];
        else if (high == windows.second) ++expected.counts[width + (key & 65535u)];
        else expected.outside.push_back(key);
    }
    if (expected.outside.size() != residual) throw std::logic_error("unexpected external count");
    std::sort(expected.sorted.begin(), expected.sorted.end());
    return expected;
}

void classify(Arm arm, const Key* source, size_t n, Proposal windows, Key* counts,
              Key* outside, size_t residual) {
    if (!residual) count_all(source, n, windows, counts);
    else if (arm == Arm::scalar) separate(source, n, windows, counts, outside);
    else separate_compact(source, n, windows, counts, outside, residual);
}

void check_sorted(const Expected& expected, Proposal windows, const Key* counts,
                  Key* outside, Key* destination) {
    const auto residual = expected.outside.size();
    if (!std::equal(expected.counts.begin(), expected.counts.end(), counts) ||
        (residual && !std::equal(expected.outside.begin(), expected.outside.end(), outside))) {
        throw std::runtime_error("wrong counts or unstable residual");
    }
    if (residual > 1) vq_sort_u32(outside, residual);
    reconstruct(destination, windows, counts, outside, residual);
    if (!std::equal(expected.sorted.begin(), expected.sorted.end(), destination)) {
        throw std::runtime_error("reconstruction differs from std::sort");
    }
}

int run_timed(size_t n, std::string_view distribution, uint64_t seed, int repeats) {
    const Case spec = settings(distribution);
    const size_t residual = spec.divisor ? n / spec.divisor : 0;
    const Keys source = generate(n, spec, seed);
    const Expected expected = make_expected(source, spec.windows, residual);
    Keys destination(n);
    std::array<Arm, 2> arms{Arm::scalar, Arm::compact};
    std::mt19937_64 order(seed ^ 0x09bcac24ce2fa4a1ULL);
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(arms.begin(), arms.end(), order);
        for (Arm arm : arms) {
            const auto start = std::chrono::steady_clock::now();
            const auto counts = std::make_unique<Key[]>(width * spec.windows.count);
            std::unique_ptr<Key[]> outside;
            if (residual) outside.reset(new Key[residual]);
            classify(arm, source.data(), n, spec.windows, counts.get(), outside.get(), residual);
            const auto stop = std::chrono::steady_clock::now();
            check_sorted(expected, spec.windows, counts.get(), outside.get(), destination.data());
            if (round >= 0) {
                const double ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << (arm == Arm::scalar ? "scalar" : "compact") << ','
                          << ms << ',' << n - residual << ',' << residual << '\n';
            }
        }
    }
    return 0;
}

bool guards_intact(const Keys& storage, size_t start, size_t length) {
    const auto first = storage.begin() + start;
    const auto untouched = [](Key key) { return key == guard; };
    return std::all_of(storage.begin(), first, untouched) &&
           std::all_of(first + length, storage.end(), untouched);
}

void verify(const Keys& source, Proposal windows, size_t offset, size_t& checked) {
    const size_t residual = std::count_if(source.begin(), source.end(),
                                         [=](Key key) { return external(key, windows); });
    const Expected expected = make_expected(source, windows, residual);
    const size_t margin = 16 + offset;
    Keys input(margin + source.size() + 16, guard);
    std::copy(source.begin(), source.end(), input.begin() + margin);
    for (Arm arm : {Arm::scalar, Arm::compact}) {
        Keys count_storage(margin + expected.counts.size() + 16, guard);
        Keys out_storage(margin + residual + 16, guard);
        Keys destination(margin + source.size() + 16, guard);
        Key* counts = count_storage.data() + margin;
        Key* outside = out_storage.data() + margin;
        std::fill_n(counts, expected.counts.size(), 0);
        classify(arm, input.data() + margin, source.size(), windows, counts, outside, residual);
        if (!guards_intact(input, margin, source.size()) ||
            !std::equal(source.begin(), source.end(), input.begin() + margin) ||
            !guards_intact(count_storage, margin, expected.counts.size()) ||
            !guards_intact(out_storage, margin, residual)) {
            throw std::runtime_error("classification changed source or guards");
        }
        check_sorted(expected, windows, counts, outside, destination.data() + margin);
        if (!guards_intact(destination, margin, source.size())) {
            throw std::runtime_error("reconstruction changed guards");
        }
        ++checked;
    }
}

int verify_all() {
    size_t checked = 0;
    for (Proposal windows : {one, two}) {
        for (unsigned mask = 0; mask < 256; ++mask) {
            Keys source(8);
            for (unsigned lane = 0; lane < 8; ++lane) {
                const Key high = lane & 1u ? windows.first : windows.second;
                source[lane] = mask & (1u << lane) ? (lane * 0x24500001u) : (high << 16) | (lane / 3);
            }
            verify(source, windows, mask % 8, checked);
            // Allow a wide store for this mask and finish with a scalar tail.
            source.insert(source.end(), 8, 0xffffffffu);
            source.push_back(0);
            verify(source, windows, mask % 8, checked);
        }
        for (size_t n : {0, 1, 7, 8, 9, 15, 16, 17, 31, 32, 33, 65}) {
            for (size_t offset : {0, 1, 7, 15}) {
                verify(generate(n, {windows, 2, Order::random}, 41647), windows, offset, checked);
            }
        }
    }
    for (size_t offset : {0, 1, 7, 15}) {
        verify({0, 0, 0xffffu, 0x10000u, 0xfffeffffu, 0xffffffffu, 0xffffffffu,
                0x10000u, 0xffffffffu}, {0, 0xffffu, 2}, offset, checked);
    }
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
