#include <cstdint>
#include <cstddef>
#include <ips2ra.hpp>
#include <ips4o.hpp>

void ips2ra_sort_u32(uint32_t* data,size_t n){ips2ra::sort(data,data+n);}
void ips4o_sort_u32(uint32_t* data,size_t n){ips4o::sort(data,data+n);}
