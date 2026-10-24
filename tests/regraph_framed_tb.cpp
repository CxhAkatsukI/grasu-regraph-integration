#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <thread>
#include <vector>
#include "../kernels/regraph_stream_little_gs/little_gs_stream.cpp"
#if TEST_COMPACT_INPUT
#define GRASU_REGRAPH_WEIGHTED_PMA HAVE_EDGE_PROP
#define GRASU_REGRAPH_DESTINATION_ONLY (!HAVE_EDGE_PROP)
#include "../kernels/pma_prefetch_compact/top.cpp"
#endif

static unsigned source_property(unsigned source) {
#if TEST_PAGERANK
    float value = (int(source % 9) - 4) * 0.125f;
    unsigned bits;
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
#else
    return (source % 7 == 0 ? 0U : 0x80000000U) | (source % 113);
#endif
}

static unsigned reduce(unsigned a, unsigned b) {
#if TEST_PAGERANK
    float x, y;
    std::memcpy(&x, &a, sizeof(x));
    std::memcpy(&y, &b, sizeof(y));
    x += y;
    std::memcpy(&a, &x, sizeof(a));
    return a;
#else
    if (!(b & 0x80000000U)) return a;
    return !(a & 0x80000000U) || (b & 0x7fffffffU) < (a & 0x7fffffffU) ? b : a;
#endif
}

#if TEST_COMPACT_INPUT
static void compacted_input(hls::stream<edge_burst_pkt_t> &edges,
                            std::vector<std::vector<unsigned>> &oracle,
                            bool empty) {
    const unsigned vertices = 8193;
    std::vector<ap_uint<512>> rows((vertices + 7) / 8 + 1, 0);
    std::vector<ap_uint<512>> banks[4];
    for (auto &bank : banks) bank.resize(vertices * 2 + 1, 0);
    unsigned segments = 0;
    for (unsigned src = 0; src < vertices; ++src) {
        unsigned begin = segments * 16;
        unsigned length = !empty && src % 31 == 0 ? src % 3 + 1 : 0;
        for (unsigned j = 0; j < length; ++j) {
            ap_uint<512> word = 0;
            for (unsigned lane = 0; lane < 16; ++lane) {
                unsigned dst = lane % 5 == 0 ? 65535 : (src + lane) % 127;
                unsigned weight = (src + j + lane) % 13;
                bool dummy = (j + lane) % 11 == 0;
                unsigned encoded = dst | (dummy ? 0x80000000U : 0U);
#if HAVE_EDGE_PROP
                encoded |= weight << 19;
#endif
                word.range(lane * 32 + 31, lane * 32) = encoded;
                if (dummy) continue;
                unsigned update = source_property(src);
#if HAVE_EDGE_PROP
                if (!weight) continue;
                update = update & 0x80000000U ?
                    ((update & 0x7fffffffU) + weight) | 0x80000000U : 0;
#endif
                oracle[0][dst] = reduce(oracle[0][dst], update);
            }
            unsigned bank = (segments < 4 ? 0 : 1) + (segments % 2 ? 2 : 0);
            banks[bank][segments / 2] = word;
            ++segments;
        }
        rows[src / 8].range((src % 8) * 64 + 63, (src % 8) * 64) =
            (ap_uint<64>(begin) << 32) | (segments * 16);
    }
    pma_to_regraph_adapter(banks[0].data(), banks[1].data(), banks[2].data(),
        banks[3].data(), rows.data(), vertices, segments * 16, 2, 131072,
        65536, edges);
}
#endif

static void check(unsigned invocation, bool empty) {
    hls::stream<edge_burst_pkt_t> edges;
    hls::stream<l_ppb_request_pkt> requests;
    hls::stream<l_ppb_response_pkt> responses;
    hls::stream<l_tmp_prop_pkt> results;
    std::vector<std::vector<unsigned>> oracle(8, std::vector<unsigned>(65536));
#if TEST_COMPACT_INPUT
    std::thread adapter([&] { compacted_input(edges, oracle, empty); });
#else
    // Gaps force independent preload to jump over source windows with no edges.
    const unsigned windows[] = {0, 1, 4, 5};
    unsigned packets = empty ? 1 : 24;
    for (unsigned p = 0; p < packets; ++p) {
        edge_burst_pkt_t packet;
        packet.data = 0;
        unsigned window = empty ? 0 : windows[p / 6];
        for (unsigned lane = 0; lane < 8; ++lane) {
            unsigned src = window * 4096 + (p * 19 + lane * 7) % 4096;
            unsigned dst = p % 3 == 0 ? 65535 : (p * 31 + lane) % 127;
            unsigned weight = (p + lane) % 13 + 1;
            bool dummy = empty || (p + lane) % 11 == 0;
            unsigned encoded_dst = dst | (dummy ? 0x80000000U : 0);
#if HAVE_EDGE_PROP
            encoded_dst |= weight << 19;
#endif
            packet.data.range(lane * 64 + 31, lane * 64) = src;
            packet.data.range(lane * 64 + 63, lane * 64 + 32) = encoded_dst;
            if (dummy) continue;
            unsigned update = source_property(src);
#if HAVE_EDGE_PROP
            if (update & 0x80000000U)
                update = ((update & 0x7fffffffU) + weight) | 0x80000000U;
            else update = 0;
#endif
            oracle[lane][dst] = reduce(oracle[lane][dst], update);
        }
        packet.keep = -1;
        packet.strb = -1;
        packet.last = p + 1 == packets;
        edges.write(packet);
    }
#endif
    unsigned request_count = 0;
    std::thread source([&] {
        while (true) {
            auto request = requests.read();
            if (request.last) {
                l_ppb_response_pkt end;
                end.data = 0; end.dest = 0; end.last = 1;
                responses.write(end);
                return;
            }
            ++request_count;
            unsigned window = request.data;
            for (unsigned row = 0; row < 256; ++row) {
                l_ppb_response_pkt response;
                response.data = 0;
                for (unsigned lane = 0; lane < 16; ++lane)
                    response.data.range(lane * 32 + 31, lane * 32) =
                        source_property(window * 4096 + row * 16 + lane);
                response.dest = window * 256 + row;
                response.keep = -1; response.strb = -1; response.last = 0;
                responses.write(response);
            }
        }
    });
    // A deliberately wrong slot count verifies TLAST, not a scalar edge count,
    // controls termination. The nonzero base must not be subtracted a second time.
    lksg_stream(edges, 123456, 0, 131072, invocation == 0,
                requests, responses, results);
    source.join();
#if TEST_COMPACT_INPUT
    adapter.join();
#endif
    for (unsigned row = 0; row < 32768; ++row) {
        auto packet = results.read();
        for (unsigned half = 0; half < 2; ++half) {
            unsigned expected = 0;
            for (unsigned lane = 0; lane < 8; ++lane)
                expected = reduce(expected, oracle[lane][row * 2 + half]);
            assert((unsigned)packet.data.range(half * 32 + 31, half * 32) == expected);
        }
        assert(bool(packet.last) == (row == 32767));
    }
    assert(edges.empty() && requests.empty() && responses.empty() && results.empty());
    assert(request_count >= 2);
}

int main() {
    for (unsigned invocation = 0; invocation < 6; ++invocation)
        check(invocation, invocation == 1 || invocation == 4);
    std::cout << "REGRAPH_FRAMED PASS invocations=6 policies=1 reset_reuse=5"
              << " connected_adapter=" << TEST_COMPACT_INPUT << "\n";
}
