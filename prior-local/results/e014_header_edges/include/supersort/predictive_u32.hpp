#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>
#include <x86simdsort-static-incl.h>

namespace supersort {

// Research prototype, CPU only. Best measured niche: ~80k-120k uniform uint32.
// Correct for arbitrary uint32 distributions, with overflow fallback to SIMD.
// Does not sort payloads and provides no stability guarantee.
template<int H=10, int Slack=4>
void predictive_u32(uint32_t* data, size_t n) {
    static_assert(H>=1 && H<=16 && Slack>=0);
    if(n<2)return;
    constexpr size_t K=size_t(1)<<H;
    size_t mean=n/K+(n%K!=0);
    size_t capacity=(mean+size_t(Slack*std::sqrt(double(mean)))+16+15)&~size_t(15);
    if(capacity>std::numeric_limits<size_t>::max()/K)throw std::length_error("capacity overflow");
    std::vector<uint32_t> tmp(K*capacity);
    std::array<size_t,K> count{};
    for(size_t i=0;i<n;++i){
        uint32_t x=data[i];unsigned bucket=x>>(32-H);size_t used=count[bucket];
        // data is still unchanged, so fallback sorts the complete original.
        if(used==capacity){x86simdsortStatic::qsort(data,n);return;}
        tmp[bucket*capacity+used]=x;count[bucket]=used+1;
    }
    size_t out=0;
    for(size_t b=0;b<K;++b){
        uint32_t* begin=tmp.data()+b*capacity;size_t size=count[b];
        if(size)x86simdsortStatic::qsort(begin,size);
        std::copy_n(begin,size,data+out);out+=size;
    }
}

} // namespace supersort
