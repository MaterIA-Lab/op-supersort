#include "placement.hpp"
#include "windows_views.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <iterator>
#include <optional>
#include <random>
#include <string_view>
#include <vector>

#include <immintrin.h>

namespace {

using namespace placement;
using Clock = std::chrono::steady_clock;
using Word = std::uint64_t;
constexpr std::size_t eviction_bytes = 96 * 1024 * 1024;

struct alignas(64) Row {
    Word key;
    std::array<Word, 15> payload;
};
static_assert(sizeof(Row) == row_bytes);

using Input = std::array<std::vector<Row>, 2>;

Runs bytes_of(const Input& input) {
    return {{{reinterpret_cast<const std::byte*>(input[0].data()), input[0].size()},
             {reinterpret_cast<const std::byte*>(input[1].data()), input[1].size()}}};
}

void copy_rows(std::byte* out, Run input) {
    if (input.size) std::memcpy(out, input.data, input.size * row_bytes);
}

template <bool Streaming>
void write_twice(std::byte* batch, std::byte* output, Run input) {
    const auto vectors = input.size * row_bytes / sizeof(__m256i);
    const auto* from = reinterpret_cast<const __m256i*>(input.data);
    auto* to_batch = reinterpret_cast<__m256i*>(batch);
    auto* to_output = reinterpret_cast<__m256i*>(output);
    for (std::size_t i = 0; i < vectors; ++i) {
        const auto value = _mm256_load_si256(from + i);
        if constexpr (Streaming) {
            _mm256_stream_si256(to_batch + i, value);
            _mm256_stream_si256(to_output + i, value);
        } else {
            _mm256_store_si256(to_batch + i, value);
            _mm256_store_si256(to_output + i, value);
        }
    }
}

void copy_merge(std::byte* output, const Runs& inputs, Edges edges) {
    visit_merge(inputs, edges, [&](std::size_t side, std::size_t first, std::size_t size) {
        copy_rows(output, inputs[side].range(first, first + size));
        output += size * row_bytes;
    });
}

enum class Method { split, fused_cached, fused_stream, fixed, shifted };

constexpr std::array methods{
    Method::split, Method::fused_cached, Method::fused_stream, Method::fixed, Method::shifted,
};

const char* label(Method method) {
    switch (method) {
        case Method::split: return "split_bulk";
        case Method::fused_cached: return "fused_cached";
        case Method::fused_stream: return "fused_stream";
        case Method::fixed: return "fixed_remap";
        case Method::shifted: return "shifted_remap";
    }
    throw std::logic_error("unexpected method");
}

std::vector<Fragment> fragments_for(Plan plan, const std::array<std::size_t, 2>& bases,
                                    std::size_t input_bytes, std::size_t output_bytes) {
    std::vector<Fragment> fragments;
    fragments.reserve(4);
    std::size_t output = 0;
    std::size_t scratch = input_bytes;
    const auto add_writable = [&](std::size_t end) {
        if (output < end) {
            fragments.push_back({output, end - output, scratch, true});
            scratch += end - output;
            output = end;
        }
    };
    for (const auto& slice : {plan.mapped.prefix, plan.mapped.suffix}) {
        if (!slice.size) continue;
        add_writable(slice.output * row_bytes);
        const auto backing = bases[slice.side] + (plan.phase[slice.side] + slice.source) * row_bytes;
        fragments.push_back({output, slice.size * row_bytes, backing, false});
        output += slice.size * row_bytes;
    }
    add_writable(output_bytes);
    return fragments;
}

void fill_gaps(std::byte* output, const Runs& batches, Edges already_mapped) {
    const auto [head, tail] = already_mapped;
    std::array<std::size_t, 2> start{};
    std::array<std::size_t, 2> end{batches[0].size, batches[1].size};
    start[head.side] = head.size;
    if (tail.size) end[tail.side] = tail.source;
    const Runs middle{batches[0].range(start[0], end[0]), batches[1].range(start[1], end[1])};
    copy_merge(output + head.size * row_bytes, middle, outer_slices(middle));

    if (tail.size) {
        const auto tail_end = tail.source + tail.size;
        auto* last_fragment = output + (tail.output + tail.size) * row_bytes;
        copy_rows(last_fragment, batches[tail.side].range(tail_end, batches[tail.side].size));
    }
}

void evict_cache(const std::vector<Word>& buffer) {
    const volatile Word* lines = buffer.data();
    for (std::size_t i = 0; i < buffer.size(); i += 64 / sizeof(Word)) (void)lines[i];
}

Word first_read(const std::byte* data, std::size_t bytes) {
    Word sum = 0;
    for (std::size_t i = 0; i < bytes; i += 64) {
        Word word;
        std::memcpy(&word, data + i, sizeof(word));
        sum += word;
    }
    return sum;
}

Word nanoseconds(Clock::duration duration) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();
}

struct Expected {
    std::vector<Row> merged;
    Word digest;
};

Expected build_expected(const Input& input) {
    std::vector<Row> rows;
    rows.reserve(input[0].size() + input[1].size());
    std::merge(input[0].begin(), input[0].end(), input[1].begin(), input[1].end(),
               std::back_inserter(rows),
               [](const Row& a, const Row& b) { return a.key < b.key; });
    const auto digest = first_read(reinterpret_cast<const std::byte*>(rows.data()),
                                   rows.size() * row_bytes);
    return {std::move(rows), digest};
}

struct Timing {
    Word batches;
    Word assemble;
    Word read;
    Word total;
    Word teardown;
    std::size_t mapped;
};

Timing measure(const MappingApi& api, Method method, const Runs& input, const Expected& expected) {
    std::optional<PrivateBlock> direct;
    std::optional<Section> section;
    std::optional<OutputViews> views;
    std::array<std::byte*, 2> batches;
    std::byte* result;
    std::size_t mapped = 0;
    Clock::time_point prepared;

    const auto start = Clock::now();
    const auto [a, b] = input;
    const auto bytes = (a.size + b.size) * row_bytes;
    const auto rounded_bytes = page_ceil(a.size + b.size) * row_bytes;
    const auto edges = outer_slices(input);
    if (method == Method::fixed || method == Method::shifted) {
        const auto plan = plan_edges(edges, method == Method::shifted);
        const auto first_bytes = page_ceil(a.size + plan.phase[0]) * row_bytes;
        const auto input_bytes = first_bytes + page_ceil(b.size + plan.phase[1]) * row_bytes;
        mapped = (plan.mapped.prefix.size + plan.mapped.suffix.size) * row_bytes;
        section.emplace(input_bytes + rounded_bytes - mapped, input_bytes);
        batches = {section->input() + plan.phase[0] * row_bytes,
                   section->input() + first_bytes + plan.phase[1] * row_bytes};
        copy_rows(batches[0], a);
        copy_rows(batches[1], b);
        prepared = Clock::now();

        views.emplace(api);
        views->map(section->handle(), rounded_bytes,
                   fragments_for(plan, {0, first_bytes}, input_bytes, rounded_bytes));
        result = views->data();
        const Runs produced{{{batches[0], a.size}, {batches[1], b.size}}};
        fill_gaps(result, produced, plan.mapped);
        views->seal_writes();
        seal(section->input(), input_bytes);
    } else {
        direct.emplace(rounded_bytes * 2);
        batches = {direct->data(), direct->data() + a.size * row_bytes};
        result = direct->data() + rounded_bytes;
        if (method == Method::split) {
            copy_rows(batches[0], a);
            copy_rows(batches[1], b);
            prepared = Clock::now();
            const Runs produced{{{batches[0], a.size}, {batches[1], b.size}}};
            copy_merge(result, produced, edges);
        } else {
            prepared = Clock::now();
            auto* next = result;
            visit_merge(input, edges, [&](std::size_t side, std::size_t first, std::size_t size) {
                const auto* row = input[side].row(first);
                auto* batch = batches[side] + first * row_bytes;
                if (method == Method::fused_stream) {
                    write_twice<true>(batch, next, {row, size});
                } else {
                    write_twice<false>(batch, next, {row, size});
                }
                next += size * row_bytes;
            });
            if (method == Method::fused_stream) _mm_sfence();
        }
        seal(direct->data(), rounded_bytes * 2);
    }
    const auto assembled = Clock::now();
    const auto digest = first_read(result, bytes);
    const auto consumed = Clock::now();

    if (digest != expected.digest || std::memcmp(result, expected.merged.data(), bytes)) {
        throw std::runtime_error(std::string(label(method)) + " merged output mismatch");
    }
    for (std::size_t side = 0; side < 2; ++side) {
        if (input[side].size && std::memcmp(batches[side], input[side].data,
                                            input[side].size * row_bytes)) {
            throw std::runtime_error(std::string(label(method)) + " batch output mismatch");
        }
    }

    const auto release_start = Clock::now();
    views.reset();
    section.reset();
    direct.reset();
    const auto released = Clock::now();
    return {nanoseconds(prepared - start), nanoseconds(assembled - prepared),
            nanoseconds(consumed - assembled), nanoseconds(consumed - start),
            nanoseconds(released - release_start), mapped};
}

Input fixture(std::size_t left, std::size_t right, std::string_view layout, Word seed) {
    Input input;
    input[0].reserve(left);
    input[1].reserve(right);
    std::mt19937_64 random(seed);
    std::size_t rank = 0;
    const auto append = [&](unsigned side) {
        Row row;
        row.key = rank - (rank % 2048 == 1 ? 1 : 0);
        for (auto& word : row.payload) word = random();
        input[side].push_back(row);
        ++rank;
    };
    const auto overlap = [&](std::size_t size) {
        if (layout == "interleaved") return size;
        return layout == "edge_2pct" ? size / 50 : 0;
    };
    const auto left_overlap = overlap(left);
    const auto right_overlap = overlap(right);
    const auto prefix = left - left_overlap;
    for (std::size_t i = 0; i < prefix; ++i) append(0);
    std::size_t remaining_left = left_overlap;
    std::size_t remaining_right = right_overlap;
    while (remaining_left && remaining_right) {
        std::uniform_int_distribution<std::size_t> pick(0, remaining_left + remaining_right - 1);
        if (pick(random) < remaining_left) {
            append(0);
            --remaining_left;
        } else {
            append(1);
            --remaining_right;
        }
    }
    while (input[0].size() < left) append(0);
    while (input[1].size() < right) append(1);
    return input;
}

void test_edge_cases(const MappingApi& api) {
    for (const auto sizes : {std::array<std::size_t, 2>{0, 546}, {1051, 0}, {31, 33}, {512, 535},
                             {513, 1021}, {2043, 1023}}) {
        for (const auto shape : {0, 1, 2}) {
            auto input = fixture(sizes[0], sizes[1], "disjoint", 37);
            for (std::size_t side = 0; side < 2; ++side) {
                for (auto& row : input[side]) {
                    if (shape == 0) row.key = 17;
                    if (shape == 1) row.key = (1 - side) * 10'000 + row.key;
                    if (shape == 2 && side == 1) row.key = sizes[0] / 2;
                }
            }
            const auto expected = build_expected(input);
            for (const auto method : methods) measure(api, method, bytes_of(input), expected);
        }
    }
}

void run_case(const MappingApi& api, std::string_view layout, std::size_t left, std::size_t right,
              Word seed, unsigned rounds, const std::vector<Word>& eviction) {
    const auto fixture_input = fixture(left, right, layout, seed);
    const auto input = bytes_of(fixture_input);
    const auto expected = build_expected(fixture_input);
    const auto overlap_begin = std::max(input[0].key(0), input[1].key(0));
    const auto overlap_end = std::min(input[0].key(left - 1), input[1].key(right - 1));
    std::size_t overlap_rows = 0;
    if (overlap_begin <= overlap_end) {
        for (auto run : input) {
            overlap_rows += bound(run, overlap_end, true) - bound(run, overlap_begin, false);
        }
    }
    auto order = methods;
    std::mt19937_64 random(seed);
    for (unsigned round = 0; round <= rounds; ++round) {
        std::shuffle(order.begin(), order.end(), random);
        for (const auto method : order) {
            evict_cache(eviction);
            const auto t = measure(api, method, input, expected);
            std::cout << layout << ',' << left << ',' << right << ',' << seed << ',' << round
                      << ',' << label(method) << ',' << t.batches << ',' << t.assemble << ','
                      << t.read << ',' << t.total << ',' << t.teardown << ',' << t.mapped
                      << ',' << overlap_rows << '\n';
        }
        std::cout.flush();
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 2 || (std::string_view(argv[1]) != "--smoke" && std::string_view(argv[1]) != "--bench")) {
            throw std::invalid_argument("usage: bench --smoke|--bench");
        }
        const bool smoke = std::string_view(argv[1]) == "--smoke";
        if (!SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << 8)) {
            windows_error("SetThreadAffinityMask");
        }
        SYSTEM_INFO memory;
        GetSystemInfo(&memory);
        if (memory.dwPageSize != page_bytes) throw std::runtime_error("expected 4 KiB pages");
        const auto kernel = GetModuleHandleW(L"KernelBase.dll");
        if (!kernel) windows_error("GetModuleHandleW");
        const MappingApi api(kernel);
        if (smoke) test_edge_cases(api);
        const std::vector<Word> eviction(eviction_bytes / sizeof(Word), 1);
        std::cout << "layout,left_rows,right_rows,seed,round,method,batches_ns,assembly_ns,"
                     "read_ns,total_ns,teardown_ns,mapped_bytes,overlap_rows\n";
        for (const auto layout : {"edge_2pct", "disjoint", "interleaved"}) {
            if (smoke) {
                run_case(api, layout, 8205, 8191, 109, 0, eviction);
            } else {
                const auto samples = std::string_view(layout) == "edge_2pct" ? 2u : 1u;
                for (unsigned size = 0; size < samples; ++size) {
                    const std::size_t half = std::size_t{1} << (19 + size);
                    run_case(api, layout, half + 13, half - 1, 4'316'079, 5, eviction);
                    run_case(api, layout, half + 19, half + 4, 99'237'281, 5, eviction);
                }
            }
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
