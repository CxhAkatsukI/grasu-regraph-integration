#include <hls_stream.h>
#include <ap_int.h>

#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>

#define GRASU_REGRAPH_PAGERANK_MODE 2
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
    std::array<ap_uint<512>, 1> residual = {0};
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
    put_float(residual[0], 0, 0.0375F);
    put_float(residual[0], 1, 0.0375F);
    put_float(residual[0], 2, 5.0e-7F);
    put_float(residual[0], 3, 0.0375F);
    put_float(incoming_packet.data, 0, 0.01F);
    put_float(incoming_packet.data, 1, 0.02F);
    put_float(incoming_packet.data, 2, 0.0F);
    put_float(incoming_packet.data, 3, 0.04F);
    degree[0].range(31, 0) = 2;
    degree[0].range(63, 32) = 1;
    degree[0].range(95, 64) = 1;
    degree[0].range(127, 96) = 0;
    incoming.write(incoming_packet);

    regraph_pagerank_apply(rank.data(), residual.data(), degree.data(),
                           stats.data(), 1, 4, 0.85F, 1.0e-6F, 0.0F, 0.0F,
                           incoming, source_output);

    const regraph_write_burst_pkt_t payload = source_output.read();
    const regraph_write_burst_pkt_t end = source_output.read();
    assert(payload.last == 0);
    assert(end.last == 1);
    assert(source_output.empty());
    assert(incoming.empty());

    expect_close(get_float(rank[0], 0), 0.0375F);
    expect_close(get_float(rank[0], 1), 0.0375F);
    expect_close(get_float(rank[0], 2), 0.0F);
    expect_close(get_float(rank[0], 3), 0.0375F);
    expect_close(get_float(residual[0], 0), 0.01F);
    expect_close(get_float(residual[0], 1), 0.02F);
    expect_close(get_float(residual[0], 2), 5.0e-7F);
    expect_close(get_float(residual[0], 3), 0.04F);
    expect_close(get_float(payload.data, 0), 0.85F * 0.01F / 2.0F);
    expect_close(get_float(payload.data, 1), 0.85F * 0.02F);
    expect_close(get_float(payload.data, 2), 0.0F);
    expect_close(get_float(payload.data, 3), 0.0F);
    assert(stats[kReGraphPageRankStatus] == kReGraphPageRankOk);
    assert(stats[kReGraphPageRankActiveVertices] == 3);
    assert(stats[kReGraphPageRankAppliedVertices] == 4);
    expect_close(test_word_to_float(stats[kReGraphPageRankErrorBits]),
                 0.07000001F, 2.0e-6F);
    expect_close(test_word_to_float(stats[kReGraphPageRankNextDanglingBits]),
                 0.04F);

    hls::stream<regraph_write_burst_pkt_t> second_incoming;
    hls::stream<regraph_write_burst_pkt_t> second_output;
    incoming_packet.data = 0;
    second_incoming.write(incoming_packet);
    regraph_pagerank_apply(rank.data(), residual.data(), degree.data(),
                           stats.data(), 1, 4, 0.85F, 1.0e-6F, 0.0F, 0.0085F,
                           second_incoming, second_output);
    assert(second_output.read().last == 0);
    assert(second_output.read().last == 1);
    assert(second_output.empty());
    expect_close(get_float(rank[0], 0), 0.0475F);
    expect_close(get_float(rank[0], 1), 0.0575F);
    expect_close(get_float(rank[0], 2), 0.0F);
    expect_close(get_float(rank[0], 3), 0.0775F);
    expect_close(get_float(residual[0], 0), 0.0085F);
    expect_close(get_float(residual[0], 1), 0.0085F);
    expect_close(get_float(residual[0], 2), 0.0085005F);
    expect_close(get_float(residual[0], 3), 0.0085F);
    assert(stats[kReGraphPageRankActiveVertices] == 4);
    expect_close(test_word_to_float(stats[kReGraphPageRankNextDanglingBits]),
                 0.0085F, 2.0e-6F);

    return 0;
}
