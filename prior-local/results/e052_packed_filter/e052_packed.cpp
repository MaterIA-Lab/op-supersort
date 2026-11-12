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

#include "include/supersort/prefix_packed_u32.hpp"

void vq_sort_u32(std::uint32_t*, std::size_t);
void seed_vq_for_benchmark(std::uint64_t, std::uint64_t);

namespace {

using Key = std::uint32_t;
using Keys = std::vector<Key>;

enum class Arm { wide, packed, vq };
enum class Family { uniform, external_mix, external_low, prefix_distinct, dense16, skew, mixed, bimodal, few, equal };

constexpr std::array arms{Arm::wide, Arm::packed, Arm::vq};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::wide: return "wide";
        case Arm::packed: return "packed";
        case Arm::vq: return "vq";
    }
    throw std::logic_error("unknown arm");
}

Family family_from_name(std::string_view name) {
    if (name == "uniform") return Family::uniform;
    if (name == "external_mix") return Family::external_mix;
    if (name == "external_low") return Family::external_low;
    if (name == "prefix_distinct") return Family::prefix_distinct;
    if (name == "dense16") return Family::dense16;
    if (name == "skew") return Family::skew;
    if (name == "mixed") return Family::mixed;
    if (name == "bimodal") return Family::bimodal;
    if (name == "few") return Family::few;
    if (name == "equal") return Family::equal;
    throw std::invalid_argument("unknown distribution");
}

Keys generate(std::size_t n, Family family, std::uint64_t seed) {
    constexpr Key dense = 0x54880000u;
    constexpr Key first_mode = 0x18010000u;
    constexpr Key second_mode = 0xd8200000u;
    constexpr Key outside_window = 0x8000u;
    std::mt19937_64 rng(seed);
    Keys keys(n);
    if (family == Family::prefix_distinct) {
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
            const std::size_t p = i % prefixes.size();
            const Key suffix = (stride[p] * Key(i / prefixes.size()) + offset[p]) & 0xffffffu;
            keys[i] = (prefixes[p] << 24) | suffix;
        }
        return keys;
    }
    for (Key& key : keys) {
        switch (family) {
            case Family::uniform:
                key = Key(rng());
                break;
            case Family::external_mix:
                do { key = Key(rng()); } while ((key >> 16) == outside_window);
                break;
            case Family::external_low:
                key = Key(rng()) & 0x7fffffffu;
                break;
            case Family::dense16:
                key = dense | (Key(rng()) & 65535u);
                break;
            case Family::skew:
                key = Key(rng()) % 100 < 95 ? dense | (Key(rng()) & 4095u) : Key(rng());
                break;
            case Family::mixed:
                key = rng() & 1u ? dense | (Key(rng()) & 4095u) : Key(rng());
                break;
            case Family::bimodal: {
                const Key draw = Key(rng());
                key = (draw & 4096u ? first_mode : second_mode) | (draw & 4095u);
                break;
            }
            case Family::few:
                key = (Key(rng()) & 15u) * 2654435761u;
                break;
            case Family::equal:
                key = 0xffffffffu;
                break;
            case Family::prefix_distinct:
                throw std::logic_error("prefix_distinct handled before scalar generation");
        }
    }
    return keys;
}

struct Work {
    std::size_t coarse = 0;
    std::size_t leaves = 0;
    std::size_t above128 = 0;
    std::size_t above256 = 0;
};

Work count_work(const Keys& keys) {
    std::vector<std::size_t> counts(1u << 16);
    for (Key key : keys) ++counts[key >> 16];
    Work work;
    for (std::size_t coarse = 0; coarse < 256; ++coarse) {
        bool active = false;
        for (std::size_t leaf = 0; leaf < 256; ++leaf) {
            const auto count = counts[coarse * 256 + leaf];
            active |= count != 0;
            work.leaves += count != 0;
            if (count > 128) work.above128 += count;
            if (count > 256) work.above256 += count;
        }
        work.coarse += active;
    }
    return work;
}

void run(Arm arm, Key* data, std::size_t n) {
    switch (arm) {
        case Arm::wide: supersort::prefix_leaf_sort<false>(data, n); break;
        case Arm::packed: supersort::prefix_leaf_sort<true>(data, n); break;
        case Arm::vq: if (n > 1) vq_sort_u32(data, n); break;
    }
}

int run_timed(std::size_t n, Family family, std::uint64_t seed, int repeats) {
    const Keys source = generate(n, family, seed);
    const Work work = count_work(source);
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
        for (Arm arm : order) {
            std::copy(source.begin(), source.end(), data.begin());
            seed_vq_for_benchmark(first, second);
            const auto start = std::chrono::steady_clock::now();
            run(arm, data.data(), n);
            const auto stop = std::chrono::steady_clock::now();
            if (data != expected) {
                throw std::runtime_error(std::string(name(arm)) + " differs from std::sort");
            }
            if (round >= 0) {
                const double ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << work.coarse << ','
                          << work.leaves << ',' << work.above128 << ',' << work.above256 << '\n';
            }
        }
    }
    return 0;
}

void verify(const Keys& source, std::size_t offset, std::size_t& checked) {
    constexpr Key guard = 0xdeadbeefu;
    const auto margin = 16 + offset;
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    for (Arm arm : arms) {
        Keys storage(margin + source.size() + 16, guard);
        Key* data = storage.data() + margin;
        std::copy(source.begin(), source.end(), data);
        run(arm, data, source.size());
        const auto untouched = [](Key key) { return key == guard; };
        if (!std::equal(expected.begin(), expected.end(), data) ||
            !std::all_of(storage.data(), data, untouched) ||
            !std::all_of(data + source.size(), storage.data() + storage.size(), untouched)) {
            throw std::runtime_error(std::string(name(arm)) + " failed exactness or guards");
        }
        ++checked;
    }
}

int verify_all() {
    std::size_t checked = 0;
    std::mt19937_64 rng(39521);
    for (std::size_t offset : {0, 1, 7, 15}) {
        for (std::size_t n : {0, 1, 2, 7, 8, 9, 15, 16, 17, 31, 32, 33, 127, 128, 129, 255, 256, 257}) {
            verify(generate(n, Family::uniform, 54403), offset, checked);
        }
        verify({0, 0, 65535u, 65536u, 0xfffffffeu, 0xffffffffu, 0xffffffffu}, offset, checked);
        verify(generate(4097, Family::dense16, 17623), offset, checked);
        verify(generate(4097, Family::equal, 13103), offset, checked);
        verify(generate(8193, Family::bimodal, 37243), offset, checked);
        for (std::size_t leaf_size : {127, 128, 129, 255, 256, 257}) {
            Keys one_coarse;
            Keys two_coarse;
            for (std::size_t i = 0; i < leaf_size; ++i) {
                const Key suffix = Key(rng()) & 65535u;
                one_coarse.push_back(0x12340000u | suffix);
                one_coarse.push_back(0x12ff0000u | (65535u ^ suffix));
                two_coarse.push_back(suffix);
                two_coarse.push_back(0xffff0000u | (65535u ^ suffix));
            }
            std::shuffle(one_coarse.begin(), one_coarse.end(), rng);
            std::shuffle(two_coarse.begin(), two_coarse.end(), rng);
            verify(one_coarse, offset, checked);
            verify(two_coarse, offset, checked);
        }
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
        return run_timed(n, family_from_name(argv[2]), std::stoull(argv[3]), repeats);
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
