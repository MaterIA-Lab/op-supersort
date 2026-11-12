#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <random>
#include <string>
#include <vector>
#include "vendor/pdqsort.h"
#include "vendor/ska_sort.hpp"
using U = uint32_t;
using V = std::vector<U>;

template<int B> void lsd(V& a) {
    constexpr unsigned K=1u<<B, P=(32+B-1)/B;
    std::array<std::array<size_t,K>,P> h{};
    V tmp(a.size());
    for(U x:a) for(unsigned p=0;p<P;++p) ++h[p][(x>>(p*B))&(K-1)];
    U* src=a.data(); U* dst=tmp.data();
    for(unsigned p=0;p<P;++p){
        size_t sum=0; for(auto& c:h[p]) {auto old=c;c=sum;sum+=old;}
        for(size_t i=0;i<a.size();++i) {U x=src[i];dst[h[p][(x>>(p*B))&(K-1)]++]=x;}
        std::swap(src,dst);
    }
    if(src!=a.data()) std::copy(src,src+a.size(),a.data());
}

// One global MSD distribution, followed by two local LSD distributions.
template<int H> void local_radix(V& a){
    constexpr unsigned K=1u<<H, L=(32-H+1)/2, M=1u<<L;
    std::array<size_t,K+1> off{};
    for(U x:a) ++off[(x>>(32-H))+1];
    std::partial_sum(off.begin(),off.end(),off.begin());
    auto pos=off; V tmp(a.size());
    for(U x:a) tmp[pos[x>>(32-H)]++]=x;
    for(unsigned b=0;b<K;++b){
        size_t lo=off[b],hi=off[b+1];
        if(hi-lo<64){std::sort(tmp.begin()+lo,tmp.begin()+hi);std::copy(tmp.begin()+lo,tmp.begin()+hi,a.begin()+lo);continue;}
        std::array<size_t,M> h0{},h1{};
        for(size_t i=lo;i<hi;++i){U x=tmp[i];++h0[x&(M-1)];++h1[(x>>L)&(M-1)];}
        size_t s0=lo,s1=lo; for(unsigned j=0;j<M;++j){auto c0=h0[j],c1=h1[j];h0[j]=s0;h1[j]=s1;s0+=c0;s1+=c1;}
        for(size_t i=lo;i<hi;++i){U x=tmp[i];a[h0[x&(M-1)]++]=x;}
        for(size_t i=lo;i<hi;++i){U x=a[i];tmp[h1[(x>>L)&(M-1)]++]=x;}
        std::copy(tmp.begin()+lo,tmp.begin()+hi,a.begin()+lo);
    }
}

void sort_with(const std::string& name,V& a){
    if(name=="std") std::sort(a.begin(),a.end());
    else if(name=="pdq") pdqsort_branchless(a.begin(),a.end());
    else if(name=="ska") ska_sort(a.begin(),a.end());
    else if(name=="lsd8") lsd<8>(a);
    else if(name=="lsd11") lsd<11>(a);
    else if(name=="local8") local_radix<8>(a);
    else if(name=="local10") local_radix<10>(a);
    else if(name=="local12") local_radix<12>(a);
    else throw std::runtime_error("unknown algorithm");
}
V generate(size_t n,const std::string& dist,uint64_t seed){
    std::mt19937_64 rng(seed); V a(n);
    for(size_t i=0;i<n;++i){
        U x=U(rng());
        if(dist=="uniform") a[i]=x;
        else if(dist=="dense16") a[i]=x&65535;
        else if(dist=="few") a[i]=(x&15)*2654435761u;
        else if(dist=="equal") a[i]=0xffffffffu;
        else if(dist=="sorted" || dist=="reverse") a[i]=x;
        else if(dist=="skew") a[i]=(x%100<99)?U(rng()&65535):U(rng());
        else throw std::runtime_error("unknown distribution");
    }
    if(dist=="sorted" || dist=="reverse")std::sort(a.begin(),a.end());
    if(dist=="reverse")std::reverse(a.begin(),a.end());
    return a;
}
int main(int argc,char** argv){
    size_t n=argc>1?std::stoull(argv[1]):1000000;
    int repeats=argc>2?std::stoi(argv[2]):5;
    std::string dist=argc>3?argv[3]:"uniform";
    uint64_t seed=argc>4?std::stoull(argv[4]):42;
    V source=generate(n,dist,seed), expected=source;
    std::sort(expected.begin(),expected.end());
    std::vector<std::string> algos={"std","pdq","ska","lsd8","lsd11","local8","local10","local12"};
    std::mt19937 order(seed+1);
    std::cout<<"n,distribution,seed,repeat,algorithm,ms\n";
    for(int r=-1;r<repeats;++r){
        std::shuffle(algos.begin(),algos.end(),order);
        for(const auto& algo:algos){
            V a=source;
            auto start=std::chrono::steady_clock::now();sort_with(algo,a);
            auto end=std::chrono::steady_clock::now();
            if(a!=expected){std::cerr<<"WRONG "<<algo<<" n="<<n<<" dist="<<dist<<"\n";return 2;}
            if(r>=0)std::cout<<n<<','<<dist<<','<<seed<<','<<r<<','<<algo<<','<<std::chrono::duration<double,std::milli>(end-start).count()<<'\n';
        }
    }
}
