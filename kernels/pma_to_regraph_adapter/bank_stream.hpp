#ifndef GRASU_REGRAPH_BANK_STREAM_HPP
#define GRASU_REGRAPH_BANK_STREAM_HPP

// One AXI owner reads directory lines and bounded sequential bank bursts.
// Contiguous aligned PMA rows are required; the join restores bank order.
static void read_bank_interval(const ap_uint<512> *cached,
                               const ap_uint<512> *external,
                               unsigned first, unsigned count, unsigned cache_limit,
                               hls::stream<ap_uint<512>> &output)
{
#pragma HLS INLINE
    const unsigned last = first + count;
    const unsigned boundary = first < cache_limit
        ? (last < cache_limit ? last : cache_limit) : first;
read_cached_bank_loop:
    for (unsigned i = first; i < boundary; ++i) {
#pragma HLS PIPELINE II=1
        output.write(cached[i]);
    }
read_external_bank_loop:
    for (unsigned i = boundary; i < last; ++i) {
#pragma HLS PIPELINE II=1
        output.write(external[i]);
    }
}

static void read_directory_and_banks(const ap_uint<512> *pma0,
                                     const ap_uint<512> *pma1,
                                     const ap_uint<512> *pma2,
                                     const ap_uint<512> *pma3,
                                     const ap_uint<512> *rows,
                                     unsigned nodes, unsigned capacity,
                                     unsigned cache_limit, ap_uint<64> total,
                                     hls::stream<ap_uint<512>> &directory,
                                     hls::stream<ap_uint<512>> &even,
                                     hls::stream<ap_uint<512>> &odd)
{
#pragma HLS INLINE off
    constexpr unsigned tile = GRASU_REGRAPH_DIRECTORY_TILE_ROWS;
    unsigned segment = 0;
bank_tile_loop:
    for (unsigned base = 0; base < nodes && (ap_uint<64>(segment) << 4) < total; base += tile) {
        const unsigned count = nodes - base < tile ? nodes - base : tile;
        ap_uint<64> end = 0;
load_directory_tile_loop:
        for (unsigned line = 0; line < (count + 7) / 8; ++line) {
#pragma HLS PIPELINE II=1
            const ap_uint<512> value = rows[(base >> 3) + line];
            directory.write(value);
            if (line == (count - 1) / 8) {
                const unsigned lane = (count - 1) & 7;
                ap_uint<64> unused = 0;
                unpack_row_bounds(value.range(lane * 64 + 63, lane * 64), unused, end);
            }
        }
        if (end > capacity) end = capacity;
        const unsigned last = unsigned(end >> 4);
bank_chunk_loop:
        while (segment < last) {
            constexpr unsigned chunk = 2 * GRASU_REGRAPH_BANK_FIFO_LINES;
            const unsigned length = last - segment < chunk ? last - segment : chunk;
            const unsigned even_first = (segment + 1) >> 1;
            const unsigned odd_first = segment >> 1;
            const unsigned even_count = (length + 1 - (segment & 1)) >> 1;
            const unsigned odd_count = length - even_count;
            read_bank_interval(pma0, pma1, even_first, even_count, cache_limit, even);
            read_bank_interval(pma2, pma3, odd_first, odd_count, cache_limit, odd);
            segment += length;
        }
    }
}

static void join_bank_segments(hls::stream<ap_uint<512>> &directory,
                               hls::stream<ap_uint<512>> &even,
                               hls::stream<ap_uint<512>> &odd,
                               unsigned nodes, unsigned capacity, ap_uint<64> total,
                               hls::stream<loaded_row_segment> &loaded)
{
#pragma HLS INLINE off
    constexpr unsigned tile = GRASU_REGRAPH_DIRECTORY_TILE_ROWS;
    ap_uint<64> cache[tile];
#pragma HLS ARRAY_PARTITION variable=cache cyclic factor=8
    ap_uint<64> emitted = 0;
join_tile_loop:
    for (unsigned base = 0; base < nodes && emitted < total; base += tile) {
        const unsigned count = nodes - base < tile ? nodes - base : tile;
load_join_directory_loop:
        for (unsigned line = 0; line < (count + 7) / 8; ++line) {
#pragma HLS PIPELINE II=1
            const ap_uint<512> value = directory.read();
            for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
                cache[line * 8 + lane] = value.range(lane * 64 + 63, lane * 64);
            }
        }
        unsigned source = base;
        ap_uint<64> begin = 0, end = 0;
        unpack_row_bounds(cache[0], begin, end);
        if (end > capacity) end = capacity;
        ap_uint<64> segment = begin >> 4;
read_tiled_sources_loop:
        while (source < base + count && emitted < total) {
#pragma HLS PIPELINE II=1
            if (segment < (end >> 4)) {
                loaded_row_segment record;
                record.task = {source, begin, end, segment, total, false};
                record.data = (segment & 1) ? odd.read() : even.read();
                loaded.write(record);
                ++segment;
                emitted += 16;
            } else {
                ++source;
                unpack_row_bounds(cache[source & (tile - 1)], begin, end);
                if (end > capacity) end = capacity;
                segment = begin >> 4;
            }
        }
    }
    loaded_row_segment terminal = {};
    terminal.task.terminal = true;
    loaded.write(terminal);
}

static void bank_stream_dataflow(const ap_uint<512> *pma0,
                                const ap_uint<512> *pma1,
                                const ap_uint<512> *pma2,
                                const ap_uint<512> *pma3,
                                const ap_uint<512> *rows,
                                unsigned nodes, unsigned capacity,
                                unsigned cache_limit, unsigned dst_base,
                                unsigned dst_count, ap_uint<64> total,
                                hls::stream<edge_burst_pkt_t> &output)
{
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<ap_uint<512>> directory("bank_directory"), even("bank_even"), odd("bank_odd");
#pragma HLS STREAM variable=directory depth=128
#pragma HLS STREAM variable=even depth=GRASU_REGRAPH_BANK_FIFO_LINES
#pragma HLS STREAM variable=odd depth=GRASU_REGRAPH_BANK_FIFO_LINES
    hls::stream<loaded_row_segment> loaded("bank_joined_segments");
#pragma HLS STREAM variable=loaded depth=16
    read_directory_and_banks(pma0, pma1, pma2, pma3, rows, nodes, capacity,
                             cache_limit, total, directory, even, odd);
    join_bank_segments(directory, even, odd, nodes, capacity, total, loaded);
    publish_packet_pipeline(loaded, dst_base, dst_count, output);
}

#endif
