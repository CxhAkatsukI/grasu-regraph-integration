#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

typedef ap_axiu<64, 0, 0, 0> l_tmp_prop_pkt;

static l_tmp_prop_pkt read_selected(
    unsigned selected,
    hls::stream<l_tmp_prop_pkt> &input0,
    hls::stream<l_tmp_prop_pkt> &input1,
    hls::stream<l_tmp_prop_pkt> &input2,
    hls::stream<l_tmp_prop_pkt> &input3)
{
#pragma HLS INLINE
    switch (selected) {
    case 0:
        return input0.read();
    case 1:
        return input1.read();
    case 2:
        return input2.read();
    default:
        return input3.read();
    }
}

extern "C" {
void regraph_frontend_mux(hls::stream<l_tmp_prop_pkt> &input0,
                          hls::stream<l_tmp_prop_pkt> &input1,
                          hls::stream<l_tmp_prop_pkt> &input2,
                          hls::stream<l_tmp_prop_pkt> &input3,
                          unsigned selected,
                          unsigned packet_count,
                          hls::stream<l_tmp_prop_pkt> &output)
{
#pragma HLS INTERFACE axis port=input0
#pragma HLS INTERFACE axis port=input1
#pragma HLS INTERFACE axis port=input2
#pragma HLS INTERFACE axis port=input3
#pragma HLS INTERFACE axis port=output
#pragma HLS INTERFACE s_axilite port=selected bundle=control
#pragma HLS INTERFACE s_axilite port=packet_count bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    if (selected >= 4) {
        return;
    }
forward_loop:
    for (unsigned packet_index = 0; packet_index < packet_count;
         ++packet_index) {
#pragma HLS PIPELINE II=1
        l_tmp_prop_pkt packet =
            read_selected(selected, input0, input1, input2, input3);
        output.write(packet);
    }
}
}
