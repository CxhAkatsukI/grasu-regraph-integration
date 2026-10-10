#ifndef GRASU_REGRAPH_PMA_ROW_PREFETCH_HPP
#define GRASU_REGRAPH_PMA_ROW_PREFETCH_HPP

// Eight contiguous 64-bit rows form one 512-bit memory line. Keep the ABI
// unchanged; the pipelined copy permits burst inference on the shared master.
static constexpr unsigned kRowPrefetchCount = 8;

static ap_uint<64> read_prefetched_row(const ap_uint<64> *rows,
                                      unsigned source, unsigned node_count,
                                      ap_uint<64> cache[kRowPrefetchCount])
{
#pragma HLS INLINE
    const unsigned offset = source % kRowPrefetchCount;
    if (offset == 0) {
        const unsigned remaining = node_count - source;
        const unsigned count = remaining < kRowPrefetchCount
            ? remaining : kRowPrefetchCount;
    row_prefetch_loop:
        for (unsigned i = 0; i < count; ++i) {
#pragma HLS PIPELINE II=1
            cache[i] = rows[source + i];
        }
    }
    return cache[offset];
}

#endif
