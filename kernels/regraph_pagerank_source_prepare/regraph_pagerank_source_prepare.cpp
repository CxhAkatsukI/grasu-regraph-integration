#include <ap_int.h>
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
void regraph_pagerank_source_prepare(
    const ap_uint<512> *rank_state,
#if GRASU_REGRAPH_PAGERANK_MODE == 2
    const ap_uint<512> *residual_state,
#endif
    const ap_uint<512> *out_degree,
    ap_uint<512> *source_prop_1,
    ap_uint<512> *source_prop_2,
    ap_uint<32> *round_stats,
    unsigned burst_count,
    unsigned vertices,
    float damping,
    float epsilon
#if GRASU_REGRAPH_PAGERANK_MODE == 2
    , bool correction_mode
#endif
    )
{
#pragma HLS INTERFACE m_axi port=rank_state offset=slave bundle=gmem0
#if GRASU_REGRAPH_PAGERANK_MODE == 2
#if defined(GRASU_REGRAPH_SHARDED_PMA)
#pragma HLS INTERFACE m_axi port=residual_state offset=slave bundle=gmem0
#else
#pragma HLS INTERFACE m_axi port=residual_state offset=slave bundle=gmem1
#endif
#endif
#pragma HLS INTERFACE m_axi port=out_degree offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=source_prop_1 offset=slave bundle=gmem3
#pragma HLS INTERFACE m_axi port=source_prop_2 offset=slave bundle=gmem4
#pragma HLS INTERFACE m_axi port=round_stats offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=rank_state bundle=control
#if GRASU_REGRAPH_PAGERANK_MODE == 2
#pragma HLS INTERFACE s_axilite port=residual_state bundle=control
#endif
#pragma HLS INTERFACE s_axilite port=out_degree bundle=control
#pragma HLS INTERFACE s_axilite port=source_prop_1 bundle=control
#pragma HLS INTERFACE s_axilite port=source_prop_2 bundle=control
#pragma HLS INTERFACE s_axilite port=round_stats bundle=control
#pragma HLS INTERFACE s_axilite port=burst_count bundle=control
#pragma HLS INTERFACE s_axilite port=vertices bundle=control
#pragma HLS INTERFACE s_axilite port=damping bundle=control
#pragma HLS INTERFACE s_axilite port=epsilon bundle=control
#if GRASU_REGRAPH_PAGERANK_MODE == 2
#pragma HLS INTERFACE s_axilite port=correction_mode bundle=control
#endif
#pragma HLS INTERFACE s_axilite port=return bundle=control

    float dangling_partials[kVerticesPerBurst][kReductionBanks];
    unsigned active_partials[kVerticesPerBurst][kReductionBanks];
#pragma HLS ARRAY_PARTITION variable=dangling_partials complete dim=0
#pragma HLS ARRAY_PARTITION variable=active_partials complete dim=0

initialize_partials:
    for (unsigned lane_index = 0; lane_index < kVerticesPerBurst;
         ++lane_index) {
#pragma HLS UNROLL
        for (unsigned bank = 0; bank < kReductionBanks; ++bank) {
#pragma HLS UNROLL
            dangling_partials[lane_index][bank] = 0.0F;
            active_partials[lane_index][bank] = 0;
        }
    }

    const unsigned capacity = burst_count * kVerticesPerBurst;
    const float threshold = epsilon;

prepare_bursts:
    for (unsigned burst = 0; burst < burst_count; ++burst) {
#pragma HLS PIPELINE II=1
#if GRASU_REGRAPH_PAGERANK_MODE == 2
        // A residual round consumes exactly one state array.  Sharing this
        // conditional read avoids spending a U55C HMSS master on an array
        // that is inactive for the whole launch.
        const ap_uint<512> value_beat = correction_mode
                                            ? rank_state[burst]
                                            : residual_state[burst];
#else
        const ap_uint<512> value_beat = rank_state[burst];
#endif
        const ap_uint<512> degree_beat = out_degree[burst];
        ap_uint<512> source_payload = 0;
        const unsigned reduction_bank = burst & (kReductionBanks - 1);

    prepare_lanes:
        for (unsigned lane_index = 0; lane_index < kVerticesPerBurst;
             ++lane_index) {
#pragma HLS UNROLL
            const unsigned vertex = burst * kVerticesPerBurst + lane_index;
            if (vertex >= vertices) {
                set_lane(source_payload, lane_index, 0);
                continue;
            }
            const unsigned degree = lane(degree_beat, lane_index).to_uint();
#if GRASU_REGRAPH_PAGERANK_MODE == 1
            const float value = word_to_float(lane(value_beat, lane_index));
            const bool active = true;
#else
            const float value = word_to_float(lane(value_beat, lane_index));
            const bool active = correction_mode || float_abs(value) > threshold;
#endif
            const float payload = active && degree != 0
                                      ? damping * value / degree
                                      : 0.0F;
            set_lane(source_payload, lane_index, float_to_word(payload));
            if (active) {
                active_partials[lane_index][reduction_bank]++;
                if (degree == 0) {
                    dangling_partials[lane_index][reduction_bank] += value;
                }
            }
        }

        source_prop_1[burst] = source_payload;
        source_prop_2[burst] = source_payload;
    }

    float dangling = 0.0F;
    unsigned active_vertices = 0;
reduce_stats:
    for (unsigned lane_index = 0; lane_index < kVerticesPerBurst;
         ++lane_index) {
        for (unsigned bank = 0; bank < kReductionBanks; ++bank) {
#pragma HLS PIPELINE II=1
            dangling += dangling_partials[lane_index][bank];
            active_vertices += active_partials[lane_index][bank];
        }
    }

    round_stats[kReGraphPageRankStatus] =
        vertices <= capacity ? kReGraphPageRankOk
                             : kReGraphPageRankVertexCapacityExceeded;
    round_stats[kReGraphPageRankActiveVertices] = active_vertices;
    round_stats[kReGraphPageRankErrorBits] = float_to_word(0.0F);
    round_stats[kReGraphPageRankNextDanglingBits] = float_to_word(dangling);
    round_stats[kReGraphPageRankAppliedVertices] = 0;
}
}
