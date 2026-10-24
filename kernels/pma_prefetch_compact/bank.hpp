#pragma once
#include "memory.hpp"

namespace pma_compact {
struct Parent { ap_uint<5> length; bool external; };

static void request_bank(hls::burst_maxi<Word> &cache,
                         hls::burst_maxi<Word> &external,
                         unsigned cache_lines, unsigned total,
                         hls::stream<Parent> &parents,
                         hls::stream<bool> &completed,
                         hls::stream<bool> &released) {
#pragma HLS INLINE OFF
    unsigned issued = 0, retired = 0;
    ap_uint<5> outstanding = 0;
    ap_uint<10> reserved = 0;
    while (retired < total || outstanding) {
#pragma HLS PIPELINE II=1
        bool credit;
        if (released.read_nb(credit)) { ++retired; --reserved; }
        if (completed.read_nb(credit)) --outstanding;
        unsigned length = total - issued;
        if (length > kBurst) length = kBurst;
        if (issued < cache_lines) {
            const unsigned cached_remaining = cache_lines - issued;
            if (length > cached_remaining) length = cached_remaining;
        }
        if (length && outstanding < kParents &&
            reserved + ap_uint<10>(length) <= kRingLines) {
            const bool ext = issued >= cache_lines;
            if (ext) request(external, issued, length);
            else request(cache, issued, length);
            parents.write(Parent{ap_uint<5>(length), ext});
            ++outstanding;
            reserved += length;
            issued += length;
        }
    }
    parents.write(Parent{0, false});
}

static void receive_bank(hls::burst_maxi<Word> &cache,
                         hls::burst_maxi<Word> &external,
                         hls::stream<Parent> &parents,
                         hls::stream<bool> &completed,
                         hls::stream<Word> &output) {
#pragma HLS INLINE OFF
    while (true) {
        const Parent parent = parents.read();
        if (!parent.length) break;
        for (unsigned beat = 0; beat < parent.length; ++beat) {
#pragma HLS PIPELINE II=1
            output.write(parent.external ? response(external) : response(cache));
        }
        completed.write(true);
    }
}

static void bank_dataflow(hls::burst_maxi<Word> &cache,
                          hls::burst_maxi<Word> &external,
                          unsigned cache_lines, unsigned total,
                          hls::stream<Word> &output,
                          hls::stream<bool> &released) {
#pragma HLS INLINE OFF
#pragma HLS DATAFLOW
    hls::stream<Parent> parents;
    hls::stream<bool> completed;
#pragma HLS STREAM variable=parents depth=16
#pragma HLS STREAM variable=completed depth=16
#ifdef __SYNTHESIS__
    request_bank(cache, external, cache_lines, total, parents, completed, released);
    receive_bank(cache, external, parents, completed, output);
#else
    std::thread requests([&] {
        request_bank(cache, external, cache_lines, total, parents, completed, released);
    });
    receive_bank(cache, external, parents, completed, output);
    requests.join();
#endif
}

static void read_bank(hls::burst_maxi<Word> &cache,
                      hls::burst_maxi<Word> &external, unsigned cache_lines,
                      hls::stream<unsigned> &extent,
                      hls::stream<Word> &output, hls::stream<bool> &released) {
#pragma HLS INLINE OFF
    bank_dataflow(cache, external, cache_lines, extent.read(), output, released);
}
}
