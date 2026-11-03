#pragma once
#include "directory_spans.hpp"

#ifndef __SYNTHESIS__
#include <thread>
#endif

namespace pma_compact {
static Segment register_segment(Segment value) {
#pragma HLS INLINE OFF
#pragma HLS PIPELINE II=1
#pragma HLS LATENCY min=2 max=2
    return value;
}

static void read_spans(unsigned total, hls::stream<RowSpan> &spans,
                       hls::stream<Word> &even, hls::stream<Word> &odd,
                       hls::stream<bool> &even_release,
                       hls::stream<bool> &odd_release,
                       hls::stream<Segment> &output) {
#pragma HLS INLINE OFF
    unsigned segment = 0, end = 0, source = 0;
    for (unsigned consumed = 0; consumed < total; ++consumed) {
#pragma HLS PIPELINE II=1
        if (segment == end) {
            RowSpan span = spans.read();
            segment = span.begin;
            end = span.end;
            source = span.source;
        }
        bool parity = segment & 1;
        Segment value;
        value.data = parity ? odd.read() : even.read();
        value.source = source;
        value.last = consumed + 1 == total;
        output.write(register_segment(value));
        if (parity) odd_release.write(true);
        else even_release.write(true);
        ++segment;
    }
}

static void join_nonempty(unsigned vertices, unsigned total,
                          hls::stream_of_blocks<DirectoryTile, 2> &tiles,
                          hls::stream<bool> &ready, hls::stream<bool> &released,
                          hls::stream<Word> &even, hls::stream<Word> &odd,
                          hls::stream<bool> &even_release,
                          hls::stream<bool> &odd_release,
                          hls::stream<Segment> &output) {
#pragma HLS INLINE OFF
#pragma HLS DATAFLOW
    hls::stream<RowSpan> spans;
#pragma HLS STREAM variable=spans depth=16
#ifdef __SYNTHESIS__
    describe_rows(vertices, tiles, ready, released, spans);
    read_spans(total, spans, even, odd, even_release, odd_release, output);
#else
    std::thread describe([&] { describe_rows(vertices, tiles, ready, released, spans); });
    read_spans(total, spans, even, odd, even_release, odd_release, output);
    describe.join();
#endif
}

static void join_segments(unsigned vertices, hls::stream<unsigned> &extent,
                           hls::stream_of_blocks<DirectoryTile, 2> &tiles,
                           hls::stream<bool> &ready, hls::stream<bool> &released,
                           hls::stream<Word> &even, hls::stream<Word> &odd,
                           hls::stream<bool> &even_release,
                           hls::stream<bool> &odd_release,
                           hls::stream<Segment> &output) {
#pragma HLS INLINE OFF
    unsigned total = extent.read();
    if (!total) {
        output.write(Segment{~Word(0), 0, true});
        return;
    }
    join_nonempty(vertices, total, tiles, ready, released, even, odd,
                  even_release, odd_release, output);
}
}
