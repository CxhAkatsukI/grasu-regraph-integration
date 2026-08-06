#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

#include "acc_config.h"
#include "acc_data_types.h"
#include "hbm_wrapper.h"
#include "l1_api.h"

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
#pragma HLS INTERFACE m_axi port=src_prop_3 offset=slave bundle=gmem3
#pragma HLS INTERFACE m_axi port=src_prop_4 offset=slave bundle=gmem4
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

    littleKernelReadMemory<0>(0, src_prop_1, num_partitions_1,
                              l_ppb_request_stm_1, l_ppb_response_stm_1);
    littleKernelReadMemory<1>(1, src_prop_2, num_partitions_2,
                              l_ppb_request_stm_2, l_ppb_response_stm_2);
    littleKernelReadMemory<2>(2, src_prop_3, num_partitions_3,
                              l_ppb_request_stm_3, l_ppb_response_stm_3);
    littleKernelReadMemory<3>(3, src_prop_4, num_partitions_4,
                              l_ppb_request_stm_4, l_ppb_response_stm_4);
    write_out(new_prop_1, new_prop_2, prop_write_burst_stm);
}
}
