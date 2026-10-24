#pragma once
#include "scatter.hpp"
#include "gather.hpp"
#ifndef __SYNTHESIS__
#include <thread>
#endif

namespace framed_regraph {
static void run(hls::stream<EdgePacket> &edges, bool reset,
                hls::stream<l_ppb_request_pkt> &requests,
                hls::stream<l_ppb_response_pkt> &responses,
                hls::stream<l_tmp_prop_pkt> &output) {
#pragma HLS INLINE OFF
#pragma HLS DATAFLOW
    hls::stream<Updates> updates;
    hls::stream<ap_uint<64>> values[GATHER_PE_NUM];
#pragma HLS STREAM variable=updates depth=8
#pragma HLS STREAM variable=values depth=8
#ifdef __SYNTHESIS__
    scatter(edges, requests, responses, updates);
    gather(updates, values, reset);
    merge(values, output);
#else
    std::thread s([&] { scatter(edges, requests, responses, updates); });
    std::thread g([&] { gather(updates, values, reset); });
    merge(values, output);
    s.join(); g.join();
#endif
}
}
