#pragma once
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>
#include <x86simdsort-static-incl.h>

namespace supersort {
struct tree_run {size_t lo,hi;};
struct tree_op {size_t lo,mid,hi;};
struct tree_stack {size_t lo;unsigned power;};
struct tree_stats {
    size_t runs=0,simd_elements=0,reversed_elements=0,operations=0;
    size_t tree_elements=0,executed_elements=0,copied_elements=0,skipped=0;
    uint64_t run_hash=1469598103934665603ULL;
};

// Dyadic midpoint definition of Powersort node power. n <= SIZE_MAX/2.
// Powersort policy: Munro/Wild; see pinned upstream MIT sources in vendor/powersort.
inline unsigned tree_node_power(size_t n,size_t lo,size_t mid,size_t hi){
    size_t left=lo+mid,right=mid+hi;unsigned power=1;
    while((left>=n)==(right>=n)){
        if(left>=n){left-=n;right-=n;}
        left*=2;right*=2;++power;
    }
    return power;
}

template<bool Profile=false>
void form_tree_runs(uint32_t* data,size_t n,std::vector<tree_run>& runs,tree_stats* stats){
    for(size_t lo=0;lo<n;){
        size_t hi=lo+1;
        if(hi<n && data[hi]<data[lo]){
            while(hi<n && data[hi]<data[hi-1])++hi;
            std::reverse(data+lo,data+hi);
            if constexpr(Profile)stats->reversed_elements+=hi-lo;
        }else while(hi<n && data[hi-1]<=data[hi])++hi;
        if(hi-lo<128){
            hi=lo+std::min(size_t(128),n-lo);
            x86simdsortStatic::qsort(data+lo,hi-lo);
            if constexpr(Profile)stats->simd_elements+=hi-lo;
        }
        runs.push_back({lo,hi});
        if constexpr(Profile){stats->run_hash=(stats->run_hash^lo)*1099511628211ULL;stats->run_hash=(stats->run_hash^hi)*1099511628211ULL;}
        lo=hi;
    }
    if constexpr(Profile)stats->runs=runs.size();
}

template<bool Weighted>
void build_tree_plan(std::vector<tree_run>& runs,size_t n,std::vector<tree_op>& plan,std::vector<tree_stack>& stack){
    if constexpr(!Weighted){
        while(runs.size()>1){
            size_t out=0;
            for(size_t i=0;i<runs.size();i+=2){
                auto a=runs[i];
                if(i+1<runs.size()){auto b=runs[i+1];plan.push_back({a.lo,a.hi,b.hi});a.hi=b.hi;}
                runs[out++]=a;
            }
            runs.resize(out);
        }
    }else{
        tree_run a=runs[0];
        for(size_t i=1;i<runs.size();++i){
            auto b=runs[i];unsigned p=tree_node_power(n,a.lo,b.lo,b.hi);
            while(!stack.empty() && stack.back().power>p){
                auto top=stack.back();stack.pop_back();
                plan.push_back({top.lo,a.lo,a.hi});a.lo=top.lo;
            }
            assert(stack.empty() || stack.back().power<p);
            stack.push_back({a.lo,p});a=b;
        }
        while(!stack.empty()){
            auto top=stack.back();stack.pop_back();
            plan.push_back({top.lo,a.lo,a.hi});a.lo=top.lo;
        }
    }
}

// A single compiled executor shared by both policies prevents kernel inlining
// from making the causal contrast depend on distinct merge implementations.
template<bool Profile=false,bool Cmov=false>
#if defined(__GNUC__)
__attribute__((noinline))
#endif
void execute_tree_plan(uint32_t* data,uint32_t* scratch,const std::vector<tree_op>& plan,tree_stats* stats){
    for(auto op:plan){
        if constexpr(Profile){++stats->operations;stats->tree_elements+=op.hi-op.lo;}
        if(data[op.mid-1]<=data[op.mid]){if constexpr(Profile)++stats->skipped;continue;}
        if constexpr(Cmov){
            size_t i=op.lo,j=op.mid,k=op.lo;
            while(i<op.mid && j<op.hi){
                uint32_t left=data[i],right=data[j];
                bool take_left=left<=right;
                scratch[k++]=take_left?left:right;
                i+=take_left;j+=!take_left;
            }
            auto tail=std::copy(data+i,data+op.mid,scratch+k);
            std::copy(data+j,data+op.hi,tail);
        }else std::merge(data+op.lo,data+op.mid,data+op.mid,data+op.hi,scratch+op.lo);
        std::copy(scratch+op.lo,scratch+op.hi,data+op.lo);
        if constexpr(Profile){stats->executed_elements+=op.hi-op.lo;stats->copied_elements+=op.hi-op.lo;}
    }
}

template<bool Weighted,bool Profile=false,bool Cmov=false>
void tree_merge_u32(uint32_t* data,size_t n,tree_stats* stats=nullptr){
    if(n<2)return;
    if(n>std::numeric_limits<size_t>::max()/2)throw std::length_error("node power domain");
    size_t capacity=n/128+(n%128!=0);
    std::vector<tree_run> runs;runs.reserve(capacity);
    std::vector<tree_op> plan;plan.reserve(capacity-1);
    std::vector<tree_stack> stack;stack.reserve(capacity);
    form_tree_runs<Profile>(data,n,runs,stats);
    if(runs.size()==1)return;
    build_tree_plan<Weighted>(runs,n,plan,stack);
    std::unique_ptr<uint32_t[]> scratch(new uint32_t[n]);
    execute_tree_plan<Profile,Cmov>(data,scratch.get(),plan,stats);
}
}
