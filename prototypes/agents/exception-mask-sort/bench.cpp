#include <immintrin.h>

#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace {
using Key = std::uint32_t;
using Index = std::uint32_t;
using Tag = std::uint64_t;
using Clock = std::chrono::steady_clock;
constexpr Index kBlock = 64;
constexpr std::size_t kPrefetch = 24;

struct alignas(64) Record {
    Key key;
    Index id;
    std::array<std::uint64_t, 7> payload;
};
static_assert(sizeof(Record) == 64);

Tag tag(Key key, Index handle) { return (Tag{key} << 32) | handle; }
Index handle(Tag value) { return static_cast<Index>(value); }

enum class Encoding { row, run, mask };

struct Plan {
    std::vector<Tag> tags;
    std::vector<Index> boundaries;
    std::vector<std::uint64_t> masks;

    std::size_t capacity_bytes() const {
        return tags.capacity() * sizeof(Tag) + boundaries.capacity() * sizeof(Index)
             + masks.capacity() * sizeof(std::uint64_t);
    }
};

Plan row_plan(const Key* keys, Index size) {
    Plan plan;
    plan.tags.reserve(size);
    for (Index i = 0; i < size; ++i) plan.tags.push_back(tag(keys[i], i));
    return plan;
}

unsigned lanes(__m256i bits) {
    return static_cast<unsigned>(_mm256_movemask_ps(_mm256_castsi256_ps(bits)));
}

__m256i load8(const Key* keys) {
    return _mm256_loadu_si256(reinterpret_cast<const __m256i*>(keys));
}

Plan run_plan(const Key* keys, Index size) {
    Plan plan;
    if (!size) return plan;
    plan.tags.reserve(std::min<Index>(4096, size));
    plan.boundaries.reserve(std::min<Index>(4096, size) + 1);
    const auto add = [&](Index i) {
        plan.tags.push_back(tag(keys[i], static_cast<Index>(plan.boundaries.size())));
        plan.boundaries.push_back(i);
    };
    add(0);
    Index i = 1;
    for (; i + 8 <= size; i += 8) {
        unsigned different = 0xffU ^ lanes(_mm256_cmpeq_epi32(load8(keys + i), load8(keys + i - 1)));
        while (different) {
            add(i + std::countr_zero(different));
            different &= different - 1;
        }
    }
    for (; i < size; ++i) {
        if (keys[i] != keys[i - 1]) add(i);
    }
    plan.boundaries.push_back(size);
    return plan;
}

Key choose_key(const Key* keys, Index count) {
    const Key first = keys[0], middle = keys[count / 2], last = keys[count - 1];
    return middle == last ? middle : first;
}

std::uint64_t equality_mask(const Key* keys, Index count, Key key) {
    const auto repeated = _mm256_set1_epi32(std::bit_cast<std::int32_t>(key));
    std::uint64_t mask = 0;
    Index i = 0;
    for (; i + 8 <= count; i += 8) {
        const auto equal = _mm256_cmpeq_epi32(load8(keys + i), repeated);
        mask |= std::uint64_t{lanes(equal)} << i;
    }
    for (; i < count; ++i) mask |= std::uint64_t{keys[i] == key} << i;
    return mask;
}

Plan mask_plan(const Key* keys, Index size) {
    Plan plan;
    plan.tags.reserve(std::min<Index>(4096, size));
    plan.masks.reserve((size + kBlock - 1) / kBlock);
    for (Index begin = 0; begin < size; begin += kBlock) {
        const Index count = std::min(kBlock, size - begin);
        const Key key = choose_key(keys + begin, count);
        const auto mask = equality_mask(keys + begin, count, key);
        plan.masks.push_back(mask);
        plan.tags.push_back(tag(key, 2 * begin + 1));
        const auto valid = UINT64_MAX >> (kBlock - count);
        auto exceptions = mask ^ valid;
        while (exceptions) {
            const Index i = begin + std::countr_zero(exceptions);
            plan.tags.push_back(tag(keys[i], 2 * i));
            exceptions &= exceptions - 1;
        }
    }
    return plan;
}

template<Encoding Kind>
Plan make_plan(const Key* keys, Index size) {
    if constexpr (Kind == Encoding::row) return row_plan(keys, size);
    if constexpr (Kind == Encoding::run) return run_plan(keys, size);
    return mask_plan(keys, size);
}

std::size_t radix_sort(std::vector<Tag>& values) {
    if (values.size() < 2) return 0;
    auto temporary = std::make_unique_for_overwrite<Tag[]>(values.size());
    std::array<std::array<Index, 256>, 4> offsets{};
    for (const Tag value : values) {
        const Key key = static_cast<Key>(value >> 32);
        for (unsigned pass = 0; pass < offsets.size(); ++pass) ++offsets[pass][(key >> (8 * pass)) & 255U];
    }
    Tag* source = values.data();
    Tag* target = temporary.get();
    for (unsigned pass = 0; pass < offsets.size(); ++pass) {
        auto& starts = offsets[pass];
        Index next = 0;
        for (auto& cell : starts) {
            const auto count = cell;
            cell = next;
            next += count;
        }
        const unsigned shift = 32 + 8 * pass;
        for (std::size_t i = 0; i < values.size(); ++i) {
            const Tag value = source[i];
            target[starts[(value >> shift) & 255U]++] = value;
        }
        std::swap(source, target);
    }
    return values.size() * sizeof(Tag);
}

void stream_rows(Record* target, const Record* source, Index count) {
    for (Index i = 0; i < count; ++i) {
        const auto* src = reinterpret_cast<const __m256i*>(source + i);
        auto* dst = reinterpret_cast<__m256i*>(target + i);
        _mm256_stream_si256(dst, _mm256_load_si256(src));
        _mm256_stream_si256(dst + 1, _mm256_load_si256(src + 1));
    }
}

class SpanWriter {
public:
    SpanWriter(const Record* input, Record* output) : input_(input), output_(output) {}

    void append(Index first, Index count) {
        if (count_ && first_ + count_ == first) {
            count_ += count;
            return;
        }
        flush();
        first_ = first;
        count_ = count;
    }

    std::size_t finish() {
        flush();
        _mm_sfence();
        return copies_;
    }

private:
    void flush() {
        if (!count_) return;
        stream_rows(output_, input_ + first_, count_);
        output_ += count_;
        count_ = 0;
        ++copies_;
    }

    const Record* input_;
    Record* output_;
    Index first_ = 0;
    Index count_ = 0;
    std::size_t copies_ = 0;
};

template<Encoding Kind>
Index first_row(const Plan& plan, Index item) {
    if constexpr (Kind == Encoding::row) return item;
    if constexpr (Kind == Encoding::run) return plan.boundaries[item];
    const Index first = item / 2;
    if (item & 1U) return first + std::countr_zero(plan.masks[first / kBlock]);
    return first;
}

void append_mask(SpanWriter& writer, Index first, std::uint64_t mask) {
    while (mask) {
        const auto offset = std::countr_zero(mask);
        const auto count = std::countr_one(mask >> offset);
        writer.append(first + offset, count);
        // A carry from the first set bit clears its consecutive run.
        mask &= mask + (std::uint64_t{1} << offset);
    }
}

template<Encoding Kind>
std::size_t materialize(const Plan& plan, const Record* input, Record* output) {
    SpanWriter writer(input, output);
    for (std::size_t i = 0; i < plan.tags.size(); ++i) {
        if (i + kPrefetch < plan.tags.size()) {
            const Index next = first_row<Kind>(plan, handle(plan.tags[i + kPrefetch]));
            _mm_prefetch(reinterpret_cast<const char*>(input + next), _MM_HINT_T0);
        }
        const Index item = handle(plan.tags[i]);
        if constexpr (Kind == Encoding::row) {
            writer.append(item, 1);
        } else if constexpr (Kind == Encoding::run) {
            const Index first = plan.boundaries[item];
            writer.append(first, plan.boundaries[item + 1] - first);
        } else {
            const Index first = item / 2;
            if (item & 1U) append_mask(writer, first, plan.masks[first / kBlock]);
            else writer.append(first, 1);
        }
    }
    return writer.finish();
}

std::uint64_t elapsed(Clock::time_point start, Clock::time_point end) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
}

struct Sample {
    std::uint64_t total_ns, prepare_ns, sort_ns, output_ns;
    std::size_t tags, copies, scratch_bytes;
};

template<Encoding Kind, bool Radix>
Sample sort_rows(const Key* keys, const Record* input, Record* output, Index size) {
    Sample sample{};
    const auto start = Clock::now();
    {
        auto plan = make_plan<Kind>(keys, size);
        sample.tags = plan.tags.size();
        sample.scratch_bytes = plan.capacity_bytes();
        const auto prepared = Clock::now();
        if constexpr (Radix) {
            sample.scratch_bytes += radix_sort(plan.tags);
        } else if (plan.tags.size() >= 2) {
            hwy::HWY_NAMESPACE::VQSortStatic(plan.tags.data(), plan.tags.size(), hwy::SortAscending());
        }
        const auto ordered = Clock::now();
        sample.copies = materialize<Kind>(plan, input, output);
        sample.output_ns = elapsed(ordered, Clock::now());
        sample.prepare_ns = elapsed(start, prepared);
        sample.sort_ns = elapsed(prepared, ordered);
    }
    sample.total_ns = elapsed(start, Clock::now());
    return sample;
}

struct Method {
    const char* name;
    Sample (*run)(const Key*, const Record*, Record*, Index);
};

constexpr std::array<Method, 6> kMethods{{
    {"row_vq", sort_rows<Encoding::row, false>},
    {"row_radix", sort_rows<Encoding::row, true>},
    {"rle_vq", sort_rows<Encoding::run, false>},
    {"rle_radix", sort_rows<Encoding::run, true>},
    {"mask_vq", sort_rows<Encoding::mask, false>},
    {"mask_radix", sort_rows<Encoding::mask, true>},
}};

struct SplitMix64 {
    std::uint64_t state;
    std::uint64_t next() {
        auto value = (state += 0x9e3779b97f4a7c15ULL);
        value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
        value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
        return value ^ (value >> 31);
    }
};

std::vector<Key> generate(Index size, std::string_view shape, std::uint64_t seed) {
    SplitMix64 bursts{seed};
    SplitMix64 exceptions{seed ^ 0xd1342543de82ef95ULL};
    std::vector<Key> keys(size);
    const unsigned denominator = shape == "burst_eighth" ? 8U : shape == "burst_quarter" ? 4U : 0U;
    for (Index start = 0; start < size;) {
        const Index length = 96 + static_cast<Index>(bursts.next() % 192);
        const auto base = static_cast<Key>(bursts.next());
        const Index end = std::min(size, start + length);
        for (; start < end; ++start) {
            const auto draw = exceptions.next();
            const auto replacement = static_cast<Key>(draw >> 32);
            const bool replace = denominator && (draw & (denominator - 1)) == 0;
            keys[start] = (replace || shape == "uniform") ? replacement : base;
        }
    }
    return keys;
}

struct Fixture {
    std::vector<Key> keys;
    std::vector<Record> input, output, oracle;
    std::size_t same_neighbors = 0;

    explicit Fixture(std::vector<Key> values)
        : keys(std::move(values)), input(keys.size()), output(keys.size()), oracle(keys.size()) {
        SplitMix64 rng{564971};
        std::vector<Index> positions;
        positions.reserve(keys.size());
        for (Index i = 0; i < keys.size(); ++i) {
            input[i].key = keys[i];
            input[i].id = i + 1;
            for (auto& word : input[i].payload) word = rng.next();
            positions.push_back(i);
            if (i) same_neighbors += keys[i] == keys[i - 1];
        }
        std::stable_sort(positions.begin(), positions.end(), [&](Index a, Index b) { return keys[a] < keys[b]; });
        for (Index i = 0; i < keys.size(); ++i) oracle[i] = input[positions[i]];
    }

    void poison() {
        if (!output.empty()) std::memset(output.data(), 0, output.size() * sizeof(Record));
    }

    Sample run(Method method) {
        const auto result = method.run(keys.data(), input.data(), output.data(), static_cast<Index>(keys.size()));
        if (!output.empty() && std::memcmp(output.data(), oracle.data(), output.size() * sizeof(Record))) {
            const auto wrong = std::mismatch(output.begin(), output.end(), oracle.begin(),
                [](const Record& a, const Record& b) { return !std::memcmp(&a, &b, sizeof(Record)); });
            throw std::runtime_error(std::string(method.name) + " differs at output "
                                     + std::to_string(wrong.first - output.begin()));
        }
        return result;
    }
};

void verify() {
    unsigned fixtures = 0;
    for (const Index n : {0U, 1U, 2U, 7U, 8U, 9U, 31U, 63U, 64U, 65U, 127U, 128U, 129U, 257U, 1023U}) {
        for (unsigned shape = 0; shape < 6; ++shape) {
            std::vector<Key> keys(n);
            if (shape == 0) keys = generate(n, "uniform", 179808 + n);
            if (shape == 1) keys = generate(n, "burst_quarter", 185489 + n);
            for (Index i = 0; i < n; ++i) {
                if (shape == 2) keys[i] = UINT32_MAX;
                if (shape == 3) keys[i] = n - i;
                if (shape == 4) keys[i] = ((i / kBlock) ^ (i % 11 == 0)) & 1U ? UINT32_MAX : 0;
                if (shape == 5) keys[i] = i % 3 ? 0x80000000U : 0x7fffffffU;
            }
            Fixture fixture(std::move(keys));
            for (const auto method : kMethods) {
                fixture.poison();
                fixture.run(method);
            }
            ++fixtures;
        }
    }
    std::cout << "Verified " << fixtures << " exact fixtures across " << kMethods.size() << " methods\n";
}

template<class T>
void flush(const std::vector<T>& values) {
    const auto* start = reinterpret_cast<const unsigned char*>(values.data());
    for (std::size_t offset = 0; offset < values.size() * sizeof(T); offset += 64)
        _mm_clflushopt(const_cast<unsigned char*>(start + offset));
    if (!values.empty()) _mm_clflushopt(const_cast<T*>(&values.back()));
}

void pin(unsigned cpu) {
    if (cpu >= std::numeric_limits<DWORD_PTR>::digits ||
        !SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << cpu))
        throw std::runtime_error("could not pin the benchmark thread");
}

void measure(Index size, std::string_view shape, std::uint64_t seed, unsigned cpu) {
    pin(cpu);
    Fixture fixture(generate(size, shape, seed));
    auto order = kMethods;
    std::mt19937_64 rng(seed ^ 0x91db57bc43848575ULL);
    std::cout << "rows,shape,seed,round,method,total_ns,prepare_ns,sort_ns,output_ns,tags,"
                 "copy_spans,scratch_bytes,same_neighbors,verified\n";
    for (unsigned round = 0; round < 9; ++round) {
        std::shuffle(order.begin(), order.end(), rng);
        for (const auto method : order) {
            fixture.poison();
            _mm_sfence();
            flush(fixture.keys);
            flush(fixture.input);
            flush(fixture.output);
            _mm_mfence();
            const auto sample = fixture.run(method);
            std::cout << size << ',' << shape << ',' << seed << ',' << round << ',' << method.name << ','
                      << sample.total_ns << ',' << sample.prepare_ns << ',' << sample.sort_ns << ','
                      << sample.output_ns << ',' << sample.tags << ',' << sample.copies << ','
                      << sample.scratch_bytes << ',' << fixture.same_neighbors << ",true\n";
        }
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") {
            verify();
            return 0;
        }
        if (argc != 5) throw std::invalid_argument("usage: bench --verify | ROWS SHAPE SEED CPU");
        const auto n = std::stoul(argv[1]);
        const std::string_view shape = argv[2];
        if ((n != 524288 && n != 2097152)
            || (shape != "burst_eighth" && shape != "burst_quarter" && shape != "burst_clean" && shape != "uniform"))
            throw std::invalid_argument("unregistered size or shape");
        measure(n, shape, std::stoull(argv[3]), std::stoul(argv[4]));
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
