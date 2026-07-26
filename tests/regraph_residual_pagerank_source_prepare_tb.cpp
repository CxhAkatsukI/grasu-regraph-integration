#include <hls_stream.h>
#include <ap_int.h>

#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>

#define GRASU_REGRAPH_PAGERANK_MODE 2
#include "../kernels/regraph_pagerank_source_prepare/regraph_pagerank_source_prepare.cpp"

namespace {

ap_uint<32> float_word(float value)
{
    union {
        float value;
        std::uint32_t word;
    } bits = {value};
    return bits.word;
}

float word_float(ap_uint<32> word)
{
    union {
        std::uint32_t word;
        float value;
    } bits = {word.to_uint()};
    return bits.value;
}

void put(ap_uint<512> &beat, unsigned index, float value)
{
    beat.range(index * 32 + 31, index * 32) = float_word(value);
}

float get(const ap_uint<512> &beat, unsigned index)
{
    return word_float(beat.range(index * 32 + 31, index * 32));
}

}  // namespace

int main()
{
    std::array<ap_uint<512>, 1> rank = {0};
    std::array<ap_uint<512>, 1> residual = {0};
    std::array<ap_uint<512>, 1> degree = {0};
    std::array<ap_uint<32>, kReGraphPageRankStatWords> stats = {};
    hls::stream<regraph_write_burst_pkt_t> output;
    put(residual[0], 0, 0.01F);
    put(residual[0], 1, -0.02F);
    put(residual[0], 2, 1.0e-8F);
    put(residual[0], 3, 0.04F);
    degree[0].range(31, 0) = 2;
    degree[0].range(63, 32) = 1;
    degree[0].range(95, 64) = 0;
    degree[0].range(127, 96) = 0;

    regraph_pagerank_source_prepare(
        rank.data(), residual.data(), degree.data(), stats.data(), 1, 4,
        0.85F, 1.0e-6F, output);
    const regraph_write_burst_pkt_t payload = output.read();
    assert(output.read().last == 1);
    assert(output.empty());
    assert(std::fabs(get(payload.data, 0) - 0.00425F) <= 1.0e-6F);
    assert(std::fabs(get(payload.data, 1) + 0.017F) <= 1.0e-6F);
    assert(get(payload.data, 2) == 0.0F);
    assert(get(payload.data, 3) == 0.0F);
    assert(stats[kReGraphPageRankStatus] == kReGraphPageRankOk);
    assert(stats[kReGraphPageRankActiveVertices] == 3);
    assert(std::fabs(word_float(stats[kReGraphPageRankNextDanglingBits]) -
                     0.04F) <= 1.0e-6F);
    return 0;
}
