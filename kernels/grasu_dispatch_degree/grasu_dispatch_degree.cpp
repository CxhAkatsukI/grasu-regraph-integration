#include "kernel_config.h"

#include "grasu_degree_delta.hpp"

extern "C" {
void dispatch_degree(
    const int size,
    hls::stream<pipe_type_96> &segment_head_stream_1,
    hls::stream<pipe_type_96> &segment_head_stream_2,
    hls::stream<pipe_type_96> &segment_head_stream_3,
    hls::stream<pipe_type_96> &segment_head_stream_4,
    hls::stream<pipe_type_96> &dispatch_to_process_cache_1,
    hls::stream<pipe_type_96> &dispatch_to_process_cache_2,
    hls::stream<pipe_type_96> &dispatch_to_process_ddr_1,
    hls::stream<pipe_type_96> &dispatch_to_process_ddr_2,
    hls::stream<grasu_degree_delta_pkt_t> &degree_delta)
{
#pragma HLS INTERFACE s_axilite port=size bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS INTERFACE axis port=segment_head_stream_1
#pragma HLS INTERFACE axis port=segment_head_stream_2
#pragma HLS INTERFACE axis port=segment_head_stream_3
#pragma HLS INTERFACE axis port=segment_head_stream_4
#pragma HLS INTERFACE axis port=dispatch_to_process_cache_1
#pragma HLS INTERFACE axis port=dispatch_to_process_cache_2
#pragma HLS INTERFACE axis port=dispatch_to_process_ddr_1
#pragma HLS INTERFACE axis port=dispatch_to_process_ddr_2
#pragma HLS INTERFACE axis port=degree_delta

dispatch_loop:
    for (int ordinal = 0; ordinal < size; ++ordinal) {
#pragma HLS PIPELINE II=1
        pipe_type_96 update;
        switch (ordinal & 3) {
        case 0:
            update = segment_head_stream_1.read();
            break;
        case 1:
            update = segment_head_stream_2.read();
            break;
        case 2:
            update = segment_head_stream_3.read();
            break;
        default:
            update = segment_head_stream_4.read();
            break;
        }

        const ap_uint<1> location = update.data[4];
        const ap_uint<32> segment = update.data.range(31, 5);
        const bool delete_op = update.data[95];
        const ap_uint<32> source = update.data.range(94, 64);
        degree_delta.write(make_degree_delta_packet(
            source, delete_op, static_cast<ap_uint<31>>(ordinal), false));

        if (segment < MAX_CACHE_SEGMENT) {
            if (location == 0) {
                dispatch_to_process_cache_1.write(update);
            } else {
                dispatch_to_process_cache_2.write(update);
            }
        } else if (location == 0) {
            dispatch_to_process_ddr_1.write(update);
        } else {
            dispatch_to_process_ddr_2.write(update);
        }
    }

    pipe_type_96 end_update;
    end_update.data = END_EDGE;
    end_update.keep = -1;
    end_update.strb = -1;
    end_update.last = 1;
    dispatch_to_process_cache_1.write(end_update);
    dispatch_to_process_cache_2.write(end_update);
    dispatch_to_process_ddr_1.write(end_update);
    dispatch_to_process_ddr_2.write(end_update);
    degree_delta.write(make_degree_delta_packet(0, false, 0, true));
}
}
