#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <x86simdsort-static-incl.h>

namespace supersort {
// E036: fixed SIMD leaves followed by binary ping-pong merges.
// uint32 keys only; no stability/payload contract. Auxiliary space: n uint32.
template<bool SkipOrdered>
void merge_u32(uint32_t* data,size_t n){
    if(n<2)return;
    constexpr size_t leaf=128;
    for(size_t lo=0;lo<n;){
        size_t len=std::min(leaf,n-lo);
        x86simdsortStatic::qsort(data+lo,len);lo+=len;
    }
    if(n<=leaf)return;
    std::unique_ptr<uint32_t[]> scratch(new uint32_t[n]);
    uint32_t* src=data;uint32_t* dst=scratch.get();
    for(size_t width=leaf;width<n;){
        for(size_t lo=0;lo<n;){
            size_t mid=lo+std::min(width,n-lo);
            size_t hi=mid+std::min(width,n-mid);
            bool copy=mid==hi;
            if constexpr(SkipOrdered)copy=copy || src[mid-1]<=src[mid];
            if(copy)std::copy(src+lo,src+hi,dst+lo);
            else std::merge(src+lo,src+mid,src+mid,src+hi,dst+lo);
            lo=hi;
        }
        std::swap(src,dst);
        width=width>n/2?n:width*2;
    }
    if(src!=data)std::copy_n(src,n,data);
}
}
