#include <hls_stream.h>
#include <ap_axi_sdata.h>
#include <ap_int.h>
#if defined(SW_EMU) && !defined(__SYNTHESIS__)
#include <stdio.h>
#define BARRIER_DEBUG_PRINTF(fmt, ...) do { printf(fmt, ##__VA_ARGS__); fflush(stdout); } while (0)
#else
#define BARRIER_DEBUG_PRINTF(fmt, ...)
#endif

typedef ap_axiu<32, 0, 0, 0> done_pkt_t;

extern "C" {
void pma_completion_barrier(hls::stream<done_pkt_t> &done0,
                            hls::stream<done_pkt_t> &done1,
                            hls::stream<done_pkt_t> &done2,
                            hls::stream<done_pkt_t> &done3)
{
#pragma HLS INTERFACE axis port=done0
#pragma HLS INTERFACE axis port=done1
#pragma HLS INTERFACE axis port=done2
#pragma HLS INTERFACE axis port=done3
#pragma HLS INTERFACE s_axilite port=return bundle=control

    BARRIER_DEBUG_PRINTF("[KDEBUG] pma_completion_barrier: waiting done0\n");
    (void)done0.read();
    BARRIER_DEBUG_PRINTF("[KDEBUG] pma_completion_barrier: got done0\n");
    BARRIER_DEBUG_PRINTF("[KDEBUG] pma_completion_barrier: waiting done1\n");
    (void)done1.read();
    BARRIER_DEBUG_PRINTF("[KDEBUG] pma_completion_barrier: got done1\n");
    BARRIER_DEBUG_PRINTF("[KDEBUG] pma_completion_barrier: waiting done2\n");
    (void)done2.read();
    BARRIER_DEBUG_PRINTF("[KDEBUG] pma_completion_barrier: got done2\n");
    BARRIER_DEBUG_PRINTF("[KDEBUG] pma_completion_barrier: waiting done3\n");
    (void)done3.read();
    BARRIER_DEBUG_PRINTF("[KDEBUG] pma_completion_barrier: got done3\n");
}
}
