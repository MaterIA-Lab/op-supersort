#define VQSORT_ONLY_STATIC 1
#define HWY_COMPILE_ONLY_STATIC 1
#include <hwy/contrib/sort/vqsort-inl.h>

void vq_sort_u32(uint32_t* data,size_t n){
    hwy::HWY_NAMESPACE::VQSortStatic(data,n,hwy::SortAscending());
}

void seed_vq_for_benchmark(uint64_t first, uint64_t second) {
    auto* state = hwy::detail::GetGeneratorStateStatic();
    state[0] = first;
    state[1] = second;
    state[2] = 1;
}
