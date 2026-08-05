#include <ap_int.h>
#include <hls_stream.h>

#include <array>
#include <cassert>
#include <climits>

#include "../kernels/regraph_sssp_apply_status/kernel_apply.cpp"

namespace {

constexpr unsigned kActiveMask = 0x80000000U;

void put(ap_uint<512> &beat, unsigned lane, unsigned value)
{
    beat.range(lane * 32 + 31, lane * 32) = value;
}

unsigned get(const ap_uint<512> &beat, unsigned lane)
{
    return beat.range(lane * 32 + 31, lane * 32).to_uint();
}

}  // namespace

int main()
{
    std::array<ap_uint<512>, 1> vertex_prop = {0};
    std::array<ap_uint<32>, 1> active_count = {0};
    hls::stream<write_burst_pkt> merged;
    hls::stream<write_burst_pkt> source_write;

    put(vertex_prop[0], 0, 10);
    put(vertex_prop[0], 1, 3);
    put(vertex_prop[0], 2, INT_MAX - 1);

    write_burst_pkt update;
    update.data = 0;
    put(update.data, 0, kActiveMask | 5U);
    put(update.data, 1, kActiveMask | 5U);
    put(update.data, 2, kActiveMask | 7U);
    update.dest = 0;
    update.last = 0;
    merged.write(update);

    kernelApply(vertex_prop.data(), active_count.data(), 1, 0, 0,
                merged, source_write);

    assert(merged.empty());
    assert(active_count[0] == 2);
    assert(get(vertex_prop[0], 0) == (kActiveMask | 5U));
    assert(get(vertex_prop[0], 1) == 3U);
    assert(get(vertex_prop[0], 2) == (kActiveMask | 7U));

    const write_burst_pkt payload = source_write.read();
    const write_burst_pkt end = source_write.read();
    assert(payload.last == 0);
    assert(end.last == 1);
    assert(source_write.empty());
    return 0;
}
