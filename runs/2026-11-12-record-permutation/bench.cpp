#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include <pdqsort.h>
#include <x86simdsort-static-incl.h>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <psapi.h>
#else
#include <sched.h>
#include <sys/resource.h>
#endif

void vq_sort_u64(uint64_t* values, size_t count);

using Clock = std::chrono::steady_clock;

int64_t elapsed(Clock::time_point start, Clock::time_point end) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
}

class SplitMix64 {
public:
    explicit SplitMix64(uint64_t seed) : state_(seed) {}

    uint64_t next() {
        uint64_t value = (state_ += 0x9e3779b97f4a7c15ULL);
        value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
        value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
        return value ^ (value >> 31);
    }

private:
    uint64_t state_;
};

template <size_t Width>
struct alignas(64) Record {
    uint32_t key;
    uint32_t origin;
    std::array<uint64_t, (Width - 8) / 8> payload;
};

template <size_t Width>
std::vector<Record<Width>> make_input(size_t count, uint64_t seed, uint32_t mask) {
    static_assert(sizeof(Record<Width>) == Width);
    SplitMix64 keys(seed);
    SplitMix64 payload(seed ^ 0x5ce86fd4ea5b2ab1ULL);
    std::vector<Record<Width>> input(count);
    for (size_t index = 0; index < count; ++index) {
        auto& row = input[index];
        row.key = static_cast<uint32_t>(keys.next() >> 32) & mask;
        row.origin = static_cast<uint32_t>(index);
        for (auto& word : row.payload) {
            word = payload.next();
        }
    }
    return input;
}

template <size_t Width>
bool correct(const std::vector<Record<Width>>& input, const Record<Width>* output) {
    std::vector<uint8_t> seen(input.size());
    uint32_t last_key = 0;
    for (size_t index = 0; index < input.size(); ++index) {
        const auto& row = output[index];
        if (row.key < last_key || row.origin >= input.size() || seen[row.origin] ||
            std::memcmp(&row, &input[row.origin], Width) != 0) {
            return false;
        }
        seen[row.origin] = 1;
        last_key = row.key;
    }
    return true;
}

enum class Method { vq, x86, pdq, copy };
constexpr std::array methods{Method::vq, Method::x86, Method::pdq, Method::copy};
constexpr std::array method_names{"vq_gather", "x86_gather", "pdq_rows", "sequential_copy"};

struct Times {
    int64_t total;
    int64_t pack;
    int64_t sort;
    int64_t materialize;
};

template <size_t Width>
Times measure(const std::vector<Record<Width>>& input, Method method) {
    const size_t count = input.size();
    std::unique_ptr<Record<Width>[]> output;
    int64_t pack = 0;
    int64_t sort = 0;
    int64_t materialize = 0;
    const auto start = Clock::now();
    if (method == Method::vq || method == Method::x86) {
        std::unique_ptr<uint64_t[]> packed(new uint64_t[count]);
        for (size_t index = 0; index < count; ++index) {
            packed[index] = (uint64_t{input[index].key} << 32) | index;
        }
        const auto packed_at = Clock::now();
        if (method == Method::vq) {
            vq_sort_u64(packed.get(), count);
        } else {
            x86simdsortStatic::qsort(packed.get(), count);
        }
        const auto sorted_at = Clock::now();
        output.reset(new Record<Width>[count]);
        for (size_t index = 0; index < count; ++index) {
            output[index] = input[static_cast<uint32_t>(packed[index])];
        }
        pack = elapsed(start, packed_at);
        sort = elapsed(packed_at, sorted_at);
        materialize = elapsed(sorted_at, Clock::now());
    } else {
        output.reset(new Record<Width>[count]);
        std::memcpy(output.get(), input.data(), count * Width);
        const auto copied_at = Clock::now();
        materialize = elapsed(start, copied_at);
        if (method == Method::pdq) {
            pdqsort(output.get(), output.get() + count,
                    [](const auto& left, const auto& right) { return left.key < right.key; });
            sort = elapsed(copied_at, Clock::now());
        }
    }
    const auto total = elapsed(start, Clock::now());
    const bool valid = method == Method::copy
        ? std::memcmp(output.get(), input.data(), count * Width) == 0
        : correct(input, output.get());
    if (!valid) {
        throw std::runtime_error(std::string(method_names[static_cast<size_t>(method)]) + " failed output verification");
    }
    return {total, pack, sort, materialize};
}

void pin_thread(unsigned cpu) {
#ifdef _WIN32
    if (cpu >= sizeof(DWORD_PTR) * 8 || !SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << cpu)) {
        throw std::runtime_error("cannot set Windows thread affinity");
    }
#else
    if (cpu >= CPU_SETSIZE) {
        throw std::runtime_error("CPU index is outside the Linux affinity mask");
    }
    cpu_set_t mask;
    CPU_ZERO(&mask);
    CPU_SET(cpu, &mask);
    if (sched_setaffinity(0, sizeof(mask), &mask) != 0) {
        throw std::runtime_error("cannot set Linux thread affinity");
    }
#endif
}

uint64_t peak_resident_bytes() {
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS counters{};
    if (!GetProcessMemoryInfo(GetCurrentProcess(), &counters, sizeof(counters))) {
        throw std::runtime_error("cannot read process working-set counters");
    }
    return counters.PeakWorkingSetSize;
#else
    rusage usage{};
    if (getrusage(RUSAGE_SELF, &usage) != 0) {
        throw std::runtime_error("cannot read peak RSS");
    }
    return static_cast<uint64_t>(usage.ru_maxrss) * 1024;
#endif
}

void evict(const std::vector<uint64_t>& buffer) {
    const volatile uint64_t* lines = buffer.data();
    uint64_t sum = 0;
    for (size_t index = 0; index < buffer.size(); index += 8) {
        sum += lines[index];
    }
    if (sum == 0) {
        throw std::runtime_error("cache eviction buffer was not initialized");
    }
}

template <size_t Width>
void run_case(size_t count, std::string_view distribution, uint32_t mask,
              uint64_t seed, unsigned seed_order, unsigned repeats,
              const std::vector<uint64_t>& eviction_buffer) {
    const auto input = make_input<Width>(count, seed, mask);
    for (unsigned repetition = 0; repetition <= repeats; ++repetition) {
        for (size_t slot = 0; slot < methods.size(); ++slot) {
            const size_t index = (slot + repetition + seed_order) % methods.size();
            evict(eviction_buffer);
            const auto times = measure(input, methods[index]);
            std::cout << count << ',' << Width << ',' << distribution << ',' << seed << ',' << repetition
                      << ',' << method_names[index] << ',' << (repetition == 0)
                      << ',' << times.total << ',' << times.pack << ',' << times.sort
                      << ',' << times.materialize << std::endl;
        }
    }
}

int main(int argc, char** argv) {
    try {
        const bool smoke = argc == 3 && std::string_view(argv[2]) == "--smoke";
        if (argc != 2 && !smoke) {
            throw std::runtime_error("usage: record-bench LOGICAL_CPU [--smoke]");
        }
        pin_thread(static_cast<unsigned>(std::stoul(argv[1])));
        const std::vector<uint64_t> eviction_buffer((64 * 1024 * 1024) / sizeof(uint64_t), 1);
        std::cout << "n,record_bytes,distribution,seed,repetition,method,warmup,total_ns,pack_ns,sort_ns,materialize_ns\n";
        if (smoke) {
            run_case<64>(257, "uniform32", UINT32_MAX, 53, 0, 1, eviction_buffer);
            run_case<128>(257, "low12", 4095, 53, 0, 1, eviction_buffer);
        } else {
            constexpr std::array<uint64_t, 2> seeds{271, 1601};
            for (const size_t count : {size_t{1} << 20, size_t{1} << 22}) {
                for (unsigned index = 0; index < seeds.size(); ++index) {
                    run_case<64>(count, "uniform32", UINT32_MAX, seeds[index], index, 3, eviction_buffer);
                    run_case<64>(count, "low12", 4095, seeds[index], index, 3, eviction_buffer);
                    run_case<128>(count, "uniform32", UINT32_MAX, seeds[index], index, 3, eviction_buffer);
                    run_case<128>(count, "low12", 4095, seeds[index], index, 3, eviction_buffer);
                }
            }
        }
        std::cerr << peak_resident_bytes() << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
