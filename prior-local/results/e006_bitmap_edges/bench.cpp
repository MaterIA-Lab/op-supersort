#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <string>
#include <vector>
#include "vendor/pdqsort.h"
#include "vendor/ska_sort.hpp"
#include "vendor/x86-simd-sort/src/x86simdsort-static-incl.h"
using U = uint32_t;
using V = std::vector<U>;

template<unsigned K, bool Buffered, class Digit>
void scatter(const U* src, U* dst, size_t n, std::array<size_t,K>& pos, Digit digit){
    if constexpr(!Buffered){
        for(size_t i=0;i<n;++i){U x=src[i];dst[pos[digit(x)]++]=x;}
    } else {
        alignas(64) std::array<std::array<U,16>,K> buffers;
        std::array<unsigned,K> used{};
        for(size_t i=0;i<n;++i){
            U x=src[i];unsigned d=digit(x),u=used[d];buffers[d][u++]=x;
            if(u==16){std::copy_n(buffers[d].data(),16,dst+pos[d]);pos[d]+=16;u=0;}
            used[d]=u;
        }
        for(unsigned d=0;d<K;++d)std::copy_n(buffers[d].data(),used[d],dst+pos[d]);
    }
}

template<int B, bool Buffered=false> void lsd(V& a) {
    constexpr unsigned K=1u<<B, P=(32+B-1)/B;
    std::array<std::array<size_t,K>,P> h{};
    V tmp(a.size());
    for(U x:a) for(unsigned p=0;p<P;++p) ++h[p][(x>>(p*B))&(K-1)];
    U* src=a.data(); U* dst=tmp.data();
    for(unsigned p=0;p<P;++p){
        size_t sum=0; for(auto& c:h[p]) {auto old=c;c=sum;sum+=old;}
        scatter<K,Buffered>(src,dst,a.size(),h[p],[p](U x){return (x>>(p*B))&(K-1);});
        std::swap(src,dst);
    }
    if(src!=a.data()) std::copy(src,src+a.size(),a.data());
}

// One global MSD distribution, followed by two local LSD distributions.
template<int H, bool Buffered=false, class Counter=size_t> void local_radix(V& a){
    constexpr unsigned K=1u<<H, L=(32-H+1)/2, M=1u<<L;
    std::array<size_t,K+1> off{};
    for(U x:a) ++off[(x>>(32-H))+1];
    std::partial_sum(off.begin(),off.end(),off.begin());
    std::array<size_t,K> pos; std::copy_n(off.begin(),K,pos.begin()); V tmp(a.size());
    scatter<K,Buffered>(a.data(),tmp.data(),a.size(),pos,[](U x){return x>>(32-H);});
    for(unsigned b=0;b<K;++b){
        size_t lo=off[b],hi=off[b+1];
        if(hi-lo<64 || hi-lo>std::numeric_limits<Counter>::max()){std::sort(tmp.begin()+lo,tmp.begin()+hi);std::copy(tmp.begin()+lo,tmp.begin()+hi,a.begin()+lo);continue;}
        std::array<Counter,M> h0{},h1{};
        for(size_t i=lo;i<hi;++i){U x=tmp[i];++h0[x&(M-1)];++h1[(x>>L)&(M-1)];}
        Counter s0=0,s1=0; for(unsigned j=0;j<M;++j){auto c0=h0[j],c1=h1[j];h0[j]=s0;h1[j]=s1;s0+=c0;s1+=c1;}
        for(size_t i=lo;i<hi;++i){U x=tmp[i];a[lo+h0[x&(M-1)]++]=x;}
        for(size_t i=lo;i<hi;++i){U x=a[i];tmp[lo+h1[(x>>L)&(M-1)]++]=x;}
        std::copy(tmp.begin()+lo,tmp.begin()+hi,a.begin()+lo);
    }
}

template<int H> void local_simd(V& a){
    constexpr unsigned K=1u<<H;
    std::array<size_t,K+1> off{};
    for(U x:a)++off[(x>>(32-H))+1];
    std::partial_sum(off.begin(),off.end(),off.begin());
    auto pos=off;V tmp(a.size());
    for(U x:a)tmp[pos[x>>(32-H)]++]=x;
    for(unsigned b=0;b<K;++b){
        size_t lo=off[b],hi=off[b+1];
        if(hi>lo)x86simdsortStatic::qsort(tmp.data()+lo,hi-lo);
    }
    std::copy(tmp.begin(),tmp.end(),a.begin());
}

// Sparse hierarchical bitmap per prefix. Duplicate copies are merged separately.
// Exact for every distribution; no assumption of uniqueness is made.
template<int H> void local_bitmap(V& a){
    constexpr unsigned K=1u<<H, R=32-H, W=1u<<(R-6), T=(W+63)/64;
    std::array<size_t,K+1> off{};
    for(U x:a)++off[(x>>R)+1];
    std::partial_sum(off.begin(),off.end(),off.begin());
    auto pos=off;V tmp(a.size());
    for(U x:a)tmp[pos[x>>R]++]=x;
    std::vector<uint64_t> bits(W),top(T);
    V duplicates;
    for(unsigned bucket=0;bucket<K;++bucket){
        size_t lo=off[bucket],hi=off[bucket+1];
        duplicates.clear();
        for(size_t i=lo;i<hi;++i){
            U x=tmp[i],low=x&((1u<<R)-1),word=low>>6;
            uint64_t mask=uint64_t(1)<<(low&63);
            if(bits[word]&mask)duplicates.push_back(x);
            else{bits[word]|=mask;top[word>>6]|=uint64_t(1)<<(word&63);}
        }
        std::sort(duplicates.begin(),duplicates.end());
        size_t output=lo,dup=0;
        for(unsigned t=0;t<T;++t){
            uint64_t occupied=top[t];top[t]=0;
            while(occupied){
                unsigned word=t*64+__builtin_ctzll(occupied);occupied&=occupied-1;
                uint64_t present=bits[word];bits[word]=0;
                while(present){
                    U x=(U(bucket)<<R)|(word*64+__builtin_ctzll(present));present&=present-1;
                    a[output++]=x;
                    while(dup<duplicates.size() && duplicates[dup]==x){a[output++]=x;++dup;}
                }
            }
        }
        if(output!=hi || dup!=duplicates.size())throw std::runtime_error("bitmap accounting error");
    }
}

void sort_with(const std::string& name,V& a){
    if(a.size()<2)return;
    if(name=="std") std::sort(a.begin(),a.end());
    else if(name=="pdq") pdqsort_branchless(a.begin(),a.end());
    else if(name=="ska") ska_sort(a.begin(),a.end());
    else if(name=="lsd8") lsd<8>(a);
    else if(name=="lsd11") lsd<11>(a);
    else if(name=="local8") local_radix<8>(a);
    else if(name=="local10") local_radix<10>(a);
    else if(name=="local12") local_radix<12>(a);
    else if(name=="lsd8buf") lsd<8,true>(a);
    else if(name=="lsd11buf") lsd<11,true>(a);
    else if(name=="local8buf") local_radix<8,true>(a);
    else if(name=="local10buf") local_radix<10,true>(a);
    else if(name=="simd") {if(!a.empty())x86simdsortStatic::qsort(a.data(),a.size());}
    else if(name=="local8simd") local_simd<8>(a);
    else if(name=="local10simd") local_simd<10>(a);
    else if(name=="local8c32") local_radix<8,false,U>(a);
    else if(name=="local10c32") local_radix<10,false,U>(a);
    else if(name=="local12c32") local_radix<12,false,U>(a);
    else if(name=="local10bitmap") local_bitmap<10>(a);
    else if(name=="local11bitmap") local_bitmap<11>(a);
    else if(name=="local12bitmap") local_bitmap<12>(a);
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
    std::vector<std::string> algos={"std","pdq","ska","lsd8","lsd11","local8","local10","local12","lsd8buf","lsd11buf","local8buf","local10buf","simd","local8simd","local10simd","local8c32","local10c32","local12c32","local10bitmap","local11bitmap","local12bitmap"};
    if(argc>5){
        algos.clear();std::string requested=argv[5];size_t start=0;
        do{size_t end=requested.find(',',start);algos.push_back(requested.substr(start,end-start));if(end==std::string::npos)break;start=end+1;}while(true);
    }
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
