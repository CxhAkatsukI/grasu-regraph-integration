#pragma once

#include <hls_burst_maxi.h>
#ifndef __SYNTHESIS__
#include <mutex>
#include <thread>
#endif

namespace prefetch_apply {
using Word = ap_uint<512>;
constexpr unsigned kBurst = 16;
constexpr unsigned kParents = 16;

// The vendor C model keys both masters by host pointer and its bookkeeping is
// not thread-safe. This guard has no synthesized storage or scheduling effect.
struct MemoryAccessGuard {
#ifndef __SYNTHESIS__
    static std::mutex mutex;
    std::lock_guard<std::mutex> lock{mutex};
#endif
};
#ifndef __SYNTHESIS__
std::mutex MemoryAccessGuard::mutex;
#endif

static void request_old(hls::burst_maxi<Word> &memory, unsigned total,
                        hls::stream<ap_uint<5>> &lengths,
                        hls::stream<bool> &completed) {
#pragma HLS INLINE OFF
    unsigned issued = 0;
    ap_uint<5> parents = 0;
    while (issued < total || parents) {
#pragma HLS PIPELINE II=1
        bool credit;
        if (completed.read_nb(credit)) --parents;
        if (issued < total && parents < kParents) {
            unsigned length = total - issued;
            if (length > kBurst) length = kBurst;
            { MemoryAccessGuard guard; memory.read_request(issued, length); }
            lengths.write(length);
            ++parents;
            issued += length;
        }
    }
    lengths.write(0);
}

static void receive_old(hls::burst_maxi<Word> &memory,
                        hls::stream<ap_uint<5>> &lengths,
                        hls::stream<bool> &completed,
                        hls::stream<Word> &output,
                        hls::stream<bool> &read_complete) {
#pragma HLS INLINE OFF
    while (true) {
        unsigned length = lengths.read();
        if (!length) break;
        for (unsigned beat = 0; beat < length; ++beat) {
#pragma HLS PIPELINE II=1
            Word value;
            { MemoryAccessGuard guard; value = memory.read(); }
            output.write(value);
        }
        read_complete.write(true);
        completed.write(true);
    }
}

static void read_old(hls::burst_maxi<Word> &memory, unsigned total,
                     hls::stream<Word> &output,
                     hls::stream<bool> &read_complete) {
#pragma HLS INLINE OFF
#pragma HLS DATAFLOW
    hls::stream<ap_uint<5>> lengths;
    hls::stream<bool> completed;
#pragma HLS STREAM variable=lengths depth=16
#pragma HLS STREAM variable=completed depth=16
#ifdef __SYNTHESIS__
    request_old(memory, total, lengths, completed);
    receive_old(memory, lengths, completed, output, read_complete);
#else
    std::thread requester([&] { request_old(memory, total, lengths, completed); });
    receive_old(memory, lengths, completed, output, read_complete);
    requester.join();
#endif
}

static void apply(unsigned arg_reg, hls::stream<Word> &old_state,
                  hls::stream<write_burst_dt> &input,
                  hls::stream<write_burst_dt> &output,
                  hls::stream<write_burst_pkt> &source_output) {
#pragma HLS INLINE OFF
    while (true) {
#pragma HLS PIPELINE II=1
        write_burst_dt item = input.read();
        write_burst_pkt packet;
        packet.data = 0;
        packet.dest = item.end_flag ? 0U : (unsigned)item.write_idx;
        packet.keep = -1;
        packet.strb = -1;
        packet.last = item.end_flag;
        if (!item.end_flag) {
            Word old = old_state.read();
            Word next;
            for (unsigned lane = 0; lane < 16; ++lane) {
#pragma HLS UNROLL
                next.range(lane * 32 + 31, lane * 32) = applyFunc(
                    item.data.range(lane * 32 + 31, lane * 32),
                    old.range(lane * 32 + 31, lane * 32), 0, arg_reg);
            }
            item.data = next;
            packet.data = next;
        }
        output.write(item);
        source_output.write(packet);
        if (item.end_flag) break;
    }
}

static void write(hls::burst_maxi<Word> &memory, unsigned total,
                  ap_uint<32> *active_count,
                  hls::stream<bool> &read_complete,
                  hls::stream<write_burst_dt> &input) {
#pragma HLS INLINE OFF
    unsigned issued = 0, parents = 0, active = 0;
    while (issued < total) {
        if (parents == kParents) {
            { MemoryAccessGuard guard; memory.write_response(); }
            --parents;
        }
        unsigned length = total - issued;
        if (length > kBurst) length = kBurst;
        // Both ports may alias one BO. Do not announce a write burst until
        // every old-state beat in that address range has been consumed.
        read_complete.read();
        { MemoryAccessGuard guard; memory.write_request(issued, length); }
        ++parents;
        for (unsigned beat = 0; beat < length; ++beat) {
#pragma HLS PIPELINE II=1
            write_burst_dt item = input.read();
#ifndef __SYNTHESIS__
            assert(!item.end_flag && (unsigned)item.write_idx == issued + beat);
#endif
            ap_uint<5> count = 0;
            for (unsigned lane = 0; lane < 16; ++lane) {
#pragma HLS UNROLL
                count += item.data[lane * 32 + 31];
            }
            active += count;
            { MemoryAccessGuard guard; memory.write(item.data); }
        }
        issued += length;
    }
    write_burst_dt terminal = input.read();
#ifndef __SYNTHESIS__
    assert(terminal.end_flag);
#endif
    while (parents) {
        { MemoryAccessGuard guard; memory.write_response(); }
        --parents;
    }
    active_count[0] = active;
}
}
