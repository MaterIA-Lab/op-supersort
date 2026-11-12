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
#include <string_view>
#include <utility>
#include <vector>

namespace e063 {
using Key = std::uint32_t;
using Keys = std::vector<Key>;

struct Span {
    std::uint64_t priority;
    std::size_t offset;
    Key pivot;
    Keys input;
    Keys expected;
    std::size_t work_offset = 0;
    std::size_t cut = 0;
};

struct Band {
    std::size_t population = 0;
    std::size_t sampled = 0;
    std::size_t partition_writes = 0;
    std::size_t exchange_writes = 0;
    std::vector<Span> spans;
};

using Corpus = std::array<Band, 32>;
struct Capture {
    const Key* base;
    std::uint64_t seed;
    Corpus& corpus;
};

Capture* active = nullptr;

unsigned size_band(std::size_t size) {
    return 63u - __builtin_clzll(size);
}

std::uint64_t mix(std::uint64_t value) {
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

void capture(const Key* keys, std::size_t size, Key pivot) {
    auto& ctx = *active;
    auto& band = ctx.corpus[size_band(size)];
    band.population += size;
    const auto offset = static_cast<std::size_t>(keys - ctx.base);
    const auto priority = mix(ctx.seed ^ (std::uint64_t(offset) << 32) ^ size);
    const auto limit = size < 16384 ? 64u : 1u;
    if (band.spans.size() < limit) {
        band.spans.push_back({priority, offset, pivot, Keys(keys, keys + size), {}});
    } else {
        const auto worst = std::max_element(band.spans.begin(), band.spans.end(),
            [](const Span& a, const Span& b) { return a.priority < b.priority; });
        if (priority < worst->priority) {
            worst->priority = priority;
            worst->offset = offset;
            worst->pivot = pivot;
            worst->input.assign(keys, keys + size);
        }
    }
}
}  // namespace e063

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

#include "include/supersort/exchange_partition_u32.hpp"

namespace {
namespace hn = hwy::HWY_NAMESPACE;
using e063::Band;
using e063::Corpus;
using e063::Key;
using e063::Keys;
using e063::Span;
using State = std::array<std::uint64_t, 3>;
using Clock = std::chrono::steady_clock;
using Tag = hn::SortTag<Key>;
using Traits = hn::detail::MakeTraits<Key, hwy::SortAscending>;
constexpr auto sort_mode = hn::detail::RecurseMode::kSort;
constexpr std::size_t scratch_size = hwy::SortConstants::BufBytes<Key>(HWY_MAX_BYTES) / sizeof(Key);
constexpr std::size_t alignment_keys = 64 / sizeof(Key);
constexpr Key guard = 0xdeadbeefu;
constexpr Key max_key = std::numeric_limits<Key>::max();
static_assert(hn::CompressIsPartition<Key>::value, "The write model assumes AVX2-style partitioning compress");
static_assert(hwy::SortConstants::kPartitionUnroll == 4, "The write model assumes four-vector blocks");

enum class Arm { partition, exchange, vq };
constexpr std::array all_arms{Arm::partition, Arm::exchange, Arm::vq};

const char* name(Arm arm) {
    switch (arm) {
        case Arm::partition: return "partition";
        case Arm::exchange: return "exchange";
        case Arm::vq: return "vq";
    }
    throw std::logic_error("unknown arm");
}

Key* aligned(Keys& storage) {
    const auto mod64 = reinterpret_cast<std::uintptr_t>(storage.data()) % 64;
    return storage.data() + ((64 - mod64) % 64) / sizeof(Key);
}

Keys generate(std::size_t n, std::string_view family, std::uint64_t seed) {
    std::mt19937_64 rng(seed);
    Keys source(n);
    if (family == "uniform" || family == "skew95" || family == "separated") {
        for (auto& key : source) key = Key(rng());
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

HWY_NOINLINE void direct(Key* data, std::size_t n, const State& state) {
    std::copy(state.begin(), state.end(), hwy::detail::GetGeneratorStateStatic());
    hn::VQSortStatic(data, n, hwy::SortAscending());
}

void capture_tree(Key* data, std::size_t n, Corpus& corpus, std::uint64_t seed, State state) {
    HWY_ALIGN Key scratch[scratch_size];
    e063::Capture ctx{data, seed, corpus};
    e063::active = &ctx;
    hn::detail::Recurse<sort_mode, true>(Tag{}, Traits{}, data, n, scratch, state.data(), 50);
    e063::active = nullptr;
}

std::size_t main_write_keys(std::size_t n) {
    constexpr std::size_t lanes = 8, block = 4 * lanes;
    const auto remainder = n % block;
    const auto edge = std::min(n, remainder + (remainder < lanes ? block : 0));
    const auto main = n - edge;
    // Exclude PartitionRightmost, the last two vectors and the final copy.
    return main >= 2 * block ? 2 * (main - 2 * lanes) : 0;
}

void check_span(Key* data, const Span& span, std::size_t cut) {
    if (cut != span.cut) throw std::runtime_error("incorrect partition cut");
    auto* middle = data + cut;
    auto* end = data + span.input.size();
    const auto low = [&](Key key) { return key <= span.pivot; };
    if (!std::all_of(data, middle, low) || std::any_of(middle, end, low)) {
        throw std::runtime_error("wrong side of partition");
    }
    std::sort(data, middle);
    std::sort(middle, end);
    if (!std::equal(span.expected.begin(), span.expected.end(), data)) {
        throw std::runtime_error("partition differs from std::sort");
    }
}

std::size_t prepare(Corpus& corpus) {
    std::size_t work_size = 0;
    for (auto& band : corpus) {
        std::size_t cursor = 0;
        std::sort(band.spans.begin(), band.spans.end(),
                  [](const Span& a, const Span& b) { return a.offset < b.offset; });
        for (auto& span : band.spans) {
            const auto n = span.input.size();
            span.work_offset = cursor + (span.offset - cursor) % alignment_keys;
            cursor = span.work_offset + n;
            span.expected = span.input;
            std::sort(span.expected.begin(), span.expected.end());
            span.cut = std::upper_bound(span.expected.begin(), span.expected.end(), span.pivot) - span.expected.begin();
            band.sampled += n;
            band.partition_writes += main_write_keys(n);
        }
        work_size = std::max(work_size, cursor);
    }
    return work_size;
}

void count_exchange(Corpus& corpus, Key* work) {
    for (auto& band : corpus) {
        for (const auto& span : band.spans) {
            auto* data = work + span.work_offset;
            std::copy(span.input.begin(), span.input.end(), data);
            std::size_t written = 0;
            const auto cut = supersort::exchange_partition_u32<true>(data, span.input.size(), span.pivot, &written);
            check_span(data, span, cut);
            band.exchange_writes += written;
        }
    }
}

template <bool Exchange>
HWY_NOINLINE void run_band(const Band& band, Key* work, std::size_t* cuts) {
    HWY_ALIGN Key scratch[scratch_size];
    for (const auto& span : band.spans) {
        auto* data = work + span.work_offset;
        if constexpr (Exchange) {
            *cuts++ = supersort::exchange_partition_u32(data, span.input.size(), span.pivot);
        } else {
            *cuts++ = hn::detail::Partition(Tag{}, Traits{}, data, span.input.size(), hn::Set(Tag{}, span.pivot), scratch);
        }
    }
}

void verify_all() {
    std::mt19937_64 rng(82573);
    std::size_t checked = 0;
    for (std::size_t n = 0; n <= 513; ++n) {
        for (unsigned pattern = 0; pattern < 8; ++pattern) {
            const auto margin = 16 + (n + pattern) % 16;
            const Key pivot = pattern == 1 ? 0 : pattern == 2 ? max_key :
                              pattern == 3 ? 0xf3333333u : pattern == 4 ? 0x0cccccccu : Key(rng());
            Span span{0, 0, pivot, Keys(n), {}};
            for (std::size_t i = 0; i < n; ++i) {
                const auto draw = Key(rng());
                span.input[i] = pattern == 5 ? (draw & 1 ? max_key : 0) :
                                pattern == 6 ? pivot : pattern == 7 ? (i & 1 ? 0 : max_key) : draw;
            }
            if (pattern == 7) std::sort(span.input.begin(), span.input.end());
            span.expected = span.input;
            std::sort(span.expected.begin(), span.expected.end());
            span.cut = std::upper_bound(span.expected.begin(), span.expected.end(), pivot) - span.expected.begin();
            for (const bool track : {false, true}) {
                Keys data(margin + n + 16, guard);
                auto* keys = data.data() + margin;
                std::copy(span.input.begin(), span.input.end(), keys);
                std::size_t written = 0;
                const auto cut = track ? supersort::exchange_partition_u32<true>(keys, n, pivot, &written)
                                       : supersort::exchange_partition_u32(keys, n, pivot);
                check_span(keys, span, cut);
                const auto clean = [](Key key) { return key == guard; };
                if (!std::all_of(data.data(), keys, clean) || !std::all_of(keys + n, data.data() + data.size(), clean)) {
                    throw std::runtime_error("partition touched guards");
                }
                if ((pattern == 2 || pattern == 6 || pattern == 7) && written != 0) {
                    throw std::runtime_error("already partitioned input requested stores");
                }
                ++checked;
            }
        }
    }
    std::cout << "verified," << checked << '\n';
}

void timed(std::size_t n, std::string_view family, std::uint64_t seed, int repeats) {
    if (hn::Lanes(Tag{}) != 8) throw std::runtime_error("E063 requires eight-lane AVX2");
    auto source = generate(n, family, seed);
    const bool full = family == "uniform" || family == "prefix_distinct";
    std::mt19937_64 pivots(seed ^ 0x5bf295f649df8fd9ULL);
    std::mt19937_64 order_rng(seed ^ 0x09bcac24ce2fa4a1ULL);
    std::vector<Arm> order(all_arms.begin(), all_arms.begin() + (full ? 3 : 2));
    Keys data_storage(full ? n + alignment_keys - 1 : 0), expected;
    auto* data = full ? aligned(data_storage) : nullptr;
    Corpus corpus;
    if (full) {
        expected = source;
        std::sort(expected.begin(), expected.end());
        auto capture_pivots = pivots;
        const State initial{capture_pivots(), capture_pivots(), 1};
        std::copy(source.begin(), source.end(), data);
        capture_tree(data, n, corpus, e063::mix(seed ^ 0x8d59c2b38197f6adULL), initial);
        if (!std::equal(expected.begin(), expected.end(), data)) throw std::runtime_error("capture differs from std::sort");
    } else {
        const Key pivot = family == "skew95" ? 0xf3333333u : 0x7fffffffu;
        if (family == "separated") std::partition(source.begin(), source.end(), [=](Key key) { return key <= pivot; });
        auto& band = corpus[e063::size_band(n)];
        band.population = n;
        band.spans.push_back({0, 0, pivot, std::move(source), {}});
    }
    const auto work_size = prepare(corpus);
    if (work_size == 0) throw std::runtime_error("empty partition corpus");
    Keys work_storage(work_size + alignment_keys - 1);
    auto* work = aligned(work_storage);
    count_exchange(corpus, work);

    std::array<std::size_t, 64> cuts;
    std::cout << std::fixed << std::setprecision(8);
    for (int round = -1; round < repeats; ++round) {
        std::shuffle(order.begin(), order.end(), order_rng);
        const State state{pivots(), pivots(), 1};
        for (const auto arm : order) {
            if (arm == Arm::vq) {
                std::copy(source.begin(), source.end(), data);
                const auto start = Clock::now();
                direct(data, n, state);
                const auto stop = Clock::now();
                if (!std::equal(expected.begin(), expected.end(), data)) throw std::runtime_error("vq differs from std::sort");
                if (round >= 0) {
                    const auto ms = std::chrono::duration<double, std::milli>(stop - start).count();
                    std::cout << round << ",vq,-1," << ms << ",0,0,0,0\n";
                }
                continue;
            }
            for (unsigned index = 0; index < corpus.size(); ++index) {
                const auto& band = corpus[index];
                if (band.spans.empty()) continue;
                for (const auto& span : band.spans) {
                    std::copy(span.input.begin(), span.input.end(), work + span.work_offset);
                }
                const auto start = Clock::now();
                if (arm == Arm::exchange) run_band<true>(band, work, cuts.data());
                else run_band<false>(band, work, cuts.data());
                const auto stop = Clock::now();
                for (std::size_t i = 0; i < band.spans.size(); ++i) {
                    const auto& span = band.spans[i];
                    check_span(work + span.work_offset, span, cuts[i]);
                }
                if (round >= 0) {
                    const auto ms = std::chrono::duration<double, std::milli>(stop - start).count();
                    const auto writes = arm == Arm::exchange ? band.exchange_writes : band.partition_writes;
                    std::cout << round << ',' << name(arm) << ',' << index << ',' << ms << ',' << band.population
                              << ',' << band.sampled << ',' << band.spans.size() << ',' << writes << '\n';
                }
            }
        }
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") verify_all();
        else if (argc == 5) {
            const auto n = std::stoull(argv[1]);
            const auto repeats = std::stoi(argv[4]);
            if (n <= 16384 || n > max_key || repeats < 1) throw std::invalid_argument("invalid size or repeats");
            timed(n, argv[2], std::stoull(argv[3]), repeats);
        } else {
            throw std::invalid_argument("usage: n distribution seed repetitions | --verify");
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
