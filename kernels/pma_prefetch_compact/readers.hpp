#pragma once
#include "bank.hpp"

namespace pma_compact {

static void read_directory(hls::burst_maxi<Word> &memory, unsigned vertices,
                           unsigned max_slots,
                           hls::stream<unsigned> &even_extent,
                           hls::stream<unsigned> &odd_extent,
                           hls::stream<unsigned> &join_extent,
                           hls::stream_of_blocks<DirectoryTile, 2> &tiles,
                           hls::stream<bool> &ready,
                           hls::stream<bool> &released) {
#pragma HLS INLINE OFF
    unsigned slots = 0;
    if (vertices) {
        request(memory, (vertices - 1) / 8, 1);
        Word last = response(memory);
        ap_uint<64> row = last.range(((vertices - 1) % 8) * 64 + 63,
                                    ((vertices - 1) % 8) * 64);
        slots = (unsigned)row.range(31, 0);
    }
    // Invalid extents produce an empty frame, never an out-of-bounds read.
    if (slots > max_slots || (slots & 15)) slots = 0;
    unsigned segments = slots / 16;
    even_extent.write((segments + 1) / 2);
    odd_extent.write(segments / 2);
    join_extent.write(segments);
    if (!segments) return;
    for (unsigned base = 0; base < vertices; base += 1024) {
        if (base >= 2048) released.read();
        {
        hls::write_lock<DirectoryTile> lock(tiles);
        DirectoryTile &tile = lock;
        unsigned rows = vertices - base;
        if (rows > 1024) rows = 1024;
        unsigned lines = (rows + 7) / 8;
        // Eight 16-beat parents fill one finite directory tile.
        for (unsigned first = 0; first < lines; first += kBurst) {
#pragma HLS PIPELINE II=1
            unsigned length = lines - first;
            if (length > kBurst) length = kBurst;
            request(memory, base / 8 + first, length);
        }
        for (unsigned line = 0; line < lines; ++line) {
#pragma HLS PIPELINE II=1
            tile[line] = response(memory);
        }
        }
        // The explicit publication token also makes vendor C simulation safe:
        // its stream_of_blocks queue exposes storage before write_lock release.
        ready.write(true);
    }
    unsigned tile_count = (vertices + 1023) / 1024;
    for (unsigned i = 0; i < (tile_count < 2 ? tile_count : 2); ++i)
        released.read();
}

}
