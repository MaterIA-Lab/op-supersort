#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <new>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
#include <immintrin.h>

#define HWY_COMPILE_ONLY_STATIC 1
#define VQSORT_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace {

using Index = std::uint32_t;
using Key = std::uint32_t;
using Tag = std::uint64_t;
using Clock = std::chrono::steady_clock;

constexpr std::size_t group_width = 8;
constexpr std::size_t tile_width = 32;
constexpr unsigned warmups = 2;
constexpr unsigned repetitions = 7;
constexpr Index unwritten = std::numeric_limits<Index>::max();

constexpr auto make_shuffle_table() {
    std::array<std::array<std::int32_t, group_width>, 1 << group_width> table{};
    for (unsigned mask = 0; mask < table.size(); ++mask) {
        std::size_t position = 0;
        for (unsigned lane = 0; lane < group_width; ++lane) {
            if (mask & (1u << lane)) table[mask][position++] = static_cast<int>(lane);
        }
    }
    return table;
}

alignas(32) constexpr auto shuffle_table = make_shuffle_table();

void sort_tags(const Key* keys, std::size_t start, std::size_t count, Tag* tags) {
    for (std::size_t i = 0; i < count; ++i) {
        tags[i] = (Tag{keys[start + i]} << 32) | (start + i);
    }
    hwy::HWY_NAMESPACE::VQSortStatic(tags, count, hwy::SortAscending());
}

template <std::size_t Width>
void window_vq(const Key* keys, std::size_t windows, Index* output) {
    alignas(32) Tag tags[Width];
    for (std::size_t window = 0; window < windows; ++window) {
        sort_tags(keys, window, Width, tags);
        for (std::size_t i = 0; i < Width; ++i) output[window * Width + i] = static_cast<Index>(tags[i]);
    }
}

template <std::size_t Width>
void stream_row(const Index* source, Index* output) {
    for (std::size_t i = 0; i < Width; i += group_width) {
        const auto chunk = _mm256_load_si256(reinterpret_cast<const __m256i*>(source + i));
        _mm256_stream_si256(reinterpret_cast<__m256i*>(output + i), chunk);
    }
}

struct Positions {
    std::size_t expired;
    std::size_t incoming;
};

template <std::size_t Width, bool Simd>
Positions replacement_positions(const Key* ordered, Key expired, Key incoming) {
    if constexpr (!Simd) {
        return {
            static_cast<std::size_t>(std::lower_bound(ordered, ordered + Width, expired) - ordered),
            static_cast<std::size_t>(std::upper_bound(ordered, ordered + Width, incoming) - ordered),
        };
    } else {
        const auto sign = _mm256_set1_epi32(std::numeric_limits<int>::min());
        const auto old_key = _mm256_xor_si256(_mm256_set1_epi32(std::bit_cast<int>(expired)), sign);
        const auto new_key = _mm256_xor_si256(_mm256_set1_epi32(std::bit_cast<int>(incoming)), sign);
        unsigned less_than_old = 0;
        unsigned greater_than_new = 0;
        for (std::size_t i = 0; i < Width; i += group_width) {
            const auto data = _mm256_load_si256(reinterpret_cast<const __m256i*>(ordered + i));
            const auto signed_keys = _mm256_xor_si256(data, sign);
            const auto less = _mm256_cmpgt_epi32(old_key, signed_keys);
            const auto greater = _mm256_cmpgt_epi32(signed_keys, new_key);
            less_than_old += std::popcount(static_cast<unsigned>(_mm256_movemask_ps(_mm256_castsi256_ps(less))));
            greater_than_new += std::popcount(static_cast<unsigned>(_mm256_movemask_ps(_mm256_castsi256_ps(greater))));
        }
        return {less_than_old, Width - greater_than_new};
    }
}

void replace_in_order(std::uint32_t* row, std::size_t expired, std::size_t incoming, std::uint32_t value) {
    if (expired < incoming) {
        std::memmove(row + expired, row + expired + 1, (incoming - expired) * sizeof(value));
    } else if (incoming < expired) {
        std::memmove(row + incoming + 1, row + incoming, (expired - incoming) * sizeof(value));
    }
    row[incoming] = value;
}

template <std::size_t Width>
void copy_replacement(const Index* previous, Index* next, Positions positions, Index value) {
    const auto [expired, incoming] = positions;
    const std::size_t low = std::min(expired, incoming);
    const std::size_t high = std::max(expired, incoming);
    std::memcpy(next, previous, low * sizeof(Index));
    if (expired < incoming) {
        std::memcpy(next + expired, previous + expired + 1, (incoming - expired) * sizeof(Index));
    } else if (incoming < expired) {
        std::memcpy(next + incoming + 1, previous + incoming, (expired - incoming) * sizeof(Index));
    }
    next[incoming] = value;
    std::memcpy(next + high + 1, previous + high + 1, (Width - high - 1) * sizeof(Index));
}

enum class Store { cached, stream, direct };

template <std::size_t Width, bool Simd, Store Output>
void rolling(const Key* keys, std::size_t windows, Index* output) {
    if (windows == 0) return;
    alignas(32) Tag tags[Width];
    alignas(32) Key ordered_keys[Width];
    alignas(32) Index ordered_indices[Width];
    sort_tags(keys, 0, Width, tags);
    for (std::size_t i = 0; i < Width; ++i) {
        ordered_keys[i] = static_cast<Key>(tags[i] >> 32);
        ordered_indices[i] = static_cast<Index>(tags[i]);
    }
    if constexpr (Output == Store::stream) stream_row<Width>(ordered_indices, output);
    else std::memcpy(output, ordered_indices, sizeof(ordered_indices));

    for (std::size_t window = 1; window < windows; ++window) {
        const auto index = static_cast<Index>(window + Width - 1);
        const auto new_key = keys[index];
        // The expired index is the earliest among equal keys. The new index is the latest.
        auto positions = replacement_positions<Width, Simd>(ordered_keys, keys[window - 1], new_key);
        positions.incoming -= positions.expired < positions.incoming;
        replace_in_order(ordered_keys, positions.expired, positions.incoming, new_key);
        Index* row = output + Width * window;
        if constexpr (Output == Store::direct) {
            copy_replacement<Width>(row - Width, row, positions, index);
        } else {
            replace_in_order(ordered_indices, positions.expired, positions.incoming, index);
            if constexpr (Output == Store::stream) stream_row<Width>(ordered_indices, row);
            else std::memcpy(row, ordered_indices, sizeof(ordered_indices));
        }
    }
    if constexpr (Output == Store::stream) _mm_sfence();
}

template <std::size_t Width>
struct RankTile {
    static constexpr std::size_t capacity = Width + tile_width;
    alignas(32) Index indices[capacity];
    std::uint8_t ranks[capacity];
    std::uint64_t active[(capacity + 63) / 64];
    std::size_t groups;

    void flip(std::size_t rank) {
        active[rank / 64] ^= std::uint64_t{1} << (rank % 64);
    }

    void initialize(const Key* keys, std::size_t base, std::size_t windows) {
        const std::size_t count = Width + windows - 1;
        groups = (count + group_width - 1) / group_width;
        alignas(32) Tag tags[capacity];
        sort_tags(keys, base, count, tags);
        std::fill(std::begin(active), std::end(active), 0);
        for (std::size_t rank = 0; rank < count; ++rank) {
            const Index index = static_cast<Index>(tags[rank]);
            const std::size_t slot = index - base;
            indices[rank] = index;
            ranks[slot] = static_cast<std::uint8_t>(rank);
            if (slot < Width) flip(rank);
        }
        std::fill(indices + count, indices + groups * group_width, 0);
    }

    unsigned group_mask(std::size_t group) const {
        const auto first_rank = group * group_width;
        return static_cast<unsigned>((active[first_rank / 64] >> (first_rank % 64)) & 255u);
    }
};

struct PackedGroup {
    __m256i indices;
    unsigned count;
};

template <std::size_t Width>
PackedGroup pack(const RankTile<Width>& tile, std::size_t group) {
    const auto mask = tile.group_mask(group);
    const auto lanes = _mm256_load_si256(reinterpret_cast<const __m256i*>(shuffle_table[mask].data()));
    const auto indices = _mm256_load_si256(reinterpret_cast<const __m256i*>(tile.indices + group * group_width));
    return {_mm256_permutevar8x32_epi32(indices, lanes), static_cast<unsigned>(std::popcount(mask))};
}

enum class UnionMode { walk, pack_all, cache, cache_stream };

template <std::size_t Width, UnionMode Mode>
void rolling_union(const Key* keys, std::size_t windows, Index* output) {
    constexpr bool cache = Mode == UnionMode::cache || Mode == UnionMode::cache_stream;
    for (std::size_t base = 0; base < windows; base += tile_width) {
        const std::size_t count = std::min(tile_width, windows - base);
        RankTile<Width> tile;
        tile.initialize(keys, base, count);
        if constexpr (Mode == UnionMode::walk) {
            for (std::size_t offset = 0; offset < count; ++offset) {
                Index* row = output + (base + offset) * Width;
                for (std::size_t word = 0; word < std::size(tile.active); ++word) {
                    for (auto bits = tile.active[word]; bits != 0; bits &= bits - 1) {
                        *row++ = tile.indices[word * 64 + std::countr_zero(bits)];
                    }
                }
                if (offset + 1 < count) {
                    tile.flip(tile.ranks[offset]);
                    tile.flip(tile.ranks[offset + Width]);
                }
            }
        } else {
            PackedGroup groups[RankTile<Width>::capacity / group_width];
            if constexpr (cache) {
                for (std::size_t group = 0; group < tile.groups; ++group) groups[group] = pack(tile, group);
            }
            alignas(32) Index scratch[Width + group_width];
            for (std::size_t offset = 0; offset < count; ++offset) {
                Index* row = output + (base + offset) * Width;
                const bool last = base + offset + 1 == windows;
                // Wide stores may spill into the next row, which is produced afterwards.
                // The final row uses scratch to keep every store inside the buffer.
                Index* cursor = Mode == UnionMode::cache_stream || last ? scratch : row;
                for (std::size_t group = 0; group < tile.groups; ++group) {
                    const auto packed = cache ? groups[group] : pack(tile, group);
                    _mm256_storeu_si256(reinterpret_cast<__m256i*>(cursor), packed.indices);
                    cursor += packed.count;
                }
                if constexpr (Mode == UnionMode::cache_stream) stream_row<Width>(scratch, row);
                else if (last) std::memcpy(row, scratch, Width * sizeof(Index));
                if (offset + 1 < count) {
                    const auto expired = tile.ranks[offset];
                    const auto incoming = tile.ranks[offset + Width];
                    tile.flip(expired);
                    tile.flip(incoming);
                    if constexpr (cache) {
                        const std::size_t old_group = expired / group_width;
                        const std::size_t new_group = incoming / group_width;
                        groups[old_group] = pack(tile, old_group);
                        if (new_group != old_group) groups[new_group] = pack(tile, new_group);
                    }
                }
            }
        }
    }
    if constexpr (Mode == UnionMode::cache_stream) _mm_sfence();
}

struct Method {
    std::string_view name;
    void (*run)(const Key*, std::size_t, Index*);
};

template <std::size_t Width>
constexpr std::array methods = {
    Method{"window_vq", window_vq<Width>},
    Method{"rolling_binary", rolling<Width, false, Store::cached>},
    Method{"rolling_simd", rolling<Width, true, Store::cached>},
    Method{"rolling_stream", rolling<Width, true, Store::stream>},
    Method{"rolling_direct", rolling<Width, true, Store::direct>},
    Method{"union_walk", rolling_union<Width, UnionMode::walk>},
    Method{"union_pack", rolling_union<Width, UnionMode::pack_all>},
    Method{"union_cache", rolling_union<Width, UnionMode::cache>},
    Method{"union_cache_stream", rolling_union<Width, UnionMode::cache_stream>},
};

template <std::size_t Width>
std::vector<Index> stable_oracle(const std::vector<Key>& keys, std::size_t windows) {
    std::vector<Index> expected(windows * Width);
    for (std::size_t window = 0; window < windows; ++window) {
        auto* row = expected.data() + window * Width;
        std::iota(row, row + Width, static_cast<Index>(window));
        std::stable_sort(row, row + Width, [&keys](Index a, Index b) { return keys[a] < keys[b]; });
    }
    return expected;
}

auto aligned_output(std::size_t count) {
    auto* buffer = static_cast<Index*>(::operator new[](count * sizeof(Index), std::align_val_t{64}));
    auto release = [](Index* ptr) { ::operator delete[](ptr, std::align_val_t{64}); };
    return std::unique_ptr<Index[], decltype(release)>(buffer, release);
}

template <std::size_t Width>
unsigned verify_fixtures() {
    unsigned calls = 0;
    for (const auto windows : {0u, 1u, 2u, 7u, 31u, 32u, 33u, 63u, 64u, 65u}) {
        std::vector<Key> keys(windows + Width - 1);
        for (const std::string_view shape : {"equal", "ascending", "descending", "unsigned_boundary"}) {
            for (std::size_t i = 0; i < keys.size(); ++i) {
                if (shape == "equal") keys[i] = 0;
                else if (shape == "ascending") keys[i] = static_cast<Key>(i);
                else if (shape == "descending") keys[i] = static_cast<Key>(keys.size() - i);
                else {
                    constexpr Key values[] = {0, 0xffffffffu, 0x80000000u, 0x7fffffffu, 0x80000001u, 0};
                    keys[i] = values[i % std::size(values)];
                }
            }
            const auto expected = stable_oracle<Width>(keys, windows);
            auto output = aligned_output(expected.size() + group_width);
            for (const auto method : methods<Width>) {
                std::fill_n(output.get(), expected.size() + group_width, unwritten);
                method.run(keys.data(), windows, output.get());
                if (!std::equal(expected.begin(), expected.end(), output.get()) ||
                    !std::all_of(output.get() + expected.size(), output.get() + expected.size() + group_width,
                                 [](Index value) { return value == unwritten; })) {
                    throw std::runtime_error("fixture failed for " + std::string(method.name));
                }
                ++calls;
            }
        }
    }
    return calls;
}

std::uint64_t splitmix(std::uint64_t& state) {
    auto value = (state += 0x9e3779b97f4a7c15ull);
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ull;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebull;
    return value ^ (value >> 31);
}

void flush_lines(const void* data, std::size_t bytes) {
    const auto* start = static_cast<const unsigned char*>(data);
    for (std::size_t offset = 0; offset < bytes; offset += 64) _mm_clflushopt(const_cast<unsigned char*>(start + offset));
    if (bytes != 0) _mm_clflushopt(const_cast<unsigned char*>(start + bytes - 1));
}

template <std::size_t Width>
void measure(std::size_t windows, std::string_view shape, std::uint64_t seed) {
    if (windows == 0 || windows > std::numeric_limits<Index>::max() - Width ||
        (shape != "uniform" && shape != "keys16")) throw std::invalid_argument("invalid case");
    std::vector<Key> keys(windows + Width - 1);
    auto state = seed;
    for (Key& key : keys) {
        key = static_cast<Key>(splitmix(state));
        if (shape == "keys16") key &= 15;
    }
    const auto expected = stable_oracle<Width>(keys, windows);
    auto output = aligned_output(expected.size());
    auto order = methods<Width>;
    std::mt19937_64 random(seed ^ (Width << 16) ^ windows);
    std::cout << "windows,width,shape,seed,round,order,method,total_ns,verified\n";
    for (unsigned round = 0; round < warmups + repetitions; ++round) {
        std::shuffle(order.begin(), order.end(), random);
        for (std::size_t position = 0; position < order.size(); ++position) {
            const auto method = order[position];
            std::fill_n(output.get(), expected.size(), unwritten);
            flush_lines(keys.data(), keys.size() * sizeof(Key));
            flush_lines(output.get(), expected.size() * sizeof(Index));
            _mm_mfence();
            const auto start = Clock::now();
            method.run(keys.data(), windows, output.get());
            const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count();
            if (!std::equal(expected.begin(), expected.end(), output.get())) {
                throw std::runtime_error("incorrect output for " + std::string(method.name));
            }
            std::cout << windows << ',' << Width << ',' << shape << ',' << seed << ',' << round << ',' << position
                      << ',' << method.name << ',' << elapsed << ",true\n";
        }
    }
}

void pin(unsigned cpu) {
    if (cpu >= std::numeric_limits<DWORD_PTR>::digits ||
        !SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << cpu)) {
        throw std::runtime_error("could not pin the benchmark thread");
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") {
            const unsigned calls = verify_fixtures<32>() + verify_fixtures<64>();
            std::cout << "Verified " << calls << " fixture calls and checked the output boundary.\n";
            return 0;
        }
        if (argc != 6) throw std::invalid_argument("usage: bench windows width shape seed cpu");
        pin(std::stoul(argv[5]));
        const auto windows = std::stoull(argv[1]);
        const auto width = std::stoul(argv[2]);
        const auto seed = std::stoull(argv[4]);
        if (width == 32) measure<32>(windows, argv[3], seed);
        else if (width == 64) measure<64>(windows, argv[3], seed);
        else throw std::invalid_argument("width must be 32 or 64");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
