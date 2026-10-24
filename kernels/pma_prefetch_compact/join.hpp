#pragma once
#include "types.hpp"

namespace pma_compact {
static Segment register_segment(Segment value) {
#pragma HLS INLINE OFF
#pragma HLS PIPELINE II=1
#pragma HLS LATENCY min=2 max=2
    return value;
}

static void join_segments(unsigned vertices,
                           hls::stream<unsigned> &extent,
                           hls::stream_of_blocks<DirectoryTile, 2> &tiles,
                           hls::stream<bool> &ready,
                           hls::stream<bool> &released,
                           hls::stream<Word> &even, hls::stream<Word> &odd,
                           hls::stream<bool> &even_release,
                           hls::stream<bool> &odd_release,
                           hls::stream<Segment> &output) {
#pragma HLS INLINE OFF
    unsigned total = extent.read();
    if (!total) {
        Segment terminal{~Word(0), 0, true};
        output.write(terminal);
        return;
    }
    unsigned consumed = 0;
    for (unsigned base = 0; base < vertices; base += 1024) {
        ready.read();
        {
        hls::read_lock<DirectoryTile> lock(tiles);
        DirectoryTile &tile = lock;
#pragma HLS ARRAY_PARTITION variable=tile cyclic factor=8
        unsigned row = 0;
        while (row < 1024 && base + row < vertices) {
#pragma HLS PIPELINE II=1
            // Skip at most eight *consecutive* empty rows per selection.
            unsigned skipped = 0;
            bool stop = false;
            for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
                unsigned index = row + lane;
                if (index >= 1024 || base + index >= vertices) stop = true;
                if (!stop) {
                    ap_uint<64> bounds = tile[index];
                    if (bounds.range(63, 32) == bounds.range(31, 0)) ++skipped;
                    else stop = true;
                }
            }
            if (skipped) { row += skipped; continue; }
            ap_uint<64> bounds = tile[row];
            unsigned begin = (unsigned)bounds.range(63, 32) / 16;
            unsigned end = (unsigned)bounds.range(31, 0) / 16;
            for (unsigned segment = begin; segment < end; ++segment) {
#pragma HLS PIPELINE II=1
                Segment value;
                bool parity = segment & 1;
                value.data = parity ? odd.read() : even.read();
                value.source = base + row;
                value.last = ++consumed == total;
                output.write(register_segment(value));
                if (parity) odd_release.write(true);
                else even_release.write(true);
            }
            ++row;
        }
        }
        released.write(true);
    }
}
}
