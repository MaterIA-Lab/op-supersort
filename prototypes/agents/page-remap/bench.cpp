#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include <immintrin.h>
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace {

using Clock = std::chrono::steady_clock;
using Word = std::uint64_t;
constexpr std::size_t page_size = 4096;
constexpr std::size_t eviction_bytes = 96 * 1024 * 1024;

[[noreturn]] void windows_error(std::string_view operation, DWORD error = GetLastError()) {
    throw std::runtime_error(std::string(operation) + " failed with " + std::to_string(error));
}

template <typename Function>
Function load_api(HMODULE module, const char* name) {
    const auto address = GetProcAddress(module, name);
    if (!address) windows_error(name);
    return std::bit_cast<Function>(address);
}

struct MappingApi {
    explicit MappingApi(HMODULE module)
        : reserve(load_api<decltype(&VirtualAlloc2)>(module, "VirtualAlloc2")),
          map(load_api<decltype(&MapViewOfFile3)>(module, "MapViewOfFile3")),
          unmap(load_api<decltype(&UnmapViewOfFileEx)>(module, "UnmapViewOfFileEx")) {}

    decltype(&VirtualAlloc2) reserve;
    decltype(&MapViewOfFile3) map;
    decltype(&UnmapViewOfFileEx) unmap;
};

struct InputSection {
    explicit InputSection(std::size_t bytes)
        : section(CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE,
                                     static_cast<DWORD>(Word{bytes} >> 32),
                                     static_cast<DWORD>(bytes), nullptr)) {
        if (!section) windows_error("CreateFileMappingW");
        data = static_cast<std::byte*>(MapViewOfFile(section, FILE_MAP_WRITE, 0, 0, bytes));
        if (!data) {
            const auto error = GetLastError();
            CloseHandle(section);
            windows_error("MapViewOfFile", error);
        }
    }

    ~InputSection() {
        UnmapViewOfFile(data);
        CloseHandle(section);
    }

    InputSection(const InputSection&) = delete;
    InputSection& operator=(const InputSection&) = delete;

    HANDLE section;
    std::byte* data;
};

struct CopyBuffer {
    explicit CopyBuffer(std::size_t bytes)
        : data(static_cast<std::byte*>(
              VirtualAlloc(nullptr, bytes, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE))) {
        if (!data) windows_error("VirtualAlloc");
    }

    ~CopyBuffer() { VirtualFree(data, 0, MEM_RELEASE); }

    CopyBuffer(const CopyBuffer&) = delete;
    CopyBuffer& operator=(const CopyBuffer&) = delete;

    std::byte* data;
};

class MappedResult {
public:
    MappedResult(const MappingApi& api, std::size_t extent, std::size_t count)
        : api_(api), extent_(extent), count_(count) {}

    ~MappedResult() { release(); }

    MappedResult(const MappedResult&) = delete;
    MappedResult& operator=(const MappedResult&) = delete;

    const std::byte* assemble(HANDLE section, const std::vector<std::size_t>& order) {
        base_ = static_cast<std::byte*>(api_.reserve(nullptr, nullptr, extent_ * count_,
            MEM_RESERVE | MEM_RESERVE_PLACEHOLDER, PAGE_NOACCESS, nullptr, 0));
        if (!base_) windows_error("VirtualAlloc2");

        for (; split_ + 1 < count_; ++split_) {
            if (!VirtualFree(base_ + split_ * extent_, extent_,
                             MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {
                windows_error("VirtualFree split");
            }
        }
        for (; mapped_ < count_; ++mapped_) {
            if (!api_.map(section, nullptr, base_ + mapped_ * extent_, order[mapped_] * extent_,
                          extent_, MEM_REPLACE_PLACEHOLDER, PAGE_READONLY, nullptr, 0)) {
                windows_error("MapViewOfFile3");
            }
        }
        return base_;
    }

    bool release() {
        if (!base_) return true;
        bool success = true;
        for (std::size_t i = 0; i < mapped_; ++i) {
            if (!api_.unmap(base_ + i * extent_, 0)) success = false;
        }
        for (std::size_t i = mapped_; i <= split_; ++i) {
            if (!VirtualFree(base_ + i * extent_, 0, MEM_RELEASE)) success = false;
        }
        base_ = nullptr;
        return success;
    }

private:
    const MappingApi& api_;
    const std::size_t extent_;
    const std::size_t count_;
    std::byte* base_ = nullptr;
    std::size_t split_ = 0;
    std::size_t mapped_ = 0;
};

void evict_cache(const std::vector<Word>& buffer) {
    const volatile Word* lines = buffer.data();
    for (std::size_t i = 0; i < buffer.size(); i += 64 / sizeof(Word)) {
        (void)lines[i];
    }
}

void copy_streaming(std::byte* dest, const std::byte* source, std::size_t bytes) {
    for (std::size_t offset = 0; offset < bytes; offset += 64) {
        const auto* input = reinterpret_cast<const __m256i*>(source + offset);
        auto* output = reinterpret_cast<__m256i*>(dest + offset);
        const auto a = _mm256_load_si256(input);
        const auto b = _mm256_load_si256(input + 1);
        _mm256_stream_si256(output, a);
        _mm256_stream_si256(output + 1, b);
    }
}

Word add_page(Word digest, Word value) {
    return (digest ^ value) * Word{1099511628211};
}

Word first_sweep(const std::byte* source, std::size_t extent,
                 const std::vector<std::size_t>& order) {
    Word digest = 0;
    for (const auto part : order) {
        for (std::size_t offset = 0; offset < extent; offset += page_size) {
            Word value;
            std::memcpy(&value, source + part * extent + offset, sizeof(value));
            digest = add_page(digest, value);
        }
    }
    return digest;
}

Word first_sweep(const std::byte* output, std::size_t bytes) {
    Word digest = 0;
    for (std::size_t offset = 0; offset < bytes; offset += page_size) {
        Word value;
        std::memcpy(&value, output + offset, sizeof(value));
        digest = add_page(digest, value);
    }
    return digest;
}

enum class Method { copy, streaming, remap };

const char* name(Method method) {
    switch (method) {
        case Method::copy: return "memcpy";
        case Method::streaming: return "streaming_copy";
        case Method::remap: return "remap";
    }
    throw std::logic_error("unknown method");
}

std::uint64_t nanoseconds(Clock::duration elapsed) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count();
}

void run(const MappingApi& api, std::size_t bytes, std::size_t extent, Word seed,
         unsigned repeats) {
    InputSection input(bytes);
    CopyBuffer copy(bytes);
    for (std::size_t offset = 0; offset < bytes; offset += sizeof(Word)) {
        const Word value = (offset / sizeof(Word)) * Word{0x9e3779b97f4a7c15} ^ seed;
        std::memcpy(input.data + offset, &value, sizeof(value));
    }

    std::mt19937_64 random(seed);
    std::vector<std::size_t> order(bytes / extent);
    std::iota(order.begin(), order.end(), std::size_t{0});
    std::shuffle(order.begin(), order.end(), random);
    const auto expected_digest = first_sweep(input.data, extent, order);
    const std::vector<Word> eviction(eviction_bytes / sizeof(Word), seed);
    std::array methods{Method::copy, Method::streaming, Method::remap};

    std::cout << "bytes,extent,seed,round,method,assembly_ns,sweep_ns,release_ns\n";
    for (unsigned round = 0; round <= repeats; ++round) {
        std::shuffle(methods.begin(), methods.end(), random);
        for (const auto method : methods) {
            if (method != Method::remap) std::memset(copy.data, 0xff, bytes);
            evict_cache(eviction);
            MappedResult mapping(api, extent, order.size());
            const std::byte* output = copy.data;

            const auto start = Clock::now();
            if (method == Method::remap) {
                output = mapping.assemble(input.section, order);
            } else if (method == Method::streaming) {
                for (std::size_t i = 0; i < order.size(); ++i) {
                    copy_streaming(copy.data + i * extent, input.data + order[i] * extent, extent);
                }
                _mm_sfence();
            } else {
                for (std::size_t i = 0; i < order.size(); ++i) {
                    std::memcpy(copy.data + i * extent, input.data + order[i] * extent, extent);
                }
            }
            const auto assembled = Clock::now();
            const auto observed_digest = first_sweep(output, bytes);
            const auto consumed = Clock::now();

            if (observed_digest != expected_digest) throw std::runtime_error("sweep mismatch");
            for (std::size_t i = 0; i < order.size(); ++i) {
                if (std::memcmp(output + i * extent, input.data + order[i] * extent, extent)) {
                    throw std::runtime_error("bytewise output mismatch");
                }
            }

            const auto release_start = Clock::now();
            if (!mapping.release()) throw std::runtime_error("could not release mapped views");
            const auto released = Clock::now();
            std::cout << bytes << ',' << extent << ',' << seed << ',' << round << ','
                      << name(method) << ',' << nanoseconds(assembled - start) << ','
                      << nanoseconds(consumed - assembled) << ','
                      << nanoseconds(released - release_start) << '\n';
        }
        std::cout.flush();
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 6) {
            throw std::invalid_argument("usage: bench BYTES EXTENT_BYTES SEED REPEATS LOGICAL_CPU");
        }
        const auto bytes = std::stoull(argv[1]);
        const auto extent = std::stoull(argv[2]);
        const auto seed = std::stoull(argv[3]);
        const auto repeats = std::stoull(argv[4]);
        const auto cpu = std::stoull(argv[5]);
        if (extent == 0 || extent % page_size || bytes == 0 || bytes % extent || repeats > 1000 ||
            cpu >= sizeof(DWORD_PTR) * 8) {
            throw std::invalid_argument("invalid region size, extent size, repeats or CPU");
        }
        if (!SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR{1} << cpu)) {
            windows_error("SetThreadAffinityMask");
        }
        SYSTEM_INFO info;
        GetSystemInfo(&info);
        if (info.dwPageSize != page_size) throw std::runtime_error("expected 4 KiB system pages");
        const auto kernel = GetModuleHandleW(L"KernelBase.dll");
        if (!kernel) windows_error("GetModuleHandleW");
        run(MappingApi(kernel), bytes, extent, seed, static_cast<unsigned>(repeats));
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
