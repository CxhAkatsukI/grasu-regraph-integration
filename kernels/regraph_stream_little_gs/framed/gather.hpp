#pragma once
#include "types.hpp"

namespace framed_regraph {
static void gather(hls::stream<Updates> &input,
                   hls::stream<ap_uint<64>> (&output)[GATHER_PE_NUM],
                   bool reset) {
#pragma HLS INLINE OFF
    static ap_uint<64> memory[GATHER_PE_NUM][LITTLE_KERNEL_DST_BUFFER_SIZE >> 1];
#pragma HLS ARRAY_PARTITION variable=memory dim=1 complete
#pragma HLS BIND_STORAGE variable=memory type=RAM_S2P impl=URAM
#pragma HLS DEPENDENCE variable=memory inter false
    if (reset) {
        for (unsigned row = 0; row < (LITTLE_KERNEL_DST_BUFFER_SIZE >> 1); ++row) {
#pragma HLS PIPELINE II=1
            for (unsigned lane = 0; lane < GATHER_PE_NUM; ++lane) {
#pragma HLS UNROLL
                memory[lane][row] = 0;
            }
        }
    }
    ap_uint<64> last_value[GATHER_PE_NUM][L + 1];
    unsigned last_index[GATHER_PE_NUM][L + 1];
#pragma HLS ARRAY_PARTITION variable=last_value complete dim=0
#pragma HLS ARRAY_PARTITION variable=last_index complete dim=0
    for (unsigned history = 0; history <= L; ++history) {
        for (unsigned lane = 0; lane < GATHER_PE_NUM; ++lane) {
#pragma HLS UNROLL
            last_value[lane][history] = 0;
            last_index[lane][history] = 0;
        }
    }
    bool terminal = false;
    while (!terminal) {
#pragma HLS PIPELINE II=1
        Updates updates = input.read();
        terminal = updates.last;
        for (unsigned lane = 0; lane < GATHER_PE_NUM; ++lane) {
#pragma HLS UNROLL
            auto tuple = updates.values.tuples[lane];
            if (!tuple.dst[19] && IS_ACTIVE_VERTEX(tuple.update)) {
                unsigned dst = (unsigned)tuple.dst & (LITTLE_KERNEL_DST_BUFFER_SIZE - 1);
                unsigned row = dst / 2;
                ap_uint<64> value = memory[lane][row];
                for (unsigned h = 0; h <= L; ++h) {
#pragma HLS UNROLL
                    if (last_index[lane][h] == row) value = last_value[lane][h];
                }
                for (unsigned h = 0; h < L; ++h) {
#pragma HLS UNROLL
                    last_value[lane][h] = last_value[lane][h + 1];
                    last_index[lane][h] = last_index[lane][h + 1];
                }
                unsigned old = dst & 1 ? (unsigned)value.range(63, 32) :
                                         (unsigned)value.range(31, 0);
                unsigned reduced = PROP_COMPUTE_STAGE3(old, (unsigned)tuple.update);
                if (dst & 1) value.range(63, 32) = reduced;
                else value.range(31, 0) = reduced;
                memory[lane][row] = value;
                last_value[lane][L] = value;
                last_index[lane][L] = row;
            }
        }
    }
    // Publication clears every row. Only the first physical invocation needs init.
    for (unsigned row = 0; row < (LITTLE_KERNEL_DST_BUFFER_SIZE >> 1); ++row) {
#pragma HLS PIPELINE II=1
        for (unsigned lane = 0; lane < GATHER_PE_NUM; ++lane) {
#pragma HLS UNROLL
            ap_uint<64> value = memory[lane][row];
            memory[lane][row] = 0;
            output[lane].write(value);
        }
    }
}

static void merge(hls::stream<ap_uint<64>> (&input)[GATHER_PE_NUM],
                  hls::stream<l_tmp_prop_pkt> &output) {
#pragma HLS INLINE OFF
    for (unsigned row = 0; row < (LITTLE_KERNEL_DST_BUFFER_SIZE >> 1); ++row) {
#pragma HLS PIPELINE II=1
        unsigned low = 0, high = 0;
        for (unsigned lane = 0; lane < GATHER_PE_NUM; ++lane) {
#pragma HLS UNROLL
            ap_uint<64> value = input[lane].read();
            low = PROP_COMPUTE_STAGE3(low, (unsigned)value.range(31, 0));
            high = PROP_COMPUTE_STAGE3(high, (unsigned)value.range(63, 32));
        }
        l_tmp_prop_pkt packet;
        packet.data.range(31, 0) = low;
        packet.data.range(63, 32) = high;
        packet.keep = -1;
        packet.strb = -1;
        packet.last = row + 1 == (LITTLE_KERNEL_DST_BUFFER_SIZE >> 1);
        output.write(packet);
    }
}
}
