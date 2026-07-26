#include <hls_stream.h>
#include <ap_int.h>

#include <array>
#include <cassert>
#include <cstdint>

#include "grasu_degree_delta.hpp"
#include "kernel_config.h"

#include "../kernels/grasu_dispatch_degree/grasu_dispatch_degree.cpp"
#include "../kernels/grasu_degree_update/grasu_degree_update.cpp"

namespace {

pipe_type_96 make_update(unsigned source,
                         unsigned segment,
                         bool location,
                         bool delete_op)
{
    pipe_type_96 packet;
    packet.data = 0;
    packet.data.range(31, 5) = segment;
    packet.data[4] = location;
    packet.data.range(94, 64) = source;
    packet.data[95] = delete_op;
    packet.keep = -1;
    packet.strb = -1;
    packet.last = 0;
    return packet;
}

void expect_end(hls::stream<pipe_type_96> &stream)
{
    const pipe_type_96 packet = stream.read();
    assert(packet.data == END_EDGE);
    assert(packet.last == 1);
    assert(stream.empty());
}

}  // namespace

int main()
{
    std::array<hls::stream<pipe_type_96>, 4> inputs;
    std::array<hls::stream<pipe_type_96>, 4> outputs;
    hls::stream<grasu_degree_delta_pkt_t> degree_delta;

    inputs[0].write(make_update(2, 1, false, false));
    inputs[1].write(make_update(2, 2, true, true));
    inputs[2].write(make_update(5, MAX_CACHE_SEGMENT + 1, false, false));
    inputs[3].write(make_update(7, MAX_CACHE_SEGMENT + 2, true, true));
    inputs[0].write(make_update(2, 3, false, false));

    dispatch_degree(5, inputs[0], inputs[1], inputs[2], inputs[3],
                    outputs[0], outputs[1], outputs[2], outputs[3],
                    degree_delta);

    assert(outputs[0].read().data.range(94, 64) == 2);
    assert(outputs[0].read().data.range(94, 64) == 2);
    assert(outputs[1].read().data.range(94, 64) == 2);
    assert(outputs[2].read().data.range(94, 64) == 5);
    assert(outputs[3].read().data.range(94, 64) == 7);
    for (auto &output : outputs) {
        expect_end(output);
    }

    std::array<ap_uint<32>, 8> degree = {0, 0, 1, 0, 0, 0, 0, 1};
    std::array<ap_uint<32>, 2> status = {99, 99};
    grasu_degree_update(degree_delta, degree.data(), status.data(),
                        degree.size(), 5);
    assert(status[0] == 0);
    assert(status[1] == 5);
    assert(degree[2] == 2);
    assert(degree[5] == 1);
    assert(degree[7] == 0);
    assert(degree_delta.empty());

    hls::stream<grasu_degree_delta_pkt_t> underflow;
    underflow.write(make_degree_delta_packet(1, true, 0, false));
    underflow.write(make_degree_delta_packet(0, false, 0, true));
    status = {99, 99};
    grasu_degree_update(underflow, degree.data(), status.data(),
                        degree.size(), 1);
    assert(status[0] == 4);
    assert(status[1] == 0);
    assert(underflow.empty());

    hls::stream<grasu_degree_delta_pkt_t> out_of_order;
    out_of_order.write(make_degree_delta_packet(1, false, 1, false));
    out_of_order.write(make_degree_delta_packet(0, false, 0, true));
    status = {99, 99};
    grasu_degree_update(out_of_order, degree.data(), status.data(),
                        degree.size(), 1);
    assert(status[0] == 2);
    assert(status[1] == 0);
    assert(out_of_order.empty());

    hls::stream<grasu_degree_delta_pkt_t> out_of_range;
    out_of_range.write(make_degree_delta_packet(8, false, 0, false));
    out_of_range.write(make_degree_delta_packet(0, false, 0, true));
    status = {99, 99};
    grasu_degree_update(out_of_range, degree.data(), status.data(),
                        degree.size(), 1);
    assert(status[0] == 3);
    assert(status[1] == 0);
    assert(out_of_range.empty());

    hls::stream<grasu_degree_delta_pkt_t> overflow;
    overflow.write(make_degree_delta_packet(4, false, 0, false));
    overflow.write(make_degree_delta_packet(0, false, 0, true));
    degree[4] = ~ap_uint<32>(0);
    status = {99, 99};
    grasu_degree_update(overflow, degree.data(), status.data(),
                        degree.size(), 1);
    assert(status[0] == kDegreeUpdateOverflow);
    assert(status[1] == 0);
    assert(degree[4] == ~ap_uint<32>(0));
    assert(overflow.empty());

    hls::stream<grasu_degree_delta_pkt_t> early_end;
    early_end.write(make_degree_delta_packet(0, false, 0, true));
    status = {99, 99};
    grasu_degree_update(early_end, degree.data(), status.data(),
                        degree.size(), 1);
    assert(status[0] == kDegreeUpdateEarlyEnd);
    assert(status[1] == 0);
    assert(early_end.empty());

    hls::stream<grasu_degree_delta_pkt_t> missing_end;
    missing_end.write(make_degree_delta_packet(0, false, 0, false));
    status = {99, 99};
    grasu_degree_update(missing_end, degree.data(), status.data(),
                        degree.size(), 0);
    assert(status[0] == kDegreeUpdateMissingEnd);
    assert(status[1] == 0);
    assert(missing_end.empty());

    return 0;
}
