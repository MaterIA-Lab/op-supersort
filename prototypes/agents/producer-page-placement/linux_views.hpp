#pragma once

#include <cerrno>
#include <cstddef>
#include <stdexcept>
#include <system_error>
#include <utility>
#include <vector>

#include <sched.h>
#include <sys/mman.h>
#include <unistd.h>

namespace placement {

[[noreturn]] inline void throw_errno(const char* operation, int error = errno) {
    throw std::system_error(error, std::generic_category(), operation);
}

inline int pin_linux_thread() {
    cpu_set_t allowed;
    if (sched_getaffinity(0, sizeof(allowed), &allowed) == -1) throw_errno("sched_getaffinity");
    for (int cpu = CPU_SETSIZE - 1; cpu >= 0; --cpu) {
        if (!CPU_ISSET(cpu, &allowed)) continue;
        cpu_set_t selected;
        CPU_ZERO(&selected);
        CPU_SET(cpu, &selected);
        if (sched_setaffinity(0, sizeof(selected), &selected) == -1) throw_errno("sched_setaffinity");
        return cpu;
    }
    throw std::runtime_error("no available CPU for the benchmark");
}

inline std::byte* checked_map(void* address, std::size_t bytes, int protection, int flags,
                             int fd, std::size_t offset) {
    void* result = mmap(address, bytes, protection, flags, fd, static_cast<off_t>(offset));
    if (result == MAP_FAILED) throw_errno("mmap");
    return static_cast<std::byte*>(result);
}

inline void seal(std::byte* data, std::size_t bytes) {
    if (mprotect(data, bytes, PROT_READ) == -1) throw_errno("mprotect");
}

// Linux calls its mapping functions directly. Windows supplies resolved function addresses.
struct MappingApi {};

class PrivateBlock {
public:
    explicit PrivateBlock(std::size_t bytes)
        : data_(checked_map(nullptr, bytes, PROT_READ | PROT_WRITE,
                            MAP_PRIVATE | MAP_ANONYMOUS, -1, 0)), bytes_(bytes) {}

    ~PrivateBlock() { munmap(data_, bytes_); }
    PrivateBlock(const PrivateBlock&) = delete;
    PrivateBlock& operator=(const PrivateBlock&) = delete;

    std::byte* data() const { return data_; }

private:
    std::byte* data_;
    std::size_t bytes_;
};

class Section {
public:
    Section(std::size_t bytes, std::size_t input_bytes) : input_bytes_(input_bytes) {
        fd_ = memfd_create("supersort-producer-placement", MFD_CLOEXEC);
        if (fd_ == -1) throw_errno("memfd_create");
        if (ftruncate(fd_, static_cast<off_t>(bytes)) == -1) {
            const int error = errno;
            close(fd_);
            throw_errno("ftruncate", error);
        }
        try {
            input_ = checked_map(nullptr, input_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
        } catch (...) {
            close(fd_);
            throw;
        }
    }

    ~Section() {
        munmap(input_, input_bytes_);
        close(fd_);
    }

    Section(const Section&) = delete;
    Section& operator=(const Section&) = delete;

    int handle() const { return fd_; }
    std::byte* input() const { return input_; }

private:
    int fd_;
    std::byte* input_;
    std::size_t input_bytes_;
};

struct Fragment {
    std::size_t output;
    std::size_t bytes;
    std::size_t backing;
    bool writable;
};

class OutputViews {
public:
    explicit OutputViews(const MappingApi&, bool populate) : populate_(populate) {}
    ~OutputViews() {
        if (base_) munmap(base_, bytes_);
    }

    OutputViews(const OutputViews&) = delete;
    OutputViews& operator=(const OutputViews&) = delete;

    void map(int fd, std::size_t bytes, std::vector<Fragment> fragments) {
        fragments_ = std::move(fragments);
        bytes_ = bytes;
        base_ = checked_map(nullptr, bytes_, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        for (const auto& fragment : fragments_) {
            if (fragment.output > bytes_ || fragment.bytes > bytes_ - fragment.output) {
                throw std::logic_error("output fragment outside the reserved range");
            }
            const int protection = fragment.writable ? PROT_READ | PROT_WRITE : PROT_READ;
            int flags = MAP_SHARED | MAP_FIXED;
            if (populate_ && !fragment.writable) flags |= MAP_POPULATE;
            checked_map(base_ + fragment.output, fragment.bytes, protection, flags,
                        fd, fragment.backing);
        }
    }

    void seal_writes() const {
        for (const auto& fragment : fragments_) {
            if (fragment.writable) seal(base_ + fragment.output, fragment.bytes);
        }
    }

    std::byte* data() const { return base_; }

private:
    bool populate_;
    std::vector<Fragment> fragments_;
    std::byte* base_ = nullptr;
    std::size_t bytes_ = 0;
};

}  // namespace placement
