#include <array>
#include <cassert>
#include <cstdint>

#ifndef APPLY_TEST_SOURCE
#define APPLY_TEST_SOURCE "../kernels/regraph_pagerank_apply/regraph_pagerank_apply.cpp"
#endif
#include APPLY_TEST_SOURCE

namespace {

constexpr unsigned kMaxBursts = 17;
using Beats = std::array<ap_uint<512>, kMaxBursts>;

void exercise(unsigned bursts, unsigned vertices, bool correction)
{
    Beats rank = {}, residual = {}, degree = {}, incoming = {};
    Beats expected_rank = {}, expected_residual = {}, expected_source = {};
    std::array<ap_uint<32>, kReGraphPageRankStatWords> stats = {};
    float errors[16][8] = {}, dangling[16][8] = {};
    unsigned counts[16][8] = {};
    const float epsilon = 0.0001F, base = 0.0375F, share = 0.0025F;
    const float old_residuals[] = {-0.125F, -epsilon, -0.0F, 0.0F,
                                   epsilon, 0.00001F, 0.125F};
    for (unsigned burst = 0; burst < bursts; ++burst) {
        for (unsigned li = 0; li < 16; ++li) {
            const unsigned vertex = burst * 16 + li;
            const float old_rank = 0.03125F * (vertex % 13);
            const float old_residual = old_residuals[vertex % 7];
            const unsigned deg = vertex % 5;
            const float contribution = 0.015625F * (int(vertex % 9) - 4);
            set_lane(rank[burst], li, float_to_word(old_rank));
            set_lane(residual[burst], li, float_to_word(old_residual));
            set_lane(degree[burst], li, deg);
            set_lane(incoming[burst], li, float_to_word(contribution));
            float next_rank = old_rank, next_value = 0.0F;
            bool active = true;
            if (vertex < vertices) {
#if GRASU_REGRAPH_PAGERANK_MODE == 1
                next_rank = base + share + contribution;
                next_value = next_rank;
                errors[li][burst & 7] += float_abs(next_rank - old_rank);
#else
                if (correction) {
                    next_value = base + share + contribution - old_rank;
                } else {
                    const bool old_active = float_abs(old_residual) > epsilon;
                    if (old_active) next_rank += old_residual;
                    const float retained = old_active ? 0.0F : old_residual;
                    next_value = retained + contribution + share;
                }
                active = float_abs(next_value) > epsilon;
                errors[li][burst & 7] += float_abs(next_value);
#endif
                if (active) {
                    ++counts[li][burst & 7];
                    if (deg == 0) dangling[li][burst & 7] += next_value;
                }
            }
            set_lane(expected_rank[burst], li, float_to_word(next_rank));
            set_lane(expected_residual[burst], li,
                     float_to_word(vertex < vertices ? next_value : old_residual));
            const float payload = vertex < vertices && active && deg != 0
                                      ? 0.85F * next_value / deg : 0.0F;
            set_lane(expected_source[burst], li, float_to_word(payload));
        }
    }
    hls::stream<regraph_write_burst_pkt_t> input, output;
    for (unsigned burst = 0; burst < bursts; ++burst) {
        regraph_write_burst_pkt_t packet;
        packet.data = incoming[burst];
        packet.keep = -1;
        packet.strb = -1;
        packet.dest = burst;
        packet.last = 0;
        input.write(packet);
    }
    regraph_pagerank_apply(rank.data(),
#if GRASU_REGRAPH_PAGERANK_MODE == 2
                           residual.data(),
#endif
                           degree.data(), stats.data(), bursts, vertices,
                           0.85F, epsilon, base, share,
#if GRASU_REGRAPH_PAGERANK_MODE == 2
                           correction,
#endif
                           input, output);
    assert(input.empty());
    for (unsigned burst = 0; burst < bursts; ++burst) {
        assert(rank[burst] == expected_rank[burst]);
#if GRASU_REGRAPH_PAGERANK_MODE == 2
        assert(residual[burst] == expected_residual[burst]);
#endif
        const auto packet = output.read();
        assert(packet.data == expected_source[burst]);
        assert(packet.dest == burst && packet.last == 0);
        assert(packet.keep == ap_uint<64>(-1));
        assert(packet.strb == ap_uint<64>(-1));
    }
    const auto end = output.read();
    assert(end.last == 1 && end.dest == 0 && end.data == 0);
    assert(end.keep == ap_uint<64>(-1) && end.strb == ap_uint<64>(-1));
    assert(output.empty());
    float error = 0.0F, next_dangling = 0.0F;
    unsigned active = 0;
    for (unsigned li = 0; li < 16; ++li) {
        for (unsigned bank = 0; bank < 8; ++bank) {
            error += errors[li][bank];
            next_dangling += dangling[li][bank];
            active += counts[li][bank];
        }
    }
    const unsigned capacity = bursts * 16;
    assert(stats[kReGraphPageRankErrorBits] == float_to_word(error));
    assert(stats[kReGraphPageRankNextDanglingBits] == float_to_word(next_dangling));
    assert(stats[kReGraphPageRankActiveVertices] == active);
    assert(stats[kReGraphPageRankAppliedVertices] == (vertices > capacity ? capacity : vertices));
    assert(stats[kReGraphPageRankStatus] == (vertices > capacity
        ? kReGraphPageRankVertexCapacityExceeded : kReGraphPageRankOk));
}

}  // namespace

int main()
{
    for (unsigned bursts : {0U, 1U, 2U, 9U, 17U}) {
        for (unsigned vertices : {0U, 1U, 15U, 16U, 17U, bursts * 16, bursts * 16 + 1}) {
            exercise(bursts, vertices, false);
            exercise(bursts, vertices, true);
        }
    }
    return 0;
}
