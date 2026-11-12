#include <algorithm>

#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

namespace hn = hwy::HWY_NAMESPACE;

void vq_sort_u32(uint32_t* data, size_t n) {
    hn::VQSortStatic(data, n, hwy::SortAscending());
}

void seed_vq_for_benchmark(uint64_t first, uint64_t second) {
    auto* state = hwy::detail::GetGeneratorStateStatic();
    state[0] = first;
    state[1] = second;
    state[2] = 1;
}

size_t vq_partition_le_u32(uint32_t* data, size_t n, uint32_t pivot) {
    if (n == 0) return 0;
    const hn::SortTag<uint32_t> d;
    if (n <= 2 * hn::Lanes(d)) {
        return std::partition(data, data + n, [pivot](uint32_t key) { return key <= pivot; }) - data;
    }
    const hn::detail::MakeTraits<uint32_t, hwy::SortAscending> traits;
    HWY_ALIGN uint32_t buffer[hwy::SortConstants::BufBytes<uint32_t>(HWY_MAX_BYTES) / sizeof(uint32_t)];
    return hn::detail::Partition(d, traits, data, n, hn::Set(d, pivot), buffer);
}
