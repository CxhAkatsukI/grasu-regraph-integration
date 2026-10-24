#include "readers.hpp"
#include "join.hpp"
#include "compactor.hpp"

#ifndef __SYNTHESIS__
#include <thread>
#endif

extern "C" void pma_to_regraph_adapter(
    hls::burst_maxi<pma_compact::Word> pma0,
    hls::burst_maxi<pma_compact::Word> pma1,
    hls::burst_maxi<pma_compact::Word> pma2,
    hls::burst_maxi<pma_compact::Word> pma3,
    hls::burst_maxi<pma_compact::Word> row_offset,
    unsigned node_num, unsigned slot_count, unsigned max_cache_segment,
    unsigned dst_base, unsigned dst_count,
    hls::stream<pma_compact::Packet> &edge_burst_out) {
#pragma HLS INTERFACE m_axi port=pma0 bundle=even channel=0 offset=slave num_read_outstanding=16 max_read_burst_length=16
#pragma HLS INTERFACE m_axi port=pma1 bundle=even channel=1 offset=slave num_read_outstanding=16 max_read_burst_length=16
#pragma HLS INTERFACE m_axi port=pma2 bundle=odd channel=0 offset=slave num_read_outstanding=16 max_read_burst_length=16
#pragma HLS INTERFACE m_axi port=pma3 bundle=odd channel=1 offset=slave num_read_outstanding=16 max_read_burst_length=16
#pragma HLS INTERFACE m_axi port=row_offset bundle=directory offset=slave num_read_outstanding=16 max_read_burst_length=16
#pragma HLS INTERFACE s_axilite port=pma0 bundle=control
#pragma HLS INTERFACE s_axilite port=pma1 bundle=control
#pragma HLS INTERFACE s_axilite port=pma2 bundle=control
#pragma HLS INTERFACE s_axilite port=pma3 bundle=control
#pragma HLS INTERFACE s_axilite port=row_offset bundle=control
#pragma HLS INTERFACE s_axilite port=node_num bundle=control
#pragma HLS INTERFACE s_axilite port=slot_count bundle=control
#pragma HLS INTERFACE s_axilite port=max_cache_segment bundle=control
#pragma HLS INTERFACE s_axilite port=dst_base bundle=control
#pragma HLS INTERFACE s_axilite port=dst_count bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS INTERFACE axis port=edge_burst_out
    using namespace pma_compact;
    (void)dst_base; // Shards already store partition-local destinations.
#pragma HLS DATAFLOW
    hls::stream<unsigned> even_extent, odd_extent, join_extent;
#pragma HLS STREAM variable=even_extent depth=1
#pragma HLS STREAM variable=odd_extent depth=1
#pragma HLS STREAM variable=join_extent depth=1
    hls::stream_of_blocks<DirectoryTile, 2> tiles;
    hls::stream<bool> tile_ready, tile_released;
#pragma HLS STREAM variable=tile_ready depth=2
#pragma HLS STREAM variable=tile_released depth=2
    hls::stream<Word> even, odd;
#pragma HLS STREAM variable=even depth=512
#pragma HLS STREAM variable=odd depth=512
    hls::stream<bool> even_release, odd_release;
#pragma HLS STREAM variable=even_release depth=512
#pragma HLS STREAM variable=odd_release depth=512
    hls::stream<Segment> segments;
#pragma HLS STREAM variable=segments depth=3
#ifdef __SYNTHESIS__
    read_directory(row_offset, node_num, slot_count, even_extent, odd_extent,
                   join_extent, tiles, tile_ready, tile_released);
    read_bank(pma0, pma1, max_cache_segment, even_extent, even, even_release);
    read_bank(pma2, pma3, max_cache_segment, odd_extent, odd, odd_release);
    join_segments(node_num, join_extent, tiles, tile_ready, tile_released, even, odd, even_release,
                  odd_release, segments);
    compact(dst_count, segments, edge_burst_out);
#else
    std::thread directory([&] { read_directory(row_offset, node_num, slot_count,
        even_extent, odd_extent, join_extent, tiles, tile_ready, tile_released); });
    std::thread bank0([&] { read_bank(pma0, pma1, max_cache_segment,
        even_extent, even, even_release); });
    std::thread bank1([&] { read_bank(pma2, pma3, max_cache_segment,
        odd_extent, odd, odd_release); });
    std::thread join([&] { join_segments(node_num, join_extent, tiles, tile_ready, tile_released, even,
        odd, even_release, odd_release, segments); });
    compact(dst_count, segments, edge_burst_out);
    directory.join(); bank0.join(); bank1.join(); join.join();
#endif
}
