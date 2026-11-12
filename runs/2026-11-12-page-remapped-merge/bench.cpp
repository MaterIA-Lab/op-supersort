#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <new>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <system_error>
#include <vector>

#include <sys/mman.h>
#include <sys/resource.h>
#include <unistd.h>

#include "../../prototypes/agents/page-remapped-merge/slice.hpp"

namespace {

using page_remapped_merge::full_source_pages;
using page_remapped_merge::page_bytes;
constexpr size_t mib = 1024 * 1024;
constexpr size_t calibration_bytes = 128 * mib;
constexpr std::array extent_sizes{page_bytes, size_t{64 * 1024}, 2 * mib, 16 * mib, 128 * mib};
using Clock = std::chrono::steady_clock;

[[noreturn]] void system_error(const char* operation) {
    throw std::system_error(errno, std::generic_category(), operation);
}

class MemoryFile {
public:
    explicit MemoryFile(size_t bytes) : fd_(memfd_create("supersort-page-merge", MFD_CLOEXEC)) {
        if (fd_ == -1) {
            system_error("memfd_create");
        }
        if (ftruncate(fd_, static_cast<off_t>(bytes)) == -1) {
            const int error = errno;
            close(fd_);
            throw std::system_error(error, std::generic_category(), "ftruncate");
        }
    }

    ~MemoryFile() { close(fd_); }
    MemoryFile(const MemoryFile&) = delete;
    MemoryFile& operator=(const MemoryFile&) = delete;
    int fd() const { return fd_; }

private:
    int fd_;
};

class Region {
public:
    explicit Region(size_t bytes, int fd = -1) : size_(bytes) {
        const int flags = fd == -1 ? MAP_PRIVATE | MAP_ANONYMOUS : MAP_SHARED;
        void* address = mmap(nullptr, size_, PROT_READ | PROT_WRITE, flags, fd, 0);
        if (address == MAP_FAILED) {
            system_error("mmap");
        }
        data_ = static_cast<char*>(address);
    }

    ~Region() { munmap(data_, size_); }
    Region(const Region&) = delete;
    Region& operator=(const Region&) = delete;
    char* data() const { return data_; }

    void map_slice(int fd, size_t source, size_t destination, size_t bytes) {
        if (destination > size_ || bytes > size_ - destination || !bytes ||
            (source | destination | bytes) % page_bytes != 0) {
            throw std::logic_error("unaligned or out-of-range mapping");
        }
        if (mmap(data_ + destination, bytes, PROT_READ, MAP_SHARED | MAP_FIXED, fd,
                 static_cast<off_t>(source)) == MAP_FAILED) {
            system_error("mmap slice");
        }
    }

    void make_read_only() {
        if (mprotect(data_, size_, PROT_READ) == -1) {
            system_error("mprotect");
        }
    }

private:
    char* data_;
    size_t size_;
};

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

uint64_t cache_line_sum(const char* data, size_t bytes) {
    uint64_t sum = 0;
    for (size_t offset = 0; offset < bytes; offset += 64) {
        uint64_t word;
        std::memcpy(&word, data + offset, sizeof(word));
        sum += word;
    }
    return sum;
}

void evict(const std::vector<uint64_t>& buffer) {
    const volatile uint64_t* data = buffer.data();
    uint64_t sum = 0;
    for (size_t word = 0; word < buffer.size(); word += 8) {
        sum += data[word];
    }
    if (!sum) {
        throw std::logic_error("empty eviction buffer");
    }
}

struct Times {
    int64_t assembly;
    int64_t scan;
    int64_t total;
    int64_t teardown;
};

template <class Assemble, class Verify>
Times sample(size_t bytes, uint64_t checksum, const std::vector<uint64_t>& buffer,
             Assemble assemble, Verify verify, bool reuse = false) {
    std::optional<Region> output;
    if (reuse) {
        output.emplace(bytes);
        volatile char* data = output->data();
        for (size_t offset = 0; offset < bytes; offset += page_bytes) {
            data[offset] = 0;
        }
    }
    evict(buffer);
    const auto start = Clock::now();
    if (!reuse) {
        output.emplace(bytes);
    }
    assemble(*output);
    output->make_read_only();
    const auto assembled = Clock::now();
    const uint64_t actual_checksum = cache_line_sum(output->data(), bytes);
    const auto finished = Clock::now();
    if (actual_checksum != checksum || !verify(output->data())) {
        throw std::runtime_error("output did not match every expected byte");
    }
    const auto teardown = Clock::now();
    output.reset();
    const auto released = Clock::now();
    const auto nanoseconds = [](Clock::duration duration) {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();
    };
    return {nanoseconds(assembled - start), nanoseconds(finished - assembled), nanoseconds(finished - start),
            nanoseconds(released - teardown)};
}

void print_times(Times times) {
    std::cout << ',' << times.assembly << ',' << times.scan << ',' << times.total;
}

void calibrate(bool smoke, const std::vector<uint64_t>& buffer) {
    const size_t bytes = smoke ? 2 * mib : calibration_bytes;
    MemoryFile file(bytes);
    Region source(bytes, file.fd());
    SplitMix64 random(53);
    for (size_t offset = 0; offset < bytes; offset += sizeof(uint64_t)) {
        const uint64_t word = random.next();
        std::memcpy(source.data() + offset, &word, sizeof(word));
    }
    source.make_read_only();
    const uint64_t checksum = cache_line_sum(source.data(), bytes);
    std::cout << "bytes,extent_bytes,repetition,method,warmup,assembly_ns,scan_ns,total_ns\n";
    for (size_t extent : extent_sizes) {
        if (extent > bytes) {
            break;
        }
        for (unsigned repetition = 0; repetition <= (smoke ? 1U : 5U); ++repetition) {
            for (unsigned slot = 0; slot < 2; ++slot) {
                const bool alias = (slot + repetition) % 2;
                const Times times = sample(bytes, checksum, buffer, [&](Region& output) {
                    for (size_t destination = 0; destination < bytes; destination += extent) {
                        const size_t offset = bytes - destination - extent;
                        if (alias) {
                            output.map_slice(file.fd(), offset, destination, extent);
                        } else {
                            std::memcpy(output.data() + destination, source.data() + offset, extent);
                        }
                    }
                }, [&](const char* output) {
                    for (size_t destination = 0; destination < bytes; destination += extent) {
                        if (std::memcmp(output + destination, source.data() + bytes - destination - extent, extent)) {
                            return false;
                        }
                    }
                    return true;
                });
                std::cout << bytes << ',' << extent << ',' << repetition << ','
                          << (alias ? "map" : "copy") << ',' << (repetition == 0);
                print_times(times);
                std::cout << '\n';
            }
        }
    }
}

struct alignas(64) Record {
    uint64_t key;
    uint64_t rank;
    std::array<uint64_t, 14> payload;
};
static_assert(sizeof(Record) == 128);

struct Run {
    const Record* data;
    size_t count;
};

enum class Layout { adjacent, edge, bursty, interleaved };
constexpr std::array layout_names{"adjacent", "edge_overlap", "bursty", "interleaved"};

std::vector<uint8_t> make_labels(size_t count, Layout layout, uint64_t seed) {
    std::vector<uint8_t> labels(count);
    SplitMix64 random(seed);
    if (layout == Layout::adjacent) {
        std::fill(labels.begin() + count / 2, labels.end(), 1);
    } else if (layout == Layout::edge) {
        const size_t overlap_start = 3 * count / 8 + 3;
        const size_t overlap_end = overlap_start + count / 4;
        for (size_t index = overlap_start; index < overlap_end; ++index) {
            labels[index] = random.next() & 1;
        }
        std::fill(labels.begin() + overlap_end, labels.end(), 1);
    } else if (layout == Layout::bursty) {
        constexpr size_t window = 32768;
        for (size_t start = 0; start < count; start += window) {
            const size_t end = std::min(start + window, count);
            const size_t exclusive_end = std::min(start + 28672 + random.next() % 127, end);
            std::fill(labels.begin() + start, labels.begin() + exclusive_end, (start / window) % 2);
            for (size_t index = exclusive_end; index < end; ++index) {
                labels[index] = random.next() & 1;
            }
        }
    } else {
        for (auto& label : labels) {
            label = random.next() & 1;
        }
    }
    return labels;
}

size_t winning_prefix(const Record* data, size_t count, uint64_t other_key) {
    if (data[count - 1].key < other_key) {
        return count;
    }
    size_t upper = 1;
    while (upper < count && data[upper].key < other_key) {
        upper *= 2;
    }
    const Record* bound = std::lower_bound(data + upper / 2 + 1, data + std::min(upper + 1, count),
                                           other_key, [](const Record& row, uint64_t key) { return row.key < key; });
    return static_cast<size_t>(bound - data);
}

template <class Emit>
void visit_slices(const std::array<Run, 2>& runs, Emit emit) {
    std::array<size_t, 2> next{};
    while (next[0] < runs[0].count && next[1] < runs[1].count) {
        const unsigned side = runs[1].data[next[1]].key < runs[0].data[next[0]].key;
        const size_t count = winning_prefix(runs[side].data + next[side], runs[side].count - next[side],
                                            runs[1 - side].data[next[1 - side]].key);
        emit(side, next[side], next[0] + next[1], count);
        next[side] += count;
    }
    for (unsigned side = 0; side < 2; ++side) {
        if (next[side] < runs[side].count) {
            emit(side, next[side], next[0] + next[1], runs[side].count - next[side]);
        }
    }
}

struct Coverage {
    size_t source_aligned = 0;
    size_t extent_count = 0;
    std::array<size_t, extent_sizes.size()> bytes{};
};

Coverage coverage(const std::array<Run, 2>& runs, const std::vector<Record>& expected) {
    Coverage result;
    visit_slices(runs, [&](unsigned side, size_t source, size_t destination, size_t count) {
        const size_t bytes = count * sizeof(Record);
        if (std::memcmp(runs[side].data + source, expected.data() + destination, bytes)) {
            throw std::runtime_error("merge slice did not match expected records");
        }
        const auto pages = full_source_pages(source * sizeof(Record), bytes);
        result.source_aligned += pages.bytes;
        if (pages.bytes && (source * sizeof(Record)) % page_bytes == (destination * sizeof(Record)) % page_bytes) {
            const size_t bucket = std::upper_bound(extent_sizes.begin(), extent_sizes.end(), pages.bytes) -
                                  extent_sizes.begin() - 1;
            result.bytes[bucket] += pages.bytes;
            ++result.extent_count;
        }
    });
    return result;
}

void scalar_merge(const std::array<Run, 2>& runs, char* output) {
    size_t left = 0;
    size_t right = 0;
    while (left < runs[0].count && right < runs[1].count) {
        const auto* source = runs[1].data[right].key < runs[0].data[left].key
            ? runs[1].data + right++ : runs[0].data + left++;
        std::memcpy(output, source, sizeof(Record));
        output += sizeof(Record);
    }
    if (left < runs[0].count) {
        std::memcpy(output, runs[0].data + left, (runs[0].count - left) * sizeof(Record));
    } else {
        std::memcpy(output, runs[1].data + right, (runs[1].count - right) * sizeof(Record));
    }
}

void hybrid_merge(std::array<Run, 2> runs, char* output) {
    if (!runs[0].count || !runs[1].count) {
        scalar_merge(runs, output);
        return;
    }
    const unsigned first = runs[1].data[0].key < runs[0].data[0].key;
    auto& leading = runs[first];
    const size_t prefix = winning_prefix(leading.data, leading.count, runs[1 - first].data[0].key);
    std::memcpy(output, leading.data, prefix * sizeof(Record));
    output += prefix * sizeof(Record);
    leading.data += prefix;
    leading.count -= prefix;
    if (!leading.count) {
        std::memcpy(output, runs[1 - first].data, runs[1 - first].count * sizeof(Record));
        return;
    }

    const unsigned last = runs[0].data[runs[0].count - 1].key < runs[1].data[runs[1].count - 1].key;
    auto& trailing = runs[last];
    const auto& other = runs[1 - last];
    const auto* suffix = std::lower_bound(trailing.data, trailing.data + trailing.count,
                                          other.data[other.count - 1].key,
                                          [](const Record& row, uint64_t key) { return row.key < key; });
    const size_t middle = static_cast<size_t>(suffix - trailing.data);
    const size_t suffix_bytes = (trailing.count - middle) * sizeof(Record);
    trailing.count = middle;
    scalar_merge(runs, output);
    std::memcpy(output + (runs[0].count + runs[1].count) * sizeof(Record), suffix, suffix_bytes);
}

enum class Method { scalar, bulk, hybrid, reused, remap };
constexpr std::array method_names{"scalar", "bulk", "hybrid", "hybrid_reused", "remap"};
constexpr std::array pilot_methods{Method::scalar, Method::bulk};
constexpr std::array candidate_methods{Method::scalar, Method::bulk, Method::hybrid, Method::reused, Method::remap};

size_t round_to_page(size_t bytes) {
    return (bytes + page_bytes - 1) / page_bytes * page_bytes;
}

template <size_t MethodCount>
void merge_case(size_t count, Layout layout, uint64_t seed, unsigned seed_order, bool smoke,
                const std::vector<uint64_t>& buffer, const std::array<Method, MethodCount>& methods) {
    const auto labels = make_labels(count, layout, seed);
    const size_t left = std::count(labels.begin(), labels.end(), uint8_t{0});
    const size_t second_offset = round_to_page(left * sizeof(Record));
    const size_t input_bytes = second_offset + round_to_page((count - left) * sizeof(Record));
    MemoryFile file(input_bytes);
    Region input(input_bytes, file.fd());
    const std::array source{input.data(), input.data() + second_offset};
    const std::array rows{::new (source[0]) Record[left], ::new (source[1]) Record[count - left]};
    const std::array runs{Run{rows[0], left}, Run{rows[1], count - left}};
    std::array<size_t, 2> next{};
    std::vector<Record> expected(count);
    SplitMix64 jitter(seed ^ 0xc13fa9a902a6328fULL);
    SplitMix64 payload(seed ^ 0x91e10da5c79e7b1dULL);
    for (size_t rank = 0; rank < count; ++rank) {
        auto& row = expected[rank];
        row.key = rank * 32 + (jitter.next() & 31);
        row.rank = rank;
        for (auto& word : row.payload) {
            word = payload.next();
        }
        const unsigned side = labels[rank];
        rows[side][next[side]++] = row;
    }
    input.make_read_only();
    const auto geometry = coverage(runs, expected);
    const auto* expected_bytes = reinterpret_cast<const char*>(expected.data());
    const size_t bytes = count * sizeof(Record);
    const uint64_t checksum = cache_line_sum(expected_bytes, bytes);
    for (unsigned repetition = 0; repetition <= (smoke ? 1U : 5U); ++repetition) {
        for (size_t slot = 0; slot < methods.size(); ++slot) {
            const Method method = methods[(slot + repetition + seed_order) % methods.size()];
            size_t mapped_bytes = 0;
            size_t map_calls = 0;
            const Times times = sample(bytes, checksum, buffer, [&](Region& output) {
                if (method == Method::scalar) {
                    scalar_merge(runs, output.data());
                } else if (method == Method::hybrid || method == Method::reused) {
                    hybrid_merge(runs, output.data());
                } else {
                    visit_slices(runs, [&](unsigned side, size_t from, size_t to, size_t length) {
                        const size_t source_offset = from * sizeof(Record);
                        const size_t destination = to * sizeof(Record);
                        const size_t length_bytes = length * sizeof(Record);
                        const auto copy = [&](size_t relative, size_t amount) {
                            std::memcpy(output.data() + destination + relative,
                                        source[side] + source_offset + relative, amount);
                        };
                        if (method == Method::remap) {
                            const size_t backing_offset = side == 0 ? 0 : second_offset;
                            mapped_bytes += page_remapped_merge::materialize_slice(source_offset, destination, length_bytes,
                                copy, [&](size_t relative, size_t amount) {
                                    output.map_slice(file.fd(), backing_offset + source_offset + relative,
                                                     destination + relative, amount);
                                    ++map_calls;
                                });
                        } else {
                            copy(0, length_bytes);
                        }
                    });
                }
            }, [&](const char* output) { return std::memcmp(output, expected_bytes, bytes) == 0; },
            method == Method::reused);
            std::cout << count << ',' << layout_names[static_cast<size_t>(layout)] << ',' << seed << ','
                      << repetition << ',' << method_names[static_cast<size_t>(method)] << ',' << (repetition == 0);
            print_times(times);
            std::cout << ',' << geometry.source_aligned << ',' << geometry.extent_count;
            for (size_t bucket : geometry.bytes) {
                std::cout << ',' << bucket;
            }
            if constexpr (MethodCount == candidate_methods.size()) {
                std::cout << ',' << mapped_bytes << ',' << map_calls << ',' << times.teardown;
            }
            std::cout << '\n';
        }
    }
}

template <size_t MethodCount>
void benchmark_merge(bool smoke, const std::vector<uint64_t>& buffer, const std::array<Method, MethodCount>& methods,
                     const std::array<uint64_t, 2>& seeds) {
    std::cout << "records,layout,seed,repetition,method,warmup,assembly_ns,scan_ns,total_ns,source_aligned_bytes,extents";
    for (size_t size : extent_sizes) {
        std::cout << ",eligible_" << size;
    }
    if constexpr (MethodCount == candidate_methods.size()) {
        std::cout << ",mapped_bytes,map_calls,teardown_ns";
    }
    std::cout << '\n';
    for (size_t count : {size_t{1} << 20, size_t{1} << 22}) {
        for (auto layout : {Layout::adjacent, Layout::edge, Layout::bursty, Layout::interleaved}) {
            for (unsigned index = 0; index < seeds.size(); ++index) {
                const unsigned order = MethodCount == candidate_methods.size() ? index : 0;
                merge_case(smoke ? size_t{1} << 15 : count, layout, seeds[index], order, smoke, buffer, methods);
            }
        }
        if (smoke) {
            break;
        }
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const bool smoke = argc == 3 && std::string_view(argv[2]) == "--smoke";
        if (argc != 2 && !smoke) {
            throw std::runtime_error("usage: bench calibrate|merge|candidate [--smoke]");
        }
        if (sysconf(_SC_PAGESIZE) != page_bytes) {
            throw std::runtime_error("experiment requires 4 KiB pages");
        }
        const std::vector<uint64_t> buffer(64 * mib / sizeof(uint64_t), 1);
        const std::string_view mode(argv[1]);
        if (mode == "calibrate") {
            calibrate(smoke, buffer);
        } else if (mode == "merge") {
            benchmark_merge(smoke, buffer, pilot_methods, {271, 1601});
        } else if (mode == "candidate") {
            benchmark_merge(smoke, buffer, candidate_methods, {104729, 130363});
        } else {
            throw std::runtime_error("unknown benchmark mode");
        }
        rusage usage{};
        if (getrusage(RUSAGE_SELF, &usage) == -1) {
            system_error("getrusage");
        }
        std::cerr << mode << "_peak_rss_kib=" << usage.ru_maxrss << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
