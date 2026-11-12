#pragma once

#include "windows_forward_u32.hpp"

namespace supersort::window_detail {

constexpr std::size_t shadow_width = width + 256;

__attribute__((noinline)) inline std::size_t compact_window_shadow(Key* a, std::size_t n,
                                                                  Key prefix, Key* counts) {
    std::size_t used = 0;
    for (std::size_t read = 0; read < n; ++read) {
        const auto key = a[read];
        const auto external = static_cast<Key>((key >> 16) != prefix);
        const auto mask = 65535u ^ (external * 0xff00u);
        const auto index = (key & mask) + (external << 16);
        ++counts[index];
        // An accepted key is only a provisional store at the next free slot.
        a[used] = key;
        used += external;
    }
    return used;
}

// One known window with an unshifted 16-bit prefix and n <= UINT32_MAX.
inline SplitWork sort_window_shadow(Key* a, std::size_t n, Key prefix) {
    if (!n) return {0, 0};
    const auto counts = std::make_unique<Key[]>(shadow_width);
    const auto residual = compact_window_shadow(a, n, prefix, counts.get());
    if (residual > 1) vq_sort_u32(a, residual);
    return restore_window_forward(a, n, prefix, counts.get(), residual);
}

}  // namespace supersort::window_detail
