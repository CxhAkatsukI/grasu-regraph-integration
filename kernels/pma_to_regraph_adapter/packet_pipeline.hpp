#ifndef GRASU_REGRAPH_PACKET_PIPELINE_HPP
#define GRASU_REGRAPH_PACKET_PIPELINE_HPP

// Keep the loaded segment across two iterations instead of restarting an
// inner pipelined loop for each segment. The finite input FIFO is unchanged.
static void publish_packet_pipeline(hls::stream<loaded_row_segment> &loaded,
                                    unsigned part_dst_offset,
                                    unsigned part_vertex_count,
                                    hls::stream<edge_burst_pkt_t> &output)
{
#pragma HLS INLINE off
    loaded_row_segment record = {};
    unsigned half = 0;
    ap_uint<64> emitted = 0;
publish_packet_loop:
    while (true) {
#pragma HLS PIPELINE II=1
        if (half == 0) {
            record = loaded.read();
            if (record.task.terminal) break;
        }
        edge_burst_pkt_t packet;
        packet.data = 0;
        packet.keep = -1;
        packet.strb = -1;
publish_packet_lane_loop:
        for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
            const ap_uint<64> slot = (record.task.segment << 4) + (half << 3) + lane;
            const unsigned pma_lane = half * 8 + lane;
            const ap_uint<32> raw = record.data.range(pma_lane * 32 + 31, pma_lane * 32);
            const ap_uint<32> local = raw & kDstLocalMask;
            const bool in_partition = local < part_vertex_count;
            ap_uint<32> destination = raw;
#if GRASU_REGRAPH_DESTINATION_ONLY
            destination = ap_uint<32>(part_dst_offset) + local;
#endif
            const bool dummy = raw[31] || slot < record.task.begin || slot >= record.task.end
                               || slot >= record.task.total_slots || !in_partition;
            const ap_uint<32> source = dummy ? ap_uint<32>(record.task.source) | kPmaEmptyMask
                                             : ap_uint<32>(record.task.source);
            write_edge_burst(packet, lane, source, pack_regraph_dst(destination, dummy));
        }
        emitted += 8;
        packet.last = emitted >= record.task.total_slots;
        output.write(packet);
        half ^= 1;
    }
}

#endif
