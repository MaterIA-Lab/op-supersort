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
#include <sys/mman.h>

#include "include/supersort/scatter_nt.hpp"

void vq_sort_u32(std::uint32_t*, std::size_t);

namespace {

using Key = std::uint32_t;
using Keys = std::vector<Key>;
constexpr std::size_t bucket_count = 256;
constexpr std::size_t minimum_size = 1u << 18;
constexpr std::size_t scratch_size = 1u << 16;
constexpr std::size_t line_keys = 64 / sizeof(Key);
using Offsets = std::array<std::size_t, bucket_count>;

class Mapping {
public:
    explicit Mapping(std::size_t keys)
        : bytes_(keys * sizeof(Key)), address_(mmap(nullptr, bytes_, PROT_READ | PROT_WRITE,
                                                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0)) {}
    ~Mapping() { if (available()) munmap(address_, bytes_); }
    Mapping(const Mapping&) = delete;
    Mapping& operator=(const Mapping&) = delete;

    bool available() const { return address_ != MAP_FAILED; }
    Key* data() const { return static_cast<Key*>(address_); }

private:
    std::size_t bytes_;
    void* address_;
};

constexpr std::size_t align_line(std::size_t n) {
    return (n + line_keys - 1) & ~(line_keys - 1);
}

constexpr unsigned prefix(Key key) { return key >> 24; }

void finish(const Key* source, std::size_t count, Key* dest, Key* scratch) {
    if (count < 256 || count > scratch_size) {
        std::copy_n(source, count, dest);
        if (count > 1) vq_sort_u32(dest, count);
        return;
    }

    constexpr unsigned bits = 12;
    constexpr unsigned digits = 1u << bits;
    constexpr Key mask = digits - 1;
    std::array<unsigned, digits> low{}, high{};
    for (std::size_t i = 0; i < count; ++i) {
        const auto key = source[i];
        ++low[key & mask];
        ++high[(key >> bits) & mask];
    }
    unsigned low_start = 0, high_start = 0;
    for (unsigned d = 0; d < digits; ++d) {
        const auto low_count = low[d], high_count = high[d];
        low[d] = low_start;
        high[d] = high_start;
        low_start += low_count;
        high_start += high_count;
    }
    for (std::size_t i = 0; i < count; ++i) {
        const auto key = source[i];
        scratch[low[key & mask]++] = key;
    }
    for (std::size_t i = 0; i < count; ++i) {
        const auto key = scratch[i];
        dest[high[(key >> bits) & mask]++] = key;
    }
}

enum class Arm { counted, virtual_range, vq };
constexpr std::array arms{Arm::counted, Arm::virtual_range, Arm::vq};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::counted: return "counted";
        case Arm::virtual_range: return "virtual";
        case Arm::vq: return "vq";
    }
    throw std::logic_error("unknown arm");
}

// Nonzero means that the partition ran and reports the largest bucket.
template <bool Virtual>
std::size_t partition_sort(Key* data, std::size_t n) {
    constexpr auto max_keys = std::size_t(std::numeric_limits<std::ptrdiff_t>::max()) / sizeof(Key);
    if (n > max_keys / bucket_count - (line_keys - 1)) return 0;

    Offsets start;
    std::size_t capacity = 0;
    if constexpr (Virtual) {
        const auto stride = align_line(n);
        for (std::size_t b = 0; b < bucket_count; ++b) start[b] = b * stride;
        capacity = bucket_count * stride;
    } else {
        Offsets counts{};
        for (std::size_t i = 0; i < n; ++i) ++counts[prefix(data[i])];
        for (std::size_t b = 0; b < bucket_count; ++b) {
            start[b] = capacity;
            capacity += align_line(counts[b]);
        }
    }

    Mapping arena(capacity), scratch(scratch_size);
    if (!arena.available() || !scratch.available()) return 0;

    auto end = start;
    supersort::scatter_nt<bucket_count>(data, arena.data(), n, end, prefix);
    std::size_t written = 0, largest = 0;
    for (std::size_t b = 0; b < bucket_count; ++b) {
        const auto count = end[b] - start[b];
        if (count == 0) continue;
        finish(arena.data() + start[b], count, data + written, scratch.data());
        written += count;
        largest = std::max(largest, count);
    }
    return largest;
}

std::size_t run(Arm arm, Key* data, std::size_t n) {
    if (arm != Arm::vq && n >= minimum_size) {
        const auto largest = arm == Arm::counted ? partition_sort<false>(data, n)
                                                 : partition_sort<true>(data, n);
        if (largest != 0) return largest;
    }
    if (n > 1) vq_sort_u32(data, n);
    return 0;
}

// Same draws and key construction as E054 for the four filter families.
Keys generate(std::size_t n, std::string_view family, std::uint64_t seed) {
    std::mt19937_64 rng(seed);
    Keys source(n);
    if (family == "uniform") {
        for (auto& key : source) key = Key(rng());
    } else if (family == "mixed") {
        for (auto& key : source) key = rng() & 1u ? 0x54880000u | (Key(rng()) & 4095u) : Key(rng());
    } else if (family == "dense16") {
        for (auto& key : source) key = 0x54880000u | (Key(rng()) & 65535u);
    } else if (family == "prefix_distinct") {
        constexpr std::array<Key, 4> prefixes{0x00u, 0x23u, 0xa7u, 0xffu};
        if (n > (std::size_t{1} << 26)) throw std::invalid_argument("prefix_distinct exhausted");
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
    } else {
        throw std::invalid_argument("unknown distribution");
    }
    return source;
}

std::size_t largest_bucket(const Keys& source) {
    Offsets counts{};
    for (auto key : source) ++counts[prefix(key)];
    return *std::max_element(counts.begin(), counts.end());
}

void verify(const Keys& source, std::size_t offset, bool fail_reserve, std::size_t& checked) {
    constexpr Key guard = 0xdeadbeef;
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    const auto largest = largest_bucket(source);
    const auto margin = line_keys + offset;
    for (const auto arm : arms) {
        Keys storage(margin + source.size() + line_keys, guard);
        auto* data = storage.data() + margin;
        std::copy(source.begin(), source.end(), data);
        const auto work = run(arm, data, source.size());
        const auto untouched = [](Key key) { return key == guard; };
        const bool fallback = source.size() < minimum_size || arm == Arm::vq ||
                              (arm == Arm::virtual_range && fail_reserve);
        if (work != (fallback ? 0 : largest) || !std::equal(expected.begin(), expected.end(), data) ||
            !std::all_of(storage.data(), data, untouched) ||
            !std::all_of(data + source.size(), storage.data() + storage.size(), untouched)) {
            throw std::runtime_error(std::string(name(arm)) + " failed equality, guards or route");
        }
        ++checked;
    }
}

void verify_all(bool fail_reserve) {
    std::size_t checked = 0;
    if (fail_reserve) {
        verify(generate(minimum_size, "uniform", 36767), 7, true, checked);
    } else {
        std::mt19937_64 rng(54403);
        Keys boundaries;
        const std::array<std::size_t, 8> counts{1, 15, 16, 17, 255, 256, scratch_size, scratch_size + 1};
        for (std::size_t b = 0; b < counts.size(); ++b) {
            for (std::size_t i = 0; i < counts[b]; ++i) {
                boundaries.push_back((Key(b) << 24) | (Key(rng()) & 0xffffffu));
            }
        }
        boundaries[0] = 0;
        boundaries.resize(minimum_size + 3, std::numeric_limits<Key>::max());
        std::shuffle(boundaries.begin(), boundaries.end(), rng);
        for (std::size_t offset : {0, 1, 7, 15}) {
            for (std::size_t n : {0, 1, 2, 15, 16, 17, 255, 256, 257}) {
                verify(generate(n, "uniform", 54403), offset, false, checked);
            }
            verify({0, 0, 0xffffffffu, 0xffffffffu, 0x80000000u}, offset, false, checked);
            verify(boundaries, offset, false, checked);
        }
        verify(Keys(minimum_size - 1, 0), 1, false, checked);
        verify(Keys(minimum_size, 0xffffffffu), 7, false, checked);
        for (const auto* family : {"uniform", "prefix_distinct", "mixed", "dense16"}) {
            verify(generate(minimum_size + 1, family, 36767), 15, false, checked);
        }
    }
    std::cout << "verified," << checked << '\n';
}

void timed(std::size_t n, std::string_view family, std::uint64_t seed, int repeats) {
    const auto source = generate(n, family, seed);
    const auto largest = largest_bucket(source);
    auto expected = source;
    std::sort(expected.begin(), expected.end());
    Keys data(n);
    auto order = arms;
    std::mt19937_64 order_rng(seed ^ 0x09bcac24ce2fa4a1ULL);
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
        for (const auto arm : order) {
            std::copy(source.begin(), source.end(), data.begin());
            const auto start = std::chrono::steady_clock::now();
            const auto work = run(arm, data.data(), n);
            const auto stop = std::chrono::steady_clock::now();
            if (data != expected) throw std::runtime_error(std::string(name(arm)) + " differs from std::sort");
            if (work != 0 && work != largest) {
                throw std::runtime_error(std::string(name(arm)) + " reported the wrong largest bucket");
            }
            if (round >= 0) {
                const auto ms = std::chrono::duration<double, std::milli>(stop - start).count();
                std::cout << round << ',' << name(arm) << ',' << ms << ',' << work << '\n';
            }
        }
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") verify_all(false);
        else if (argc == 2 && std::string_view(argv[1]) == "--verify-reserve") verify_all(true);
        else if (argc == 5) {
            const auto n = std::stoull(argv[1]);
            const auto repeats = std::stoi(argv[4]);
            if (n < minimum_size || n > std::numeric_limits<Key>::max() || repeats < 1) {
                throw std::invalid_argument("unsupported size or repetition count");
            }
            timed(n, argv[2], std::stoull(argv[3]), repeats);
        } else {
            throw std::invalid_argument("usage: n distribution seed repetitions | --verify | --verify-reserve");
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
