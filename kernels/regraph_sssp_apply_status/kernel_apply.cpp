#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

#include "acc_apply.h"
#include "acc_config.h"
#include "acc_data_types.h"
#include "l1_api.h"

#if GRASU_REGRAPH_PREFETCH_COMPACT
#include <cassert>
#include "prefetch.hpp"
#ifndef __SYNTHESIS__
#include <thread>
#endif
#endif

namespace {

void write_out_with_active_count(
    ap_uint<512> *vertex_prop,
    ap_uint<32> *active_count,
    hls::stream<write_burst_dt> &write_burst_stm)
{
    ap_uint<32> active_vertices = 0;

write_out:
    while (true) {
#pragma HLS PIPELINE II=1
        write_burst_dt write_burst;
        read_from_stream(write_burst_stm, write_burst);
        if (write_burst.end_flag) {
            break;
        }

        const ap_uint<512> new_prop = write_burst.data;
        ap_uint<3> group_count[4];
#pragma HLS ARRAY_PARTITION variable=group_count complete
    count_groups:
        for (int group = 0; group < 4; ++group) {
#pragma HLS UNROLL
            const int lane = group * 4;
            group_count[group] =
                new_prop[(lane + 0) * 32 + 31] +
                new_prop[(lane + 1) * 32 + 31] +
                new_prop[(lane + 2) * 32 + 31] +
                new_prop[(lane + 3) * 32 + 31];
        }
        const ap_uint<5> beat_active =
            group_count[0] + group_count[1] +
            group_count[2] + group_count[3];
        active_vertices += beat_active;
        vertex_prop[write_burst.write_idx] = new_prop;
    }

    active_count[0] = active_vertices;
}

}  // namespace

extern "C" {
void kernelApply(
#if GRASU_REGRAPH_PREFETCH_COMPACT
    hls::burst_maxi<ap_uint<512>> vertex_prop,
#else
    ap_uint<512> *vertex_prop,
#endif
    ap_uint<32> *active_count,
#if HAVE_APPLY_OUTDEG
    ap_uint<512> *outdegree,
#endif
    ap_uint<32> num_dense_paritions,
    ap_uint<32> num_sparse_paritions,
    unsigned int arg_reg,
#if LITTLE_KERNEL_NUM
    hls::stream<write_burst_pkt> &l_merged_prop_stm,
#endif
#if BIG_KERNEL_NUM
    hls::stream<write_burst_pkt> &b_merged_prop_stm,
#endif
    hls::stream<write_burst_pkt> &prop_write_burst_stm
#if GRASU_REGRAPH_PREFETCH_COMPACT
    , hls::burst_maxi<ap_uint<512>> vertex_prop_write
#endif
    )
{
#if GRASU_REGRAPH_PREFETCH_COMPACT
#pragma HLS INTERFACE m_axi port=vertex_prop offset=slave bundle=gmem1 num_read_outstanding=16 max_read_burst_length=16
#else
#pragma HLS INTERFACE m_axi port=vertex_prop offset=slave bundle=gmem1
#endif
#pragma HLS INTERFACE m_axi port=active_count offset=slave bundle=gmem1
#pragma HLS INTERFACE s_axilite port=vertex_prop bundle=control
#pragma HLS INTERFACE s_axilite port=active_count bundle=control
#if GRASU_REGRAPH_PREFETCH_COMPACT
#pragma HLS INTERFACE m_axi port=vertex_prop_write offset=slave bundle=gmem_write num_write_outstanding=16 max_write_burst_length=16
#pragma HLS INTERFACE s_axilite port=vertex_prop_write bundle=control
#endif
#if HAVE_APPLY_OUTDEG
#pragma HLS INTERFACE m_axi port=outdegree offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=outdegree bundle=control
#endif
#pragma HLS INTERFACE s_axilite port=num_dense_paritions bundle=control
#pragma HLS INTERFACE s_axilite port=num_sparse_paritions bundle=control
#pragma HLS INTERFACE s_axilite port=arg_reg bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS DATAFLOW

    hls::stream<write_burst_dt> write_burst_stm;
    hls::stream<write_burst_dt> write_burst_stm_apply;

#if GRASU_REGRAPH_PREFETCH_COMPACT
#if BIG_KERNEL_NUM || HAVE_APPLY_OUTDEG
#error "prefetch-compact Apply requires Little-only SSSP or CC"
#endif
    hls::stream<ap_uint<512>> old_state;
    hls::stream<bool> read_complete;
#pragma HLS STREAM variable=old_state depth=256
#pragma HLS STREAM variable=read_complete depth=16
#pragma HLS STREAM variable=write_burst_stm depth=32
#pragma HLS STREAM variable=write_burst_stm_apply depth=32
    const unsigned total = (LITTLE_KERNEL_DST_BUFFER_SIZE >> 4) * num_dense_paritions;
#ifndef __SYNTHESIS__
    assert(num_sparse_paritions == 0);
    std::thread merge([&] { merge_big_little_writes(l_merged_prop_stm,
        write_burst_stm, num_dense_paritions, num_sparse_paritions); });
    std::thread reader([&] { prefetch_apply::read_old(vertex_prop, total, old_state,
                                                  read_complete); });
    std::thread compute([&] { prefetch_apply::apply(arg_reg, old_state,
        write_burst_stm, write_burst_stm_apply, prop_write_burst_stm); });
    prefetch_apply::write(vertex_prop_write, total, active_count, read_complete,
                         write_burst_stm_apply);
    merge.join(); reader.join(); compute.join();
#else
    merge_big_little_writes(l_merged_prop_stm, write_burst_stm,
        num_dense_paritions, num_sparse_paritions);
    prefetch_apply::read_old(vertex_prop, total, old_state, read_complete);
    prefetch_apply::apply(arg_reg, old_state, write_burst_stm,
        write_burst_stm_apply, prop_write_burst_stm);
    prefetch_apply::write(vertex_prop_write, total, active_count, read_complete,
                         write_burst_stm_apply);
#endif
#else
    merge_big_little_writes(
#if LITTLE_KERNEL_NUM
        l_merged_prop_stm,
#endif
#if BIG_KERNEL_NUM
        b_merged_prop_stm,
#endif
        write_burst_stm, num_dense_paritions, num_sparse_paritions);

    Apply(vertex_prop,
#if HAVE_APPLY_OUTDEG
          outdegree,
#endif
          arg_reg, write_burst_stm, write_burst_stm_apply,
          prop_write_burst_stm);

    write_out_with_active_count(vertex_prop, active_count,
                                write_burst_stm_apply);
#endif
}
}
