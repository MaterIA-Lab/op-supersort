#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>
#include <x86simdsort-static-incl.h>

namespace supersort {
struct merge_run_stats {
    size_t runs=0, simd_elements=0, reversed_elements=0;
    size_t levels=0, merged_elements=0, copied_elements=0, final_elements=0;
};

// E037: identical pairwise scheduler and merge kernel; only run formation differs.
// Key-only uint32; SIMD extension means no payload stability guarantee.
template<bool Natural, bool Profile=false>
void natural_merge_u32(uint32_t* data,size_t n,merge_run_stats* stats=nullptr){
    if(n<2)return;
    constexpr size_t leaf=128;
    struct run {size_t lo,hi;};
    std::vector<run> runs;
    runs.reserve(n/leaf+(n%leaf!=0));
    for(size_t lo=0;lo<n;){
        size_t hi=lo+1;
        if constexpr(Natural){
            if(hi<n && data[hi]<data[lo]){
                while(hi<n && data[hi]<data[hi-1])++hi;
                std::reverse(data+lo,data+hi);
                if constexpr(Profile)stats->reversed_elements+=hi-lo;
            }else{
                while(hi<n && data[hi-1]<=data[hi])++hi;
            }
        }
        if(!Natural || hi-lo<leaf){
            hi=lo+std::min(leaf,n-lo);
            x86simdsortStatic::qsort(data+lo,hi-lo);
            if constexpr(Profile)stats->simd_elements+=hi-lo;
        }
        runs.push_back({lo,hi});lo=hi;
    }
    if constexpr(Profile)stats->runs=runs.size();
    if(runs.size()==1)return;
    std::unique_ptr<uint32_t[]> scratch(new uint32_t[n]);
    uint32_t* src=data;uint32_t* dst=scratch.get();
    while(runs.size()>1){
        size_t out=0;
        for(size_t i=0;i<runs.size();i+=2){
            size_t lo=runs[i].lo,mid=runs[i].hi;
            size_t hi=i+1<runs.size()?runs[i+1].hi:mid;
            if(mid==hi || src[mid-1]<=src[mid]){
                std::copy(src+lo,src+hi,dst+lo);
                if constexpr(Profile)stats->copied_elements+=hi-lo;
            }else{
                std::merge(src+lo,src+mid,src+mid,src+hi,dst+lo);
                if constexpr(Profile)stats->merged_elements+=hi-lo;
            }
            runs[out++]={lo,hi};
        }
        runs.resize(out);std::swap(src,dst);
        if constexpr(Profile)++stats->levels;
    }
    if(src!=data){
        std::copy_n(src,n,data);
        if constexpr(Profile)stats->final_elements+=n;
    }
}
}
