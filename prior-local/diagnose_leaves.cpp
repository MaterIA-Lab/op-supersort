#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>
#include <x86simdsort-static-incl.h>
using U=uint32_t;
int main(int argc,char** argv){
    if(argc>1){
        std::cout<<"n,distribution,seed,k,mean,maximum,gt64,gt128,gt256\n";
        for(size_t n:{68000,98000,114687,114689,129000,131073})
        for(uint64_t seed:{2027,7907})for(int dist=0;dist<2;++dist){
            std::mt19937_64 rng(seed);std::vector<U> a(n);
            for(size_t i=0;i<n;++i){
                U x=U(rng());
                if(dist){uint64_t z=seed+0x9e3779b97f4a7c15ULL*(i+1);
                    z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;
                    z=(z^(z>>27))*0x94d049bb133111ebULL;x=U(z^(z>>31));}
                a[i]=x;
            }
            for(size_t k:{1024,1280}){
                std::vector<size_t> counts(k);
                for(U x:a)++counts[(uint64_t(x)*k)>>32];
                std::cout<<n<<','<<(dist?"splitmix":"uniform")<<','<<seed<<','<<k<<','<<double(n)/k<<','
                    <<*std::max_element(counts.begin(),counts.end());
                for(size_t t:{64,128,256})std::cout<<','<<std::count_if(counts.begin(),counts.end(),[t](size_t c){return c>t;});
                std::cout<<'\n';
            }
        }
        return 0;
    }
    constexpr size_t batches=512;
    std::mt19937_64 rng(2027);std::mt19937 order(7907);
    std::vector<size_t> sizes={31,32,33,63,64,65,95,96,97,111,112,113,127,128,129,159,160,161,255,256,257};
    std::cout<<"n,repeat,batches,total_ns,ns_per_leaf\n";
    // Each length has a fixed, independent input corpus; all checks are outside timing.
    std::vector<std::vector<U>> src(258),expected(258),work(258);
    for(size_t n:sizes){
        src[n].resize(n*batches);for(U& x:src[n])x=U(rng());
        expected[n]=src[n];work[n].resize(n*batches);
        for(size_t b=0;b<batches;++b)std::sort(expected[n].begin()+b*n,expected[n].begin()+(b+1)*n);
    }
    for(int r=-1;r<15;++r){
        std::shuffle(sizes.begin(),sizes.end(),order);
        for(size_t n:sizes){
            std::copy(src[n].begin(),src[n].end(),work[n].begin());
            auto start=std::chrono::steady_clock::now();
            for(size_t b=0;b<batches;++b)x86simdsortStatic::qsort(work[n].data()+b*n,n);
            auto end=std::chrono::steady_clock::now();
            if(work[n]!=expected[n]){std::cerr<<"incorrect leaf "<<n<<'\n';return 1;}
            if(r>=0){auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(end-start).count();
                std::cout<<n<<','<<r<<','<<batches<<','<<ns<<','<<double(ns)/batches<<'\n';}
        }
    }
}
