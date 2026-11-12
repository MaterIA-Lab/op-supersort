#pragma once
#include <chrono>
#include <iostream>
#include <memory>

// Diagnostic copy of predict10shiftraw, with coarse phase timing.
// Its total benchmark time includes stderr output and MUST NOT be ranked.
void profile_predict(V& a){
    using Clock=std::chrono::steady_clock;
    constexpr size_t K=1024;size_t n=a.size(),mean=n/K+(n%K!=0);
    size_t capacity=((mean+size_t(4*std::sqrt(double(mean)))+31)&~size_t(15))+1;
    auto t0=Clock::now();
    std::unique_ptr<U[]> raw(new U[K*capacity]);U* tmp=raw.get();
    auto t1=Clock::now();
    std::array<size_t,K> count{};
    bool overflow=false;
    for(U x:a){unsigned b=x>>22;size_t p=count[b];if(p==capacity){overflow=true;break;}tmp[b*capacity+p]=x;count[b]=p+1;}
    auto t2=Clock::now();
    if(overflow)x86simdsortStatic::qsort(a.data(),n);
    else{
        size_t out=0;for(size_t b=0;b<K;++b){U* begin=tmp+b*capacity;size_t size=count[b];if(size)x86simdsortStatic::qsort(begin,size);std::copy_n(begin,size,a.data()+out);out+=size;}
    }
    auto t3=Clock::now();
    auto src_address=reinterpret_cast<uintptr_t>(a.data()),dst_address=reinterpret_cast<uintptr_t>(tmp);
    raw.reset();auto t4=Clock::now();
    auto us=[](auto x,auto y){return std::chrono::duration<double,std::micro>(y-x).count();};
    std::cerr<<n<<','<<src_address%4096<<','<<dst_address%4096<<','<<us(t0,t1)<<','<<us(t1,t2)<<','<<us(t2,t3)<<','<<us(t3,t4)<<','<<overflow<<'\n';
}
