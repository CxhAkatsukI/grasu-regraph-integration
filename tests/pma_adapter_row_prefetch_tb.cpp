#include <hls_stream.h>
#include <hls_streamofblocks.h>
#include <ap_axi_sdata.h>
#include <ap_int.h>

#include <cassert>
#include <iostream>
#include <vector>

#ifndef GRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS
#define GRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS 1
#endif
#ifndef GRASU_REGRAPH_SHARDED_PMA
#define GRASU_REGRAPH_SHARDED_PMA 1
#endif
#ifndef GRASU_REGRAPH_WEIGHTED_PMA
#define GRASU_REGRAPH_WEIGHTED_PMA 1
#endif
#ifndef PMA_ADAPTER_TEST_SKIP_EMPTY
#define PMA_ADAPTER_TEST_SKIP_EMPTY 0
#endif
#ifndef PMA_ADAPTER_TEST_ROW_LINE
#define PMA_ADAPTER_TEST_ROW_LINE 0
#endif
#ifndef PMA_ADAPTER_TEST_CROSS_ROW
#define PMA_ADAPTER_TEST_CROSS_ROW 0
#endif

namespace baseline {
#define pma_to_regraph_adapter baseline_adapter
#include "../kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
#undef pma_to_regraph_adapter
}

namespace candidate {
#undef GRASU_REGRAPH_ROW_PREFETCH
#define GRASU_REGRAPH_ROW_PREFETCH 1
#undef GRASU_REGRAPH_STOP_AFTER_LAST
#define GRASU_REGRAPH_STOP_AFTER_LAST 1
#undef GRASU_REGRAPH_SKIP_EMPTY_SEGMENT
#define GRASU_REGRAPH_SKIP_EMPTY_SEGMENT PMA_ADAPTER_TEST_SKIP_EMPTY
#undef GRASU_REGRAPH_ROW_LINE_READ
#define GRASU_REGRAPH_ROW_LINE_READ PMA_ADAPTER_TEST_ROW_LINE
#undef GRASU_REGRAPH_CROSS_ROW_PIPELINE
#define GRASU_REGRAPH_CROSS_ROW_PIPELINE PMA_ADAPTER_TEST_CROSS_ROW
#define pma_to_regraph_adapter prefetched_adapter
#include "../kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
#undef pma_to_regraph_adapter
}

int main()
{
    unsigned cases = 0;
    unsigned packets = 0;
    const auto run_candidate = [](const std::vector<ap_uint<512>> (&pma)[4],
                                  const std::vector<ap_uint<64>> &rows,
                                  unsigned capacity,
                                  hls::stream<candidate::edge_burst_pkt_t> &out) {
#if PMA_ADAPTER_TEST_ROW_LINE
        std::vector<ap_uint<512>> lines((rows.size() + 7) / 8 + (rows.empty() ? 1 : 0));
        for (auto &line : lines) line = -1;
        for (unsigned row = 0; row < rows.size(); ++row)
            lines[row / 8].range((row % 8) * 64 + 63, (row % 8) * 64) = rows[row];
        const auto *row_data = lines.data();
#else
        const auto *row_data = rows.data();
#endif
        candidate::prefetched_adapter(pma[0].data(), pma[1].data(), pma[2].data(),
            pma[3].data(), row_data, rows.size(), capacity, 2, 65536, 32, out);
    };
    for (unsigned vertices : {0U, 1U, 7U, 8U, 9U, 15U, 16U, 17U, 65U}) {
        for (unsigned density : {0U, 1U, 3U}) {
          for (unsigned placement : {0U, 1U, 2U}) {
            std::vector<ap_uint<64>> rows(vertices);
            std::vector<ap_uint<512>> pma[4];
            for (auto &bank : pma) bank.resize(256);
            unsigned segments = 0;
            for (unsigned source = 0; source < vertices; ++source) {
                const bool occupied = placement == 0 ? source % 3 == 0
                    : placement == 1 ? source == 0 : source + 1 == vertices;
                const unsigned length = occupied ? density : 0;
                const unsigned begin = segments * 16;
                for (unsigned s = 0; s < length; ++s) {
                    ap_uint<512> word = 0;
                    for (unsigned lane = 0; lane < 16; ++lane) {
                        const unsigned value = lane % 3 == 0 ? 0x80000000U
                            : ((source + lane) % 32) | ((s + 1) << 19);
                        word.range(lane * 32 + 31, lane * 32) = value;
                    }
                    const unsigned bank = (segments < 4 ? 0 : 1) +
                        (segments % 2 ? 2 : 0);
                    pma[bank][segments / 2] = word;
                    ++segments;
                }
                rows[source] = (ap_uint<64>(begin) << 32) | (segments * 16);
            }
            for (unsigned capacity : {segments * 16, segments * 16 + 16,
                                      segments ? segments * 16 - 16 : 0}) {
                hls::stream<baseline::edge_burst_pkt_t> before;
                hls::stream<candidate::edge_burst_pkt_t> after;
                baseline::baseline_adapter(pma[0].data(), pma[1].data(), pma[2].data(),
                    pma[3].data(), rows.data(), vertices, capacity, 2, 65536, 32, before);
                run_candidate(pma, rows, capacity, after);
                while (!before.empty()) {
                    assert(!after.empty());
                    const auto left = before.read();
                    const auto right = after.read();
                    assert(left.data == right.data && left.keep == right.keep &&
                           left.strb == right.strb && left.last == right.last);
                    ++packets;
                }
                assert(after.empty());
                ++cases;
            }
          }
        }
    }
    const auto check_boundary = [&](const std::vector<ap_uint<64>> &rows,
                                     unsigned capacity, unsigned expected_packets,
                                     unsigned dummy_prefix) {
        std::vector<ap_uint<512>> pma[4];
        ap_uint<512> dummy_word = 0;
        for (unsigned lane = 0; lane < 16; ++lane)
            dummy_word.range(lane * 32 + 31, lane * 32) = 0x80000000U;
        for (auto &bank : pma) bank.assign(8, dummy_word);
        // The first allocated segment is an all-dummy source-zero reservation.
        // Later segments carry live lanes, even when row bounds mask them out.
        pma[2][0] = 1;
        hls::stream<baseline::edge_burst_pkt_t> before;
        hls::stream<candidate::edge_burst_pkt_t> after;
        baseline::baseline_adapter(pma[0].data(), pma[1].data(), pma[2].data(),
            pma[3].data(), rows.data(), rows.size(), capacity, 2, 65536, 32, before);
        run_candidate(pma, rows, capacity, after);
        unsigned seen = 0;
        while (!before.empty()) {
            assert(!after.empty());
            const auto left = before.read();
            const auto right = after.read();
            assert(left.data == right.data && left.keep == right.keep &&
                   left.strb == right.strb && left.last == right.last);
            if (seen < dummy_prefix) {
                for (unsigned lane = 0; lane < 8; ++lane) {
                    assert(left.data[lane * 64 + 31]);
                    assert(left.data[lane * 64 + 63]);
                }
            }
            ++seen;
        }
        assert(after.empty() && seen == expected_packets);
        packets += seen;
        ++cases;
    };
    const auto bounds = [](unsigned begin, unsigned end) -> ap_uint<64> {
        return (ap_uint<64>(begin) << 32) | end;
    };
    // Unaligned begin==end still emits masked packets in the legacy ABI.
    for (unsigned offset : {1U, 7U, 15U, 17U})
        check_boundary({bounds(offset, offset)}, 64, 2, 2);
    for (unsigned offset : {0U, 16U, 32U})
        check_boundary({bounds(offset, offset)}, 64, 0, 0);
    check_boundary({bounds(0, 16)}, 16, 2, 2);
    check_boundary({bounds(0, 16), bounds(16, 32)}, 32, 4, 2);
    check_boundary({bounds(3, 19)}, 64, 4, 2);
    check_boundary({bounds(32, 48)}, 16, 0, 0);
    std::cout << "ROW_PREFETCH_EQUIVALENCE status=PASS cases=" << cases
              << " packets=" << packets
              << " skip_empty=" << PMA_ADAPTER_TEST_SKIP_EMPTY;
#if PMA_ADAPTER_TEST_ROW_LINE
    std::cout << " row_line=1";
#endif
#if PMA_ADAPTER_TEST_CROSS_ROW
    std::cout << " cross_row=1";
#endif
    std::cout << '\n';
}
