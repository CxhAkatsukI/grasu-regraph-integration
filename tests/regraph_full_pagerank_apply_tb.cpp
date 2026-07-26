#include <hls_stream.h>
#include <ap_int.h>

#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>

#define GRASU_REGRAPH_PAGERANK_MODE 1
#include "../kernels/regraph_pagerank_apply/regraph_pagerank_apply.cpp"

namespace {

ap_uint<32> test_float_to_word(float value)
{
    union {
        float value;
        std::uint32_t word;
    } bits = {value};
    return bits.word;
}

float test_word_to_float(ap_uint<32> word)
{
    union {
        std::uint32_t word;
        float value;
    } bits = {word.to_uint()};
    return bits.value;
}

void put_float(ap_uint<512> &beat, unsigned lane_index, float value)
{
    beat.range(lane_index * 32 + 31, lane_index * 32) =
        test_float_to_word(value);
}

float get_float(const ap_uint<512> &beat, unsigned lane_index)
{
    return test_word_to_float(
        beat.range(lane_index * 32 + 31, lane_index * 32));
}

void expect_close(float actual, float expected, float tolerance = 1.0e-6F)
{
    assert(std::fabs(actual - expected) <= tolerance);
}

}  // namespace

int main()
{
    std::array<ap_uint<512>, 1> rank = {0};
    std::array<ap_uint<512>, 1> degree = {0};
    std::array<ap_uint<32>, kReGraphPageRankStatWords> stats = {};
    hls::stream<regraph_write_burst_pkt_t> incoming;
    hls::stream<regraph_write_burst_pkt_t> source_output;

    regraph_write_burst_pkt_t incoming_packet;
    incoming_packet.data = 0;
    incoming_packet.keep = -1;
    incoming_packet.strb = -1;
    incoming_packet.dest = 0;
    incoming_packet.last = 0;
    for (unsigned lane_index = 0; lane_index < 4; ++lane_index) {
        put_float(rank[0], lane_index, 0.25F);
        put_float(incoming_packet.data, lane_index,
                  0.1F * static_cast<float>(lane_index + 1));
    }
    degree[0].range(31, 0) = 2;
    degree[0].range(63, 32) = 1;
    degree[0].range(95, 64) = 0;
    degree[0].range(127, 96) = 1;
    incoming.write(incoming_packet);

    const float base = 0.0375F;
    const float dangling_share = 0.053125F;
    regraph_pagerank_apply(rank.data(), degree.data(), stats.data(), 1, 4,
                           0.85F, 1.0e-6F, base, dangling_share,
                           incoming, source_output);

    const regraph_write_burst_pkt_t payload = source_output.read();
    const regraph_write_burst_pkt_t end = source_output.read();
    assert(payload.dest == 0);
    assert(payload.last == 0);
    assert(end.last == 1);
    assert(source_output.empty());
    assert(incoming.empty());

    const std::array<float, 4> expected_rank = {
        0.190625F, 0.290625F, 0.390625F, 0.490625F};
    for (unsigned lane_index = 0; lane_index < expected_rank.size();
         ++lane_index) {
        expect_close(get_float(rank[0], lane_index),
                     expected_rank[lane_index]);
    }
    expect_close(get_float(payload.data, 0), 0.85F * expected_rank[0] / 2.0F);
    expect_close(get_float(payload.data, 1), 0.85F * expected_rank[1]);
    expect_close(get_float(payload.data, 2), 0.0F);
    expect_close(get_float(payload.data, 3), 0.85F * expected_rank[3]);
    assert(stats[kReGraphPageRankStatus] == kReGraphPageRankOk);
    assert(stats[kReGraphPageRankActiveVertices] == 4);
    assert(stats[kReGraphPageRankAppliedVertices] == 4);
    expect_close(test_word_to_float(stats[kReGraphPageRankErrorBits]),
                 0.48125F, 2.0e-6F);
    expect_close(test_word_to_float(stats[kReGraphPageRankNextDanglingBits]),
                 expected_rank[2]);

    hls::stream<regraph_write_burst_pkt_t> oversized_input;
    hls::stream<regraph_write_burst_pkt_t> oversized_output;
    oversized_input.write(incoming_packet);
    regraph_pagerank_apply(rank.data(), degree.data(), stats.data(), 1, 17,
                           0.85F, 1.0e-6F, base, dangling_share,
                           oversized_input, oversized_output);
    assert(stats[kReGraphPageRankStatus] ==
           kReGraphPageRankVertexCapacityExceeded);
    assert(stats[kReGraphPageRankAppliedVertices] == 16);
    assert(oversized_output.read().last == 0);
    assert(oversized_output.read().last == 1);
    assert(oversized_output.empty());

    return 0;
}
