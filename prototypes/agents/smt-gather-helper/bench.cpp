#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <immintrin.h>

#include "../record-permutation/blocked.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <barrier>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <latch>
#include <memory>
#include <numeric>
#include <stdexcept>
#include <string_view>
#include <thread>
#include <vector>

namespace {

struct alignas(64) Row {
    std::array<std::uint64_t, 16> words;
};
static_assert(sizeof(Row) == 128);
constexpr std::size_t chunk = 128;
enum class Method { split_plain, split16, split32, split64, split128, split_nt_plain,
                    split_nt32, single32, hint256, hint1024, load256, load1024, hint_nt1024 };
constexpr std::array names{"split_plain", "split16", "split32", "split64", "split128",
                           "split_nt_plain", "split_nt32", "single32", "hint256", "hint1024",
                           "load256", "load1024", "hint_nt1024"};

struct Placement {
    std::string_view name;
    std::array<DWORD_PTR, 2> masks;
};

DWORD_PTR lowest_cpu(DWORD_PTR mask) { return mask & (DWORD_PTR{0} - mask); }

std::array<Placement, 2> placements() {
    DWORD bytes = 0;
    if (GetLogicalProcessorInformationEx(RelationProcessorCore, nullptr, &bytes) ||
        GetLastError() != ERROR_INSUFFICIENT_BUFFER) {
        throw std::runtime_error("Cannot size the CPU topology buffer");
    }
    std::vector<std::byte> buffer(bytes);
    auto* topology = reinterpret_cast<PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX>(buffer.data());
    DWORD_PTR allowed = 0;
    DWORD_PTR system = 0;
    if (!GetLogicalProcessorInformationEx(RelationProcessorCore, topology, &bytes) ||
        !GetProcessAffinityMask(GetCurrentProcess(), &allowed, &system)) {
        throw std::runtime_error("Cannot read CPU topology");
    }

    std::vector<DWORD_PTR> core_masks;
    for (DWORD offset = 0; offset < bytes;) {
        auto* entry = reinterpret_cast<PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX>(buffer.data() + offset);
        if (entry->Processor.GroupCount != 1 || entry->Processor.GroupMask[0].Group != 0) {
            throw std::runtime_error("Expected a single Windows processor group");
        }
        const DWORD_PTR mask = entry->Processor.GroupMask[0].Mask & allowed;
        if (mask != 0) core_masks.push_back(mask);
        offset += entry->Size;
    }
    std::sort(core_masks.begin(), core_masks.end());
    auto sibling = std::find_if(core_masks.begin(), core_masks.end(), [](DWORD_PTR mask) {
        return (mask & (mask - 1)) != 0;
    });
    if (sibling == core_masks.end() || core_masks.size() < 2) {
        throw std::runtime_error("The preregistered placement needs SMT and two physical cores");
    }
    const auto core = lowest_cpu(*sibling);
    const auto other = sibling == core_masks.begin() ? core_masks[1] : core_masks.front();
    return {Placement{"smt", {core, lowest_cpu(*sibling ^ core)}},
            Placement{"two_cores", {core, lowest_cpu(other)}}};
}

std::uint64_t splitmix(std::uint64_t& state) {
    std::uint64_t key = (state += 0x9e3779b97f4a7c15ULL);
    key = (key ^ (key >> 30)) * 0xbf58476d1ce4e5b9ULL;
    key = (key ^ (key >> 27)) * 0x94d049bb133111ebULL;
    return key ^ (key >> 31);
}

void touch_lines(const void* buffer, std::size_t bytes) {
    const auto* p = static_cast<const volatile unsigned char*>(buffer);
    for (std::size_t i = 0; i < bytes; i += 64) (void)p[i];
}

void prefetch_row(const Row* row) {
    const auto* bytes = reinterpret_cast<const char*>(row);
    _mm_prefetch(bytes, _MM_HINT_T0);
    _mm_prefetch(bytes + 64, _MM_HINT_T0);
}

template <bool Streaming>
void copy_row(const Row* source, Row* output) {
    if constexpr (Streaming) {
        const auto* from = reinterpret_cast<const __m256i*>(source);
        auto* to = reinterpret_cast<__m256i*>(output);
        for (std::size_t vector = 0; vector < 4; ++vector) {
            _mm256_stream_si256(to + vector, _mm256_load_si256(from + vector));
        }
    } else {
        *output = *source;
    }
}

template <unsigned Lookahead, bool Streaming = false>
void gather(const Row* source, Row* output, const std::uint64_t* order, std::size_t count) {
    std::size_t i = 0;
    if constexpr (Lookahead != 0) {
        for (; i + Lookahead < count; ++i) {
            prefetch_row(source + order[i + Lookahead]);
            copy_row<Streaming>(source + order[i], output + i);
        }
    }
    for (; i < count; ++i) copy_row<Streaming>(source + order[i], output + i);
    if constexpr (Streaming) _mm_sfence();
}

struct Trial {
    const std::size_t rows;
    const std::unique_ptr<Row[]> source = std::make_unique_for_overwrite<Row[]>(rows);
    const std::unique_ptr<Row[]> output = std::make_unique_for_overwrite<Row[]>(rows);
    std::vector<std::uint64_t> order = std::vector<std::uint64_t>(rows);
    alignas(64) std::atomic<std::size_t> consumed{0};
    alignas(64) std::size_t requested = 0;

    Trial(std::size_t count, std::uint64_t seed) : rows(count) {
        auto rng = seed;
        std::iota(order.begin(), order.end(), std::uint64_t{0});
        for (std::size_t i = rows; i > 1; --i) std::swap(order[i - 1], order[splitmix(rng) % i]);
        for (std::size_t i = 0; i < rows; ++i) {
            source[i].words[0] = i;
            for (std::size_t word = 1; word < source[i].words.size(); ++word) {
                source[i].words[word] = splitmix(rng);
            }
        }
    }

    void verify() const {
        for (std::size_t i = 0; i < rows; ++i) {
            if (std::memcmp(&output[i], &source[order[i]], sizeof(Row)) != 0) {
                throw std::runtime_error("Gather result differs from the specified permutation");
            }
        }
    }

    template <bool Streaming>
    void consume() {
        for (std::size_t offset = 0; offset < rows; offset += chunk) {
            // One publication per chunk keeps coordination off the per-record path.
            for (std::size_t i = offset; i < offset + chunk; ++i) {
                copy_row<Streaming>(source.get() + order[i], output.get() + i);
            }
            consumed.store(offset + chunk, std::memory_order_relaxed);
        }
        if constexpr (Streaming) _mm_sfence();
    }

    template <bool Demand, std::size_t Lead>
    void fetch_ahead() {
        std::size_t next = 0;
        std::size_t issued = 0;
        for (auto done = consumed.load(std::memory_order_relaxed); done < rows;
             done = consumed.load(std::memory_order_relaxed)) {
            next = std::max(next, done + chunk);
            const auto end = std::min({rows, done + Lead, next + chunk});
            if (next >= end) {
                _mm_pause();
                continue;
            }
            issued += end - next;
            for (; next < end; ++next) {
                const auto* row = source.get() + order[next];
                if constexpr (Demand) {
                    const auto* bytes = reinterpret_cast<const volatile unsigned char*>(row);
                    (void)bytes[0];
                    (void)bytes[64];
                } else {
                    prefetch_row(row);
                }
            }
        }
        requested = issued;
    }

    void run(Method method, std::size_t worker) {
        const auto half = rows / 2;
        const auto* split_order = order.data() + worker * half;
        auto* split_output = output.get() + worker * half;
        switch (method) {
            case Method::split_plain: gather<0>(source.get(), split_output, split_order, half); return;
            case Method::split16: gather<16>(source.get(), split_output, split_order, half); return;
            case Method::split32: record_permutation::materialize<0, true>(source.get(), split_output, split_order, half); return;
            case Method::split64: gather<64>(source.get(), split_output, split_order, half); return;
            case Method::split128: gather<128>(source.get(), split_output, split_order, half); return;
            case Method::split_nt_plain: gather<0, true>(source.get(), split_output, split_order, half); return;
            case Method::split_nt32: gather<32, true>(source.get(), split_output, split_order, half); return;
            case Method::single32:
                if (worker == 0) record_permutation::materialize<0, true>(source.get(), output.get(), order.data(), rows);
                return;
            default: break;
        }
        if (worker == 0) {
            if (method == Method::hint_nt1024) consume<true>();
            else consume<false>();
            return;
        }
        switch (method) {
            case Method::hint256: fetch_ahead<false, 256>(); break;
            case Method::hint1024:
            case Method::hint_nt1024: fetch_ahead<false, 1024>(); break;
            case Method::load256: fetch_ahead<true, 256>(); break;
            case Method::load1024: fetch_ahead<true, 1024>(); break;
            default: break;
        }
    }
};

void measure(std::size_t rows, std::uint64_t seed, const Placement& placement,
             const std::vector<unsigned char>& eviction, bool fits_cache, unsigned repeats) {
    Trial trial(rows, seed);
    std::latch launch(1);
    std::barrier ready(3), start(3), end(3);
    std::array<bool, 2> pinned{};
    bool stop = false;
    std::size_t method = 0;
    std::vector<std::jthread> threads;
    threads.reserve(2);

    try {
        for (std::size_t i = 0; i < 2; ++i) {
            threads.emplace_back([&, i] {
                launch.wait();
                if (stop) return;
                pinned[i] = SetThreadAffinityMask(GetCurrentThread(), placement.masks[i]) != 0;
                ready.arrive_and_wait();
                for (;;) {
                    start.arrive_and_wait();
                    if (stop) return;
                    trial.run(static_cast<Method>(method), i);
                    end.arrive_and_wait();
                }
            });
        }
    } catch (...) {
        stop = true;
        launch.count_down();
        throw;
    }

    launch.count_down();
    ready.arrive_and_wait();
    try {
        if (!pinned[0] || !pinned[1]) throw std::runtime_error("Cannot set the requested placement");
        for (unsigned round = 0; round <= repeats; ++round) {
            for (std::size_t position = 0; position < names.size(); ++position) {
                const auto direction = round % 2 == 0 ? position : names.size() - 1 - position;
                method = (direction + round + seed % names.size()) % names.size();
                trial.consumed.store(0, std::memory_order_relaxed);
                trial.requested = 0;
                std::memset(trial.output.get(), 0xa5, rows * sizeof(Row));
                touch_lines(eviction.data(), fits_cache ? (8u << 20) : eviction.size());
                if (fits_cache) {
                    touch_lines(trial.source.get(), rows * sizeof(Row));
                    touch_lines(trial.order.data(), rows * sizeof(trial.order[0]));
                }

                const auto before = std::chrono::steady_clock::now();
                start.arrive_and_wait();
                end.arrive_and_wait();
                const auto after = std::chrono::steady_clock::now();
                trial.verify();
                const auto ms = std::chrono::duration<double, std::milli>(after - before);
                std::cout << placement.name << ',' << rows << ',' << seed << ',' << round << ','
                          << position << ',' << names[method] << ',' << ms.count() << ','
                          << trial.requested << ",1\n";
            }
        }
    } catch (...) {
        stop = true;
        start.arrive_and_wait();
        throw;
    }
    stop = true;
    start.arrive_and_wait();
    std::cout.flush();
    std::cerr << "Verified " << (repeats + 1) * names.size() << " outputs: " << placement.name
              << ", " << rows << " rows, seed " << seed << '\n';
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const bool smoke = argc == 2 && std::string_view(argv[1]) == "--smoke";
        if (argc > 1 && !smoke) throw std::runtime_error("Usage: bench.exe [--smoke]");
        const auto cpus = placements();
        for (const auto& placement : cpus) {
            std::cerr << placement.name << " CPU masks: 0x" << std::hex << placement.masks[0]
                      << " and 0x" << placement.masks[1] << std::dec << '\n';
        }
        const std::vector<unsigned char> eviction((smoke ? 8u : 128u) << 20, 0x67);
        std::cout << "placement,rows,seed,round,position,method,ms,requested,verified\n"
                  << std::fixed << std::setprecision(6);
        if (smoke) {
            for (const auto& placement : cpus) measure(4096, 271, placement, eviction, true, 1);
            return 0;
        }

        for (std::uint64_t seed : {104729u, 130363u}) {
            measure(1u << 15, seed, cpus[0], eviction, true, 7);
            for (const auto& placement : cpus) measure(1u << 21, seed, placement, eviction, false, 7);
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
