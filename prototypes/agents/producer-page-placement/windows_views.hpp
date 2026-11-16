#pragma once

#include <bit>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace placement {

[[noreturn]] inline void windows_error(std::string_view operation, DWORD error = GetLastError()) {
    throw std::runtime_error(std::string(operation) + " failed with " + std::to_string(error));
}

template <typename Function>
Function windows_function(HMODULE module, const char* name) {
    const auto address = GetProcAddress(module, name);
    if (!address) windows_error(name);
    return std::bit_cast<Function>(address);
}

struct MappingApi {
    explicit MappingApi(HMODULE module)
        : reserve(windows_function<decltype(&VirtualAlloc2)>(module, "VirtualAlloc2")),
          map(windows_function<decltype(&MapViewOfFile3)>(module, "MapViewOfFile3")),
          unmap(windows_function<decltype(&UnmapViewOfFileEx)>(module, "UnmapViewOfFileEx")) {}

    decltype(&VirtualAlloc2) reserve;
    decltype(&MapViewOfFile3) map;
    decltype(&UnmapViewOfFileEx) unmap;
};

inline void seal(std::byte* data, std::size_t bytes) {
    DWORD previous;
    if (!VirtualProtect(data, bytes, PAGE_READONLY, &previous)) windows_error("VirtualProtect");
}

class PrivateBlock {
public:
    explicit PrivateBlock(std::size_t bytes)
        : data_(static_cast<std::byte*>(
              VirtualAlloc(nullptr, bytes, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE))) {
        if (!data_) windows_error("VirtualAlloc");
    }

    ~PrivateBlock() { VirtualFree(data_, 0, MEM_RELEASE); }
    PrivateBlock(const PrivateBlock&) = delete;
    PrivateBlock& operator=(const PrivateBlock&) = delete;

    std::byte* data() const { return data_; }

private:
    std::byte* data_;
};

class Section {
public:
    Section(std::size_t bytes, std::size_t input_bytes)
        : handle_(CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE,
                                     static_cast<DWORD>(std::uint64_t{bytes} >> 32),
                                     static_cast<DWORD>(bytes), nullptr)) {
        if (!handle_) windows_error("CreateFileMappingW");
        input_ = static_cast<std::byte*>(MapViewOfFile(handle_, FILE_MAP_WRITE, 0, 0, input_bytes));
        if (!input_) {
            const auto error = GetLastError();
            CloseHandle(handle_);
            windows_error("MapViewOfFile", error);
        }
    }

    ~Section() {
        UnmapViewOfFile(input_);
        CloseHandle(handle_);
    }

    Section(const Section&) = delete;
    Section& operator=(const Section&) = delete;

    HANDLE handle() const { return handle_; }
    std::byte* input() const { return input_; }

private:
    HANDLE handle_;
    std::byte* input_;
};

struct Fragment {
    std::size_t output;
    std::size_t bytes;
    std::size_t backing;
    bool writable;
};

class OutputViews {
public:
    explicit OutputViews(const MappingApi& api) : api_(api) {}
    ~OutputViews() {
        if (!base_) return;
        for (std::size_t i = 0; i < mapped_; ++i) {
            api_.unmap(base_ + fragments_[i].output, 0);
        }
        for (std::size_t i = mapped_; i <= splits_; ++i) {
            VirtualFree(base_ + fragments_[i].output, 0, MEM_RELEASE);
        }
    }

    OutputViews(const OutputViews&) = delete;
    OutputViews& operator=(const OutputViews&) = delete;

    void map(HANDLE section, std::size_t bytes, std::vector<Fragment> fragments) {
        fragments_ = std::move(fragments);
        base_ = static_cast<std::byte*>(api_.reserve(nullptr, nullptr, bytes,
            MEM_RESERVE | MEM_RESERVE_PLACEHOLDER, PAGE_NOACCESS, nullptr, 0));
        if (!base_) windows_error("VirtualAlloc2");
        for (; splits_ + 1 < fragments_.size(); ++splits_) {
            const auto& fragment = fragments_[splits_];
            if (!VirtualFree(base_ + fragment.output, fragment.bytes,
                             MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {
                windows_error("VirtualFree split");
            }
        }
        for (; mapped_ < fragments_.size(); ++mapped_) {
            const auto& fragment = fragments_[mapped_];
            const DWORD access = fragment.writable ? PAGE_READWRITE : PAGE_READONLY;
            if (!api_.map(section, nullptr, base_ + fragment.output, fragment.backing,
                          fragment.bytes, MEM_REPLACE_PLACEHOLDER, access, nullptr, 0)) {
                windows_error("MapViewOfFile3");
            }
        }
    }

    void seal_writes() const {
        for (const auto& piece : fragments_) {
            if (piece.writable) seal(base_ + piece.output, piece.bytes);
        }
    }

    std::byte* data() const { return base_; }

private:
    const MappingApi& api_;
    std::vector<Fragment> fragments_;
    std::byte* base_ = nullptr;
    std::size_t splits_ = 0;
    std::size_t mapped_ = 0;
};

}  // namespace placement
