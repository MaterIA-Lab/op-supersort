#include <immintrin.h>

#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace {
using Key = std::uint32_t;
using Tag = std::int64_t;
using Clock = std::chrono::steady_clock;
constexpr unsigned kWindow = 8;
constexpr unsigned kVector = 4;
constexpr Key kRight = Key{1} << 31;

struct alignas(64) Record {
    Key key, id;
    std::array<std::uint64_t, 7> payload;
};
static_assert(sizeof(Record) == 64);

struct Run {
    const Key* keys;
    const Record* records;
    std::size_t size;
};

struct Cursor {
    std::size_t left = 0, right = 0;
};

struct Window {
    std::uint16_t left_mask;
    std::uint8_t length;
};
static_assert(sizeof(Window) == 4);

template<bool Stream>
inline void copy_record(Record* out, const Record* in) {
    const auto* src = reinterpret_cast<const __m256i*>(in);
    auto* dst = reinterpret_cast<__m256i*>(out);
    const auto first = _mm256_load_si256(src);
    const auto second = _mm256_load_si256(src + 1);
    if constexpr (Stream) {
        _mm256_stream_si256(dst, first);
        _mm256_stream_si256(dst + 1, second);
    } else {
        _mm256_store_si256(dst, first);
        _mm256_store_si256(dst + 1, second);
    }
}

void copy_span(Record* out, const Record* in, std::size_t count) {
    if (count) std::memcpy(out, in, count * sizeof(Record));
}

const Record* select_source(const Record* left, const Record* right, bool take_left) {
    const auto l = reinterpret_cast<std::uintptr_t>(left);
    const auto r = reinterpret_cast<std::uintptr_t>(right);
    const auto mask = std::uintptr_t{0} - static_cast<std::uintptr_t>(take_left);
    return reinterpret_cast<const Record*>(r ^ ((l ^ r) & mask));
}

template<bool Stream, bool Branchless>
void direct(Run left, Run right, Cursor pos, Record* out) {
    while (pos.left < left.size && pos.right < right.size) {
        const bool take_left = left.keys[pos.left] <= right.keys[pos.right];
        if constexpr (Branchless) {
            const auto* source = select_source(left.records + pos.left, right.records + pos.right, take_left);
            copy_record<Stream>(out, source);
            pos.left += take_left;
            pos.right += !take_left;
        } else {
            if (take_left) copy_record<Stream>(out, left.records + pos.left++);
            else copy_record<Stream>(out, right.records + pos.right++);
        }
        ++out;
    }
    if (pos.left < left.size) copy_span(out, left.records + pos.left, left.size - pos.left);
    if (pos.right < right.size) copy_span(out, right.records + pos.right, right.size - pos.right);
}

template<bool Inclusive>
std::size_t eligible_span(const Key* begin, std::size_t size, Key limit) {
    const auto eligible = [limit](Key k) { return Inclusive ? k <= limit : k < limit; };
    if (size < kWindow || !eligible(begin[kWindow - 1])) return 1;
    std::size_t low = kWindow, high = std::min(size, 2 * low);
    while (high < size && eligible(begin[high - 1])) {
        low = high;
        high = std::min(size, high * 2);
    }
    return std::partition_point(begin + low, begin + high, eligible) - begin;
}

void gallop(Run left, Run right, Record* out) {
    Cursor pos;
    while (pos.left < left.size && pos.right < right.size) {
        const Key a = left.keys[pos.left], b = right.keys[pos.right];
        if (a <= b) {
            const auto count = eligible_span<true>(left.keys + pos.left, left.size - pos.left, b);
            if (count == 1) copy_record<false>(out, left.records + pos.left);
            else copy_span(out, left.records + pos.left, count);
            pos.left += count;
            out += count;
        } else {
            const auto count = eligible_span<false>(right.keys + pos.right, right.size - pos.right, a);
            if (count == 1) copy_record<false>(out, right.records + pos.right);
            else copy_span(out, right.records + pos.right, count);
            pos.right += count;
            out += count;
        }
    }
    direct<false, false>(left, right, pos, out);
}

Tag tag(Key key, Key index) {
    return std::bit_cast<Tag>((std::uint64_t{key ^ kRight} << 32) | index);
}

__m256i tags(const Key* keys, Key base) {
    const auto raw = _mm_loadu_si128(reinterpret_cast<const __m128i*>(keys));
    const auto extended = _mm256_slli_epi64(_mm256_cvtepu32_epi64(raw), 32);
    const auto biased = _mm256_xor_si256(extended, _mm256_set1_epi64x(std::numeric_limits<Tag>::min()));
    return _mm256_or_si256(biased, _mm256_setr_epi64x(base, base + 1, base + 2, base + 3));
}

struct MinMax {
    __m256i low, high;
};

MinMax compare_exchange(__m256i a, __m256i b) {
    const auto mask = _mm256_cmpgt_epi64(a, b);
    return {_mm256_blendv_epi8(a, b, mask), _mm256_blendv_epi8(b, a, mask)};
}

__m256i bitonic_finish(__m256i keys) {
    auto distance_two = compare_exchange(keys, _mm256_permute4x64_epi64(keys, _MM_SHUFFLE(1, 0, 3, 2)));
    keys = _mm256_blend_epi32(distance_two.low, distance_two.high, 0xf0);
    auto distance_one = compare_exchange(keys, _mm256_permute4x64_epi64(keys, _MM_SHUFFLE(2, 3, 0, 1)));
    return _mm256_blend_epi32(distance_one.low, distance_one.high, 0xcc);
}

template<bool Stream>
void copy_tag(Run left, Run right, Record* out, Tag item) {
    const auto tagged_index = static_cast<Key>(item);
    const auto* source = select_source(left.records, right.records, tagged_index < kRight);
    copy_record<Stream>(out, source + (tagged_index & (kRight - 1)));
}

template<bool Stream>
void tag_network(Run left, Run right, Record* out) {
    Cursor pos;
    const auto choose_left = [&] {
        return pos.right == right.size
            || (pos.left < left.size && left.keys[pos.left] <= right.keys[pos.right]);
    };
    const auto has_vector = [&](bool take_left) {
        return (take_left ? left.size - pos.left : right.size - pos.right) >= kVector;
    };
    const auto take_vector = [&](bool take_left) {
        if (take_left) {
            const auto result = tags(left.keys + pos.left, static_cast<Key>(pos.left));
            pos.left += kVector;
            return result;
        }
        const auto result = tags(right.keys + pos.right, kRight | static_cast<Key>(pos.right));
        pos.right += kVector;
        return result;
    };
    bool take_left = choose_left();
    if (!has_vector(take_left)) {
        direct<Stream, true>(left, right, pos, out);
        return;
    }
    auto carry = take_vector(take_left);
    alignas(32) std::array<Tag, kVector> ordered;
    take_left = choose_left();
    while (has_vector(take_left)) {
        const auto incoming = take_vector(take_left);
        const auto split = compare_exchange(carry, _mm256_permute4x64_epi64(incoming, _MM_SHUFFLE(0, 1, 2, 3)));
        _mm256_store_si256(reinterpret_cast<__m256i*>(ordered.data()), bitonic_finish(split.low));
        carry = bitonic_finish(split.high);
        for (const auto item : ordered) copy_tag<Stream>(left, right, out++, item);
        take_left = choose_left();
    }
    _mm256_store_si256(reinterpret_cast<__m256i*>(ordered.data()), carry);
    for (const auto item : ordered) {
        take_left = choose_left();
        while (pos.left < left.size || pos.right < right.size) {
            const auto index = take_left ? pos.left : pos.right;
            const auto run = take_left ? left : right;
            const Key side = take_left ? 0 : kRight;
            if (tag(run.keys[index], side | static_cast<Key>(index)) > item) break;
            copy_record<Stream>(out++, run.records + index);
            if (take_left) ++pos.left;
            else ++pos.right;
            take_left = choose_left();
        }
        copy_tag<Stream>(left, right, out++, item);
    }
    direct<Stream, true>(left, right, pos, out);
}

template<bool Left>
Window rank_mask(const Key* winner, const Key* other) {
    const auto sign = _mm256_set1_epi32(std::numeric_limits<std::int32_t>::min());
    const auto raw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(other));
    const auto opposing = _mm256_xor_si256(raw, sign);
    unsigned winner_mask = 0, count = 0;
    for (unsigned lane = 0; lane < kWindow; ++lane) {
        const auto broadcast = _mm256_set1_epi32(std::bit_cast<std::int32_t>(winner[lane] ^ kRight));
        const auto compare = Left ? _mm256_cmpgt_epi32(broadcast, opposing)
                                  : _mm256_cmpgt_epi32(opposing, broadcast);
        const auto mask = static_cast<unsigned>(_mm256_movemask_ps(_mm256_castsi256_ps(compare)));
        count = Left ? std::popcount(mask) : kWindow - std::popcount(mask);
        winner_mask |= 1U << (lane + count);
    }
    const unsigned length = kWindow + count;
    const unsigned left_mask = Left ? winner_mask : ((1U << length) - 1) ^ winner_mask;
    return {static_cast<std::uint16_t>(left_mask), static_cast<std::uint8_t>(length)};
}

bool has_window(Run left, Run right, Cursor pos) {
    return left.size - pos.left >= kWindow && right.size - pos.right >= kWindow;
}

template<bool Stream>
std::size_t place_from_source(Record* out, const Record* source, unsigned mask) {
    std::size_t copied = 0;
    while (mask) {
        const auto slot = std::countr_zero(mask);
        copy_record<Stream>(out + slot, source + copied);
        ++copied;
        mask &= mask - 1;
    }
    return copied;
}

template<bool Stream>
void place_window(Run left, Run right, Cursor& pos, Record*& out, Window window) {
    const auto right_mask = ((1U << window.length) - 1) ^ window.left_mask;
    pos.left += place_from_source<Stream>(out, left.records + pos.left, window.left_mask);
    pos.right += place_from_source<Stream>(out, right.records + pos.right, right_mask);
    out += window.length;
}

template<bool Stream>
void rank_windows(Run left, Run right, Record* out) {
    Cursor pos;
    while (has_window(left, right, pos)) {
        const auto* a = left.keys + pos.left;
        const auto* b = right.keys + pos.right;
        const auto window = a[kWindow - 1] <= b[kWindow - 1] ? rank_mask<true>(a, b) : rank_mask<false>(b, a);
        place_window<Stream>(left, right, pos, out, window);
    }
    direct<Stream, true>(left, right, pos, out);
}

std::vector<Window> make_plan(Run left, Run right) {
    std::vector<Window> plan;
    Cursor pos;
    while (has_window(left, right, pos)) {
        const auto* a = left.keys + pos.left;
        const auto* b = right.keys + pos.right;
        const Key last_left = a[kWindow - 1], last_right = b[kWindow - 1];
        const bool consume_left = last_left <= last_right;
        const unsigned a_count = consume_left ? kWindow : std::upper_bound(a, a + kWindow, last_right) - a;
        const unsigned b_count = consume_left ? std::lower_bound(b, b + kWindow, last_left) - b : kWindow;
        unsigned mask = 0, i = 0, j = 0;
        for (unsigned slot = 0; slot < a_count + b_count; ++slot) {
            if (j == b_count || (i < a_count && a[i] <= b[j])) {
                mask |= 1U << slot;
                ++i;
            } else {
                ++j;
            }
        }
        plan.push_back({static_cast<std::uint16_t>(mask), static_cast<std::uint8_t>(a_count + b_count)});
        pos.left += a_count;
        pos.right += b_count;
    }
    return plan;
}

template<bool Stream>
void replay(Run left, Run right, Record* out, const std::vector<Window>& plan) {
    Cursor pos;
    for (const auto window : plan) place_window<Stream>(left, right, pos, out, window);
    direct<Stream, true>(left, right, pos, out);
}

enum class Strategy {
    branchy, branchless, branchless_stream, gallop, tag_network, tag_network_stream,
    rank_cached, rank_stream, replay_cached, replay_stream
};

struct Method {
    Strategy strategy;
    const char* name;
};

constexpr std::array<Method, 10> kMethods{{
    {Strategy::branchy, "branchy"},
    {Strategy::branchless, "branchless"},
    {Strategy::branchless_stream, "branchless_stream"},
    {Strategy::gallop, "gallop"},
    {Strategy::tag_network, "tag_network"},
    {Strategy::tag_network_stream, "tag_network_stream"},
    {Strategy::rank_cached, "rank_cached"},
    {Strategy::rank_stream, "rank_stream"},
    {Strategy::replay_cached, "replay_cached"},
    {Strategy::replay_stream, "replay_stream"},
}};

void merge(Strategy strategy, Run left, Run right, Record* out, const std::vector<Window>& plan) {
    switch (strategy) {
        case Strategy::branchy: direct<false, false>(left, right, {}, out); break;
        case Strategy::branchless: direct<false, true>(left, right, {}, out); break;
        case Strategy::branchless_stream: direct<true, true>(left, right, {}, out); break;
        case Strategy::gallop: gallop(left, right, out); break;
        case Strategy::tag_network: tag_network<false>(left, right, out); break;
        case Strategy::tag_network_stream: tag_network<true>(left, right, out); break;
        case Strategy::rank_cached: rank_windows<false>(left, right, out); break;
        case Strategy::rank_stream: rank_windows<true>(left, right, out); break;
        case Strategy::replay_cached: replay<false>(left, right, out, plan); break;
        case Strategy::replay_stream: replay<true>(left, right, out, plan); break;
    }
    _mm_sfence();
}

struct SplitMix64 {
    std::uint64_t state;
    std::uint64_t next() {
        auto value = (state += 0x9e3779b97f4a7c15ULL);
        value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
        value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
        return value ^ (value >> 31);
    }
};

enum class Shape { uniform, alternate, few_keys, equal, disjoint, paired };

struct Input {
    std::vector<Key> keys;
    std::vector<Record> rows;

    Input(std::size_t count, bool right, Shape shape, Key origin, SplitMix64& rng)
        : keys(count), rows(count) {
        constexpr std::array<Key, 4> boundaries{0U, kRight - 1, kRight, UINT32_MAX};
        for (std::size_t i = 0; i < count; ++i) {
            const auto v = static_cast<Key>(rng.next());
            switch (shape) {
                case Shape::uniform: keys[i] = v; break;
                case Shape::alternate: keys[i] = (v & ~(1U << 20)) | (Key{right} << 20); break;
                case Shape::few_keys: keys[i] = boundaries[v & 3U]; break;
                case Shape::equal: keys[i] = UINT32_MAX; break;
                case Shape::disjoint: keys[i] = (v & (kRight - 1)) | (right ? kRight : 0U); break;
                case Shape::paired: keys[i] = static_cast<Key>(i / 3); break;
            }
        }
        std::sort(keys.begin(), keys.end());
        for (std::size_t i = 0; i < count; ++i) {
            rows[i].key = keys[i];
            rows[i].id = origin + static_cast<Key>(i) + 1;
            for (auto& word : rows[i].payload) word = rng.next();
        }
    }

    Run run() const { return {keys.data(), rows.data(), rows.size()}; }
};

struct Fixture {
    SplitMix64 rng;
    Input left, right;
    std::vector<Record> expected, output;
    std::vector<Window> plan;
    std::size_t switches = 0;

    Fixture(std::size_t a, std::size_t b, Shape shape, std::uint64_t seed)
        : rng{seed}, left(a, false, shape, 0, rng), right(b, true, shape, static_cast<Key>(a), rng),
          expected(a + b), output(a + b), plan(make_plan(left.run(), right.run())) {
        std::merge(left.rows.begin(), left.rows.end(), right.rows.begin(), right.rows.end(),
                   expected.begin(), [](const Record& x, const Record& y) { return x.key < y.key; });
        for (std::size_t i = 1; i < expected.size(); ++i)
            switches += (expected[i - 1].id > a) != (expected[i].id > a);
    }

    void poison() {
        if (!output.empty()) std::memset(output.data(), 0, output.size() * sizeof(Record));
    }

    void verify(const Method& method) const {
        if (!expected.empty() && std::memcmp(output.data(), expected.data(), expected.size() * sizeof(Record))) {
            const auto bad = std::mismatch(output.begin(), output.end(), expected.begin(),
                [](const Record& a, const Record& b) { return !std::memcmp(&a, &b, sizeof(Record)); });
            throw std::runtime_error(std::string(method.name) + " differs at record "
                                     + std::to_string(bad.first - output.begin()));
        }
    }
};

void preflight() {
    std::size_t fixtures = 0;
    for (const auto a : {0U, 1U, 3U, 4U, 7U, 8U, 9U, 15U, 16U, 17U, 31U, 65U}) {
        for (const auto b : {0U, 1U, 3U, 4U, 7U, 8U, 9U, 15U, 16U, 17U, 31U, 65U}) {
            for (const auto shape : {Shape::uniform, Shape::alternate, Shape::few_keys, Shape::equal,
                                     Shape::disjoint, Shape::paired}) {
                Fixture fixture(a, b, shape, 53439 + fixtures);
                for (const auto method : kMethods) {
                    fixture.poison();
                    merge(method.strategy, fixture.left.run(), fixture.right.run(), fixture.output.data(), fixture.plan);
                    fixture.verify(method);
                }
                ++fixtures;
            }
        }
    }
    std::cout << "Verified " << fixtures << " exact fixtures across " << kMethods.size() << " methods\n";
}

template<class T>
void flush(const std::vector<T>& values) {
    const auto* start = reinterpret_cast<const unsigned char*>(values.data());
    for (std::size_t offset = 0; offset < values.size() * sizeof(T); offset += 64)
        _mm_clflushopt(const_cast<unsigned char*>(start + offset));
    // The last cache line can straddle the last 64-byte stride.
    if (!values.empty()) _mm_clflushopt(const_cast<T*>(&values.back()));
}

void pin(unsigned cpu) {
    if (cpu >= std::numeric_limits<DWORD_PTR>::digits ||
        !SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << cpu))
        throw std::runtime_error("could not pin the benchmark thread");
}

void measure(std::size_t n, std::string_view distribution, std::uint64_t seed, unsigned cpu) {
    pin(cpu);
    Fixture fixture(n / 2, n - n / 2, distribution == "alternate" ? Shape::alternate : Shape::uniform, seed);
    std::mt19937_64 rng(seed ^ 0x4f5b2e3a9e3cf17dULL);
    auto order = kMethods;
    std::cout << "rows,distribution,seed,round,method,ns,windows,source_switches,plan_bytes,verified\n";
    for (unsigned round = 0; round < 9; ++round) {
        std::shuffle(order.begin(), order.end(), rng);
        for (const auto method : order) {
            fixture.poison();
            _mm_sfence();
            flush(fixture.left.keys);
            flush(fixture.right.keys);
            flush(fixture.left.rows);
            flush(fixture.right.rows);
            flush(fixture.output);
            flush(fixture.plan);
            _mm_mfence();
            const auto begin = Clock::now();
            merge(method.strategy, fixture.left.run(), fixture.right.run(), fixture.output.data(), fixture.plan);
            const auto span = std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - begin).count();
            fixture.verify(method);
            const bool reads_plan = method.strategy == Strategy::replay_cached || method.strategy == Strategy::replay_stream;
            std::cout << n << ',' << distribution << ',' << seed << ',' << round << ',' << method.name << ','
                      << span << ',' << fixture.plan.size() << ',' << fixture.switches << ','
                      << (reads_plan ? fixture.plan.size() * sizeof(Window) : 0) << ",true\n";
        }
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--verify") {
            preflight();
            return 0;
        }
        if (argc != 5) throw std::invalid_argument("usage: bench --verify | ROWS DISTRIBUTION SEED CPU");
        const auto n = std::stoul(argv[1]);
        const std::string_view shape = argv[2];
        if ((n != 262144 && n != 1048576) || (shape != "uniform" && shape != "alternate"))
            throw std::invalid_argument("unregistered size or distribution");
        measure(n, shape, std::stoull(argv[3]), std::stoul(argv[4]));
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
