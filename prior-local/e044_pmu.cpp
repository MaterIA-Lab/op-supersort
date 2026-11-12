#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdint>
#include <iostream>
#include <linux/perf_event.h>
#include <random>
#include <stdexcept>
#include <string>
#include <system_error>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <vector>

using U = uint32_t;
using V = std::vector<U>;
#include "e042_generator.inc"

extern "C" void ss_xss256(U*, size_t);
extern "C" void ss_xss128(U*, size_t);

struct GroupRead {
    uint64_t nr, enabled, running;
    uint64_t values[4];
};
static_assert(sizeof(GroupRead) == 7 * sizeof(uint64_t));

class CounterGroup {
    std::array<int, 4> descriptors{-1, -1, -1, -1};
    uint64_t previous_enabled = 0;
    uint64_t previous_running = 0;

    void control(unsigned long request) const {
        if (ioctl(descriptors[0], request, PERF_IOC_FLAG_GROUP) == -1)
            throw std::system_error(errno, std::generic_category(), "perf group ioctl");
    }

public:
    CounterGroup() = default;
    CounterGroup(const CounterGroup&) = delete;
    CounterGroup& operator=(const CounterGroup&) = delete;
    ~CounterGroup() {
        for (int fd : descriptors) if (fd >= 0) close(fd);
    }

    void open_events() {
        constexpr uint64_t events[] = {PERF_COUNT_HW_CPU_CYCLES, PERF_COUNT_HW_INSTRUCTIONS,
                                       PERF_COUNT_HW_CACHE_MISSES, PERF_COUNT_HW_BRANCH_MISSES};
        for (size_t i = 0; i < descriptors.size(); ++i) {
            perf_event_attr attr{};
            attr.type = PERF_TYPE_HARDWARE;
            attr.size = sizeof(attr);
            attr.config = events[i];
            attr.disabled = i == 0;
            attr.exclude_kernel = 1;
            attr.exclude_hv = 1;
            attr.read_format = PERF_FORMAT_GROUP | PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
            descriptors[i] = static_cast<int>(syscall(SYS_perf_event_open, &attr, 0, -1,
                i == 0 ? -1 : descriptors[0], PERF_FLAG_FD_CLOEXEC));
            if (descriptors[i] == -1)
                throw std::system_error(errno, std::generic_category(), "perf_event_open event " + std::to_string(events[i]));
        }
    }

    template<class Call>
    GroupRead measure(Call call) {
        control(PERF_EVENT_IOC_RESET);
        control(PERF_EVENT_IOC_ENABLE);
        call();
        control(PERF_EVENT_IOC_DISABLE);
        GroupRead sample{};
        const ssize_t bytes = read(descriptors[0], &sample, sizeof(sample));
        if (bytes < 0)
            throw std::system_error(errno, std::generic_category(), "perf group read");
        if (bytes != sizeof(sample) || sample.nr != descriptors.size())
            throw std::runtime_error("incomplete PMU group read");
        // RESET clears event values but the two time fields accumulate.
        const auto enabled = sample.enabled;
        const auto running = sample.running;
        if (enabled < previous_enabled || running < previous_running)
            throw std::runtime_error("PMU time fields went backwards");
        sample.enabled -= previous_enabled;
        sample.running -= previous_running;
        previous_enabled = enabled;
        previous_running = running;
        return sample;
    }
};

int main(int argc, char** argv) {
    if (argc != 4) return 1;
    try {
        const size_t n = std::stoull(argv[1]);
        const std::string distribution = argv[2];
        const uint64_t seed = std::stoull(argv[3]);
        const V source = generate(n, distribution, seed);
        V expected = source;
        std::sort(expected.begin(), expected.end());
        CounterGroup counters;
        counters.open_events();
        std::cout << "n,distribution,seed,repeat,algorithm,enabled_ns,running_ns,cycles,instructions,cache_misses,branch_misses\n";
        const auto emit = [&](int round, const char* algorithm, const GroupRead& sample) {
            std::cout << n << ',' << distribution << ',' << seed << ',' << round << ',' << algorithm
                      << ',' << sample.enabled << ',' << sample.running;
            for (auto count : sample.values) std::cout << ',' << count;
            std::cout << '\n';
        };
        for (int round = 0; round < 11; ++round)
            emit(round, "empty", counters.measure([] { asm volatile("" ::: "memory"); }));
        std::array<int, 2> order{256, 128};
        std::mt19937 rng(seed + 1);
        for (int round = -1; round < 11; ++round) {
            std::shuffle(order.begin(), order.end(), rng);
            for (int threshold : order) {
                V data = source;
                auto sort = threshold == 256 ? ss_xss256 : ss_xss128;
                GroupRead sample{};
                if (round == -1) sort(data.data(), n);
                else sample = counters.measure([&] { sort(data.data(), n); });
                if (data != expected) throw std::runtime_error("output differs from std::sort");
                if (round >= 0) emit(round, threshold == 256 ? "simd256dso" : "quick128", sample);
            }
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
