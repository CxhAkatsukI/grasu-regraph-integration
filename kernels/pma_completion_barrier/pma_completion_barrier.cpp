#include <hls_stream.h>
#include <ap_axi_sdata.h>
#include <ap_int.h>

typedef ap_axiu<32, 0, 0, 0> done_pkt_t;

extern "C" {
void pma_completion_barrier(hls::stream<done_pkt_t> &done0,
                            hls::stream<done_pkt_t> &done1,
                            hls::stream<done_pkt_t> &done2,
                            hls::stream<done_pkt_t> &done3,
                            hls::stream<done_pkt_t> &done_out)
{
#pragma HLS INTERFACE axis port=done0
#pragma HLS INTERFACE axis port=done1
#pragma HLS INTERFACE axis port=done2
#pragma HLS INTERFACE axis port=done3
#pragma HLS INTERFACE axis port=done_out
#pragma HLS INTERFACE s_axilite port=return bundle=control

    done_pkt_t out = done0.read();
    (void)done1.read();
    (void)done2.read();
    (void)done3.read();

    out.data = 1;
    out.keep = -1;
    out.strb = -1;
    out.last = 1;
    done_out.write(out);
}
}
