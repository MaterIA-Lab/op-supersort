#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>
#include "vendor/powersort/src/sorts/powersort.h"

void power_sort_u32(uint32_t* data,size_t n){
    if(n<2)return;
    // Fresh object: allocation, buffer initialization and destruction are timed.
    // Upstream defaults: minRunLen24, COPY_BOTH, ascending + strict descending.
    algorithms::powersort<uint32_t*> sorter;
    sorter.sort(data,data+n);
}
