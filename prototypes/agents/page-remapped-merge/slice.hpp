#pragma once

#include <algorithm>
#include <cstddef>

namespace page_remapped_merge {

inline constexpr size_t page_bytes = 4096;
inline constexpr size_t min_alias_bytes = 64 * 1024;

struct Pages {
    size_t prefix;
    size_t bytes;
};

inline Pages full_source_pages(size_t source, size_t bytes) {
    const size_t prefix = std::min((page_bytes - source % page_bytes) % page_bytes, bytes);
    return {prefix, (bytes - prefix) / page_bytes * page_bytes};
}

template <class Copy, class Map>
size_t materialize_slice(size_t source, size_t destination, size_t bytes, Copy copy, Map map) {
    if (bytes < min_alias_bytes || source % page_bytes != destination % page_bytes) {
        copy(0, bytes);
        return 0;
    }
    const auto pages = full_source_pages(source, bytes);
    if (pages.bytes < min_alias_bytes) {
        copy(0, bytes);
        return 0;
    }
    if (pages.prefix != 0) {
        copy(0, pages.prefix);
    }
    map(pages.prefix, pages.bytes);
    const size_t end = pages.prefix + pages.bytes;
    if (end < bytes) {
        copy(end, bytes - end);
    }
    return pages.bytes;
}

}  // namespace page_remapped_merge
