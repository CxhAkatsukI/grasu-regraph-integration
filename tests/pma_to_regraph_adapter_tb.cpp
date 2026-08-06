#include <cassert>
#include <cstdint>

#include "../kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"

namespace {

constexpr std::uint32_t kEmpty = 0x80000000U;
constexpr std::uint32_t kDstMask = 0x7ffffU;
constexpr std::uint32_t kWeightShift = 19U;

std::uint32_t pack(std::uint32_t destination, std::uint32_t weight)
{
    return destination | (weight << kWeightShift);
}

std::uint32_t lane_word(const edge_burst_pkt_t &burst,
                        unsigned lane,
                        bool destination)
{
    const unsigned base = lane * 64 + (destination ? 32 : 0);
    return static_cast<std::uint32_t>(
        burst.data.range(base + 31, base).to_uint());
}

}  // namespace

int main()
{
    ap_uint<512> segment = 0;
    segment.range(31, 0) = pack(3, 7);
    segment.range(63, 32) = pack(9, 12);
    for (unsigned lane = 2; lane < 16; ++lane) {
        segment.range(lane * 32 + 31, lane * 32) = kEmpty;
    }

    ap_uint<512> pma[1] = {segment};
    ap_uint<64> row_offset[1] = {16};
    hls::stream<edge_burst_pkt_t> output;
    pma_to_regraph_adapter(
        pma, pma, pma, pma, row_offset, 1, 16, 131072, 0, 65536, output);

    assert(!output.empty());
    const edge_burst_pkt_t first = output.read();
    assert(!first.last);
    assert(lane_word(first, 0, false) == 0);
    assert(lane_word(first, 1, false) == 0);
#if GRASU_REGRAPH_WEIGHTED_PMA
    assert(lane_word(first, 0, true) == pack(3, 7));
    assert(lane_word(first, 1, true) == pack(9, 12));
#elif GRASU_REGRAPH_DESTINATION_ONLY
    assert(lane_word(first, 0, true) == 3);
    assert(lane_word(first, 1, true) == 9);
#else
    assert(lane_word(first, 0, true) == pack(3, 1));
    assert(lane_word(first, 1, true) == pack(9, 1));
#endif
    for (unsigned lane = 2; lane < 8; ++lane) {
        assert((lane_word(first, lane, false) & kEmpty) != 0);
        assert((lane_word(first, lane, true) & kEmpty) != 0);
        assert((lane_word(first, lane, true) & kDstMask) == 0);
    }

    assert(!output.empty());
    const edge_burst_pkt_t second = output.read();
    assert(second.last);
    for (unsigned lane = 0; lane < 8; ++lane) {
        assert((lane_word(second, lane, false) & kEmpty) != 0);
        assert((lane_word(second, lane, true) & kEmpty) != 0);
    }
    assert(output.empty());

#if !GRASU_REGRAPH_SHARDED_PMA
    hls::stream<edge_burst_pkt_t> partitioned_output;
    pma_to_regraph_adapter(
        pma, pma, pma, pma, row_offset, 1, 16, 131072, 8, 8,
        partitioned_output);
    const edge_burst_pkt_t partitioned_first = partitioned_output.read();
    assert((lane_word(partitioned_first, 0, false) & kEmpty) != 0);
    assert((lane_word(partitioned_first, 0, true) & kEmpty) != 0);
    assert(lane_word(partitioned_first, 1, false) == 0);
#if GRASU_REGRAPH_WEIGHTED_PMA
    assert(lane_word(partitioned_first, 1, true) == pack(9, 12));
#elif GRASU_REGRAPH_DESTINATION_ONLY
    assert(lane_word(partitioned_first, 1, true) == 9);
#else
    assert(lane_word(partitioned_first, 1, true) == pack(9, 1));
#endif
    assert(!partitioned_first.last);
    assert(!partitioned_output.empty());
    assert(partitioned_output.read().last);
    assert(partitioned_output.empty());
#endif

#if GRASU_REGRAPH_SHARDED_PMA
    ap_uint<512> local_segment = 0;
    local_segment.range(31, 0) = pack(1, 7);
    for (unsigned lane = 1; lane < 16; ++lane) {
        local_segment.range(lane * 32 + 31, lane * 32) = kEmpty;
    }
    ap_uint<512> local_pma[1] = {local_segment};
    hls::stream<edge_burst_pkt_t> sharded_output;
    pma_to_regraph_adapter(
        local_pma, local_pma, local_pma, local_pma, row_offset, 1, 16,
        131072, 8, 8, sharded_output);
    const edge_burst_pkt_t sharded_first = sharded_output.read();
    assert(lane_word(sharded_first, 0, false) == 0);
#if GRASU_REGRAPH_DESTINATION_ONLY
    assert(lane_word(sharded_first, 0, true) == 9);
#elif GRASU_REGRAPH_WEIGHTED_PMA
    assert(lane_word(sharded_first, 0, true) == pack(1, 7));
#else
    assert(lane_word(sharded_first, 0, true) == pack(1, 1));
#endif
    assert(!sharded_first.last);
    assert(sharded_output.read().last);
    assert(sharded_output.empty());
#endif
    return 0;
}
