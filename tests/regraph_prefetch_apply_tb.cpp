#include <cassert>
#include <iostream>
#include <vector>
#include "../kernels/regraph_sssp_apply_status/kernel_apply.cpp"

static void check(unsigned partitions, unsigned salt, bool in_place) {
    const unsigned lines = partitions * 4096;
    std::vector<ap_uint<512>> old(lines + 1), next(lines + 1), oracle(lines + 1);
    hls::stream<write_burst_pkt> merged, published;
    unsigned expected_active = 0;
    for (unsigned row = 0; row < lines; ++row) {
        write_burst_pkt packet;
        packet.data = 0;
        for (unsigned lane = 0; lane < 16; ++lane) {
            unsigned index = row * 16 + lane;
            unsigned previous = ((index + salt) % 117) | 0x80000000U;
            unsigned candidate = ((index * 7 + salt) % 127) |
                (index % 5 ? 0x80000000U : 0U);
            old[row].range(lane * 32 + 31, lane * 32) = previous;
            packet.data.range(lane * 32 + 31, lane * 32) = candidate;
            unsigned value = applyFunc(candidate, previous, 0, 0);
            oracle[row].range(lane * 32 + 31, lane * 32) = value;
            expected_active += value >> 31;
        }
        packet.keep = -1; packet.strb = -1; packet.last = row + 1 == lines;
        merged.write(packet);
    }
    ap_uint<32> active = ~ap_uint<32>(0);
    // Production aliases both arguments to one BO. Also test separate BOs to
    // catch a dropped write independently of the read-before-write contract.
    auto *destination = in_place ? old.data() : next.data();
    kernelApply(hls::burst_maxi<ap_uint<512>>(old.data()), &active,
                partitions, 0, 0, merged, published,
                hls::burst_maxi<ap_uint<512>>(destination));
    assert((unsigned)active == expected_active);
    for (unsigned row = 0; row < lines; ++row) {
        assert(destination[row] == oracle[row]);
        auto packet = published.read();
        assert(!packet.last && (unsigned)packet.dest == row && packet.data == oracle[row]);
    }
    assert(published.read().last);
    assert(merged.empty() && published.empty());
}

int main() {
    for (bool in_place : {false, true}) {
        check(0, 0, in_place);
        check(1, 3, in_place);
        check(2, 19, in_place);
    }
    std::cout << "REGRAPH_PREFETCH_APPLY PASS cases=6 partitions=0,1,2"
                 " separate_and_in_place\n";
}
