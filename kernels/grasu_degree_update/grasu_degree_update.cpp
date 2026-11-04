#include <hls_stream.h>
#include <ap_int.h>

#include "grasu_degree_delta.hpp"

namespace {
constexpr unsigned kDegreeWordsPerLine = 16;
constexpr unsigned kDegreePrefixLines = 2048;
using DegreeLine = ap_uint<512>;

struct DegreeProgress {
    unsigned ordinal = 0;
    ap_uint<32> result = kDegreeUpdateOk;
    ap_uint<32> processed = 0;
    bool end_consumed = false;
    bool has_pending = false;
    grasu_degree_delta_pkt_t pending;
};

template <bool CachedOnly>
void consume_degrees(hls::stream<grasu_degree_delta_pkt_t> &degree_delta,
                     DegreeLine *out_degree, DegreeLine *cache, unsigned lines,
                     unsigned vertices, unsigned update_count,
                     DegreeProgress &progress)
{
#pragma HLS INLINE
    unsigned ordinal = progress.ordinal;
    bool has_pending = progress.has_pending;
update_loop:
    for (; ordinal < update_count; ++ordinal) {
        const grasu_degree_delta_pkt_t packet =
            has_pending ? progress.pending : degree_delta.read();
        has_pending = false;
        if (packet.last) {
            if (progress.result == kDegreeUpdateOk) {
                progress.result = kDegreeUpdateEarlyEnd;
            }
            progress.end_consumed = true;
            break;
        }
        if (progress.result != kDegreeUpdateOk) {
            continue;
        }
        if (degree_delta_ordinal(packet) != ordinal) {
            progress.result = kDegreeUpdateOrdinalMismatch;
            continue;
        }

        const ap_uint<32> source = degree_delta_source(packet);
        if (source >= vertices) {
            progress.result = kDegreeUpdateSourceOutOfRange;
            continue;
        }

        const unsigned index = static_cast<unsigned>(source) / kDegreeWordsPerLine;
        const unsigned low_bit = (static_cast<unsigned>(source) % kDegreeWordsPerLine) * 32;
        if (CachedOnly && index >= lines) {
            progress.pending = packet;
            has_pending = true;
            break;
        }
        const bool cached = CachedOnly || index < lines;
        DegreeLine line = cached ? cache[index] : out_degree[index];
        const ap_uint<32> old_degree = line.range(low_bit + 31, low_bit);
        ap_uint<32> new_degree;
        if (degree_delta_is_delete(packet)) {
            if (old_degree == 0) {
                progress.result = kDegreeUpdateUnderflow;
                continue;
            }
            new_degree = old_degree - 1;
        } else {
            if (old_degree == ~ap_uint<32>(0)) {
                progress.result = kDegreeUpdateOverflow;
                continue;
            }
            new_degree = old_degree + 1;
        }
        line.range(low_bit + 31, low_bit) = new_degree;
        if (cached) {
            cache[index] = line;
        } else {
            out_degree[index] = line;
        }
        progress.processed++;
    }
    progress.ordinal = ordinal;
    progress.has_pending = has_pending;
}
}

extern "C" {
void grasu_degree_update(
    hls::stream<grasu_degree_delta_pkt_t> &degree_delta,
    DegreeLine *out_degree,
    ap_uint<32> *status,
    unsigned vertices,
    unsigned update_count,
    unsigned active_source_prefix)
{
#pragma HLS INTERFACE axis port=degree_delta
#pragma HLS INTERFACE m_axi port=out_degree offset=slave bundle=gmem0 max_read_burst_length=32 max_write_burst_length=32
#pragma HLS INTERFACE m_axi port=status offset=slave bundle=gmem0
#pragma HLS INTERFACE s_axilite port=out_degree bundle=control
#pragma HLS INTERFACE s_axilite port=status bundle=control
#pragma HLS INTERFACE s_axilite port=vertices bundle=control
#pragma HLS INTERFACE s_axilite port=update_count bundle=control
#pragma HLS INTERFACE s_axilite port=active_source_prefix bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    // The state buffer is padded to whole lines. The prefix is a hint,
    // not a requirement for processing a packet correctly.
    unsigned prefix = active_source_prefix < vertices ? active_source_prefix : vertices;
    if (prefix > kDegreePrefixLines * kDegreeWordsPerLine) {
        prefix = kDegreePrefixLines * kDegreeWordsPerLine;
    }
    const unsigned lines = update_count >= 16 && (prefix + 3) / 4 <= update_count
                               ? (prefix + kDegreeWordsPerLine - 1) / kDegreeWordsPerLine
                               : 0;
    DegreeLine cache[kDegreePrefixLines];
#pragma HLS BIND_STORAGE variable=cache type=ram_1p impl=uram

load_prefix:
    for (unsigned i = 0; i < lines; ++i) {
#pragma HLS PIPELINE II=1
        cache[i] = out_degree[i];
    }

    DegreeProgress progress;
    if (lines != 0) {
        // Keep HBM latency out of the schedule of the on-chip update loop.
        consume_degrees<true>(degree_delta, out_degree, cache, lines,
                              vertices, update_count, progress);
    }
    if (progress.ordinal < update_count && !progress.end_consumed) {
        consume_degrees<false>(degree_delta, out_degree, cache, lines,
                               vertices, update_count, progress);
    }

    if (!progress.end_consumed) {
        const grasu_degree_delta_pkt_t end = degree_delta.read();
        if (!end.last && progress.result == kDegreeUpdateOk) {
            progress.result = kDegreeUpdateMissingEnd;
        }
    }

store_prefix:
    for (unsigned i = 0; i < lines; ++i) {
#pragma HLS PIPELINE II=1
        out_degree[i] = cache[i];
    }

    status[0] = progress.result;
    status[1] = progress.processed;
}
}
