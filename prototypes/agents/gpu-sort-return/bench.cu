#include <cuda_runtime.h>
#include <cub/device/device_radix_sort.cuh>
#include <cub/version.cuh>
#include <immintrin.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
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
using Narrow = std::uint16_t;
using Clock = std::chrono::steady_clock;
constexpr unsigned kTiles = 4;
constexpr unsigned kPrefixes = 65536;
constexpr unsigned kFrame = 128;
constexpr unsigned kThreads = 256;
constexpr Key kEmpty = std::numeric_limits<Key>::max();

void check(cudaError_t error, const char* action) {
    if (error != cudaSuccess) {
        throw std::runtime_error(std::string(action) + ": " + cudaGetErrorString(error));
    }
}

template<class T, bool Host = false>
class Buffer {
public:
    Buffer() = default;
    explicit Buffer(std::size_t count) { allocate(count); }
    Buffer(const Buffer&) = delete;
    Buffer& operator=(const Buffer&) = delete;

    void allocate(std::size_t count) {
        const auto bytes = std::max<std::size_t>(1, count) * sizeof(T);
        if constexpr (Host) check(cudaMallocHost(reinterpret_cast<void**>(&data_), bytes), "cudaMallocHost");
        else check(cudaMalloc(reinterpret_cast<void**>(&data_), bytes), "cudaMalloc");
    }

    ~Buffer() {
        if (!data_) return;
        if constexpr (Host) cudaFreeHost(data_);
        else cudaFree(data_);
    }

    T* get() const { return data_; }

private:
    T* data_ = nullptr;
};

class Stream {
public:
    Stream() { check(cudaStreamCreateWithFlags(&stream_, cudaStreamNonBlocking), "create stream"); }
    Stream(const Stream&) = delete;
    ~Stream() { cudaStreamDestroy(stream_); }
    cudaStream_t get() const { return stream_; }
private:
    cudaStream_t stream_{};
};

class Event {
public:
    Event() { check(cudaEventCreate(&event_), "create event"); }
    Event(const Event&) = delete;
    ~Event() { cudaEventDestroy(event_); }
    void record(cudaStream_t stream) const { check(cudaEventRecord(event_, stream), "record event"); }
    void wait() const { check(cudaEventSynchronize(event_), "wait for event"); }
    float since(const Event& start) const {
        float ms = 0;
        check(cudaEventElapsedTime(&ms, start.event_, event_), "event elapsed time");
        return ms;
    }
private:
    cudaEvent_t event_{};
};

__global__ void encode_prefixes(const Key* keys, Narrow* narrow, Key* starts, unsigned size) {
    const unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= size) return;
    const Key key = keys[i];
    narrow[i] = static_cast<Narrow>(key);
    const unsigned prefix = key >> 16;
    if (i == 0 || prefix != (keys[i - 1] >> 16)) starts[prefix] = i;
}

__global__ void encode_frames(const Key* keys, Narrow* narrow, Key* bases, Key* overflow,
                              unsigned size, unsigned frames_per_tile) {
    const unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= size) return;
    const unsigned frame = i / kFrame;
    const unsigned first = frame * kFrame;
    const Key base = keys[first];
    narrow[i] = static_cast<Narrow>(keys[i] - base);
    if (i == first) {
        bases[frame] = base;
        const unsigned end = min(size, first + kFrame);
        if (keys[end - 1] - base > 65535) atomicExch(overflow + frame / frames_per_tile, 1U);
    }
}

template<bool Frame>
void expand(const Narrow* narrow, Key* keys, unsigned first, unsigned end, Key base) {
    const auto one = [base](Narrow value) -> Key {
        if constexpr (Frame) return base + value;
        else return base | value;
    };
    while (first != end && (reinterpret_cast<std::uintptr_t>(keys + first) & 31U) != 0) {
        keys[first] = one(narrow[first]);
        ++first;
    }
    const auto bias = _mm256_set1_epi32(static_cast<int>(base));
    while (end - first >= 8) {
        const auto words = _mm_loadu_si128(reinterpret_cast<const __m128i*>(narrow + first));
        const auto low = _mm256_cvtepu16_epi32(words);
        const auto result = Frame ? _mm256_add_epi32(low, bias) : _mm256_or_si256(low, bias);
        _mm256_stream_si256(reinterpret_cast<__m256i*>(keys + first), result);
        first += 8;
    }
    for (; first < end; ++first) keys[first] = one(narrow[first]);
}

class PrefixCursor {
public:
    PrefixCursor(const Key* starts, unsigned size)
        : starts_(starts), size_(size), prefix_(find(0)), next_(find(prefix_ + 1)) {
        if (prefix_ == kPrefixes || starts_[prefix_] != 0) {
            throw std::runtime_error("prefix table is missing rank zero");
        }
    }

    void expand_until(const Narrow* narrow, Key* keys, unsigned end) {
        while (position_ < end) {
            const unsigned next_rank = next_ == kPrefixes ? size_ : starts_[next_];
            const unsigned last = std::min(end, next_rank);
            if (last <= position_) throw std::runtime_error("nonmonotonic prefix ranks");
            expand<false>(narrow, keys, position_, last, prefix_ << 16);
            position_ = last;
            if (position_ == next_rank) {
                prefix_ = next_;
                next_ = find(next_ + 1);
            }
        }
    }

private:
    unsigned find(unsigned prefix) const {
        for (; prefix < kPrefixes; ++prefix) {
            if (starts_[prefix] != kEmpty) return prefix;
        }
        return kPrefixes;
    }

    const Key* starts_;
    unsigned size_;
    unsigned prefix_;
    unsigned next_;
    unsigned position_ = 0;
};

enum class Method { raw, raw_tiles, prefix_serial, prefix_overlap, frame_serial, frame_overlap };

struct Named {
    Method method;
    const char* name;
};

constexpr std::array<Named, 6> kMethods{{
    {Method::raw, "raw"},
    {Method::raw_tiles, "raw_tiles"},
    {Method::prefix_serial, "prefix_serial"},
    {Method::prefix_overlap, "prefix_overlap"},
    {Method::frame_serial, "frame_serial"},
    {Method::frame_overlap, "frame_overlap"},
}};

struct Sample {
    std::uint64_t total_ns = 0;
    std::uint64_t cpu_expand_ns = 0;
    std::uint64_t return_bytes = 0;
    std::uint64_t escape_bytes = 0;
    float upload_ms = 0;
    float sort_ms = 0;
    float encode_ms = 0;
    float queued_return_ms = 0;
};

std::uint64_t ns_since(Clock::time_point from) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - from).count();
}

class Workspace {
public:
    explicit Workspace(unsigned size)
        : size_(size), frames_((size + kFrame - 1) / kFrame),
          frames_per_tile_((frames_ + kTiles - 1) / kTiles),
          in_(size), out_(size), h_low_(size), h_table_(kPrefixes),
          h_bases_(frames_), h_overflow_(kTiles), a_(size), b_(size),
          d_low_(size), d_table_(kPrefixes), d_bases_(frames_), d_overflow_(kTiles) {
        if (!size_) throw std::invalid_argument("expected a nonempty input");
        cub::DoubleBuffer<Key> keys(a_.get(), b_.get());
        check(cub::DeviceRadixSort::SortKeys(nullptr, temp_bytes_, keys, static_cast<int>(size_),
                                            0, 32, stream_.get()), "size radix workspace");
        temp_.allocate(temp_bytes_);
        std::fill_n(in_.get(), size_, Key{0});
        std::fill_n(out_.get(), size_, Key{0});
        std::fill_n(h_low_.get(), size_, Narrow{0});
        std::fill_n(h_table_.get(), kPrefixes, Key{0});
        std::fill_n(h_bases_.get(), frames_, Key{0});
        std::fill_n(h_overflow_.get(), kTiles, Key{0});
    }

    Key* input() const { return in_.get(); }
    const Key* output() const { return out_.get(); }
    void poison_output(const Key* expected) {
        std::transform(expected, expected + size_, out_.get(), [](Key key) { return ~key; });
    }
    std::size_t sort_scratch() const { return temp_bytes_; }
    std::size_t prefix_scratch_each() const { return size_ * sizeof(Narrow) + kPrefixes * sizeof(Key); }
    std::size_t frame_scratch_each() const { return size_ * sizeof(Narrow) + (frames_ + kTiles) * sizeof(Key); }

    Sample sort(Method method) {
        Sample sample;
        const auto start = Clock::now();
        const auto stream = stream_.get();
        before_.record(stream);
        check(cudaMemcpyAsync(a_.get(), in_.get(), bytes(size_), cudaMemcpyHostToDevice, stream), "upload keys");
        uploaded_.record(stream);
        cub::DoubleBuffer<Key> keys(a_.get(), b_.get());
        check(cub::DeviceRadixSort::SortKeys(temp_.get(), temp_bytes_, keys,
                                            static_cast<int>(size_), 0, 32, stream), "CUB radix sort");
        sorted_.record(stream);
        const auto* source = keys.Current();
        if (method == Method::raw || method == Method::raw_tiles) {
            encoded_.record(stream);
            if (method == Method::raw) {
                copy_to_host(out_.get(), source, bytes(size_));
            } else {
                for (unsigned i = 0; i < kTiles; ++i) {
                    const unsigned first = boundary(i), end = boundary(i + 1);
                    if (first < end) copy_to_host(out_.get() + first, source + first, bytes(end - first));
                }
            }
            returned_.record(stream);
            returned_.wait();
            sample.return_bytes = bytes(size_);
        } else {
            const bool prefix = method == Method::prefix_serial || method == Method::prefix_overlap;
            const bool overlap = method == Method::prefix_overlap || method == Method::frame_overlap;
            encode(source, prefix);
            encoded_.record(stream);
            sample.return_bytes = queue_result(prefix, overlap);
            if (!overlap) returned_.wait();
            if (prefix) decode_prefixes(overlap, sample);
            else decode_frames(source, overlap, sample);
            _mm_sfence();
            if (overlap) returned_.wait();
            sample.return_bytes += sample.escape_bytes;
        }
        sample.total_ns = ns_since(start);
        sample.upload_ms = uploaded_.since(before_);
        sample.sort_ms = sorted_.since(uploaded_);
        sample.encode_ms = encoded_.since(sorted_);
        sample.queued_return_ms = returned_.since(encoded_);
        return sample;
    }

private:
    static std::size_t bytes(unsigned size) { return sizeof(Key) * std::size_t{size}; }

    unsigned boundary(unsigned tile) const {
        return std::min(size_, frames_per_tile_ * kFrame * tile);
    }

    void copy_to_host(void* target, const void* source, std::size_t bytes_to_copy) {
        check(cudaMemcpyAsync(target, source, bytes_to_copy, cudaMemcpyDeviceToHost, stream_.get()),
              "return device data");
    }

    void encode(const Key* source, bool prefix) {
        const auto stream = stream_.get();
        const unsigned blocks = (size_ + kThreads - 1) / kThreads;
        if (prefix) {
            check(cudaMemsetAsync(d_table_.get(), 0xff, bytes(kPrefixes), stream), "clear prefix table");
            encode_prefixes<<<blocks, kThreads, 0, stream>>>(source, d_low_.get(), d_table_.get(), size_);
        } else {
            check(cudaMemsetAsync(d_overflow_.get(), 0, bytes(kTiles), stream), "clear frame flags");
            encode_frames<<<blocks, kThreads, 0, stream>>>(source, d_low_.get(), d_bases_.get(),
                                                         d_overflow_.get(), size_, frames_per_tile_);
        }
        check(cudaGetLastError(), "launch encoder");
    }

    std::uint64_t queue_result(bool prefix, bool overlap) {
        if (prefix) {
            copy_to_host(h_table_.get(), d_table_.get(), bytes(kPrefixes));
        } else {
            copy_to_host(h_bases_.get(), d_bases_.get(), bytes(frames_));
            copy_to_host(h_overflow_.get(), d_overflow_.get(), bytes(kTiles));
        }
        if (overlap) {
            for (unsigned tile = 0; tile < kTiles; ++tile) {
                const unsigned first = boundary(tile), end = boundary(tile + 1);
                if (first == end) break;
                copy_to_host(h_low_.get() + first, d_low_.get() + first, (end - first) * sizeof(Narrow));
                tile_ready_[tile].record(stream_.get());
            }
        } else {
            copy_to_host(h_low_.get(), d_low_.get(), size_ * sizeof(Narrow));
        }
        returned_.record(stream_.get());
        return prefix ? prefix_scratch_each() : frame_scratch_each();
    }

    void decode_prefixes(bool overlap, Sample& sample) {
        if (overlap) tile_ready_[0].wait();
        const auto before_cursor = Clock::now();
        PrefixCursor cursor(h_table_.get(), size_);
        sample.cpu_expand_ns += ns_since(before_cursor);
        for (unsigned tile = 0; tile < kTiles; ++tile) {
            const unsigned end = boundary(tile + 1);
            if (boundary(tile) == end) break;
            if (overlap && tile != 0) tile_ready_[tile].wait();
            const auto begin = Clock::now();
            cursor.expand_until(h_low_.get(), out_.get(), end);
            sample.cpu_expand_ns += ns_since(begin);
        }
    }

    void decode_frames(const Key* source, bool overlap, Sample& sample) {
        for (unsigned tile = 0; tile < kTiles; ++tile) {
            const unsigned begin = boundary(tile), end = boundary(tile + 1);
            if (begin == end) break;
            if (overlap) tile_ready_[tile].wait();
            if (h_overflow_.get()[tile]) {
                copy_to_host(out_.get() + begin, source + begin, bytes(end - begin));
                check(cudaStreamSynchronize(stream_.get()), "await frame escape");
                sample.escape_bytes += bytes(end - begin);
                continue;
            }
            const auto start = Clock::now();
            for (unsigned first = begin; first < end; first += kFrame) {
                const Key base = h_bases_.get()[first / kFrame];
                expand<true>(h_low_.get(), out_.get(), first, std::min(end, first + kFrame), base);
            }
            sample.cpu_expand_ns += ns_since(start);
        }
    }

    unsigned size_, frames_, frames_per_tile_;
    std::size_t temp_bytes_ = 0;
    Buffer<Key, true> in_, out_;
    Buffer<Narrow, true> h_low_;
    Buffer<Key, true> h_table_, h_bases_, h_overflow_;
    Buffer<Key> a_, b_;
    Buffer<Narrow> d_low_;
    Buffer<Key> d_table_, d_bases_, d_overflow_;
    Buffer<unsigned char> temp_;
    Stream stream_;
    Event before_, uploaded_, sorted_, encoded_, returned_;
    std::array<Event, kTiles> tile_ready_{};
};

void pin_thread(unsigned cpu) {
    if (cpu >= std::numeric_limits<DWORD_PTR>::digits ||
        !SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << cpu)) {
        throw std::runtime_error("cannot set host thread affinity");
    }
}

struct SplitMix64 {
    std::uint64_t state;
    std::uint64_t next() {
        std::uint64_t z = (state += 0x9e3779b97f4a7c15ULL);
        z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
        z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
        return z ^ (z >> 31);
    }
};

Key make_key(SplitMix64& rng, bool clustered) {
    const auto raw = static_cast<Key>(rng.next());
    if (!clustered) return raw;
    const Key high = (raw & 0x10000U) ? 0xffff0000U : 0U;
    return high | (raw & 0xffffU);
}

void verify() {
    unsigned fixtures = 0;
    std::uint64_t escapes = 0;
    SplitMix64 rng{381277};
    for (unsigned size : {1U, 2U, 127U, 128U, 129U, 130U, 517U, 1031U, 65537U}) {
        Workspace work(size);
        for (unsigned mode = 0; mode < 3; ++mode) {
            for (unsigned i = 0; i < size; ++i) {
                work.input()[i] = mode == 0 ? kEmpty : make_key(rng, mode == 1);
            }
            if (mode == 1 && size > 1) {
                work.input()[0] = 0;
                work.input()[1] = kEmpty;
            }
            std::vector<Key> expected(work.input(), work.input() + size);
            std::sort(expected.begin(), expected.end());
            for (const auto& named : kMethods) {
                work.poison_output(expected.data());
                escapes += work.sort(named.method).escape_bytes;
                if (!std::equal(expected.begin(), expected.end(), work.output())) {
                    throw std::runtime_error(std::string("edge case failed for ") + named.name);
                }
            }
            ++fixtures;
        }
    }
    if (!escapes) throw std::runtime_error("frame escape was not exercised in preflight");
    std::cout << "Verified " << fixtures << " fixtures across six methods, including frame escapes\n";
}

void version() {
    cudaDeviceProp gpu{};
    int driver = 0, runtime = 0;
    check(cudaGetDeviceProperties(&gpu, 0), "query CUDA device");
    check(cudaDriverGetVersion(&driver), "query CUDA driver");
    check(cudaRuntimeGetVersion(&runtime), "query CUDA runtime");
    std::cout << gpu.name << '\n' << gpu.major << '.' << gpu.minor << '\n'
              << gpu.totalGlobalMem << '\n' << driver << '\n' << runtime << '\n' << CUB_VERSION << '\n'
              << _MSC_FULL_VER << '\n';
}

void measure(unsigned size, std::string_view distribution, std::uint64_t seed, unsigned cpu) {
    pin_thread(cpu);
    Workspace work(size);
    const bool clustered = distribution == "edge_clusters";
    SplitMix64 rng{seed};
    for (unsigned i = 0; i < size; ++i) work.input()[i] = make_key(rng, clustered);
    std::vector<Key> expected(work.input(), work.input() + size);
    std::sort(expected.begin(), expected.end());
    std::mt19937_64 shuffle(seed ^ 0xefe885176aac225dULL);
    auto order = kMethods;
    std::cout << "rows,distribution,seed,round,method,total_ns,upload_ms,sort_ms,encode_ms,"
                 "queued_return_ms,cpu_expand_ns,return_bytes,escape_bytes,cub_scratch,"
                 "prefix_scratch_each,frame_scratch_each,verified\n";
    for (unsigned round = 0; round < 9; ++round) {
        std::shuffle(order.begin(), order.end(), shuffle);
        for (const auto& named : order) {
            work.poison_output(expected.data());
            const auto s = work.sort(named.method);
            if (!std::equal(expected.begin(), expected.end(), work.output())) {
                throw std::runtime_error(std::string("output differs from oracle for ") + named.name);
            }
            std::cout << size << ',' << distribution << ',' << seed << ',' << round << ','
                      << named.name << ',' << s.total_ns << ',' << s.upload_ms << ',' << s.sort_ms
                      << ',' << s.encode_ms << ',' << s.queued_return_ms << ',' << s.cpu_expand_ns
                      << ',' << s.return_bytes << ',' << s.escape_bytes << ',' << work.sort_scratch()
                      << ',' << work.prefix_scratch_each() << ',' << work.frame_scratch_each() << ",true\n";
        }
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        check(cudaSetDevice(0), "select the first CUDA device");
        if (argc == 2 && std::string_view(argv[1]) == "--verify") {
            verify();
        } else if (argc == 2 && std::string_view(argv[1]) == "--version") {
            version();
        } else {
            if (argc != 5) throw std::invalid_argument("usage: bench --verify | --version | ROWS DISTRIBUTION SEED CPU");
            const unsigned size = std::stoul(argv[1]);
            const std::string_view distribution = argv[2];
            if ((size != 16777216 && size != 67108864)
                || (distribution != "uniform" && distribution != "edge_clusters")) {
                throw std::invalid_argument("unregistered size or distribution");
            }
            measure(size, distribution, std::stoull(argv[3]), std::stoul(argv[4]));
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
