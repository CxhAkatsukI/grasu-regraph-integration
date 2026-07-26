#ifndef GRASU_REGRAPH_PAGERANK_APPLY_HPP
#define GRASU_REGRAPH_PAGERANK_APPLY_HPP

#include <ap_axi_sdata.h>
#include <ap_int.h>

using regraph_write_burst_pkt_t = ap_axiu<512, 0, 0, 32>;

static constexpr unsigned kReGraphFullPageRank = 1;
static constexpr unsigned kReGraphResidualPageRank = 2;

enum ReGraphPageRankStatus : unsigned {
    kReGraphPageRankOk = 0,
    kReGraphPageRankVertexCapacityExceeded = 1,
};

enum ReGraphPageRankStat : unsigned {
    kReGraphPageRankStatus = 0,
    kReGraphPageRankActiveVertices = 1,
    kReGraphPageRankErrorBits = 2,
    kReGraphPageRankNextDanglingBits = 3,
    kReGraphPageRankAppliedVertices = 4,
    kReGraphPageRankStatWords = 5,
};

#endif
