#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

typedef ap_axiu<32, 0, 0, 0> done_pkt_t;
typedef ap_axiu<512, 0, 0, 0> edge_burst_pkt_t;

static constexpr unsigned kSegmentSize = 16;
static constexpr unsigned kPmaEmptyMask = 0x80000000u;
static constexpr unsigned kDstLocalMask = 0x7ffffu;
static constexpr unsigned kUnitWeight = 1u;
static constexpr unsigned kWeightShift = 19;

static ap_uint<32> pack_regraph_dst(ap_uint<32> dst, bool dummy)
{
#pragma HLS INLINE
    ap_uint<32> packed = (dst & kDstLocalMask) | (kUnitWeight << kWeightShift);
    if (dummy) {
        packed |= kPmaEmptyMask;
    }
    return packed;
}

static ap_uint<512> read_pma_segment(const ap_uint<512> *pma0,
                                     const ap_uint<512> *pma1,
                                     const ap_uint<512> *pma2,
                                     const ap_uint<512> *pma3,
                                     ap_uint<64> segment_idx,
                                     unsigned max_cache_segment)
{
#pragma HLS INLINE
    const ap_uint<64> local_idx = segment_idx >> 1;
    const ap_uint<64> cache_segment_limit =
        static_cast<ap_uint<64>>(max_cache_segment) * 2;

    if (segment_idx < cache_segment_limit) {
        return (segment_idx & 0x1) ? pma2[local_idx] : pma0[local_idx];
    }
    return (segment_idx & 0x1) ? pma3[local_idx] : pma1[local_idx];
}

static void write_edge_burst(edge_burst_pkt_t &pkt,
                             unsigned lane,
                             ap_uint<32> src,
                             ap_uint<32> dst)
{
#pragma HLS INLINE
    const unsigned base = lane * 64;
    pkt.data.range(base + 31, base) = src;
    pkt.data.range(base + 63, base + 32) = dst;
}

extern "C" {
void pma_to_regraph_adapter(const ap_uint<512> *pma0,
                            const ap_uint<512> *pma1,
                            const ap_uint<512> *pma2,
                            const ap_uint<512> *pma3,
                            const ap_uint<64> *row_offset,
                            unsigned node_count,
                            unsigned pma_slot_count,
                            unsigned max_cache_segment,
                            hls::stream<done_pkt_t> &done0,
                            hls::stream<done_pkt_t> &done1,
                            hls::stream<done_pkt_t> &done2,
                            hls::stream<done_pkt_t> &done3,
                            hls::stream<edge_burst_pkt_t> &edge_burst_out)
{
#pragma HLS INTERFACE m_axi port=pma0 offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=pma1 offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=pma2 offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=pma3 offset=slave bundle=gmem3
#pragma HLS INTERFACE m_axi port=row_offset offset=slave bundle=gmem4
#pragma HLS INTERFACE s_axilite port=pma0 bundle=control
#pragma HLS INTERFACE s_axilite port=pma1 bundle=control
#pragma HLS INTERFACE s_axilite port=pma2 bundle=control
#pragma HLS INTERFACE s_axilite port=pma3 bundle=control
#pragma HLS INTERFACE s_axilite port=row_offset bundle=control
#pragma HLS INTERFACE s_axilite port=node_count bundle=control
#pragma HLS INTERFACE s_axilite port=pma_slot_count bundle=control
#pragma HLS INTERFACE s_axilite port=max_cache_segment bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS INTERFACE axis port=done0
#pragma HLS INTERFACE axis port=done1
#pragma HLS INTERFACE axis port=done2
#pragma HLS INTERFACE axis port=done3
#pragma HLS INTERFACE axis port=edge_burst_out

    (void)done0.read();
    (void)done1.read();
    (void)done2.read();
    (void)done3.read();

    edge_burst_pkt_t out;
    out.data = 0;
    out.keep = -1;
    out.strb = -1;
    out.last = 0;

    ap_uint<64> total_slots = row_offset[node_count];
    if (total_slots > pma_slot_count) {
        total_slots = pma_slot_count;
    }

    ap_uint<64> emitted_slots = 0;

source_loop:
    for (unsigned src = 0; src < node_count; ++src) {
        const ap_uint<64> begin = row_offset[src];
        ap_uint<64> end = row_offset[src + 1];
        if (end > pma_slot_count) {
            end = pma_slot_count;
        }

slot_loop:
        const ap_uint<64> begin_segment = begin >> 4;
        const ap_uint<64> end_segment = (end + (kSegmentSize - 1)) >> 4;

segment_loop:
        for (ap_uint<64> segment = begin_segment; segment < end_segment; ++segment) {
#pragma HLS PIPELINE II=1
            const ap_uint<512> pma_segment =
                read_pma_segment(pma0, pma1, pma2, pma3, segment, max_cache_segment);

        half_segment_loop:
            for (unsigned half = 0; half < 2; ++half) {
                out.data = 0;
                out.keep = -1;
                out.strb = -1;
                out.last = 0;

            lane_loop:
                for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
                    const ap_uint<64> slot = (segment << 4) + (half << 3) + lane;
                    const unsigned pma_lane = half * 8 + lane;
                    ap_uint<32> raw_dst = pma_segment.range(pma_lane * 32 + 31,
                                                            pma_lane * 32);
                    bool dummy = raw_dst[31] || slot < begin || slot >= end || slot >= total_slots;
                    const ap_uint<32> out_src = dummy ? (ap_uint<32>(src) | kPmaEmptyMask)
                                                      : ap_uint<32>(src);
                    const ap_uint<32> out_dst = pack_regraph_dst(raw_dst, dummy);
                    write_edge_burst(out, lane, out_src, out_dst);
                }

                emitted_slots += 8;
                out.last = (emitted_slots >= total_slots);
                edge_burst_out.write(out);
            }
        }
    }
}
}
