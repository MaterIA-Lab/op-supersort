#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <memory>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#ifdef SUPERSORT_E050
#include "include/supersort/windows_forward_u32.hpp"
#else
#include "include/supersort/windows_split_u32.hpp"
#endif

void seed_vq_for_benchmark(uint64_t first, uint64_t second);

namespace {

using namespace supersort::window_detail;
using Keys = std::vector<Key>;

constexpr Key prefix = 0x8000u;
constexpr Proposal window{prefix, prefix, 1};
constexpr Key guard = 0xdeadbeefu;

enum class Arm { scalar_scratch, compact_scratch, split, forward, vq };
enum class Order { grouped, periodic, random };
enum class Side { low, inside, high, either };

#ifdef SUPERSORT_E050
constexpr std::array arms{Arm::scalar_scratch, Arm::split, Arm::forward, Arm::vq};
#else
constexpr std::array arms{Arm::scalar_scratch, Arm::compact_scratch, Arm::split, Arm::vq};
#endif

const char* name(Arm arm) {
    switch (arm) {
        case Arm::scalar_scratch: return "scalar_scratch";
        case Arm::compact_scratch: return "compact_scratch";
        case Arm::split: return "split";
        case Arm::forward: return "forward";
        case Arm::vq: return "vq";
    }
    throw std::logic_error("unknown arm");
}

struct Case {
    size_t divisor;
    Order order;
    Side side;
};

Case settings(std::string_view family) {
    if (family == "half_grouped") return {2, Order::grouped, Side::either};
    if (family == "half_periodic") return {2, Order::periodic, Side::either};
    if (family == "half_random") return {2, Order::random, Side::either};
    if (family == "skew_random") return {20, Order::random, Side::either};
    if (family == "half_low") return {2, Order::random, Side::low};
    if (family == "half_high") return {2, Order::random, Side::high};
    throw std::invalid_argument("unknown distribution");
}

Side side_of(Key key) {
    const Key high = key >> 16;
    if (high < prefix) return Side::low;
    if (high > prefix) return Side::high;
    return Side::inside;
}

Keys generate(size_t n, Case spec, uint64_t seed) {
    // The three streams hold values and class interleaving independent.
    std::mt19937_64 internal_rng(seed ^ 0x927c6187d823731bULL);
    std::mt19937_64 external_rng(seed ^ 0x764d2fb231c924d7ULL);
    std::mt19937_64 order_rng(seed ^ 0xcbd165b19987e37fULL);
    size_t outside = n / spec.divisor;
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
            Side side;
            do {
                key = static_cast<Key>(external_rng());
                side = side_of(key);
            } while (side == Side::inside || (spec.side != Side::either && side != spec.side));
            source[i] = key;
            --outside;
        } else {
            source[i] = (prefix << 16) | (static_cast<Key>(internal_rng()) & 4095u);
            --inside;
        }
    }
    return source;
}

SplitWork expected_work(const Keys& source) {
    SplitWork work{};
    for (Key key : source) {
        work.low += side_of(key) == Side::low;
        work.high += side_of(key) == Side::high;
    }
    return work;
}

void scratch_sort(Arm arm, Key* data, size_t n, size_t residual) {
    const auto counts = std::make_unique<Key[]>(width);
    std::unique_ptr<Key[]> outside;
    if (residual) {
        outside.reset(new Key[residual]);
        if (arm == Arm::scalar_scratch) separate(data, n, window, counts.get(), outside.get());
        else separate_compact(data, n, window, counts.get(), outside.get(), residual);
        if (residual > 1) vq_sort_u32(outside.get(), residual);
    } else {
        count_all(data, n, window, counts.get());
    }
    reconstruct(data, window, counts.get(), outside.get(), residual);
}

SplitWork run(Arm arm, Key* data, size_t n, SplitWork expected) {
    switch (arm) {
        case Arm::scalar_scratch:
        case Arm::compact_scratch:
            scratch_sort(arm, data, n, expected.low + expected.high);
            break;
        case Arm::split:
            return sort_window_split(data, n, prefix);
        case Arm::forward:
#ifdef SUPERSORT_E050
            return sort_window_forward(data, n, prefix);
#else
            throw std::logic_error("forward is unavailable in E049");
#endif
        case Arm::vq:
            if (n > 1) vq_sort_u32(data, n);
            break;
    }
    return expected;
}

void check(SplitWork actual, SplitWork expected, const Keys& sorted, const Key* data) {
    if (actual.low != expected.low || actual.high != expected.high) {
        throw std::runtime_error("incorrect split sizes");
    }
    if (!std::equal(sorted.begin(), sorted.end(), data)) {
        throw std::runtime_error("output differs from std::sort");
    }
}

int run_timed(size_t n, std::string_view family, uint64_t seed, int repeats) {
    const auto spec = settings(family);
    const Keys source = generate(n, spec, seed);
    const SplitWork expected = expected_work(source);
    const auto residual = expected.low + expected.high;
    if (residual != n / spec.divisor || (spec.side == Side::low && expected.high) ||
        (spec.side == Side::high && expected.low)) {
        throw std::logic_error("generator emitted unexpected class counts");
    }
    auto sorted = source;
    std::sort(sorted.begin(), sorted.end());
    Keys data(n);
    auto order = arms;
    std::mt19937_64 order_rng(seed ^ 0x09bcac24ce2fa4a1ULL);
    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
        const uint64_t first = pivots();
        const uint64_t second = pivots();
        for (Arm arm : order) {
            std::copy(source.begin(), source.end(), data.begin());
            seed_vq_for_benchmark(first, second);
            const auto start = std::chrono::steady_clock::now();
            const auto actual = run(arm, data.data(), n, expected);
            const auto stop = std::chrono::steady_clock::now();
            check(actual, expected, sorted, data.data());
            if (round >= 0) {
                const double ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << expected.low << ','
                          << n - residual << ',' << expected.high << '\n';
            }
        }
    }
    return 0;
}

#ifdef SUPERSORT_E050
int run_phases(size_t n, std::string_view family, uint64_t seed, int repeats) {
    const auto source = generate(n, settings(family), seed);
    const auto expected = expected_work(source);
    auto sorted = source;
    std::sort(sorted.begin(), sorted.end());
    Keys data(n);
    std::array order{Arm::split, Arm::forward};
    std::mt19937_64 order_rng(seed ^ 0x09bcac24ce2fa4a1ULL);
    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
    using Clock = std::chrono::steady_clock;
    const auto ms = [](auto begin, auto end) {
        return std::chrono::duration<double, std::milli>(end - begin).count();
    };
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
        const auto first = pivots();
        const auto second = pivots();
        for (Arm arm : order) {
            std::copy(source.begin(), source.end(), data.begin());
            seed_vq_for_benchmark(first, second);
            auto* a = data.data();
            const auto start = Clock::now();
            auto counts = std::make_unique<Key[]>(width);
            SplitWork work{};
            size_t residual = 0;
            if (arm == Arm::forward) residual = compact_window_forward(a, n, prefix, counts.get());
            else work = split_window(a, n, prefix, counts.get());
            const auto classified = Clock::now();
            if (arm == Arm::forward) {
                if (residual > 1) vq_sort_u32(a, residual);
            } else {
                if (work.low > 1) vq_sort_u32(a, work.low);
                if (work.high > 1) vq_sort_u32(a + n - work.high, work.high);
            }
            const auto sorted_residual = Clock::now();
            if (arm == Arm::forward) work = restore_window_forward(a, n, prefix, counts.get(), residual);
            else emit_window_counts(a + work.low, prefix, counts.get());
            counts.reset();
            const auto rebuilt = Clock::now();
            check(work, expected, sorted, a);
            if (round >= 0) {
                std::cout << round << ',' << name(arm) << ',' << ms(start, classified) << ','
                          << ms(classified, sorted_residual) << ',' << ms(sorted_residual, rebuilt) << '\n';
            }
        }
    }
    return 0;
}
#endif

void verify(const Keys& source, size_t offset, size_t& checked) {
    const SplitWork expected = expected_work(source);
    auto sorted = source;
    std::sort(sorted.begin(), sorted.end());
    const size_t margin = 16 + offset;
    for (Arm arm : arms) {
        Keys storage(margin + source.size() + 16, guard);
        auto* data = storage.data() + margin;
        std::copy(source.begin(), source.end(), data);
#ifdef SUPERSORT_E050
        if (arm == Arm::forward) {
            Keys exterior;
            std::copy_if(source.begin(), source.end(), std::back_inserter(exterior),
                         [](Key key) { return side_of(key) != Side::inside; });
            const auto counts = std::make_unique<Key[]>(width);
            const auto residual = compact_window_forward(data, source.size(), prefix, counts.get());
            if (residual != exterior.size() || !std::equal(exterior.begin(), exterior.end(), data)) {
                throw std::runtime_error("forward compaction changed the stable residual");
            }
            std::copy(source.begin(), source.end(), data);
        }
#endif
        check(run(arm, data, source.size(), expected), expected, sorted, data);
        const auto untouched = [](Key key) { return key == guard; };
        if (!std::all_of(storage.data(), data, untouched) ||
            !std::all_of(data + source.size(), storage.data() + storage.size(), untouched)) {
            throw std::runtime_error("sort changed guards");
        }
        ++checked;
    }
}

int verify_all() {
    constexpr std::array<std::array<Key, 2>, 3> bounds{{
        {0, (prefix << 16) - 1},
        {prefix << 16, (prefix << 16) | 65535u},
        {(prefix + 1) << 16, 0xffffffffu},
    }};
    size_t checked = 0;
    for (size_t n = 0; n <= 33; ++n) {
        for (size_t offset : {0, 1, 7, 15}) {
            for (size_t pattern = 0; pattern < 9; ++pattern) {
                Keys source(n);
                for (size_t i = 0; i < n; ++i) {
                    const size_t side = pattern < 3 ? pattern : ((i / (pattern < 6 ? 1 : 8)) + pattern) % 3;
                    source[i] = bounds[side][(i / 2) % 2];
                }
                verify(source, offset, checked);
            }
        }
    }
    std::mt19937_64 rng(57347);
    constexpr size_t n = (1u << 18) + 17;
    for (size_t pattern = 0; pattern < 5; ++pattern) {
        Keys source(n);
        for (size_t i = 0; i < n; ++i) {
            const auto random = static_cast<Key>(rng());
            size_t side = pattern < 3 ? pattern : (pattern == 3 ? (i / 64) % 3 : random % 3);
            if (side == 0) source[i] = random & 0x7fffffffu;
            else if (side == 1) source[i] = (prefix << 16) | (random & 65535u);
            else source[i] = std::max(random | 0x80000000u, (prefix + 1) << 16);
        }
        verify(source, pattern, checked);
    }
    std::cout << "verified," << checked << '\n';
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") return verify_all();
#ifdef SUPERSORT_E050
        if (argc == 6 && std::string_view(argv[1]) == "--phases") {
            const auto n = std::stoull(argv[2]);
            const auto repeats = std::stoi(argv[5]);
            if (!n || n > std::numeric_limits<Key>::max() || repeats < 1) {
                throw std::invalid_argument("unsupported size or repetition count");
            }
            return run_phases(n, argv[3], std::stoull(argv[4]), repeats);
        }
#endif
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
