#pragma once
#include "types.hpp"

namespace pma_compact {
static ap_uint<5> select_lanes(const Segment &value, unsigned destinations,
                               ap_uint<64> compacted[16]) {
#pragma HLS INLINE
    bool valid[16];
    ap_uint<5> prefix[5][16];
    ap_uint<64> items[16];
#pragma HLS ARRAY_PARTITION variable=valid complete
#pragma HLS ARRAY_PARTITION variable=prefix complete dim=0
#pragma HLS ARRAY_PARTITION variable=items complete
    for (unsigned lane = 0; lane < 16; ++lane) {
#pragma HLS UNROLL
        ap_uint<32> dst = value.data.range(lane * 32 + 31, lane * 32);
        valid[lane] = !dst[31] && (unsigned)(dst & 0x7ffffu) < destinations;
#if GRASU_REGRAPH_WEIGHTED_PMA
        valid[lane] = valid[lane] && ((dst >> 19) & 0xfffu) != 0;
#elif !GRASU_REGRAPH_DESTINATION_ONLY
        dst = (dst & 0x7ffffu) | (1u << 19);
#endif
        prefix[0][lane] = valid[lane];
        items[lane].range(31, 0) = value.source;
        items[lane].range(63, 32) = dst;
    }
    // Four parallel prefix levels replace the serial sixteen-lane sum.
    for (unsigned level = 0; level < 4; ++level) {
#pragma HLS UNROLL
        for (unsigned lane = 0; lane < 16; ++lane) {
#pragma HLS UNROLL
            prefix[level + 1][lane] = prefix[level][lane];
            if (lane >= (1u << level))
                prefix[level + 1][lane] += prefix[level][lane - (1u << level)];
        }
    }
    // Prefix ranks are unique for valid inputs. Fixed destinations avoid
    // unrolled runtime-index writes and their array dependence scheduling.
    for (unsigned slot = 0; slot < 16; ++slot) {
#pragma HLS UNROLL
        ap_uint<64> item = 0;
        for (unsigned lane = 0; lane < 16; ++lane) {
#pragma HLS UNROLL
            if (valid[lane] && prefix[4][lane] == slot + 1) item |= items[lane];
        }
        compacted[slot] = item;
    }
    return prefix[4][15];
}

static Packet packet(const ap_uint<64> lanes[32], unsigned count,
                      unsigned window, bool last) {
#pragma HLS INLINE
    Packet result;
    result.data = 0;
    for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
        ap_uint<64> item = 0;
        item.range(31, 0) = (window * kWindow) | 0x80000000u;
        item.range(63, 32) = 0x80000000u;
        if (lane < count) item = lanes[lane];
        result.data.range(lane * 64 + 63, lane * 64) = item;
    }
    result.keep = -1;
    result.strb = -1;
    result.last = last;
    return result;
}

static void compact(unsigned destinations, hls::stream<Segment> &input,
                     hls::stream<Packet> &output) {
#pragma HLS INLINE OFF
#pragma HLS EXPRESSION_BALANCE off
    ap_uint<64> lanes[32];
#pragma HLS ARRAY_PARTITION variable=lanes complete
    ap_uint<6> count = 0;
    unsigned window = 0;
    bool have_window = false, emitted = false;
    Packet publishing[3];
    ap_uint<2> delay[3] = {0, 0, 0};
#pragma HLS ARRAY_PARTITION variable=publishing complete
#pragma HLS ARRAY_PARTITION variable=delay complete
    ap_uint<2> head = 0, tail = 0, pending = 0;
    Segment value;
    bool held = false, terminal = false, closed = false;
    while (true) {
#pragma HLS PIPELINE II=1
        const unsigned previous_pending = pending;
        for (unsigned slot = 0; slot < 3; ++slot) {
#pragma HLS UNROLL
            if (delay[slot]) --delay[slot];
        }
        if (pending && !delay[head] && output.write_nb(publishing[head])) {
            bool last = publishing[head].last;
            head = (head + 1) % 3;
            --pending;
            if (last) break;
        }
        if (!held && !terminal) held = input.read_nb(value);
        bool boundary = have_window && held && value.source / kWindow != window;
        bool flush = boundary || terminal;
        const unsigned previous_count = count;
        const bool accept = !boundary && !terminal && held && previous_count <= 16;
        const bool switch_window = boundary && !count && emitted;
        if (have_window && !closed && previous_pending < 3 && (count > 8 ||
            (flush && (count || !emitted || terminal)))) {
            unsigned take = count < 8 ? (unsigned)count : 8u;
            bool last = terminal && count <= 8;
            publishing[tail] = packet(lanes, take, window, last);
            delay[tail] = 2;
            tail = (tail + 1) % 3;
            ++pending;
            for (unsigned lane = 0; lane < 24; ++lane) {
#pragma HLS UNROLL
                lanes[lane] = lanes[lane + 8];
            }
            count -= take;
            emitted = true;
            closed = last;
        }
        if (switch_window) {
            have_window = false;
            emitted = false;
        }
        // Selection and publication use independent finite storage and may
        // advance together. A full publisher never borrows same-cycle credit.
        if (accept) {
            if (!have_window) { window = value.source / kWindow; have_window = true; }
            ap_uint<64> compacted[16];
#pragma HLS ARRAY_PARTITION variable=compacted complete
            ap_uint<5> selected = select_lanes(value, destinations, compacted);
            for (unsigned lane = 0; lane < 32; ++lane) {
#pragma HLS UNROLL
                if (lane >= count && lane < count + selected) {
                    ap_uint<4> slot = lane - count;
                    lanes[lane] = compacted[slot];
                }
            }
            count += selected;
            terminal = value.last;
            held = false;
        }
    }
}
}
