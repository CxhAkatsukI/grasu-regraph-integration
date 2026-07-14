#include <hls_stream.h>
#include <string.h>

#include "acc_data_types.h"
#include "l1_api.h"
#include "acc_config.h"
#include "acc_scatter.h"
#include "acc_gather.h"

typedef ap_axiu<512, 0, 0, 0> edge_burst_pkt_t;

static edge_burst_dt unpack_edge_burst(edge_burst_pkt_t pkt)
{
#pragma HLS INLINE
    edge_burst_dt burst;
    for (int lane = 0; lane < NUM_EDGE_PER_BURST; lane++) {
#pragma HLS UNROLL
        const int base = lane * 64;
        burst.edges[lane].src = pkt.data.range(base + 31, base);
        burst.edges[lane].dst = pkt.data.range(base + 63, base + 32);
    }
    return burst;
}

extern "C" {
void littleKernelScatterGatherStream(
        hls::stream<edge_burst_pkt_t> &edge_burst_in,
        uint             part_edge_num,
        uint             compressed_group_count,
        uint             part_dst_offset,
        bool             reset_tmp_prop,
        hls::stream<l_ppb_request_pkt>    &l_ppb_request_stm,
        hls::stream<l_ppb_response_pkt>   &l_ppb_response_stm,
        hls::stream<l_tmp_prop_pkt>       &l_tmp_prop_stm)
{
    const int stream_depth = 8;
    const int large_stream_depth = 8;

#ifdef SW_EMU
#pragma HLS DATAFLOW disable_start_propagation
#else
#pragma HLS DATAFLOW
#endif

#pragma HLS INTERFACE axis port=edge_burst_in
#pragma HLS INTERFACE s_axilite port=part_edge_num bundle=control
#pragma HLS INTERFACE s_axilite port=compressed_group_count bundle=control
#pragma HLS INTERFACE s_axilite port=part_dst_offset bundle=control
#pragma HLS INTERFACE s_axilite port=reset_tmp_prop bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    (void)compressed_group_count;

    hls::stream<edge_burst_dt> edge_burst_stm;
#pragma HLS stream variable=edge_burst_stm depth=large_stream_depth

    hls::stream<update_set_dt> update_set_stm;
#pragma HLS stream variable=update_set_stm depth=stream_depth

    hls::stream<ap_uint<64>> tmp_prop_stm[GATHER_PE_NUM];
#pragma HLS stream variable=tmp_prop_stm depth=stream_depth

#ifndef SW_EMU
    hls::stream<ppb_request_dt> ppb_request_stm;
#pragma HLS stream variable=ppb_request_stm depth=stream_depth

    hls::stream<ppb_response_dt> ppb_response_stm;
#pragma HLS stream variable=ppb_response_stm depth=stream_depth
#endif

read_stream_edges:
    for (uint i = 0; i < (part_edge_num >> LOG2_NUM_EDGE_PER_BURST); i++) {
#pragma HLS PIPELINE II=1
        edge_burst_pkt_t pkt = edge_burst_in.read();
        edge_burst_dt burst = unpack_edge_burst(pkt);

        for (int lane = 0; lane < NUM_EDGE_PER_BURST; lane++) {
#pragma HLS UNROLL
#if !HAVE_EDGE_PROP
            ap_uint<20> dst = burst.edges[lane].dst.range(30, 0) - part_dst_offset;
            dst.range(19, 19) = burst.edges[lane].dst.range(31, 31);
            burst.edges[lane].dst = dst;
#else
            (void)part_dst_offset;
#endif
        }
        write_to_stream(edge_burst_stm, burst);
    }

#ifdef SW_EMU
    accScatterDirectAxi(l_ppb_request_stm, l_ppb_response_stm,
                        edge_burst_stm, update_set_stm, part_edge_num);
#else
    stream2axistream(ppb_request_stm, l_ppb_request_stm);
    axistream2stream(l_ppb_response_stm, ppb_response_stm);
    accScatter(ppb_request_stm, ppb_response_stm,
               edge_burst_stm, update_set_stm, part_edge_num);
#endif

    accGather(part_edge_num, update_set_stm, tmp_prop_stm, reset_tmp_prop);
    mergeWriteResults(tmp_prop_stm, part_dst_offset, l_tmp_prop_stm);
}
}
