#include <cassert>
#include <iostream>
#include <utility>
#include <vector>
#include "../kernels/pma_prefetch_compact/types.hpp"

extern "C" void pma_to_regraph_adapter(
    hls::burst_maxi<pma_compact::Word>, hls::burst_maxi<pma_compact::Word>,
    hls::burst_maxi<pma_compact::Word>, hls::burst_maxi<pma_compact::Word>,
    hls::burst_maxi<pma_compact::Word>, unsigned, unsigned, unsigned,
    unsigned, unsigned, hls::stream<pma_compact::Packet> &);

namespace {
using Edge = std::pair<unsigned, unsigned>;
constexpr unsigned kDepth = 2048;

void check(unsigned vertices, unsigned placement, unsigned length,
           unsigned cache_lines, bool invalid) {
    std::vector<pma_compact::Word> rows(kDepth, 0);
    std::vector<pma_compact::Word> banks[4];
    for (auto &bank : banks) bank.resize(kDepth, -1);
    std::vector<Edge> expected;
    unsigned segments = 0;
    for (unsigned src = 0; src < vertices; ++src) {
        const unsigned begin = segments * 16;
        bool occupied = placement == 0 ? src % 3 == 0 :
            placement == 1 ? src + 1 == vertices : true;
        for (unsigned j = 0; j < (occupied ? length : 0); ++j) {
            pma_compact::Word word = 0;
            for (unsigned lane = 0; lane < 16; ++lane) {
                unsigned dst = (src + lane) % 37 | ((j % 3) << 19);
                if (invalid || lane % 5 == 0) dst |= 0x80000000u;
                word.range(lane * 32 + 31, lane * 32) = dst;
                if (!(dst >> 31) && (dst & 0x7ffffu) < 32) {
#if GRASU_REGRAPH_WEIGHTED_PMA
                    if (((dst >> 19) & 0xfffu) == 0) continue;
#elif !GRASU_REGRAPH_DESTINATION_ONLY
                    dst = (dst & 0x7ffffu) | (1u << 19);
#endif
                    expected.emplace_back(src, dst);
                }
            }
            const unsigned line = segments / 2;
            assert(line < kDepth);
            const unsigned bank = (line < cache_lines ? 0 : 1) +
                                  (segments % 2 ? 2 : 0);
            banks[bank][line] = word;
            ++segments;
        }
        ap_uint<64> bounds = (ap_uint<64>(begin) << 32) | (segments * 16);
        rows[src / 8].range((src % 8) * 64 + 63, (src % 8) * 64) = bounds;
    }
    hls::stream<pma_compact::Packet> output;
    pma_to_regraph_adapter(banks[0].data(), banks[1].data(), banks[2].data(),
        banks[3].data(), rows.data(), vertices, segments * 16, cache_lines,
        65536, 32, output);
    std::vector<Edge> actual;
    unsigned terminals = 0, packets = 0;
    while (!output.empty()) {
        auto packet = output.read();
        assert(terminals == 0 && packet.keep == ap_uint<64>(-1) &&
               packet.strb == ap_uint<64>(-1));
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
    std::cout << "PMA_RTL_CASE_PASS vertices=" << vertices
              << " segments=" << segments << " packets=" << packets << '\n';
}
}

int main() {
    check(0, 0, 0, 0, false);
    check(9, 2, 3, 2, true);
    check(17, 2, 3, 7, false);
    check(1025, 0, 3, 2, false);
    check(4097, 1, 3, 1, false);
    check(257, 2, 9, 0, false);
    check(8193, 1, 3, 16, false);
    check(1, 2, 3, 2, false);
    std::cout << "PMA_PREFETCH_COMPACT_RTL_TB PASS cases=8\n";
}
