#include "weighted_pma_graph.hpp"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <map>
#include <set>
#include <utility>
#include <vector>

using grasu::integration::WeightedEdgeRecord;
using grasu::integration::WeightedPmaGraph;
using grasu::integration::build_weighted_pma_graph;
using grasu::integration::decode_weighted_pma_destination;
using grasu::integration::decode_weighted_pma_weight;
using grasu::integration::kWeightedPmaDelete;
using grasu::integration::kWeightedPmaEmpty;
using grasu::integration::kWeightedPmaSegmentSlots;

namespace {

using EdgeMap =
    std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint16_t>;

std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint16_t>
materialize(const WeightedPmaGraph &graph, std::vector<std::uint32_t> words)
{
    for (const std::uint64_t update : graph.physical_updates) {
        const bool delete_op = (update & kWeightedPmaDelete) != 0;
        const std::uint64_t edge = update & ~kWeightedPmaDelete;
        const std::uint32_t source = static_cast<std::uint32_t>(edge >> 32);
        const std::uint32_t word = static_cast<std::uint32_t>(edge);
        const std::uint64_t row = graph.row_bounds.at(source);
        const std::size_t begin_segment = (row >> 32) / kWeightedPmaSegmentSlots;
        const std::size_t end_segment =
            (static_cast<std::uint32_t>(row)) / kWeightedPmaSegmentSlots;
        const std::uint64_t packed_key =
            (static_cast<std::uint64_t>(source) << 32) | word;
        std::size_t segment = begin_segment;
        for (std::size_t candidate = begin_segment; candidate < end_segment;
             ++candidate) {
            if (graph.binary_heads[candidate] <= packed_key) {
                segment = candidate;
            }
        }
        auto first = words.begin() + segment * kWeightedPmaSegmentSlots;
        auto last = first + kWeightedPmaSegmentSlots;
        auto position = std::lower_bound(first, last, word);
        if (delete_op) {
            assert(position != last && *position == word);
            std::rotate(position, position + 1, last);
            *(last - 1) = kWeightedPmaEmpty;
        } else {
            assert(*(last - 1) == kWeightedPmaEmpty);
            std::move_backward(position, last - 1, last);
            *position = word;
        }
    }

    std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint16_t> result;
    for (std::uint32_t source = 0; source < graph.vertices; ++source) {
        const std::uint64_t row = graph.row_bounds[source];
        const std::size_t begin = row >> 32;
        const std::size_t end = static_cast<std::uint32_t>(row);
        for (std::size_t slot = begin; slot < end; ++slot) {
            if (words[slot] == kWeightedPmaEmpty) {
                continue;
            }
            result[{source, decode_weighted_pma_destination(words[slot])}] =
                decode_weighted_pma_weight(words[slot]);
        }
    }
    return result;
}

EdgeMap external_oracle(const std::vector<WeightedEdgeRecord> &initial,
                        const std::vector<WeightedEdgeRecord> &updates)
{
    EdgeMap result;
    for (const auto &edge : initial) {
        const bool inserted =
            result.emplace(std::make_pair(edge.source, edge.destination),
                           edge.weight)
                .second;
        assert(inserted && !edge.delete_op);
    }
    for (const auto &edge : updates) {
        const auto key = std::make_pair(edge.source, edge.destination);
        if (edge.delete_op) {
            const auto found = result.find(key);
            assert(found != result.end() && found->second == edge.weight);
            result.erase(found);
        } else {
            result[key] = edge.weight;
        }
    }
    return result;
}

EdgeMap unmap_edges(const WeightedPmaGraph &graph, const EdgeMap &internal)
{
    EdgeMap result;
    for (const auto &[key, weight] : internal) {
        result[{graph.internal_to_external.at(key.first),
                graph.internal_to_external.at(key.second)}] = weight;
    }
    return result;
}

void check_graph(const std::vector<WeightedEdgeRecord> &initial,
                 const std::vector<WeightedEdgeRecord> &updates,
                 const WeightedPmaGraph &graph)
{
    assert(graph.external_to_internal.size() == graph.vertices);
    assert(graph.internal_to_external.size() == graph.vertices);
    assert(graph.row_bounds.size() == graph.vertices + 1);
    assert(graph.initial_pma_words.size() % kWeightedPmaSegmentSlots == 0);
    assert(graph.binary_heads.size() ==
           graph.initial_pma_words.size() / kWeightedPmaSegmentSlots);

    for (std::uint32_t source = 0; source < graph.vertices; ++source) {
        const std::uint64_t row = graph.row_bounds[source];
        const std::size_t begin = row >> 32;
        const std::size_t end = static_cast<std::uint32_t>(row);
        assert(begin <= end);
        assert(end <= graph.initial_pma_words.size());
        assert(begin % kWeightedPmaSegmentSlots == 0);
        assert(end % kWeightedPmaSegmentSlots == 0);
        for (std::size_t slot = begin; slot < end;
             slot += kWeightedPmaSegmentSlots) {
            const std::uint64_t head = graph.binary_heads.at(
                slot / kWeightedPmaSegmentSlots);
            assert(static_cast<std::uint32_t>(head >> 32) == source);
        }
    }

    const EdgeMap internal = materialize(graph, graph.initial_pma_words);
    assert(unmap_edges(graph, internal) == external_oracle(initial, updates));
}

}  // namespace

int main()
{
    const std::vector<WeightedEdgeRecord> initial = {
        {.source = 0, .destination = 1, .weight = 8},
        {.source = 0, .destination = 2, .weight = 2},
        {.source = 1, .destination = 3, .weight = 1},
        {.source = 2, .destination = 3, .weight = 8},
        {.source = 3, .destination = 4, .weight = 1},
    };
    const std::vector<WeightedEdgeRecord> updates = {
        {.source = 0, .destination = 1, .weight = 3},
        {.source = 0, .destination = 2, .weight = 10},
        {.source = 1, .destination = 3, .weight = 1, .delete_op = true},
        {.source = 2, .destination = 3, .weight = 4},
        {.source = 2, .destination = 4, .weight = 2},
    };
    const WeightedPmaGraph graph =
        build_weighted_pma_graph(8, initial, updates);

    check_graph(initial, updates, graph);
    assert(graph.physical_updates.size() == 8);

    std::set<std::uint32_t> observed_weights;
    for (const std::uint64_t update : graph.physical_updates) {
        observed_weights.insert(decode_weighted_pma_weight(
            static_cast<std::uint32_t>(update)));
    }
    assert(observed_weights == std::set<std::uint32_t>({1, 2, 3, 4, 8, 10}));

    const auto actual = materialize(graph, graph.initial_pma_words);
    EdgeMap expected;
    for (const auto &edge : graph.final_internal) {
        expected[{edge.source, edge.destination}] = edge.weight;
    }
    assert(actual == expected);
    assert(actual.size() == 5);

    std::vector<WeightedEdgeRecord> boundary_initial;
    for (std::uint32_t destination = 1; destination <= 15; ++destination) {
        boundary_initial.push_back(
            {.source = 0, .destination = destination, .weight = 1});
    }
    const std::vector<WeightedEdgeRecord> boundary_updates = {
        {.source = 0, .destination = 16, .weight = 1},
        {.source = 0, .destination = 17, .weight = 1},
        {.source = 0, .destination = 1, .weight = 2},
        {.source = 0, .destination = 17, .weight = 1, .delete_op = true},
        {.source = 0, .destination = 18, .weight = 3},
    };
    const WeightedPmaGraph boundary =
        build_weighted_pma_graph(32, boundary_initial, boundary_updates);
    check_graph(boundary_initial, boundary_updates, boundary);
    const std::uint32_t internal_source = boundary.external_to_internal.at(0);
    const std::uint64_t boundary_row = boundary.row_bounds.at(internal_source);
    assert(static_cast<std::uint32_t>(boundary_row) - (boundary_row >> 32) ==
           2 * kWeightedPmaSegmentSlots);

    bool rejected = false;
    try {
        (void)build_weighted_pma_graph(
            8, initial,
            {{.source = 1,
              .destination = 3,
              .weight = 7,
              .delete_op = true}});
    } catch (const std::invalid_argument &) {
        rejected = true;
    }
    assert(rejected);
    return 0;
}
