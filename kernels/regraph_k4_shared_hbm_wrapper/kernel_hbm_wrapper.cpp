#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

#include "acc_config.h"
#include "acc_data_types.h"
#include "hbm_wrapper.h"
#include "l1_api.h"

template <int Bank>
void sharedLittleKernelReadMemory(
    ap_uint<512> *src_prop_a,
    ap_uint<512> *src_prop_b,
    unsigned num_partitions_a,
    unsigned num_partitions_b,
    hls::stream<l_ppb_request_pkt> &request_a,
    hls::stream<l_ppb_request_pkt> &request_b,
    hls::stream<l_ppb_response_pkt> &response_a,
    hls::stream<l_ppb_response_pkt> &response_b)
{
    unsigned completed_a = 0;
    unsigned completed_b = 0;
    bool prefer_b = false;

service_requests:
    while (completed_a < num_partitions_a ||
           completed_b < num_partitions_b) {
        const bool ready_a = completed_a < num_partitions_a &&
                             !request_a.empty();
        const bool ready_b = completed_b < num_partitions_b &&
                             !request_b.empty();
        if (!ready_a && !ready_b) {
            continue;
        }

        const bool use_b = ready_b && (!ready_a || prefer_b);
        l_ppb_request_pkt request;
        if (use_b) {
            request = request_b.read();
        } else {
            request = request_a.read();
        }
        prefer_b = !use_b;

        if (request.last) {
            l_ppb_response_pkt response;
            response.data = 0;
            response.dest = 0;
            response.keep = -1;
            response.strb = -1;
            response.last = 1;
            if (use_b) {
                response_b.write(response);
                ++completed_b;
            } else {
                response_a.write(response);
                ++completed_a;
            }
            continue;
        }

        const ap_uint<32> base_addr =
            request.data << LOG2_SRC_BUFFER_SIZE >> 4;
    emit_source_block:
        for (unsigned offset = 0; offset < (SRC_BUFFER_SIZE >> 4); ++offset) {
#pragma HLS PIPELINE II=1
            const ap_uint<32> address = base_addr + offset;
            l_ppb_response_pkt response;
            response.data = use_b ? src_prop_b[address] : src_prop_a[address];
            response.dest = address;
            response.keep = -1;
            response.strb = -1;
            response.last = 0;
            if (use_b) {
                response_b.write(response);
            } else {
                response_a.write(response);
            }
        }
    }
}

extern "C" {
void kernelHBMWrapper(
    ap_uint<512> *src_prop_1,
    ap_uint<512> *src_prop_2,
    ap_uint<512> *src_prop_3,
    ap_uint<512> *src_prop_4,
    ap_uint<512> *new_prop_1,
    ap_uint<512> *new_prop_2,
    unsigned num_partitions_1,
    unsigned num_partitions_2,
    unsigned num_partitions_3,
    unsigned num_partitions_4,
    hls::stream<l_ppb_request_pkt> &l_ppb_request_stm_1,
    hls::stream<l_ppb_request_pkt> &l_ppb_request_stm_2,
    hls::stream<l_ppb_request_pkt> &l_ppb_request_stm_3,
    hls::stream<l_ppb_request_pkt> &l_ppb_request_stm_4,
    hls::stream<l_ppb_response_pkt> &l_ppb_response_stm_1,
    hls::stream<l_ppb_response_pkt> &l_ppb_response_stm_2,
    hls::stream<l_ppb_response_pkt> &l_ppb_response_stm_3,
    hls::stream<l_ppb_response_pkt> &l_ppb_response_stm_4,
    hls::stream<write_burst_pkt> &prop_write_burst_stm)
{
#pragma HLS INTERFACE m_axi port=src_prop_1 offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=src_prop_2 offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=src_prop_3 offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=src_prop_4 offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=new_prop_1 offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=new_prop_2 offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=src_prop_1 bundle=control
#pragma HLS INTERFACE s_axilite port=src_prop_2 bundle=control
#pragma HLS INTERFACE s_axilite port=src_prop_3 bundle=control
#pragma HLS INTERFACE s_axilite port=src_prop_4 bundle=control
#pragma HLS INTERFACE s_axilite port=new_prop_1 bundle=control
#pragma HLS INTERFACE s_axilite port=new_prop_2 bundle=control
#pragma HLS INTERFACE s_axilite port=num_partitions_1 bundle=control
#pragma HLS INTERFACE s_axilite port=num_partitions_2 bundle=control
#pragma HLS INTERFACE s_axilite port=num_partitions_3 bundle=control
#pragma HLS INTERFACE s_axilite port=num_partitions_4 bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS DATAFLOW disable_start_propagation

    sharedLittleKernelReadMemory<0>(
        src_prop_1, src_prop_3, num_partitions_1, num_partitions_3,
        l_ppb_request_stm_1, l_ppb_request_stm_3,
        l_ppb_response_stm_1, l_ppb_response_stm_3);
    sharedLittleKernelReadMemory<1>(
        src_prop_2, src_prop_4, num_partitions_2, num_partitions_4,
        l_ppb_request_stm_2, l_ppb_request_stm_4,
        l_ppb_response_stm_2, l_ppb_response_stm_4);
    write_out(new_prop_1, new_prop_2, prop_write_burst_stm);
}
}
