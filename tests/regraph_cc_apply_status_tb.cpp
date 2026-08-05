#include <ap_int.h>
#include <hls_stream.h>

#include <array>
#include <cassert>

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
    std::array<ap_uint<512>, 1> labels = {0};
    std::array<ap_uint<32>, 1> active_count = {0};
    hls::stream<write_burst_pkt> merged;
    hls::stream<write_burst_pkt> source_write;

    put(labels[0], 0, 0U);
    put(labels[0], 1, 1U);
    put(labels[0], 2, 2U);
    put(labels[0], 3, 3U);

    write_burst_pkt update;
    update.data = 0;
    put(update.data, 0, kActiveMask | 1U);
    put(update.data, 1, kActiveMask | 0U);
    put(update.data, 2, kActiveMask | 3U);
    put(update.data, 3, kActiveMask | 2U);
    update.dest = 0;
    update.last = 0;
    merged.write(update);

    kernelApply(labels.data(), active_count.data(), 1, 0, 0,
                merged, source_write);

    assert(active_count[0] == 2);
    assert(get(labels[0], 0) == 0U);
    assert(get(labels[0], 1) == (kActiveMask | 0U));
    assert(get(labels[0], 2) == 2U);
    assert(get(labels[0], 3) == (kActiveMask | 2U));

    const write_burst_pkt payload = source_write.read();
    const write_burst_pkt end = source_write.read();
    assert(payload.last == 0);
    assert(end.last == 1);
    assert(source_write.empty());
    return 0;
}
