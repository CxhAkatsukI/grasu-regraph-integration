#include <hls_stream.h>
#include <hls_streamofblocks.h>
#include <ap_axi_sdata.h>
#include <ap_int.h>

#include <cassert>
#include <iostream>
#include <vector>

using packet_t = ap_axiu<512, 0, 0, 0>;
extern "C" void pma_to_regraph_adapter(
    const ap_uint<512> *, const ap_uint<512> *, const ap_uint<512> *,
    const ap_uint<512> *, const ap_uint<64> *, unsigned, unsigned, unsigned,
    unsigned, unsigned, hls::stream<packet_t> &);

namespace reference {
#undef GRASU_REGRAPH_ROW_PREFETCH
#undef GRASU_REGRAPH_STOP_AFTER_LAST
#undef GRASU_REGRAPH_SKIP_EMPTY_SEGMENT
#define GRASU_REGRAPH_ROW_PREFETCH 0
#define GRASU_REGRAPH_STOP_AFTER_LAST 0
#define GRASU_REGRAPH_SKIP_EMPTY_SEGMENT 0
#define pma_to_regraph_adapter reference_adapter
#include "../kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
#undef pma_to_regraph_adapter
}

namespace {

unsigned check_case(unsigned vertices, unsigned placement, unsigned length)
{
    // Match the co-simulation snapshot depth even for the zero-node call.
    std::vector<ap_uint<64>> rows(1025);
    std::vector<ap_uint<512>> pma[4];
    for (auto &bank : pma) bank.resize(256);
    unsigned segments = 0;
    for (unsigned source = 0; source < vertices; ++source) {
        const unsigned begin = segments * 16;
        const bool occupied = placement == 0 ? source == 0
            : placement == 1 ? source + 1 == vertices : source % 7 == 0;
        if (occupied) {
            for (unsigned segment = 0; segment < length; ++segment) {
                ap_uint<512> word = 0;
                for (unsigned lane = 0; lane < 16; ++lane) {
                    const unsigned value = lane % 3 == 0 ? 0x80000000U
                        : ((source + lane) % 32) | ((segment + 1) << 19);
                    word.range(lane * 32 + 31, lane * 32) = value;
                }
                const unsigned bank = (segments < 4 ? 0 : 1) +
                    (segments % 2 ? 2 : 0);
                pma[bank][segments / 2] = word;
                ++segments;
            }
        }
        rows[source] = (ap_uint<64>(begin) << 32) | (segments * 16);
    }
    hls::stream<packet_t> expected;
    hls::stream<packet_t> actual;
    reference::reference_adapter(pma[0].data(), pma[1].data(), pma[2].data(),
        pma[3].data(), rows.data(), vertices, segments * 16, 2, 65536, 32, expected);
    pma_to_regraph_adapter(pma[0].data(), pma[1].data(), pma[2].data(),
        pma[3].data(), rows.data(), vertices, segments * 16, 2, 65536, 32, actual);
    unsigned packets = 0;
    while (!expected.empty()) {
        assert(!actual.empty());
        const auto a = actual.read();
        const auto e = expected.read();
        assert(a.data == e.data && a.keep == e.keep && a.strb == e.strb &&
               a.last == e.last);
        ++packets;
    }
    assert(actual.empty());
    std::cout << "PMA_COSIM_CASE vertices=" << vertices
              << " placement=" << placement << " length=" << length
              << " packets=" << packets << " status=PASS\n";
    return packets;
}

}  // namespace

int main()
{
    unsigned cases = 0;
    unsigned packets = 0;
    for (unsigned vertices : {1U, 8U, 9U, 65U, 1025U}) {
        for (unsigned placement : {0U, 1U}) {
            packets += check_case(vertices, placement, 7);
            ++cases;
        }
    }
    packets += check_case(65, 2, 3);
    packets += check_case(9, 0, 0);
    packets += check_case(0, 0, 0);
    cases += 3;
    std::cout << "PMA_COSIM_RESULT status=PASS cases=" << cases
              << " packets=" << packets << '\n';
}
