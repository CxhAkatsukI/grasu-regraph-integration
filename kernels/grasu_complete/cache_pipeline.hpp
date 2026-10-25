#pragma once

#include "cache_lane.hpp"

namespace cache_registered {
inline void dispatch(hls::stream<pipe_type_96>& input,
                     hls::stream<CacheUpdate> updates[16]) {
#pragma HLS INLINE off
  dispatch_loop:
  while (true) {
#pragma HLS PIPELINE II=1
    const CacheUpdate packet = input.read().data;
    if (packet == END_EDGE) break;
    updates[packet.range(8, 5)].write(packet);
  }
  for (unsigned bank = 0; bank < 16; ++bank) {
#pragma HLS PIPELINE II=1
    updates[bank].write(END_EDGE);
  }
}

inline void update_banks(CacheWord cache[16][cache_bank_depth],
                         hls::stream<CacheUpdate> updates[16]) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
  for (unsigned bank = 0; bank < 16; ++bank) {
#pragma HLS UNROLL
    cache_probe_detail::lane_update(cache[bank], updates[bank]);
  }
}

inline void cached_process(CacheWord* memory, hls::stream<CacheUpdate> updates[16],
                           unsigned valid_segments = MAX_CACHE_SEGMENT) {
#pragma HLS INLINE off
  static_assert(MAX_CACHE_SEGMENT == 16 * cache_bank_depth, "complete hot-half capacity");
  CacheWord cache[16][cache_bank_depth];
#pragma HLS ARRAY_PARTITION variable=cache complete dim=1
#pragma HLS BIND_STORAGE variable=cache type=RAM_1P impl=URAM
  // Keep full physical capacity; transfer populated, bank-aligned rows only.
  const unsigned bounded = valid_segments > MAX_CACHE_SEGMENT
      ? MAX_CACHE_SEGMENT : valid_segments;
  const unsigned rows = (bounded + 15) / 16;
  preload_all:
  for (unsigned row = 0; row < rows; ++row) {
#pragma HLS LOOP_TRIPCOUNT min=0 max=8192
#pragma HLS PIPELINE II=16
    for (unsigned bank = 0; bank < 16; ++bank) {
#pragma HLS UNROLL
      cache[bank][row] = memory[row * 16 + bank];
    }
  }
  update_banks(cache, updates);
  writeback_all:
  for (unsigned row = 0; row < rows; ++row) {
#pragma HLS LOOP_TRIPCOUNT min=0 max=8192
#pragma HLS PIPELINE II=16
    for (unsigned bank = 0; bank < 16; ++bank) {
#pragma HLS UNROLL
      memory[row * 16 + bank] = cache[bank][row];
    }
  }
}

inline void candidate(CacheWord* memory, hls::stream<pipe_type_96>& input,
                      unsigned valid_segments = MAX_CACHE_SEGMENT) {
#pragma HLS INLINE off
  hls::stream<CacheUpdate> updates[16];
#pragma HLS STREAM variable=updates depth=2
#pragma HLS DATAFLOW
  dispatch(input, updates);
  cached_process(memory, updates, valid_segments);
}
}  // namespace cache_registered
