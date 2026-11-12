#pragma once

#include "dictionary_u32.hpp"
#include "windows_e047_u32.hpp"

namespace supersort {

struct CombinedWork {
    bool used_dictionary;
    DictionaryWork dictionary;
    WindowWork window;
};

inline CombinedWork combined_u32(std::uint32_t* a, std::size_t n) {
    const auto proposal = window_detail::propose(a, n);
    if (!proposal.count) {
        return {true, dictionary_u32<4>(a, n), {WindowRoute::bypass, 0, 0}};
    }
    const auto work = window_detail::certify_blocks(a, n, proposal);
    window_detail::apply(a, n, proposal, work);
    return {false, {DictionaryRoute::bypass, 0, 0}, work};
}

}  // namespace supersort
