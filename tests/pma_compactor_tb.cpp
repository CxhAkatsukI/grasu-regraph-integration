#include <cassert>
#include <cstdint>
#include <iostream>
#include <utility>
#include <vector>
#include "../kernels/pma_prefetch_compact/compactor.hpp"

using Edge = std::pair<unsigned, unsigned>;

static unsigned check(const std::vector<pma_compact::Segment> &segments) {
    hls::stream<pma_compact::Segment> input;
    hls::stream<pma_compact::Packet> output;
    std::vector<Edge> expected;
    for (const auto &segment : segments) {
        input.write(segment);
        for (unsigned lane = 0; lane < 16; ++lane) {
            unsigned dst = segment.data.range(lane * 32 + 31, lane * 32);
            if ((dst >> 31) || (dst & 0x7ffffu) >= 32) continue;
#if GRASU_REGRAPH_WEIGHTED_PMA
            if (((dst >> 19) & 0xfffu) == 0) continue;
#elif !GRASU_REGRAPH_DESTINATION_ONLY
            dst = (dst & 0x7ffffu) | (1u << 19);
#endif
            expected.emplace_back(segment.source, dst);
        }
    }
    pma_compact::compact(32, input, output);
    assert(input.empty());
    std::vector<Edge> actual;
    unsigned packets = 0, terminals = 0;
    while (!output.empty()) {
        auto packet = output.read();
        assert(terminals == 0);
        assert(packet.keep == ap_uint<64>(-1));
        assert(packet.strb == ap_uint<64>(-1));
        unsigned window = (unsigned)packet.data.range(30, 0) / 4096;
        for (unsigned lane = 0; lane < 8; ++lane) {
            unsigned src = packet.data.range(lane * 64 + 31, lane * 64);
            unsigned dst = packet.data.range(lane * 64 + 63, lane * 64 + 32);
            assert((src & 0x7fffffffu) / 4096 == window);
            if (!(dst >> 31)) actual.emplace_back(src, dst);
        }
        terminals += packet.last;
        ++packets;
    }
    assert(terminals == 1 && actual == expected);
    return packets;
}

int main() {
    unsigned packets = 0;
    std::vector<pma_compact::Segment> segments;
    // Every 16-lane validity mask, including consecutive full/empty inputs.
    for (unsigned mask = 0; mask < 65536; ++mask) {
        pma_compact::Segment segment = {};
        segment.source = mask / 8;
        segment.last = mask == 65535;
        for (unsigned lane = 0; lane < 16; ++lane) {
            unsigned dst = lane | (3u << 19);
            if (!(mask & (1u << lane))) dst |= 0x80000000u;
            segment.data.range(lane * 32 + 31, lane * 32) = dst;
        }
        segments.push_back(segment);
    }
    packets += check(segments);
    segments.clear();

    // Exercise weighted-zero rejection, out-of-range destinations, partial
    // packets, and successive source-window changes with deterministic data.
    std::uint32_t random = 0x4512ab9u;
    for (unsigned index = 0; index < 4096; ++index) {
        pma_compact::Segment segment = {};
        segment.source = index * 3;
        segment.last = index == 4095;
        for (unsigned lane = 0; lane < 16; ++lane) {
            random ^= random << 13;
            random ^= random >> 17;
            random ^= random << 5;
            unsigned dst = (random & 63u) | (((random >> 8) & 3u) << 19);
            if (random & 0x400u) dst |= 0x80000000u;
            segment.data.range(lane * 32 + 31, lane * 32) = dst;
        }
        segments.push_back(segment);
    }
    packets += check(segments);
    std::cout << "PMA_COMPACTOR PASS masks=65536 random_segments=4096 packets="
              << packets << "\n";
}
