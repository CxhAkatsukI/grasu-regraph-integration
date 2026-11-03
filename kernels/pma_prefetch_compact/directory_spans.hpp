#pragma once
#include "types.hpp"

namespace pma_compact {
struct RowSpan { unsigned begin, end, source; };

static void describe_rows(unsigned vertices,
                          hls::stream_of_blocks<DirectoryTile, 2> &tiles,
                          hls::stream<bool> &ready,
                          hls::stream<bool> &released,
                          hls::stream<RowSpan> &output) {
#pragma HLS INLINE OFF
    for (unsigned base = 0; base < vertices; base += 1024) {
        ready.read();
        {
            hls::read_lock<DirectoryTile> lock(tiles);
            DirectoryTile &tile = lock;
            unsigned block = 0;
            ap_uint<8> pending = 0;
            ap_uint<64> bounds[8];
#pragma HLS ARRAY_PARTITION variable=bounds complete
            while (block < 128 || pending != 0) {
#pragma HLS PIPELINE II=1
                if (pending == 0) {
                    Word line = tile[block];
                    for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
                        ap_uint<64> value = line.range(lane * 64 + 63, lane * 64);
                        bounds[lane] = value;
                        pending[lane] = base + block * 8 + lane < vertices &&
                                        value.range(63, 32) != value.range(31, 0);
                    }
                    ++block;
                } else {
                    unsigned first = 0;
                    for (int lane = 7; lane >= 0; --lane) {
#pragma HLS UNROLL
                        if (pending[lane]) first = lane;
                    }
                    ap_uint<64> value = bounds[first];
                    output.write(RowSpan{(unsigned)value.range(63, 32) / 16,
                                         (unsigned)value.range(31, 0) / 16,
                                         base + (block - 1) * 8 + first});
                    pending[first] = 0;
                }
            }
        }
        released.write(true);
    }
}
}
