#include <hls_stream.h>
#include <ap_int.h>

#include "grasu_degree_delta.hpp"

extern "C" {
void grasu_degree_update(
    hls::stream<grasu_degree_delta_pkt_t> &degree_delta,
    ap_uint<32> *out_degree,
    ap_uint<32> *status,
    unsigned vertices,
    unsigned update_count)
{
#pragma HLS INTERFACE axis port=degree_delta
#pragma HLS INTERFACE m_axi port=out_degree offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=status offset=slave bundle=gmem0
#pragma HLS INTERFACE s_axilite port=out_degree bundle=control
#pragma HLS INTERFACE s_axilite port=status bundle=control
#pragma HLS INTERFACE s_axilite port=vertices bundle=control
#pragma HLS INTERFACE s_axilite port=update_count bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    ap_uint<32> result = kDegreeUpdateOk;
    ap_uint<32> processed = 0;
    bool end_consumed = false;

update_loop:
    for (unsigned ordinal = 0; ordinal < update_count; ++ordinal) {
        const grasu_degree_delta_pkt_t packet = degree_delta.read();
        if (packet.last) {
            if (result == kDegreeUpdateOk) {
                result = kDegreeUpdateEarlyEnd;
            }
            end_consumed = true;
            break;
        }
        if (result != kDegreeUpdateOk) {
            continue;
        }
        if (degree_delta_ordinal(packet) != ordinal) {
            result = kDegreeUpdateOrdinalMismatch;
            continue;
        }

        const ap_uint<32> source = degree_delta_source(packet);
        if (source >= vertices) {
            result = kDegreeUpdateSourceOutOfRange;
            continue;
        }

        const ap_uint<32> old_degree = out_degree[source];
        if (degree_delta_is_delete(packet)) {
            if (old_degree == 0) {
                result = kDegreeUpdateUnderflow;
                continue;
            }
            out_degree[source] = old_degree - 1;
        } else {
            if (old_degree == ~ap_uint<32>(0)) {
                result = kDegreeUpdateOverflow;
                continue;
            }
            out_degree[source] = old_degree + 1;
        }
        processed++;
    }

    if (!end_consumed) {
        const grasu_degree_delta_pkt_t end = degree_delta.read();
        if (!end.last && result == kDegreeUpdateOk) {
            result = kDegreeUpdateMissingEnd;
        }
    }

    status[0] = result;
    status[1] = processed;
}
}
