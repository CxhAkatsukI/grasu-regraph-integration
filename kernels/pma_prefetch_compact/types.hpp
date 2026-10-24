#pragma once

#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_burst_maxi.h>
#include <hls_stream.h>
#include <hls_streamofblocks.h>

namespace pma_compact {
using Word = ap_uint<512>;
using Packet = ap_axiu<512, 0, 0, 0>;
struct DirectoryTile { ap_uint<64> rows[1024]; };
struct Segment { Word data; unsigned source; bool last; };
constexpr unsigned kRingLines = 512;
constexpr unsigned kParents = 16;
constexpr unsigned kBurst = 16;
constexpr unsigned kWindow = 4096;
}
