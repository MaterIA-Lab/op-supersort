#include <cstddef>
#include <cstdint>
#include "e042_stats.hpp"
#if !defined(__AVX2__) || defined(__AVX512F__) || defined(XSS_COMPILE_OPENMP)
#error "E042 requires sequential AVX2"
#endif
#include <x86simdsort-static-incl.h>
static_assert(avx2_vector<uint32_t>::network_sort_threshold==EXPECTED_THRESHOLD);
static_assert(avx2_vector<int32_t>::network_sort_threshold==256);
extern "C" __attribute__((visibility("default")))
void SORT_API(uint32_t* a,size_t n,E042Stats* output) {
    e042_stats=E042Stats{}; e042_depth=0;
    if(n>1)x86simdsortStatic::qsort(a,n);
    *output=e042_stats;
}
