#pragma once
#include <cstdint>
#include <algorithm>

// Diagnostic ABI only. Never linked into E040 performance libraries.
struct E042Stats {
    uint64_t nodes=0, node_elements=0, max_depth=0;
    uint64_t leaves=0, leaf_elements=0, leaf_calls[6]{}, leaf_sizes[6]{};
    uint64_t partitions=0, partition_elements=0, sorted=0, sorted_elements=0;
    uint64_t only2=0, only2_elements=0, fallback=0, fallback_elements=0;
    uint64_t skipped_equal_elements=0, trace_hash=14695981039346656037ULL;
};

#ifdef E042_INSTRUMENT
static E042Stats e042_stats;
static uint64_t e042_depth=0;
static void e042_mix(uint64_t x) {
    e042_stats.trace_hash^=x;
    e042_stats.trace_hash*=1099511628211ULL;
}
struct E042Node {
    E042Node(uint64_t n, uint64_t remaining) {
        ++e042_stats.nodes; e042_stats.node_elements+=n;
        e042_stats.max_depth=std::max(e042_stats.max_depth,e042_depth);
        ++e042_depth; e042_mix(n); e042_mix(remaining);
    }
    ~E042Node() { --e042_depth; }
};
static void e042_leaf(uint64_t n) {
    ++e042_stats.leaves; e042_stats.leaf_elements+=n;
    unsigned b=0; for(uint64_t hi=8;n>hi && b<5;hi*=2)++b;
    ++e042_stats.leaf_calls[b]; e042_stats.leaf_sizes[b]+=n;
    e042_mix(1); e042_mix(n);
}
#endif
