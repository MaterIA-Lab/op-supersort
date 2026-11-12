#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
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
#include "include/supersort/predictive_u32.hpp"
#include "include/supersort/scatter_nt.hpp"
using U = uint32_t;
using V = std::vector<U>;
#include "profile_predict.hpp"
void vq_sort_u32(U*,size_t);
#ifdef SUPERSORT_WITH_IPS
void ips2ra_sort_u32(U*,size_t);
void ips4o_sort_u32(U*,size_t);
#endif

#if defined(__GNUC__)
__attribute__((noinline))
#endif
void predictive_fixed(V& a){supersort::predictive_u32<10,4,2,true>(a.data(),a.size());}

// Conservative empirical dispatcher. All choices remain exact on adversarial inputs.
template<bool Fixed=false>
void adaptive_u32(V& a){
    const size_t n=a.size();
    if(n<65536 || n>131072){vq_sort_u32(a.data(),n);return;}
    std::array<unsigned short,1024> occupancy{};
    bool asc=true,desc=true;U previous=a[0];
    for(size_t i=0;i<256;++i){
        U x=a[i*(n-1)/255];
        if(++occupancy[x>>22]>8){vq_sort_u32(a.data(),n);return;}
        asc&=previous<=x;desc&=previous>=x;previous=x;
    }
    if(asc && std::is_sorted(a.begin(),a.end()))return;
    if(desc && std::is_sorted(a.begin(),a.end(),std::greater<U>())){std::reverse(a.begin(),a.end());return;}
    if constexpr(Fixed)predictive_fixed(a);
    else supersort::predictive_u32<10,4,2,true>(a.data(),n);
}

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

template<int B, bool Buffered=false, bool NT=false> void lsd(V& a) {
    constexpr unsigned K=1u<<B, P=(32+B-1)/B;
    std::array<std::array<size_t,K>,P> h{};
    V tmp(a.size());
    for(U x:a) for(unsigned p=0;p<P;++p) ++h[p][(x>>(p*B))&(K-1)];
    U* src=a.data(); U* dst=tmp.data();
    for(unsigned p=0;p<P;++p){
        size_t sum=0; for(auto& c:h[p]) {auto old=c;c=sum;sum+=old;}
        if constexpr(NT) supersort::scatter_nt<K>(src,dst,a.size(),h[p],[p](U x){return (x>>(p*B))&(K-1);});
        else scatter<K,Buffered>(src,dst,a.size(),h[p],[p](U x){return (x>>(p*B))&(K-1);});
        std::swap(src,dst);
    }
    if(src!=a.data()) std::copy(src,src+a.size(),a.data());
}

// One global MSD distribution, followed by two local LSD distributions.
template<int H, bool Buffered=false, class Counter=size_t, bool NT=false, bool Scratch=false> void local_radix(V& a){
    constexpr unsigned K=1u<<H, L=(32-H+1)/2, M=1u<<L;
    std::array<size_t,K+1> off{};
    for(U x:a) ++off[(x>>(32-H))+1];
    std::partial_sum(off.begin(),off.end(),off.begin());
    std::array<size_t,K> pos; std::copy_n(off.begin(),K,pos.begin()); V tmp(a.size());
    if constexpr(NT) supersort::scatter_nt<K>(a.data(),tmp.data(),a.size(),pos,[](U x){return x>>(32-H);});
    else scatter<K,Buffered>(a.data(),tmp.data(),a.size(),pos,[](U x){return x>>(32-H);});
    V scratch;
    if constexpr(Scratch){
        size_t largest=0;for(unsigned b=0;b<K;++b)largest=std::max(largest,off[b+1]-off[b]);
        scratch.resize(largest);
    }
    for(unsigned b=0;b<K;++b){
        size_t lo=off[b],hi=off[b+1];
        if(hi-lo<64 || hi-lo>std::numeric_limits<Counter>::max()){std::sort(tmp.begin()+lo,tmp.begin()+hi);std::copy(tmp.begin()+lo,tmp.begin()+hi,a.begin()+lo);continue;}
        std::array<Counter,M> h0{},h1{};
        for(size_t i=lo;i<hi;++i){U x=tmp[i];++h0[x&(M-1)];++h1[(x>>L)&(M-1)];}
        Counter s0=0,s1=0; for(unsigned j=0;j<M;++j){auto c0=h0[j],c1=h1[j];h0[j]=s0;h1[j]=s1;s0+=c0;s1+=c1;}
        if constexpr(Scratch){
            for(size_t i=lo;i<hi;++i){U x=tmp[i];scratch[h0[x&(M-1)]++]=x;}
            for(size_t i=0;i<hi-lo;++i){U x=scratch[i];a[lo+h1[(x>>L)&(M-1)]++]=x;}
        }else{
            for(size_t i=lo;i<hi;++i){U x=tmp[i];a[lo+h0[x&(M-1)]++]=x;}
            for(size_t i=lo;i<hi;++i){U x=a[i];tmp[lo+h1[(x>>L)&(M-1)]++]=x;}
            std::copy(tmp.begin()+lo,tmp.begin()+hi,a.begin()+lo);
        }
    }
}

template<int H, bool Immediate=false> void local_simd(V& a){
    constexpr unsigned K=1u<<H;
    std::array<size_t,K+1> off{};
    for(U x:a)++off[(x>>(32-H))+1];
    std::partial_sum(off.begin(),off.end(),off.begin());
    auto pos=off;V tmp(a.size());
    for(U x:a)tmp[pos[x>>(32-H)]++]=x;
    for(unsigned b=0;b<K;++b){
        size_t lo=off[b],hi=off[b+1];
        if(hi>lo)x86simdsortStatic::qsort(tmp.data()+lo,hi-lo);
        if constexpr(Immediate) std::copy(tmp.begin()+lo,tmp.begin()+hi,a.begin()+lo);
    }
    if constexpr(!Immediate) std::copy(tmp.begin(),tmp.end(),a.begin());
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

template<int H, int Slack> void predictive(V& a){
    supersort::predictive_u32<H,Slack>(a.data(),a.size());
}

template<int H,int F,bool NT=false> void twolevel(V& a){
    constexpr unsigned K=1u<<H,J=1u<<F,Shift=32-H-F;
    std::array<size_t,K+1> off{};
    for(U x:a)++off[(x>>(32-H))+1];
    std::partial_sum(off.begin(),off.end(),off.begin());
    std::array<size_t,K> pos;std::copy_n(off.begin(),K,pos.begin());V tmp(a.size());
    if constexpr(NT) supersort::scatter_nt<K>(a.data(),tmp.data(),a.size(),pos,[](U x){return x>>(32-H);});
    else for(U x:a)tmp[pos[x>>(32-H)]++]=x;
    V scratch;
    for(unsigned bucket=0;bucket<K;++bucket){
        size_t lo=off[bucket],n=off[bucket+1]-lo;
        if(!n)continue;
        size_t mean=n/J+(n%J!=0);
        size_t capacity=(mean+size_t(4*std::sqrt(double(mean)))+31)&~size_t(15);
        scratch.resize(capacity*J);
        std::array<size_t,J> used{};
        bool overflow=false;
        for(size_t i=lo;i<lo+n;++i){
            U x=tmp[i];unsigned b=(x>>Shift)&(J-1);size_t p=used[b];
            if(p==capacity){overflow=true;break;}
            scratch[b*capacity+p]=x;used[b]=p+1;
        }
        if(overflow){x86simdsortStatic::qsort(tmp.data()+lo,n);std::copy_n(tmp.data()+lo,n,a.data()+lo);continue;}
        size_t out=lo;
        for(unsigned b=0;b<J;++b){
            U* begin=scratch.data()+b*capacity;size_t size=used[b];
            if(size)x86simdsortStatic::qsort(begin,size);
            std::copy_n(begin,size,a.data()+out);out+=size;
        }
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
    else if(name=="local6simd") local_simd<6>(a);
    else if(name=="local12simd") local_simd<12>(a);
    else if(name=="local14simd") local_simd<14>(a);
    else if(name=="local8simdhot") local_simd<8,true>(a);
    else if(name=="local10simdhot") local_simd<10,true>(a);
    else if(name=="local12simdhot") local_simd<12,true>(a);
    else if(name=="predict10s2") predictive<10,2>(a);
    else if(name=="predict10s4") predictive<10,4>(a);
    else if(name=="predict10s6") predictive<10,6>(a);
    else if(name=="predict12s4") predictive<12,4>(a);
    else if(name=="predict14s4") predictive<14,4>(a);
    else if(name=="predict16s4") predictive<16,4>(a);
    else if(name=="two6x8") twolevel<6,8>(a);
    else if(name=="two7x7") twolevel<7,7>(a);
    else if(name=="two8x9") twolevel<8,9>(a);
    else if(name=="two9x8") twolevel<9,8>(a);
    else if(name=="two9x9") twolevel<9,9>(a);
    else if(name=="two10x7") twolevel<10,7>(a);
    else if(name=="two10x8") twolevel<10,8>(a);
    else if(name=="vq") vq_sort_u32(a.data(),a.size());
    else if(name=="ska_copy") {V tmp(a.size());if(ska_sort_copy(a.begin(),a.end(),tmp.begin()))std::copy(tmp.begin(),tmp.end(),a.begin());}
    else if(name=="lsd8nt") lsd<8,false,true>(a);
    else if(name=="lsd11nt") lsd<11,false,true>(a);
    else if(name=="lsd16") lsd<16>(a);
    else if(name=="local8nt") local_radix<8,false,U,true>(a);
    else if(name=="local10nt") local_radix<10,false,U,true>(a);
    else if(name=="local12nt") local_radix<12,false,U,true>(a);
    else if(name=="two8x9nt") twolevel<8,9,true>(a);
    else if(name=="two9x8nt") twolevel<9,8,true>(a);
    else if(name=="local8ntscratch") local_radix<8,false,U,true,true>(a);
    else if(name=="local10ntscratch") local_radix<10,false,U,true,true>(a);
    else if(name=="local12ntscratch") local_radix<12,false,U,true,true>(a);
    else if(name=="predict10odd") supersort::predictive_u32<10,4,1>(a.data(),a.size());
    else if(name=="predict10shift") supersort::predictive_u32<10,4,2>(a.data(),a.size());
    else if(name=="predict10raw") supersort::predictive_u32<10,4,0,true>(a.data(),a.size());
    else if(name=="predict10oddraw") supersort::predictive_u32<10,4,1,true>(a.data(),a.size());
    else if(name=="predict10shiftraw") supersort::predictive_u32<10,4,2,true>(a.data(),a.size());
    else if(name=="adaptive") adaptive_u32<>(a);
    else if(name=="adaptive_fixed") adaptive_u32<true>(a);
    else if(name=="predict_fixed") predictive_fixed(a);
    else if(name=="predictk768") supersort::predictive_u32_k<768>(a.data(),a.size());
    else if(name=="predictk1280") supersort::predictive_u32_k<1280>(a.data(),a.size());
    else if(name=="predictk1536") supersort::predictive_u32_k<1536>(a.data(),a.size());
    else if(name=="predictk2048") supersort::predictive_u32_k<2048>(a.data(),a.size());
    else if(name=="predictk12288") supersort::predictive_u32_k<12288>(a.data(),a.size());
    else if(name=="predictk24576") supersort::predictive_u32_k<24576>(a.data(),a.size());
    else if(name=="predict13raw") supersort::predictive_u32<13,4,2,true>(a.data(),a.size());
    else if(name=="predict14raw") supersort::predictive_u32<14,4,2,true>(a.data(),a.size());
    else if(name=="profile") profile_predict(a);
#ifdef SUPERSORT_WITH_IPS
    else if(name=="ips2ra") ips2ra_sort_u32(a.data(),a.size());
    else if(name=="ips4o") ips4o_sort_u32(a.data(),a.size());
#endif
    else throw std::runtime_error("unknown algorithm");
}
V generate(size_t n,const std::string& dist,uint64_t seed){
    std::mt19937_64 rng(seed); V a(n);
    for(size_t i=0;i<n;++i){
        U x=U(rng());
        if(dist=="uniform" || dist=="sampletrap" || dist=="near_sorted") a[i]=x;
        else if(dist=="samplemiss" || dist=="prefixcluster")a[i]=0xa0000000u|(x&0x003fffffu);
        else if(dist=="splitmix"){
            uint64_t z=seed+0x9e3779b97f4a7c15ULL*(i+1);
            z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;
            z=(z^(z>>27))*0x94d049bb133111ebULL;
            a[i]=U(z^(z>>31));
        }
        else if(dist=="dense16") a[i]=x&65535;
        else if(dist=="few") a[i]=(x&15)*2654435761u;
        else if(dist=="equal") a[i]=0xffffffffu;
        else if(dist=="sorted" || dist=="reverse") a[i]=x;
        else if(dist=="skew") a[i]=(x%100<99)?U(rng()&65535):U(rng());
        else throw std::runtime_error("unknown distribution");
    }
    if(dist=="sorted" || dist=="reverse")std::sort(a.begin(),a.end());
    if(dist=="reverse")std::reverse(a.begin(),a.end());
    if(dist=="near_sorted"){
        std::sort(a.begin(),a.end());
        if(n)for(unsigned k=0;k<20;++k)std::swap(a[rng()%n],a[rng()%n]);
    }
    if((dist=="sampletrap" || dist=="samplemiss") && n){
        for(size_t i=0;i<256;++i)a[i*(n-1)/255]=dist=="sampletrap"?U(uint64_t(i)*0xffffffffu/255):U(rng());
    }
    return a;
}
int main(int argc,char** argv){
    size_t n=argc>1?std::stoull(argv[1]):1000000;
    int repeats=argc>2?std::stoi(argv[2]):5;
    std::string dist=argc>3?argv[3]:"uniform";
    uint64_t seed=argc>4?std::stoull(argv[4]):42;
    V source=generate(n,dist,seed), expected=source;
    std::sort(expected.begin(),expected.end());
    std::vector<std::string> algos={"std","pdq","ska_copy","simd","vq","lsd11","lsd11nt","predict_fixed","adaptive_fixed"};
#ifdef SUPERSORT_WITH_IPS
    algos.push_back("ips2ra");algos.push_back("ips4o");
#endif
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
