#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
#include "e042_stats.hpp"
using U=uint32_t; using V=std::vector<U>;
#include "e042_generator.inc"
extern "C" void e042_xss256(U*,size_t,E042Stats*);
extern "C" void e042_xss128(U*,size_t,E042Stats*);

int e042_case(int argc,char** argv) {
    if(argc!=4)return 1;
    const size_t n=std::stoull(argv[1]);
    const std::string d=argv[2]; const uint64_t seed=std::stoull(argv[3]);
    const V source=generate(n,d,seed); V expected=source;
    std::sort(expected.begin(),expected.end());
    uint64_t input_hash=14695981039346656037ULL;
    for(U x:source){input_hash^=x;input_hash*=1099511628211ULL;}
    std::cout<<"n,distribution,seed,threshold,offset,input_hash,data_address,nodes,node_elements,max_depth,leaves,leaf_elements,partitions,partition_elements,sorted,sorted_elements,only2,only2_elements,fallback,fallback_elements,skipped_equal_elements,trace_hash";
    for(int b=0;b<6;++b)std::cout<<",leaf_calls_"<<b<<",leaf_elements_"<<b;
    std::cout<<'\n';
    for(int threshold:{256,128})for(size_t offset:{0,1,7}) {
        constexpr U guard=0x6d3a0f91u;
        const size_t prefix=32+offset;
        V storage(prefix+n+32,guard); U* a=storage.data()+prefix;
        std::copy(source.begin(),source.end(),a);
        E042Stats s;
        (threshold==256?e042_xss256:e042_xss128)(a,n,&s);
        if(!std::equal(expected.begin(),expected.end(),a))throw std::runtime_error("WRONG");
        for(size_t i=0;i<prefix;++i)if(storage[i]!=guard)throw std::runtime_error("prefix guard");
        for(size_t i=prefix+n;i<storage.size();++i)if(storage[i]!=guard)throw std::runtime_error("suffix guard");
        if(s.nodes!=s.leaves+s.fallback+s.sorted+s.partitions || s.only2>s.partitions)
            throw std::runtime_error("node accounting");
        uint64_t calls=0,elements=0;
        for(int b=0;b<6;++b){calls+=s.leaf_calls[b];elements+=s.leaf_sizes[b];}
        if(calls!=s.leaves || elements!=s.leaf_elements)throw std::runtime_error("leaf accounting");
        if(n<=1 && s.nodes)throw std::runtime_error("trivial counter");
        if(n>1 && n<=size_t(threshold) && (s.nodes!=1 || s.leaves!=1 || s.leaf_elements!=n))
            throw std::runtime_error("network boundary counter");
        std::cout<<n<<','<<d<<','<<seed<<','<<threshold<<','<<offset<<','<<input_hash<<','<<reinterpret_cast<uintptr_t>(a)<<','
            <<s.nodes<<','<<s.node_elements<<','<<s.max_depth<<','<<s.leaves<<','<<s.leaf_elements<<','
            <<s.partitions<<','<<s.partition_elements<<','<<s.sorted<<','<<s.sorted_elements<<','
            <<s.only2<<','<<s.only2_elements<<','<<s.fallback<<','<<s.fallback_elements<<','
            <<s.skipped_equal_elements<<','<<s.trace_hash;
        for(int b=0;b<6;++b)std::cout<<','<<s.leaf_calls[b]<<','<<s.leaf_sizes[b];
        std::cout<<'\n';
    }
    return 0;
}

int main() {
    std::string n,d,seed;
    while(std::cin>>n>>d>>seed) {
        char program[]="e042";
        char* args[]={program,n.data(),d.data(),seed.data()};
        int result=e042_case(4,args);
        std::cout.flush();
        if(result)return result;
    }
    return std::cin.eof()?0:3;
}
