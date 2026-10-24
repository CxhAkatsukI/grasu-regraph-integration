#pragma once
#include "types.hpp"

namespace framed_regraph {
// Source responses continue filling the two windows while edge input is empty.
static void scatter(hls::stream<EdgePacket> &edges,
                    hls::stream<l_ppb_request_pkt> &requests,
                    hls::stream<l_ppb_response_pkt> &responses,
                    hls::stream<Updates> &output) {
#pragma HLS INLINE OFF
    ap_uint<512> cache[SCATTER_PE_NUM][2][SRC_BUFFER_SIZE >> 4];
#pragma HLS ARRAY_PARTITION variable=cache dim=1 complete
#pragma HLS BIND_STORAGE variable=cache type=RAM_S2P impl=BRAM
    unsigned read_round = 0, write_round = 0, request_round = 0;
    EdgePacket edge;
    bool held = false, terminal = false;
    while (!terminal) {
#pragma HLS PIPELINE II=1
        if ((long long)request_round - read_round <= 1) {
            if (request_round < read_round) request_round = read_round;
            l_ppb_request_pkt request;
            request.data = request_round;
            request.keep = -1;
            request.strb = -1;
            request.last = 0;
            if (requests.write_nb(request)) ++request_round;
        }
        l_ppb_response_pkt response;
        if (responses.read_nb(response)) {
            unsigned address = response.dest;
            write_round = address / (SRC_BUFFER_SIZE >> 4);
            unsigned row = address % (SRC_BUFFER_SIZE >> 4);
            for (unsigned lane = 0; lane < SCATTER_PE_NUM; ++lane) {
#pragma HLS UNROLL
                cache[lane][write_round & 1][row] = response.data;
            }
        }
        if (!held) held = edges.read_nb(edge);
        if (!held) continue;
        read_round = (unsigned)edge.data.range(30, 0) / SRC_BUFFER_SIZE;
        // Seeing the following window proves all lines of this one arrived.
        if (read_round >= write_round || output.full()) continue;
        Updates updates;
        updates.last = edge.last;
        for (unsigned lane = 0; lane < SCATTER_PE_NUM; ++lane) {
#pragma HLS UNROLL
            unsigned src = edge.data.range(lane * 64 + 30, lane * 64);
            ap_uint<32> dst = edge.data.range(lane * 64 + 63, lane * 64 + 32);
            unsigned index = src % SRC_BUFFER_SIZE;
            ap_uint<512> line = cache[lane][read_round & 1][index / 16];
            ap_uint<32> prop = line.range((index % 16) * 32 + 31, (index % 16) * 32);
#if HAVE_EDGE_PROP
            ap_uint<32> weight = dst.range(30, 19);
#else
            ap_uint<32> weight = 0;
#endif
            updates.values.tuples[lane].update =
                PROP_COMPUTE_STAGE1(PROP_COMPUTE_STAGE0(prop), weight);
            ap_uint<20> local = 0;
            local.range(18, 0) = dst.range(18, 0);
            local[19] = dst[31];
            updates.values.tuples[lane].dst = local;
            updates.values.tuples[lane].end_flag = updates.last;
        }
        output.write(updates);
        terminal = edge.last;
        held = false;
    }
    l_ppb_request_pkt end;
    end.data = request_round ? request_round - 1 : 0;
    end.keep = -1;
    end.strb = -1;
    end.last = 1;
    requests.write(end);
    while (!responses.read().last) {}
}
}
