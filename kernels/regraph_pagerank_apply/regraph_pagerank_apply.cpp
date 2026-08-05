#include <ap_int.h>
#include <hls_stream.h>

#include <cstdint>

#include "regraph_pagerank_apply.hpp"

#ifndef GRASU_REGRAPH_PAGERANK_MODE
#error "GRASU_REGRAPH_PAGERANK_MODE must select Full or residual PageRank"
#endif

#if GRASU_REGRAPH_PAGERANK_MODE != 1 && GRASU_REGRAPH_PAGERANK_MODE != 2
#error "unsupported GRASU_REGRAPH_PAGERANK_MODE"
#endif

namespace {

constexpr unsigned kVerticesPerBurst = 16;
constexpr unsigned kReductionBanks = 8;

float float_abs(float value)
{
#pragma HLS INLINE
    return value < 0.0F ? -value : value;
}

std::uint32_t float_to_word(float value)
{
#pragma HLS INLINE
    union {
        float value;
        std::uint32_t word;
    } bits = {value};
    return bits.word;
}

float word_to_float(ap_uint<32> word)
{
#pragma HLS INLINE
    union {
        std::uint32_t word;
        float value;
    } bits = {word.to_uint()};
    return bits.value;
}

ap_uint<32> lane(const ap_uint<512> &beat, unsigned index)
{
#pragma HLS INLINE
    return beat.range(index * 32 + 31, index * 32);
}

void set_lane(ap_uint<512> &beat, unsigned index, ap_uint<32> value)
{
#pragma HLS INLINE
    beat.range(index * 32 + 31, index * 32) = value;
}

}  // namespace

extern "C" {
void regraph_pagerank_apply(
    ap_uint<512> *rank_state,
#if GRASU_REGRAPH_PAGERANK_MODE == 2
    ap_uint<512> *residual_state,
#endif
    const ap_uint<512> *out_degree,
    ap_uint<32> *round_stats,
    unsigned burst_count,
    unsigned vertices,
    float damping,
    float epsilon,
    float base,
    float dangling_share,
    hls::stream<regraph_write_burst_pkt_t> &merged_prop,
    hls::stream<regraph_write_burst_pkt_t> &source_prop_write)
{
#pragma HLS INTERFACE m_axi port=rank_state offset=slave bundle=gmem0
#if GRASU_REGRAPH_PAGERANK_MODE == 2
#pragma HLS INTERFACE m_axi port=residual_state offset=slave bundle=gmem1
#endif
#pragma HLS INTERFACE m_axi port=out_degree offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=round_stats offset=slave bundle=gmem2
#pragma HLS INTERFACE axis port=merged_prop
#pragma HLS INTERFACE axis port=source_prop_write
#pragma HLS INTERFACE s_axilite port=rank_state bundle=control
#if GRASU_REGRAPH_PAGERANK_MODE == 2
#pragma HLS INTERFACE s_axilite port=residual_state bundle=control
#endif
#pragma HLS INTERFACE s_axilite port=out_degree bundle=control
#pragma HLS INTERFACE s_axilite port=round_stats bundle=control
#pragma HLS INTERFACE s_axilite port=burst_count bundle=control
#pragma HLS INTERFACE s_axilite port=vertices bundle=control
#pragma HLS INTERFACE s_axilite port=damping bundle=control
#pragma HLS INTERFACE s_axilite port=epsilon bundle=control
#pragma HLS INTERFACE s_axilite port=base bundle=control
#pragma HLS INTERFACE s_axilite port=dangling_share bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    float error_partials[kVerticesPerBurst][kReductionBanks];
    float dangling_partials[kVerticesPerBurst][kReductionBanks];
    unsigned active_partials[kVerticesPerBurst][kReductionBanks];
#pragma HLS ARRAY_PARTITION variable=error_partials complete dim=0
#pragma HLS ARRAY_PARTITION variable=dangling_partials complete dim=0
#pragma HLS ARRAY_PARTITION variable=active_partials complete dim=0

initialize_partials:
    for (unsigned lane_index = 0; lane_index < kVerticesPerBurst;
         ++lane_index) {
#pragma HLS UNROLL
        for (unsigned bank = 0; bank < kReductionBanks; ++bank) {
#pragma HLS UNROLL
            error_partials[lane_index][bank] = 0.0F;
            dangling_partials[lane_index][bank] = 0.0F;
            active_partials[lane_index][bank] = 0;
        }
    }

    const unsigned capacity = burst_count * kVerticesPerBurst;
    const float threshold = epsilon;

apply_bursts:
    for (unsigned burst = 0; burst < burst_count; ++burst) {
#pragma HLS PIPELINE II=1
        const regraph_write_burst_pkt_t incoming_packet = merged_prop.read();
        ap_uint<512> rank_beat = rank_state[burst];
#if GRASU_REGRAPH_PAGERANK_MODE == 2
        ap_uint<512> residual_beat = residual_state[burst];
#endif
        const ap_uint<512> degree_beat = out_degree[burst];
        ap_uint<512> source_payload = 0;
        const unsigned reduction_bank = burst & (kReductionBanks - 1);

    apply_lanes:
        for (unsigned lane_index = 0; lane_index < kVerticesPerBurst;
             ++lane_index) {
#pragma HLS UNROLL
            const unsigned vertex = burst * kVerticesPerBurst + lane_index;
            if (vertex >= vertices) {
                set_lane(source_payload, lane_index, 0);
                continue;
            }

            const float incoming =
                word_to_float(lane(incoming_packet.data, lane_index));
            const float old_rank = word_to_float(lane(rank_beat, lane_index));
            const unsigned degree = lane(degree_beat, lane_index).to_uint();
            float next_rank = old_rank;
            float next_value = 0.0F;
            bool active = true;

#if GRASU_REGRAPH_PAGERANK_MODE == 1
            next_rank = base + dangling_share + incoming;
            next_value = next_rank;
            error_partials[lane_index][reduction_bank] +=
                float_abs(next_rank - old_rank);
#else
            const float old_residual =
                word_to_float(lane(residual_beat, lane_index));
            const bool old_active = float_abs(old_residual) > threshold;
            if (old_active) {
                next_rank += old_residual;
            }
            const float retained_residual = old_active ? 0.0F : old_residual;
            next_value = retained_residual + incoming + dangling_share;
            active = float_abs(next_value) > threshold;
            error_partials[lane_index][reduction_bank] +=
                float_abs(next_value);
            set_lane(residual_beat, lane_index, float_to_word(next_value));
#endif

            set_lane(rank_beat, lane_index, float_to_word(next_rank));
            const float payload = active && degree != 0
                                      ? damping * next_value / degree
                                      : 0.0F;
            set_lane(source_payload, lane_index, float_to_word(payload));
            if (active) {
                active_partials[lane_index][reduction_bank]++;
                if (degree == 0) {
                    dangling_partials[lane_index][reduction_bank] += next_value;
                }
            }
        }

        rank_state[burst] = rank_beat;
#if GRASU_REGRAPH_PAGERANK_MODE == 2
        residual_state[burst] = residual_beat;
#endif

        regraph_write_burst_pkt_t source_packet;
        source_packet.data = source_payload;
        source_packet.keep = -1;
        source_packet.strb = -1;
        source_packet.dest = burst;
        source_packet.last = 0;
        source_prop_write.write(source_packet);
    }

    float error_sum = 0.0F;
    float next_dangling = 0.0F;
    unsigned active_vertices = 0;
reduce_stats:
    for (unsigned lane_index = 0; lane_index < kVerticesPerBurst;
         ++lane_index) {
        for (unsigned bank = 0; bank < kReductionBanks; ++bank) {
#pragma HLS PIPELINE II=1
            error_sum += error_partials[lane_index][bank];
            next_dangling += dangling_partials[lane_index][bank];
            active_vertices += active_partials[lane_index][bank];
        }
    }

    regraph_write_burst_pkt_t end_packet;
    end_packet.data = 0;
    end_packet.keep = -1;
    end_packet.strb = -1;
    end_packet.dest = 0;
    end_packet.last = 1;
    source_prop_write.write(end_packet);

    round_stats[kReGraphPageRankStatus] =
        vertices <= capacity ? kReGraphPageRankOk
                             : kReGraphPageRankVertexCapacityExceeded;
    round_stats[kReGraphPageRankActiveVertices] = active_vertices;
    round_stats[kReGraphPageRankErrorBits] = float_to_word(error_sum);
    round_stats[kReGraphPageRankNextDanglingBits] =
        float_to_word(next_dangling);
    round_stats[kReGraphPageRankAppliedVertices] =
        vertices <= capacity ? vertices : capacity;
}
}
