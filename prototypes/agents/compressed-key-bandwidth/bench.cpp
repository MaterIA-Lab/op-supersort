#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <immintrin.h>

#include <algorithm>
#include <array>
#include <barrier>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string_view>
#include <thread>
#include <vector>

namespace {

enum class Method { copy32, stream32, copy24, stream24, pack, unpack };
constexpr std::array methods{Method::copy32, Method::stream32, Method::copy24,
                             Method::stream24, Method::pack, Method::unpack};
constexpr std::array names{"memcpy32", "stream32", "memcpy24", "stream24", "pack", "unpack"};

struct FreeAligned {
    void operator()(void* p) const { _aligned_free(p); }
};

std::unique_ptr<std::uint8_t, FreeAligned> allocate(std::size_t bytes) {
    auto* p = static_cast<std::uint8_t*>(_aligned_malloc(bytes, 64));
    if (p == nullptr) throw std::bad_alloc();
    return std::unique_ptr<std::uint8_t, FreeAligned>(p);
}

std::vector<DWORD_PTR> physical_cores() {
    DWORD bytes = 0;
    if (GetLogicalProcessorInformationEx(RelationProcessorCore, nullptr, &bytes) ||
        GetLastError() != ERROR_INSUFFICIENT_BUFFER) {
        throw std::runtime_error("Could not size the CPU topology buffer");
    }
    std::vector<std::byte> buffer(bytes);
    auto* data = reinterpret_cast<PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX>(buffer.data());
    DWORD_PTR allowed = 0;
    DWORD_PTR system = 0;
    if (!GetLogicalProcessorInformationEx(RelationProcessorCore, data, &bytes) ||
        !GetProcessAffinityMask(GetCurrentProcess(), &allowed, &system)) {
        throw std::runtime_error("Could not read CPU topology");
    }
    std::vector<DWORD_PTR> cores;
    for (DWORD offset = 0; offset < bytes;) {
        auto* entry = reinterpret_cast<PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX>(buffer.data() + offset);
        if (entry->Processor.GroupCount != 1 || entry->Processor.GroupMask[0].Group != 0) {
            throw std::runtime_error("Expected a single Windows processor group");
        }
        const DWORD_PTR mask = entry->Processor.GroupMask[0].Mask & allowed;
        if (mask != 0) cores.push_back(mask & (DWORD_PTR{0} - mask));
        offset += entry->Size;
    }
    std::sort(cores.begin(), cores.end());
    return cores;
}

std::uint64_t splitmix(std::uint64_t& state) {
    std::uint64_t key = (state += 0x9e3779b97f4a7c15ULL);
    key = (key ^ (key >> 30)) * 0xbf58476d1ce4e5b9ULL;
    key = (key ^ (key >> 27)) * 0x94d049bb133111ebULL;
    return key ^ (key >> 31);
}

void stream_copy(const std::uint8_t* src, std::uint8_t* dst, std::size_t bytes) {
    for (std::size_t i = 0; i < bytes; i += 128) {
        const auto* from = reinterpret_cast<const __m256i*>(src + i);
        auto* to = reinterpret_cast<__m256i*>(dst + i);
        const __m256i a = _mm256_load_si256(from);
        const __m256i b = _mm256_load_si256(from + 1);
        const __m256i c = _mm256_load_si256(from + 2);
        const __m256i d = _mm256_load_si256(from + 3);
        _mm256_stream_si256(to, a);
        _mm256_stream_si256(to + 1, b);
        _mm256_stream_si256(to + 2, c);
        _mm256_stream_si256(to + 3, d);
    }
    _mm_sfence();
}

void pack(const std::uint8_t* src, std::uint8_t* dst, std::size_t keys) {
    const __m128i keep = _mm_setr_epi8(0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14, -1, -1, -1, -1);
    const __m256i select = _mm256_broadcastsi128_si256(keep);
    for (std::size_t i = 0; i < keys; i += 16) {
        const auto* from = reinterpret_cast<const __m256i*>(src + 4 * i);
        auto* to = reinterpret_cast<__m128i*>(dst + 3 * i);
        const __m256i first = _mm256_shuffle_epi8(_mm256_load_si256(from), select);
        const __m256i second = _mm256_shuffle_epi8(_mm256_load_si256(from + 1), select);
        const __m128i a = _mm256_castsi256_si128(first);
        const __m128i b = _mm256_extracti128_si256(first, 1);
        const __m128i c = _mm256_castsi256_si128(second);
        const __m128i d = _mm256_extracti128_si256(second, 1);

        // Four 12-byte groups form exactly three 16-byte stores.
        _mm_stream_si128(to, _mm_or_si128(a, _mm_slli_si128(b, 12)));
        _mm_stream_si128(to + 1, _mm_or_si128(_mm_srli_si128(b, 4), _mm_slli_si128(c, 8)));
        _mm_stream_si128(to + 2, _mm_or_si128(_mm_srli_si128(c, 8), _mm_slli_si128(d, 4)));
    }
    _mm_sfence();
}

void unpack(const std::uint8_t* src, std::uint8_t* dst, std::size_t keys, std::uint32_t prefix) {
    const __m128i insert = _mm_setr_epi8(0, 1, 2, -1, 3, 4, 5, -1, 6, 7, 8, -1, 9, 10, 11, -1);
    const __m256i spread = _mm256_broadcastsi128_si256(insert);
    const __m256i upper = _mm256_set1_epi32(static_cast<std::int32_t>(prefix));
    for (std::size_t i = 0; i < keys; i += 16) {
        const auto* from = reinterpret_cast<const __m128i*>(src + 3 * i);
        auto* to = reinterpret_cast<__m256i*>(dst + 4 * i);
        const __m128i a = _mm_load_si128(from);
        const __m128i b = _mm_load_si128(from + 1);
        const __m128i c = _mm_load_si128(from + 2);
        const __m256i first = _mm256_set_m128i(_mm_alignr_epi8(b, a, 12), a);
        const __m256i second = _mm256_set_m128i(_mm_srli_si128(c, 4), _mm_alignr_epi8(c, b, 8));

        _mm256_stream_si256(to, _mm256_or_si256(_mm256_shuffle_epi8(first, spread), upper));
        _mm256_stream_si256(to + 1, _mm256_or_si256(_mm256_shuffle_epi8(second, spread), upper));
    }
    _mm_sfence();
}

struct Buffers {
    const std::size_t keys;
    const std::uint32_t prefix;
    const std::unique_ptr<std::uint8_t, FreeAligned> source32 = allocate(4 * keys);
    const std::unique_ptr<std::uint8_t, FreeAligned> source24 = allocate(3 * keys);
    const std::unique_ptr<std::uint8_t, FreeAligned> target32 = allocate(4 * keys);
    const std::unique_ptr<std::uint8_t, FreeAligned> target24 = allocate(3 * keys);

    Buffers(std::size_t count, std::uint32_t high_byte) : keys(count), prefix(high_byte) {}

    void set(std::size_t index, std::uint32_t suffix) {
        const auto word = prefix | suffix;
        std::memcpy(source32.get() + 4 * index, &word, sizeof(word));
        for (unsigned byte = 0; byte < 3; ++byte) {
            source24.get()[3 * index + byte] = static_cast<std::uint8_t>(suffix >> (8 * byte));
        }
    }

    void run(Method method, std::size_t offset, std::size_t count) const {
        const auto* from32 = source32.get() + 4 * offset;
        const auto* from24 = source24.get() + 3 * offset;
        auto* to32 = target32.get() + 4 * offset;
        auto* to24 = target24.get() + 3 * offset;
        switch (method) {
            case Method::copy32: std::memcpy(to32, from32, 4 * count); break;
            case Method::stream32: stream_copy(from32, to32, 4 * count); break;
            case Method::copy24: std::memcpy(to24, from24, 3 * count); break;
            case Method::stream24: stream_copy(from24, to24, 3 * count); break;
            case Method::pack: pack(from32, to24, count); break;
            case Method::unpack: unpack(from24, to32, count, prefix); break;
        }
    }

    bool narrow_output(Method method) const {
        return method == Method::copy24 || method == Method::stream24 || method == Method::pack;
    }

    void poison(Method method) const {
        if (narrow_output(method)) std::memset(target24.get(), 0x5a, 3 * keys);
        else std::memset(target32.get(), 0xa5, 4 * keys);
    }

    void verify(Method method) const {
        const bool matches = narrow_output(method)
            ? std::memcmp(target24.get(), source24.get(), 3 * keys) == 0
            : std::memcmp(target32.get(), source32.get(), 4 * keys) == 0;
        if (!matches) throw std::runtime_error("Output differs from its independent reference");
    }
};

void verify_boundaries() {
    constexpr std::array<std::uint32_t, 16> suffixes{
        0, 1, 0xff, 0x100, 0x101, 0x8000, 0xffff, 0x10000,
        0x7fffff, 0x800000, 0xfffffe, 0xffffff, 0xa5, 0x5aa5, 0xa55aa5, 0x010203};
    for (std::uint32_t prefix : {0u, 0x01000000u, 0x80000000u, 0xff000000u}) {
        Buffers data(suffixes.size(), prefix);
        for (std::size_t i = 0; i < suffixes.size(); ++i) data.set(i, suffixes[i]);
        for (Method method : {Method::pack, Method::unpack}) {
            data.poison(method);
            data.run(method, 0, data.keys);
            data.verify(method);
        }
    }
}

void measure(std::size_t keys, std::uint64_t seed, std::size_t workers,
             const std::vector<DWORD_PTR>& cores, const std::uint8_t* evict,
             std::size_t evict_bytes, unsigned repeats) {
    Buffers data(keys, static_cast<std::uint32_t>(seed & 0xff) << 24);
    auto rng = seed;
    for (std::size_t i = 0; i < keys; ++i) {
        data.set(i, static_cast<std::uint32_t>(splitmix(rng)) & 0xffffff);
    }

    std::barrier ready(static_cast<std::ptrdiff_t>(workers + 1));
    std::barrier start(static_cast<std::ptrdiff_t>(workers + 1));
    std::barrier end(static_cast<std::ptrdiff_t>(workers + 1));
    std::vector<unsigned> pinned(workers, 0);
    std::vector<std::thread> threads;
    threads.reserve(workers);
    Method active = Method::copy32;
    bool done = false;
    const auto slice = keys / workers;

    auto stop_workers = [&] {
        done = true;
        start.arrive_and_wait();
        for (auto& t : threads) t.join();
    };
    for (std::size_t worker = 0; worker < workers; ++worker) {
        threads.emplace_back([&, worker] {
            pinned[worker] = SetThreadAffinityMask(GetCurrentThread(), cores[worker]) != 0;
            ready.arrive_and_wait();
            while (true) {
                start.arrive_and_wait();
                if (done) return;
                data.run(active, worker * slice, slice);
                end.arrive_and_wait();
            }
        });
    }
    ready.arrive_and_wait();

    try {
        if (std::find(pinned.begin(), pinned.end(), 0u) != pinned.end()) {
            throw std::runtime_error("Could not pin a worker to its physical core");
        }
        for (unsigned round = 0; round <= repeats; ++round) {
            for (std::size_t position = 0; position < methods.size(); ++position) {
                const auto direction = round % 2 == 0 ? position : methods.size() - 1 - position;
                const auto id = (direction + round + seed % methods.size()) % methods.size();
                active = methods[id];
                data.poison(active);
                for (std::size_t i = 0; i < evict_bytes; i += 64) {
                    auto* byte = static_cast<const volatile std::uint8_t*>(evict + i);
                    (void)*byte;
                }
                const auto before = std::chrono::steady_clock::now();
                start.arrive_and_wait();
                end.arrive_and_wait();
                const auto after = std::chrono::steady_clock::now();
                data.verify(active);
                const auto ms = std::chrono::duration<double, std::milli>(after - before);
                std::cout << keys << ',' << workers << ',' << seed << ',' << round << ',' << position
                          << ',' << names[id] << ',' << ms.count() << ",1\n";
            }
        }
    } catch (...) {
        stop_workers();
        throw;
    }
    stop_workers();
    std::cout.flush();
    std::cerr << "Verified " << (repeats + 1) * methods.size() << " outputs at " << keys
              << " keys, " << workers << " workers, seed " << seed << '\n';
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const bool smoke = argc == 2 && std::string_view(argv[1]) == "--smoke";
        if (argc > 1 && !smoke) throw std::runtime_error("Usage: bench.exe [--smoke]");
        verify_boundaries();
        const auto cores = physical_cores();
        if (cores.size() < 8 && !smoke) throw std::runtime_error("Preregistered matrix requires eight physical cores");
        std::cerr << "Pinned physical core masks:";
        for (const auto mask : cores) std::cerr << " 0x" << std::hex << mask;
        std::cerr << std::dec << "\nVerified 8 boundary conversions\n";
        const std::size_t evict_bytes = (smoke ? 1u : 128u) << 20;
        const auto evict = allocate(evict_bytes);
        std::memset(evict.get(), 0x67, evict_bytes);
        std::cout << "keys,workers,seed,round,position,method,ms,verified\n"
                  << std::fixed << std::setprecision(6);
        if (smoke) {
            measure(4096, 271, 1, cores, evict.get(), evict_bytes, 1);
            return 0;
        }

        for (std::size_t keys : {1u << 24, 1u << 26}) {
            for (std::size_t workers : {1u, 4u, 8u}) {
                if (keys == (1u << 26) && workers == 1) continue;
                for (std::uint64_t seed : {104729u, 130363u}) {
                    measure(keys, seed, workers, cores, evict.get(), evict_bytes, 7);
                }
            }
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
