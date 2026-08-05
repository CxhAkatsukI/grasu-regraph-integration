#include <ap_int.h>

#include <cstdint>

#define REGRAPH_POLICY_WEIGHTED_SSSP 1
#define REGRAPH_POLICY_FULL_PAGERANK 2
#define REGRAPH_POLICY_RESIDUAL_PAGERANK 3

#ifndef REGRAPH_ALGORITHM_POLICY
#error "REGRAPH_ALGORITHM_POLICY must select a supported policy"
#endif

#if REGRAPH_ALGORITHM_POLICY < REGRAPH_POLICY_WEIGHTED_SSSP || \
    REGRAPH_ALGORITHM_POLICY > REGRAPH_POLICY_RESIDUAL_PAGERANK
#error "unsupported REGRAPH_ALGORITHM_POLICY"
#endif

namespace {

constexpr unsigned kLanes = 8;
constexpr std::uint32_t kSsspInfinity = 0xffffffffU;

float float_abs(float value)
{
#pragma HLS INLINE
    return value < 0.0F ? -value : value;
}

enum PolicyOperation : unsigned {
    kSourceMap = 0,
    kEdgeMapReduce = 1,
    kApply = 2,
};

std::uint32_t float_to_word(float value)
{
#pragma HLS INLINE
    union {
        float value;
        std::uint32_t word;
    } bits = {value};
    return bits.word;
}

float word_to_float(std::uint32_t word)
{
#pragma HLS INLINE
    union {
        std::uint32_t word;
        float value;
    } bits = {word};
    return bits.value;
}

std::uint32_t saturating_weight_add(std::uint32_t value,
                                    std::uint32_t weight)
{
#pragma HLS INLINE
    if (value == kSsspInfinity || value > kSsspInfinity - weight) {
        return kSsspInfinity;
    }
    return value + weight;
}

std::uint32_t lane(const ap_uint<256> &beat, unsigned index)
{
#pragma HLS INLINE
    return static_cast<std::uint32_t>(
        beat.range(index * 32 + 31, index * 32).to_uint());
}

void set_lane(ap_uint<256> &beat, unsigned index, std::uint32_t value)
{
#pragma HLS INLINE
    beat.range(index * 32 + 31, index * 32) = value;
}

}  // namespace

extern "C" {

// This is an isolated arithmetic policy core, not a complete graph accelerator.
// Each 256-bit beat carries eight independent lanes. Input meanings are:
//   source-map:      primary/auxiliary state, operand_a=outdegree
//   map+reduce:      primary=source payload, operand_a=current reduction,
//                    operand_b=edge weight, valid_mask=current-valid bits
//   apply:           primary/auxiliary old state, operand_a=reduced value,
//                    valid_mask=reduced-valid bits
// result_out is the source payload or reduction result; extra_out is dangling
// payload or apply error. State outputs are meaningful for source-map/apply.
void regraph_algorithm_policy(
    const ap_uint<256> *primary_in,
    const ap_uint<256> *auxiliary_in,
    const ap_uint<256> *operand_a_in,
    const ap_uint<256> *operand_b_in,
    const ap_uint<8> *valid_mask_in,
    ap_uint<256> *primary_out,
    ap_uint<256> *auxiliary_out,
    ap_uint<256> *result_out,
    ap_uint<256> *extra_out,
    ap_uint<8> *active_mask_out,
    unsigned beat_count,
    unsigned operation,
    unsigned vertices,
    float damping,
    float epsilon,
    float base,
    float dangling_share)
{
#pragma HLS INTERFACE m_axi port=primary_in offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=auxiliary_in offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=operand_a_in offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=operand_b_in offset=slave bundle=gmem3
#pragma HLS INTERFACE m_axi port=valid_mask_in offset=slave bundle=gmem4
#pragma HLS INTERFACE m_axi port=primary_out offset=slave bundle=gmem5
#pragma HLS INTERFACE m_axi port=auxiliary_out offset=slave bundle=gmem6
#pragma HLS INTERFACE m_axi port=result_out offset=slave bundle=gmem7
#pragma HLS INTERFACE m_axi port=extra_out offset=slave bundle=gmem8
#pragma HLS INTERFACE m_axi port=active_mask_out offset=slave bundle=gmem9
#pragma HLS INTERFACE s_axilite port=primary_in bundle=control
#pragma HLS INTERFACE s_axilite port=auxiliary_in bundle=control
#pragma HLS INTERFACE s_axilite port=operand_a_in bundle=control
#pragma HLS INTERFACE s_axilite port=operand_b_in bundle=control
#pragma HLS INTERFACE s_axilite port=valid_mask_in bundle=control
#pragma HLS INTERFACE s_axilite port=primary_out bundle=control
#pragma HLS INTERFACE s_axilite port=auxiliary_out bundle=control
#pragma HLS INTERFACE s_axilite port=result_out bundle=control
#pragma HLS INTERFACE s_axilite port=extra_out bundle=control
#pragma HLS INTERFACE s_axilite port=active_mask_out bundle=control
#pragma HLS INTERFACE s_axilite port=beat_count bundle=control
#pragma HLS INTERFACE s_axilite port=operation bundle=control
#pragma HLS INTERFACE s_axilite port=vertices bundle=control
#pragma HLS INTERFACE s_axilite port=damping bundle=control
#pragma HLS INTERFACE s_axilite port=epsilon bundle=control
#pragma HLS INTERFACE s_axilite port=base bundle=control
#pragma HLS INTERFACE s_axilite port=dangling_share bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

policy_beats:
    for (unsigned beat_index = 0; beat_index < beat_count; ++beat_index) {
#pragma HLS PIPELINE II=1
        const ap_uint<256> primary_beat = primary_in[beat_index];
        const ap_uint<256> auxiliary_beat = auxiliary_in[beat_index];
        const ap_uint<256> operand_a_beat = operand_a_in[beat_index];
        const ap_uint<256> operand_b_beat = operand_b_in[beat_index];
        const ap_uint<8> valid_mask = valid_mask_in[beat_index];
        ap_uint<256> next_primary = primary_beat;
        ap_uint<256> next_auxiliary = auxiliary_beat;
        ap_uint<256> result = 0;
        ap_uint<256> extra = 0;
        ap_uint<8> active_mask = 0;

    policy_lanes:
        for (unsigned lane_index = 0; lane_index < kLanes; ++lane_index) {
#pragma HLS UNROLL
            const std::uint32_t primary = lane(primary_beat, lane_index);
            const std::uint32_t auxiliary = lane(auxiliary_beat, lane_index);
            const std::uint32_t operand_a = lane(operand_a_beat, lane_index);
            const std::uint32_t operand_b = lane(operand_b_beat, lane_index);
            const bool valid = valid_mask[lane_index];
            std::uint32_t lane_result = 0;
            std::uint32_t lane_extra = 0;
            std::uint32_t lane_primary = primary;
            std::uint32_t lane_auxiliary = auxiliary;
            bool lane_active = false;

            if (operation == kSourceMap) {
#if REGRAPH_ALGORITHM_POLICY == REGRAPH_POLICY_WEIGHTED_SSSP
                lane_result = primary;
#elif REGRAPH_ALGORITHM_POLICY == REGRAPH_POLICY_FULL_PAGERANK
                const float rank = word_to_float(primary);
                lane_result = float_to_word(
                    operand_a == 0 ? 0.0F : damping * rank / operand_a);
                lane_extra = float_to_word(operand_a == 0 ? rank : 0.0F);
#else
                const float delta = word_to_float(auxiliary);
                lane_primary = float_to_word(word_to_float(primary) + delta);
                lane_auxiliary = float_to_word(0.0F);
                lane_result = float_to_word(
                    operand_a == 0 ? 0.0F : damping * delta / operand_a);
                lane_extra = float_to_word(operand_a == 0 ? delta : 0.0F);
#endif
            } else if (operation == kEdgeMapReduce) {
#if REGRAPH_ALGORITHM_POLICY == REGRAPH_POLICY_WEIGHTED_SSSP
                const std::uint32_t candidate =
                    saturating_weight_add(primary, operand_b);
                lane_result = valid && operand_a < candidate ? operand_a
                                                              : candidate;
#else
                const float candidate = word_to_float(primary);
                lane_result = float_to_word(
                    valid ? word_to_float(operand_a) + candidate : candidate);
#endif
            } else if (operation == kApply) {
#if REGRAPH_ALGORITHM_POLICY == REGRAPH_POLICY_WEIGHTED_SSSP
                const std::uint32_t candidate = valid ? operand_a
                                                       : kSsspInfinity;
                lane_active = candidate < primary;
                lane_primary = lane_active ? candidate : primary;
                lane_extra = float_to_word(lane_active ? 1.0F : 0.0F);
#elif REGRAPH_ALGORITHM_POLICY == REGRAPH_POLICY_FULL_PAGERANK
                const float incoming = valid ? word_to_float(operand_a) : 0.0F;
                const float value = base + dangling_share + incoming;
                lane_primary = float_to_word(value);
                lane_active = true;
                lane_extra = float_to_word(
                    float_abs(value - word_to_float(primary)));
#else
                const float incoming = valid ? word_to_float(operand_a) : 0.0F;
                const float residual = word_to_float(auxiliary) + incoming +
                                       dangling_share;
                lane_auxiliary = float_to_word(residual);
                lane_active = float_abs(residual) > epsilon;
                lane_extra = float_to_word(float_abs(residual));
#endif
            }

            set_lane(next_primary, lane_index, lane_primary);
            set_lane(next_auxiliary, lane_index, lane_auxiliary);
            set_lane(result, lane_index, lane_result);
            set_lane(extra, lane_index, lane_extra);
            active_mask[lane_index] = lane_active;
        }

        primary_out[beat_index] = next_primary;
        auxiliary_out[beat_index] = next_auxiliary;
        result_out[beat_index] = result;
        extra_out[beat_index] = extra;
        active_mask_out[beat_index] = active_mask;
    }
}

}  // extern "C"
