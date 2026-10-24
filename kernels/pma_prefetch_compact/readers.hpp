#pragma once
#include "types.hpp"

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
        memory.read_request((vertices - 1) / 8, 1);
        Word last = memory.read();
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
#pragma HLS ARRAY_PARTITION variable=tile.rows cyclic factor=8
        unsigned rows = vertices - base;
        if (rows > 1024) rows = 1024;
        unsigned lines = (rows + 7) / 8;
        // Eight 16-beat parents fill one finite directory tile.
        for (unsigned first = 0; first < lines; first += kBurst) {
#pragma HLS PIPELINE II=1
            unsigned length = lines - first;
            if (length > kBurst) length = kBurst;
            memory.read_request(base / 8 + first, length);
        }
        for (unsigned line = 0; line < lines; ++line) {
#pragma HLS PIPELINE II=1
            Word value = memory.read();
            for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
                tile.rows[line * 8 + lane] = value.range(lane * 64 + 63, lane * 64);
            }
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

static void read_bank(hls::burst_maxi<Word> &cache,
                      hls::burst_maxi<Word> &external, unsigned cache_lines,
                      hls::stream<unsigned> &extent,
                      hls::stream<Word> &output, hls::stream<bool> &released) {
#pragma HLS INLINE OFF
    unsigned total = extent.read();
    unsigned issued = 0, received = 0, retired = 0;
    unsigned parents = 0, head = 0, tail = 0, in_parent = 0;
    unsigned lengths[kParents];
    bool external_parent[kParents];
#pragma HLS ARRAY_PARTITION variable=lengths complete
#pragma HLS ARRAY_PARTITION variable=external_parent complete
    bool draining = false;
    while (retired < total) {
#pragma HLS PIPELINE II=1
        bool credit;
        if (released.read_nb(credit)) ++retired;
        unsigned length = total - issued;
        if (length > kBurst) length = kBurst;
        if (issued < cache_lines && issued + length > cache_lines)
            length = cache_lines - issued;
        if (length && parents < kParents &&
            issued - retired + length <= kRingLines) {
            bool ext = issued >= cache_lines;
            if (ext) external.read_request(issued, length);
            else cache.read_request(issued, length);
            lengths[tail] = length;
            external_parent[tail] = ext;
            tail = (tail + 1) % kParents;
            ++parents;
            issued += length;
        }
        // Fill the parent window before the first blocking response read.
        draining = draining || parents == kParents || issued == total;
        if (draining && parents && !output.full()) {
            Word value = external_parent[head] ? external.read() : cache.read();
            output.write(value);
            ++received;
            if (++in_parent == lengths[head]) {
                in_parent = 0;
                head = (head + 1) % kParents;
                --parents;
            }
        }
    }
    (void)received;
}
}
