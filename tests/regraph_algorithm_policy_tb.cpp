#include <ap_int.h>

#include <cassert>
#include <cmath>
#include <cstdint>

#include "../kernels/regraph_algorithm_policy/regraph_algorithm_policy.cpp"

namespace {

std::uint32_t bits(float value)
{
    union {
        float value;
        std::uint32_t word;
    } encoded = {value};
    return encoded.word;
}

float value(std::uint32_t word)
{
    union {
        std::uint32_t word;
        float value;
    } decoded = {word};
    return decoded.value;
}

void put(ap_uint<256> &beat, unsigned lane_index, std::uint32_t word)
{
    beat.range(lane_index * 32 + 31, lane_index * 32) = word;
}

std::uint32_t get(const ap_uint<256> &beat, unsigned lane_index)
{
    return beat.range(lane_index * 32 + 31, lane_index * 32).to_uint();
}

void expect_close(float actual, float expected)
{
    assert(std::fabs(actual - expected) <= 1.0e-6F);
}

void run_operation(unsigned operation,
                   ap_uint<256> primary,
                   ap_uint<256> auxiliary,
                   ap_uint<256> operand_a,
                   ap_uint<256> operand_b,
                   ap_uint<8> valid,
                   ap_uint<256> &next_primary,
                   ap_uint<256> &next_auxiliary,
                   ap_uint<256> &result,
                   ap_uint<256> &extra,
                   ap_uint<8> &active,
                   float damping = 0.8F,
                   float epsilon = 0.08F,
                   float base = 0.05F,
                   float dangling_share = 0.1F)
{
    regraph_algorithm_policy(
        &primary, &auxiliary, &operand_a, &operand_b, &valid,
        &next_primary, &next_auxiliary, &result, &extra, &active,
        1, operation, 4, damping, epsilon, base, dangling_share);
}

}  // namespace

int main()
{
    ap_uint<256> primary = 0;
    ap_uint<256> auxiliary = 0;
    ap_uint<256> operand_a = 0;
    ap_uint<256> operand_b = 0;
    ap_uint<256> next_primary = 0;
    ap_uint<256> next_auxiliary = 0;
    ap_uint<256> result = 0;
    ap_uint<256> extra = 0;
    ap_uint<8> valid = 0;
    ap_uint<8> active = 0;

#if REGRAPH_ALGORITHM_POLICY == REGRAPH_POLICY_WEIGHTED_SSSP
    put(primary, 0, 10);
    put(primary, 1, kSsspInfinity);
    run_operation(kSourceMap, primary, auxiliary, operand_a, operand_b,
                  valid, next_primary, next_auxiliary, result, extra, active);
    assert(get(result, 0) == 10);
    assert(get(result, 1) == kSsspInfinity);

    put(operand_a, 0, 20);
    put(operand_b, 0, 3);
    put(operand_b, 1, 1);
    valid[0] = 1;
    run_operation(kEdgeMapReduce, primary, auxiliary, operand_a, operand_b,
                  valid, next_primary, next_auxiliary, result, extra, active);
    assert(get(result, 0) == 13);
    assert(get(result, 1) == kSsspInfinity);

    put(primary, 0, 20);
    put(primary, 1, 5);
    put(operand_a, 0, 13);
    valid = 1;
    run_operation(kApply, primary, auxiliary, operand_a, operand_b,
                  valid, next_primary, next_auxiliary, result, extra, active);
    assert(get(next_primary, 0) == 13);
    assert(get(next_primary, 1) == 5);
    assert(active[0] && !active[1]);
    expect_close(value(get(extra, 0)), 1.0F);
#elif REGRAPH_ALGORITHM_POLICY == REGRAPH_POLICY_FULL_PAGERANK
    put(primary, 0, bits(0.25F));
    put(primary, 1, bits(0.5F));
    put(operand_a, 0, 2);
    run_operation(kSourceMap, primary, auxiliary, operand_a, operand_b,
                  valid, next_primary, next_auxiliary, result, extra, active);
    expect_close(value(get(result, 0)), 0.1F);
    expect_close(value(get(result, 1)), 0.0F);
    expect_close(value(get(extra, 0)), 0.0F);
    expect_close(value(get(extra, 1)), 0.5F);

    put(primary, 0, bits(0.1F));
    put(primary, 1, bits(0.2F));
    put(operand_a, 0, bits(0.3F));
    valid = 1;
    run_operation(kEdgeMapReduce, primary, auxiliary, operand_a, operand_b,
                  valid, next_primary, next_auxiliary, result, extra, active);
    expect_close(value(get(result, 0)), 0.4F);
    expect_close(value(get(result, 1)), 0.2F);

    put(primary, 0, bits(0.25F));
    put(primary, 1, bits(0.5F));
    put(operand_a, 0, bits(0.4F));
    valid = 1;
    run_operation(kApply, primary, auxiliary, operand_a, operand_b,
                  valid, next_primary, next_auxiliary, result, extra, active);
    expect_close(value(get(next_primary, 0)), 0.55F);
    expect_close(value(get(next_primary, 1)), 0.15F);
    expect_close(value(get(extra, 0)), 0.30F);
    expect_close(value(get(extra, 1)), 0.35F);
    assert(active[0] && active[1]);
#else
    put(primary, 0, bits(0.2F));
    put(primary, 1, bits(0.4F));
    put(auxiliary, 0, bits(0.1F));
    put(auxiliary, 1, bits(-0.05F));
    put(operand_a, 0, 2);
    run_operation(kSourceMap, primary, auxiliary, operand_a, operand_b,
                  valid, next_primary, next_auxiliary, result, extra, active);
    expect_close(value(get(next_primary, 0)), 0.3F);
    expect_close(value(get(next_auxiliary, 0)), 0.0F);
    expect_close(value(get(result, 0)), 0.04F);
    expect_close(value(get(extra, 1)), -0.05F);

    put(primary, 0, bits(0.3F));
    put(primary, 1, bits(0.4F));
    put(auxiliary, 0, bits(0.02F));
    put(auxiliary, 1, bits(0.005F));
    put(operand_a, 0, bits(0.04F));
    valid = 1;
    run_operation(kApply, primary, auxiliary, operand_a, operand_b,
                  valid, next_primary, next_auxiliary, result, extra, active,
                  0.8F, 0.08F, 0.05F, 0.01F);
    expect_close(value(get(next_primary, 0)), 0.3F);
    expect_close(value(get(next_auxiliary, 0)), 0.07F);
    expect_close(value(get(next_auxiliary, 1)), 0.015F);
    expect_close(value(get(extra, 0)), 0.07F);
    assert(active[0] && !active[1]);
#endif

    return 0;
}
