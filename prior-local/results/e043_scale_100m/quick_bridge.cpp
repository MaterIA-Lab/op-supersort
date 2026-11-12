#include <cstddef>
#include <cstdint>

#if !defined(__AVX2__)
#error "E040 requires an AVX2 compilation target"
#endif
#if defined(__AVX512F__) || defined(__AVX512VL__) || defined(__AVX512DQ__) \
        || defined(__AVX512BW__)
#error "E040 is an AVX2-only comparison; AVX-512 targets are excluded"
#endif
#if defined(XSS_MINIMAL_NETWORK_SORT)
#error "E040 changes only the uint32 threshold; minimal-network mode is excluded"
#endif
#if !defined(SORT_API) || !defined(EXPECTED_THRESHOLD)
#error "Define the private exported API and expected network threshold"
#endif

#include <x86simdsort-static-incl.h>

static_assert(EXPECTED_THRESHOLD == 128 || EXPECTED_THRESHOLD == 256,
              "E040 only compares the preregistered thresholds");
static_assert(avx2_vector<uint32_t>::network_sort_threshold == EXPECTED_THRESHOLD,
              "Private uint32 AVX2 header has the wrong threshold");
static_assert(avx2_vector<int32_t>::network_sort_threshold == 256,
              "The int32 algorithm must remain unchanged");
static_assert(avx2_vector<float>::network_sort_threshold == 256,
              "The float algorithm must remain unchanged");

extern "C" __attribute__((visibility("default")))
void SORT_API(uint32_t* data, size_t n) {
    if (n < 2) return;
    x86simdsortStatic::qsort(data, n);
}
