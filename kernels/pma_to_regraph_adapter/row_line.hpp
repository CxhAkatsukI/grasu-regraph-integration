#ifndef GRASU_REGRAPH_PMA_ROW_LINE_HPP
#define GRASU_REGRAPH_PMA_ROW_LINE_HPP

// The host supplies a 64-byte-aligned, whole-line-padded row buffer. Unlike
// narrow prefetch, each load here explicitly fetches eight packed row bounds.
static ap_uint<64> read_row_line_entry(const ap_uint<512> *rows, unsigned source)
{
#pragma HLS INLINE
    const ap_uint<512> line = rows[source >> 3];
    const unsigned bit = (source & 7) * 64;
    return line.range(bit + 63, bit);
}

static ap_uint<64> read_cached_row_line(const ap_uint<512> *rows,
                                       unsigned source, ap_uint<64> cache[8])
{
#pragma HLS INLINE
    const unsigned offset = source & 7;
    if (offset == 0) {
        const ap_uint<512> line = rows[source >> 3];
        for (unsigned lane = 0; lane < 8; ++lane) {
#pragma HLS UNROLL
            cache[lane] = line.range(lane * 64 + 63, lane * 64);
        }
    }
    return cache[offset];
}

#endif
