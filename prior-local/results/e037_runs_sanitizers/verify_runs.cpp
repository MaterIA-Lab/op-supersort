#include <algorithm>
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>
#include "include/supersort/natural_merge_u32.hpp"
void power_sort_u32(uint32_t*,size_t);
int main(){
    std::mt19937_64 rng(20261105037ULL);size_t checked=0;
    for(size_t n:{0,1,2,15,16,17,23,24,25,63,64,65,127,128,129,255,256,257,511,512,513,1025,4097}){
        for(unsigned pattern=0;pattern<9;++pattern){
            std::vector<uint32_t> src(n);
            for(size_t i=0;i<n;++i){
                uint32_t x=uint32_t(rng());
                if(pattern==1)x&=15;
                if(pattern==2)x=0xffffffffu;
                if(pattern==3)x=(i&1)?0xffffffffu:0;
                if(pattern==4)x=uint32_t((i/17)%9);
                src[i]=x;
            }
            if(pattern==5 || pattern==6)std::sort(src.begin(),src.end());
            if(pattern==6)std::reverse(src.begin(),src.end());
            if(pattern==7)for(size_t lo=0;lo<n;lo+=129)std::sort(src.begin()+lo,src.begin()+std::min(n,lo+129));
            if(pattern==8)std::sort(src.begin(),src.begin()+n*3/4);
            auto expected=src;std::sort(expected.begin(),expected.end());
            for(size_t offset:{0,1,7,15})for(unsigned mode=0;mode<3;++mode){
                constexpr uint32_t guard=0xdeadbeefu;
                size_t margin=16+offset;
                std::vector<uint32_t> storage(n+margin+32,guard);
                auto data=storage.data()+margin;
                std::copy(src.begin(),src.end(),data);
                if(mode==0)supersort::natural_merge_u32<false>(data,n);
                if(mode==1)supersort::natural_merge_u32<true>(data,n);
                if(mode==2)power_sort_u32(data,n);
                if(!std::equal(expected.begin(),expected.end(),data))return 1;
                if(!std::all_of(storage.begin(),storage.begin()+margin,[=](uint32_t x){return x==guard;}))return 2;
                if(!std::all_of(storage.begin()+margin+n,storage.end(),[=](uint32_t x){return x==guard;}))return 3;
                ++checked;
            }
        }
    }
    std::cout<<"Verified "<<checked<<" exact cases with prefix/suffix guards.\n";
}
