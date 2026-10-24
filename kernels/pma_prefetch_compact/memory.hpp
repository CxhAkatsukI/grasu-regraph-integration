#pragma once
#include "types.hpp"
#ifndef __SYNTHESIS__
#include <mutex>
#include <thread>
#endif

namespace pma_compact {
// The vendor burst model shares a non-thread-safe pointer map. The lock is
// C-simulation-only; the synthesized request and response channels are separate.
struct MemoryGuard {
#ifndef __SYNTHESIS__
    static std::mutex &mutex() { static std::mutex value; return value; }
    std::lock_guard<std::mutex> lock{mutex()};
#endif
};

static void request(hls::burst_maxi<Word> &memory, unsigned offset,
                    unsigned length) {
#pragma HLS INLINE
    MemoryGuard guard;
    memory.read_request(offset, length);
}

static Word response(hls::burst_maxi<Word> &memory) {
#pragma HLS INLINE
    MemoryGuard guard;
    return memory.read();
}
}
