#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <new>
#include <optional>

#ifdef SUPERSORT_BLOCK_PHASES
namespace e067 {
using Clock = std::chrono::steady_clock;
std::array<double, 3> times;

void record(Clock::time_point start, Clock::time_point classified,
            Clock::time_point permuted, Clock::time_point end) {
    using Milliseconds = std::chrono::duration<double, std::milli>;
    times = {Milliseconds(classified - start).count(),
             Milliseconds(permuted - classified).count(),
             Milliseconds(end - permuted).count()};
}

const double* phase_times() { return times.data(); }
}  // namespace e067
#endif

#include <ips2ra.hpp>

namespace {

using Key = std::uint32_t;

struct FixedRanges {
    std::uint16_t operator()(Key key) const { return static_cast<std::uint16_t>(key >> 23); }
};

struct MappedRanges {
    const std::uint16_t* map;
    std::uint16_t operator()(Key key) const { return map[key >> 16]; }
};

struct BlockConfig : ips2ra::Config<> {
    static constexpr std::ptrdiff_t kBlockSizeInBytes = 512;
    static constexpr int kLogBuckets = 9;
};

template<class Extractor>
struct RangeConfig : ips2ra::ExtendedConfig<Key*, Extractor, BlockConfig> {
    // Each extractor has already mapped the key to its bucket for the only pass.
    template<int, class T>
    static T getBucket(T bucket) { return bucket; }

    template<class T>
    static T getBucket(T bucket, int) { return bucket; }
};

template<class Extractor>
bool partition(Key* data, std::size_t n, Extractor extract, std::size_t* bounds) {
    using Config = RangeConfig<Extractor>;
    using Sorter = ips2ra::detail::Sorter<Config>;
    std::optional<typename Sorter::BufferStorage> storage;
    std::optional<ips2ra::detail::AlignedPtr<typename Sorter::LocalData>> local;
    try {
        storage.emplace(1);
        local.emplace(Config::kDataAlignment, extract, storage->get());
    } catch (const std::bad_alloc&) {
        return false;
    }

    std::array<std::ptrdiff_t, Config::kMaxBuckets + 1> starts;
    Sorter(local->get()).partitionOnly(data, data + n, 0, starts.data());
    std::copy(starts.begin(), starts.end(), bounds);
    return true;
}

}  // namespace

bool ips_block_partition_u32(std::uint32_t* data, std::size_t n, const std::uint16_t* map,
                             std::size_t* bounds, bool fail_reserve) {
    if (fail_reserve || n < BlockConfig::kUnrollClassifier) return false;
    if (map) return partition(data, n, MappedRanges{map}, bounds);
    return partition(data, n, FixedRanges{}, bounds);
}
