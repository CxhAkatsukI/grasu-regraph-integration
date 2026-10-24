#include <cassert>
#include <iostream>
#include <utility>
#include <vector>
#include "../kernels/pma_prefetch_compact/top.cpp"

int main() {
    unsigned cases = 0, packets = 0;
    for (unsigned vertices : {0u, 1u, 7u, 9u, 1023u, 1024u, 1025u,
                              4095u, 4096u, 4097u, 8193u}) {
        for (unsigned placement : {0u, 1u, 2u, 3u}) {
            for (unsigned length : {0u, 1u, 3u}) {
                std::vector<ap_uint<512>> rows((vertices + 7) / 8 + 1, 0);
                std::vector<ap_uint<512>> banks[4];
                for (auto &bank : banks) bank.resize(vertices * 3 + 1, 0);
                std::vector<std::pair<unsigned, unsigned>> expected;
                unsigned segments = 0;
                for (unsigned src = 0; src < vertices; ++src) {
                    unsigned begin = segments * 16;
                    bool occupied = placement == 0 ? src % 3 == 0 :
                        placement == 1 ? src == 0 :
                        placement == 2 ? src + 1 == vertices : src % 17 == 0;
                    for (unsigned j = 0; j < (occupied ? length : 0); ++j) {
                        ap_uint<512> word = 0;
                        for (unsigned lane = 0; lane < 16; ++lane) {
                            unsigned dst = lane % 5 == 0 ? 0x80000000u :
                                ((src + lane) % 37) | ((j + 1) << 19);
                            word.range(lane * 32 + 31, lane * 32) = dst;
                            if (!(dst >> 31) && (dst & 0x7ffffu) < 32) {
#if !GRASU_REGRAPH_WEIGHTED_PMA && !GRASU_REGRAPH_DESTINATION_ONLY
                                dst = (dst & 0x7ffffu) | (1u << 19);
#endif
                                expected.emplace_back(src, dst);
                            }
                        }
                        unsigned bank = (segments < 4 ? 0 : 1) + (segments % 2 ? 2 : 0);
                        banks[bank][segments / 2] = word;
                        ++segments;
                    }
                    ap_uint<64> bounds = (ap_uint<64>(begin) << 32) | (segments * 16);
                    rows[src / 8].range((src % 8) * 64 + 63, (src % 8) * 64) = bounds;
                }
                hls::stream<pma_compact::Packet> output;
                pma_to_regraph_adapter(banks[0].data(), banks[1].data(),
                    banks[2].data(), banks[3].data(), rows.data(), vertices,
                    segments * 16, 2, 0, 32, output);
                std::vector<std::pair<unsigned, unsigned>> actual;
                unsigned terminals = 0;
                while (!output.empty()) {
                    auto pkt = output.read();
                    ++packets;
                    assert(terminals == 0 && pkt.keep == ap_uint<64>(-1));
                    unsigned window = (unsigned)pkt.data.range(30, 0) / 4096;
                    for (unsigned lane = 0; lane < 8; ++lane) {
                        unsigned src = pkt.data.range(lane * 64 + 31, lane * 64);
                        unsigned dst = pkt.data.range(lane * 64 + 63, lane * 64 + 32);
                        assert((src & 0x7fffffffu) / 4096 == window);
                        if (!(dst >> 31)) actual.emplace_back(src, dst);
                    }
                    terminals += pkt.last;
                }
                assert(terminals == 1 && expected == actual);
                ++cases;
            }
        }
    }
    std::cout << "PMA_PREFETCH_COMPACT PASS cases=" << cases
              << " packets=" << packets << "\n";
}
