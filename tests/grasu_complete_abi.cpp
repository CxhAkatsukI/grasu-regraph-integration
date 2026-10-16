#include <type_traits>
#include "../kernels/grasu_complete/search_binding/top.hpp"
#include "../kernels/grasu_complete/process_cache.cpp"

// Host type check only: the search dataflow body requires the finite harness
// or the actual HLS synthesis flow and is deliberately not compiled here.

using Metadata = const search_pipeline::Raw*;
using SearchAbi = void (*)(const unsigned long*, Metadata, Metadata, Metadata,
                          Metadata, Metadata, Metadata, Metadata, Metadata,
                          unsigned, hls::stream<search_pipeline::Packet>&);
static_assert(std::is_same<decltype(&bin_search), SearchAbi>::value,
              "search must preserve eleven arguments and compact metadata aliases");

#ifdef GRASU_ENABLE_COMPLETION_TOKEN
using CacheAbi = void (*)(ap_uint<512>*, hls::stream<pipe_type_96>&,
                         hls::stream<grasu_done_pkt_t>&);
#else
using CacheAbi = void (*)(ap_uint<512>*, hls::stream<pipe_type_96>&);
#endif
static_assert(std::is_same<decltype(&process_cache), CacheAbi>::value,
              "cache completion-token ABI must match the selected pipeline");
