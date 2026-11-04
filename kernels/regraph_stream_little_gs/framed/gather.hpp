#pragma once
#include "types.hpp"

namespace framed_regraph {
constexpr unsigned kFullShardRows = LITTLE_KERNEL_DST_BUFFER_SIZE >> 1;
#if GRASU_REGRAPH_BANKED_GATHER_CLEAR
constexpr unsigned kClearBanks = 4;
static_assert(kFullShardRows % kClearBanks == 0, "gather banks must have equal depth");
constexpr unsigned kClearGroups = kFullShardRows / kClearBanks;
#endif

static void gather(hls::stream<Updates> &input,
                   hls::stream<ap_uint<64>> (&output)[GATHER_PE_NUM],
                   bool reset, unsigned row_count) {
#pragma HLS INLINE OFF
    static ap_uint<64> memory[GATHER_PE_NUM][kFullShardRows];
    static unsigned initialized_rows = 0;
#pragma HLS ARRAY_PARTITION variable=memory dim=1 complete
#if GRASU_REGRAPH_BANKED_GATHER_CLEAR
#pragma HLS ARRAY_PARTITION variable=memory dim=2 cyclic factor=4
#endif
#pragma HLS BIND_STORAGE variable=memory type=RAM_S2P impl=URAM
#pragma HLS DEPENDENCE variable=memory inter false
    const unsigned clear_begin = reset ? 0 : initialized_rows;
    if (row_count > clear_begin) {
#if GRASU_REGRAPH_BANKED_GATHER_CLEAR
        // The prior publication left its prefix clear, so clearing a partial bank group again is safe.
        const unsigned first_group = clear_begin / kClearBanks;
        const unsigned last_group = (row_count + kClearBanks - 1) / kClearBanks;
    clear_gather_banks:
        for (unsigned group = first_group; group < last_group; ++group) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=0 max=kClearGroups
            for (unsigned lane = 0; lane < GATHER_PE_NUM; ++lane) {
#pragma HLS UNROLL
                for (unsigned bank = 0; bank < kClearBanks; ++bank) {
#pragma HLS UNROLL
                    memory[lane][group * kClearBanks + bank] = 0;
                }
            }
        }
#else
    clear_gather_rows:
        for (unsigned row = clear_begin; row < row_count; ++row) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=0 max=kFullShardRows
            for (unsigned lane = 0; lane < GATHER_PE_NUM; ++lane) {
#pragma HLS UNROLL
                memory[lane][row] = 0;
            }
        }
#endif
    }
    initialized_rows = row_count > clear_begin ? row_count : clear_begin;
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
scatter_gather_rows:
    while (!terminal) {
#pragma HLS PIPELINE II=1
        Updates updates = input.read();
        terminal = updates.last;
        for (unsigned lane = 0; lane < GATHER_PE_NUM; ++lane) {
#pragma HLS UNROLL
            auto tuple = updates.values.tuples[lane];
            const unsigned dst = (unsigned)tuple.dst & (LITTLE_KERNEL_DST_BUFFER_SIZE - 1);
            const unsigned row = dst / 2;
            if (!tuple.dst[19] && row < row_count && IS_ACTIVE_VERTEX(tuple.update)) {
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
    // A completed frame leaves the initialized prefix clear for the next shard.
publish_gather_rows:
    for (unsigned row = 0; row < row_count; ++row) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=1 max=kFullShardRows
        for (unsigned lane = 0; lane < GATHER_PE_NUM; ++lane) {
#pragma HLS UNROLL
            ap_uint<64> value = memory[lane][row];
            memory[lane][row] = 0;
            output[lane].write(value);
        }
    }
}

static void merge(hls::stream<ap_uint<64>> (&input)[GATHER_PE_NUM],
                  hls::stream<l_tmp_prop_pkt> &output, unsigned row_count) {
#pragma HLS INLINE OFF
    for (unsigned row = 0; row < row_count; ++row) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=1 max=kFullShardRows
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
        packet.last = row + 1 == row_count;
        output.write(packet);
    }
}
}
