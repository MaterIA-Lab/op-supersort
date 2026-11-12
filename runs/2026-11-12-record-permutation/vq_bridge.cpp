#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

void vq_sort_u64(uint64_t* values, size_t count) {
    hwy::HWY_NAMESPACE::VQSortStatic(values, count, hwy::SortAscending());
}
