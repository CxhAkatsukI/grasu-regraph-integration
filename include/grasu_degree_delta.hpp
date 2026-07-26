#ifndef GRASU_REGRAPH_DEGREE_DELTA_HPP
#define GRASU_REGRAPH_DEGREE_DELTA_HPP

#include <ap_axi_sdata.h>
#include <ap_int.h>

using grasu_degree_delta_pkt_t = ap_axiu<64, 0, 0, 0>;

static constexpr unsigned kDegreeSourceLow = 0;
static constexpr unsigned kDegreeSourceHigh = 31;
static constexpr unsigned kDegreeDeleteBit = 32;
static constexpr unsigned kDegreeOrdinalLow = 33;
static constexpr unsigned kDegreeOrdinalHigh = 63;

enum DegreeUpdateStatus : unsigned {
    kDegreeUpdateOk = 0,
    kDegreeUpdateEarlyEnd = 1,
    kDegreeUpdateOrdinalMismatch = 2,
    kDegreeUpdateSourceOutOfRange = 3,
    kDegreeUpdateUnderflow = 4,
    kDegreeUpdateMissingEnd = 5,
    kDegreeUpdateOverflow = 6,
};

static grasu_degree_delta_pkt_t make_degree_delta_packet(
    ap_uint<32> source,
    bool delete_op,
    ap_uint<31> ordinal,
    bool last)
{
#pragma HLS INLINE
    grasu_degree_delta_pkt_t packet;
    packet.data = 0;
    packet.data.range(kDegreeSourceHigh, kDegreeSourceLow) = source;
    packet.data[kDegreeDeleteBit] = delete_op;
    packet.data.range(kDegreeOrdinalHigh, kDegreeOrdinalLow) = ordinal;
    packet.keep = -1;
    packet.strb = -1;
    packet.last = last ? 1 : 0;
    return packet;
}

static ap_uint<32> degree_delta_source(const grasu_degree_delta_pkt_t &packet)
{
#pragma HLS INLINE
    return packet.data.range(kDegreeSourceHigh, kDegreeSourceLow);
}

static bool degree_delta_is_delete(const grasu_degree_delta_pkt_t &packet)
{
#pragma HLS INLINE
    return packet.data[kDegreeDeleteBit];
}

static ap_uint<31> degree_delta_ordinal(
    const grasu_degree_delta_pkt_t &packet)
{
#pragma HLS INLINE
    return packet.data.range(kDegreeOrdinalHigh, kDegreeOrdinalLow);
}

#endif
