#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

typedef ap_axiu<512, 0, 0, 0> edge_burst_pkt_t;

static edge_burst_pkt_t read_selected(
    unsigned selected,
    hls::stream<edge_burst_pkt_t> &input0,
    hls::stream<edge_burst_pkt_t> &input1,
    hls::stream<edge_burst_pkt_t> &input2,
    hls::stream<edge_burst_pkt_t> &input3)
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
void pma_frontend_mux(hls::stream<edge_burst_pkt_t> &input0,
                      hls::stream<edge_burst_pkt_t> &input1,
                      hls::stream<edge_burst_pkt_t> &input2,
                      hls::stream<edge_burst_pkt_t> &input3,
                      unsigned selected,
                      unsigned burst_count,
                      hls::stream<edge_burst_pkt_t> &output)
{
#pragma HLS INTERFACE axis port=input0
#pragma HLS INTERFACE axis port=input1
#pragma HLS INTERFACE axis port=input2
#pragma HLS INTERFACE axis port=input3
#pragma HLS INTERFACE axis port=output
#pragma HLS INTERFACE s_axilite port=selected bundle=control
#pragma HLS INTERFACE s_axilite port=burst_count bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    if (selected >= 4) {
        return;
    }
forward_loop:
    for (unsigned burst = 0; burst < burst_count; ++burst) {
#pragma HLS PIPELINE II=1
        edge_burst_pkt_t packet =
            read_selected(selected, input0, input1, input2, input3);
        packet.last = burst + 1 == burst_count;
        output.write(packet);
    }
}
}
