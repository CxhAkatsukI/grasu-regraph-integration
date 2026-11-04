#include <cassert>
#include <hls_stream.h>

#include "acc_config.h"
#include "acc_data_types.h"
#include "fpga_application.h"

namespace {
constexpr unsigned kRowsPerBeat = 8;
constexpr unsigned kBeatsPerShard = LITTLE_KERNEL_DST_BUFFER_SIZE / 16;
static_assert(LITTLE_KERNEL_NUM == 1 && BIG_KERNEL_NUM == 0);
static_assert(LITTLE_KERNEL_DST_BUFFER_SIZE % 16 == 0);

static void publish_beat(hls::stream<write_burst_pkt> &output,
                         ap_uint<512> value) {
#pragma HLS INLINE
    write_burst_pkt beat;
    beat.data = value;
    beat.dest = 0;
    beat.keep = -1;
    beat.strb = -1;
    beat.last = 0;
    output.write(beat);
}

static void merge_one_shard(hls::stream<l_tmp_prop_pkt> &input,
                            hls::stream<write_burst_pkt> &output) {
#pragma HLS INLINE
    ap_uint<512> packed = 0;
    ap_uint<3> lane = 0;
    unsigned beats = 0;
    bool last = false;
pack_valid_rows:
    while (!last) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=8 max=LITTLE_KERNEL_DST_BUFFER_SIZE/2
        const l_tmp_prop_pkt row = input.read();
        ap_uint<64> merged;
        merged.range(31, 0) = PROP_COMPUTE_STAGE4(0U, row.data.range(31, 0));
        merged.range(63, 32) = PROP_COMPUTE_STAGE4(0U, row.data.range(63, 32));
        // Rows arrive low to high. After eight shifts, the first is lane zero.
        packed = (ap_uint<512>(merged) << 448) | (packed >> 64);
        if (lane == kRowsPerBeat - 1) {
            publish_beat(output, packed);
            ++beats;
        }
        ++lane;
        last = row.last;
#ifndef __SYNTHESIS__
        assert((!last || lane == 0) && beats <= kBeatsPerShard);
#endif
    }

    // Apply and its replicas keep their original full-shard address space.
    // Pad in 512-bit beats here instead of sending eight empty rows per beat.
pad_shard:
    for (; beats < kBeatsPerShard; ++beats) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=0 max=kBeatsPerShard-1
        publish_beat(output, 0);
    }
}
}

extern "C" void kernelLittleGSMerger(
    hls::stream<l_tmp_prop_pkt> &l_tmp_prop_stm_1,
    hls::stream<write_burst_pkt> &l_write_burst_stm) {
#pragma HLS INTERFACE ap_ctrl_none port=return
#pragma HLS INTERFACE axis port=l_tmp_prop_stm_1
#pragma HLS INTERFACE axis port=l_write_burst_stm
    while (true) {
        merge_one_shard(l_tmp_prop_stm_1, l_write_burst_stm);
    }
}
