#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>
#include "include/supersort/predictive_u32.hpp"
#include "include/supersort/scatter_nt.hpp"
using U=uint32_t;
using V=std::vector<U>;

int main(){
    std::mt19937 rng(20261105);
    size_t checked=0;
    for(size_t n: {size_t(0),size_t(1),size_t(2),size_t(15),size_t(16),size_t(17),size_t(63),size_t(64),size_t(65),size_t(257),size_t(4097),size_t(100000)}){
        for(unsigned pattern=0;pattern<5;++pattern){
            V src(n);
            for(U& x:src){x=rng();if(pattern==1)x&=15;if(pattern==2)x=0xffffffffu;if(pattern==3)x&=0x003fffffu;if(pattern==4)x=(x&1)?0:0xffffffffu;}
            for(size_t offset=0;offset<16;++offset){
                constexpr unsigned K=16;constexpr U guard=0xdeadbeefu;
                V storage(n+64,guard),expected;
                size_t margin=16+offset;
                std::array<size_t,K> pos{},counts{};
                for(U x:src)++counts[x>>28];
                size_t total=0;for(unsigned b=0;b<K;++b){pos[b]=total;total+=counts[b];for(U x:src)if(x>>28==b)expected.push_back(x);}
                supersort::scatter_nt<K>(src.data(),storage.data()+margin,n,pos,[](U x){return x>>28;});
                if(!std::equal(expected.begin(),expected.end(),storage.begin()+margin))return 2;
                if(!std::all_of(storage.begin(),storage.begin()+margin,[=](U x){return x==guard;}))return 3;
                if(!std::all_of(storage.begin()+margin+n,storage.end(),[=](U x){return x==guard;}))return 4;
                ++checked;
            }
            V expected=src;std::sort(expected.begin(),expected.end());
            for(unsigned mode=0;mode<5;++mode){
                V a=src;
                if(mode==0)supersort::predictive_u32<10,4,2,true>(a.data(),a.size());
                if(mode==1)supersort::predictive_u32_k<768>(a.data(),a.size());
                if(mode==2)supersort::predictive_u32_k<1536>(a.data(),a.size());
                if(mode==3)supersort::predictive_u32_k<12288>(a.data(),a.size());
                if(mode==4)supersort::predictive_u32_k<24576>(a.data(),a.size());
                if(a!=expected)return 5;
                ++checked;
            }
        }
    }
    std::cout<<"Verified "<<checked<<" cases, including scatter guards and offsets.\n";
}
