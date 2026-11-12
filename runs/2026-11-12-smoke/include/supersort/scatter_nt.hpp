#pragma once
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <immintrin.h>

namespace supersort {

// Experimental software write combining. Partial cache lines use regular
// stores; only complete 64-byte aligned lines use streaming CPU stores.
template<unsigned K,bool FinalizePositions=false,class Digit>
void scatter_nt(const uint32_t* src,uint32_t* dst,size_t n,
                std::array<size_t,K>& pos,Digit digit){
    alignas(64) std::array<std::array<uint32_t,16>,K> buffer;
    std::array<unsigned,K> fill,skip;
    for(unsigned b=0;b<K;++b){
        fill[b]=skip[b]=unsigned((reinterpret_cast<uintptr_t>(dst+pos[b])>>2)&15);
    }
    for(size_t i=0;i<n;++i){
        uint32_t x=src[i];unsigned b=digit(x),u=fill[b];buffer[b][u++]=x;
        if(u==16){
            unsigned first=skip[b];
            if(first){
                std::copy_n(buffer[b].data()+first,16-first,dst+pos[b]);
                pos[b]+=16-first;skip[b]=0;
            }else{
                _mm256_stream_si256(reinterpret_cast<__m256i*>(dst+pos[b]),
                    _mm256_load_si256(reinterpret_cast<const __m256i*>(buffer[b].data())));
                _mm256_stream_si256(reinterpret_cast<__m256i*>(dst+pos[b]+8),
                    _mm256_load_si256(reinterpret_cast<const __m256i*>(buffer[b].data()+8)));
                pos[b]+=16;
            }
            u=0;
        }
        fill[b]=u;
    }
    for(unsigned b=0;b<K;++b){
        unsigned first=skip[b];
        std::copy_n(buffer[b].data()+first,fill[b]-first,dst+pos[b]);
        if constexpr(FinalizePositions)pos[b]+=fill[b]-first;
    }
    _mm_sfence();
}

} // namespace supersort
