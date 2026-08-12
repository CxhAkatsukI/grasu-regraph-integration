#include "weighted_pma_update_reference.hpp"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <vector>

using grasu::integration::WeightedEdgeRecord;
using grasu::integration::build_weighted_partitioned_pma_graph;
using grasu::integration::build_weighted_pma_update_reference;
using grasu::integration::decode_weighted_pma_destination;
using grasu::integration::decode_weighted_pma_weight;
using grasu::integration::kWeightedPmaEmpty;
using grasu::integration::weighted_pma_segment_port;

int main()
{
    const std::vector<WeightedEdgeRecord> initial{
        {0, 1, 2, false}, {0, 17, 3, false}, {2, 3, 4, false}};
    const std::vector<WeightedEdgeRecord> updates{
        {0, 2, 5, false}, {0, 17, 3, true}, {2, 19, 6, false}};
    const auto graph = build_weighted_partitioned_pma_graph(
        20, 16, initial, updates);
    const auto touched = build_weighted_pma_update_reference(graph, 1);

    assert(graph.shards.size() == 2);
    assert(touched.size() == 3);
    bool saw_cache = false;
    std::size_t live_words = 0;
    for (const auto &segment : touched) {
        assert(segment.port < 4);
        saw_cache = saw_cache || segment.port == 0 || segment.port == 2;
        assert(std::is_sorted(segment.expected.begin(),
                              segment.expected.end()));
        for (const std::uint32_t word : segment.expected) {
            if (word == kWeightedPmaEmpty) continue;
            assert(decode_weighted_pma_destination(word) < 16);
            assert(decode_weighted_pma_weight(word) != 0);
            ++live_words;
        }
    }
    assert(saw_cache);
    // Only touched segments are returned; the untouched (2,3) edge is not
    // read back by this validation path.
    assert(live_words == 3);
    const auto cache_port = weighted_pma_segment_port(0, 1);
    const auto even_ddr_port = weighted_pma_segment_port(2, 1);
    const auto odd_ddr_port = weighted_pma_segment_port(3, 1);
    assert(cache_port.first == 0 && cache_port.second == 0);
    assert(even_ddr_port.first == 1 && even_ddr_port.second == 16);
    assert(odd_ddr_port.first == 3 && odd_ddr_port.second == 16);
    return 0;
}
