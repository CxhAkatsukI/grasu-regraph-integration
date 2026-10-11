#include "weighted_pma_runtime_plan.hpp"

#include <algorithm>
#include <cassert>
#include <stdexcept>

using namespace grasu::integration;

int main()
{
    for (const std::size_t vertices : {1, 7, 8, 9, 15, 16, 17, 25, 511, 512, 513}) {
        const auto graph = build_weighted_partitioned_pma_graph(
            vertices, vertices, {{0, 0, 1}}, {});
        const auto old_plan = build_weighted_pma_runtime_plan(graph, 4);
        const auto new_plan = build_weighted_pma_runtime_plan(
            graph, 4, 23, kU55cHbmPseudoChannelBytes,
            WeightedPmaChannelPolicy::unrestricted, true);
        const auto old_buffers = pack_weighted_pma_runtime_buffers(graph, old_plan);
        const auto new_buffers = pack_weighted_pma_runtime_buffers(graph, new_plan);
        assert(new_plan.total_allocated_bytes == old_plan.total_allocated_bytes);
        assert(new_plan.channel_load_bytes == old_plan.channel_load_bytes);
        const auto &rows = new_buffers[0].row_bounds;
        assert(rows.size() == ((vertices + 1 + 7) / 8) * 8);
        assert(std::equal(old_buffers[0].row_bounds.begin(), old_buffers[0].row_bounds.end(), rows.begin()));
        assert(std::all_of(rows.begin() + vertices + 1, rows.end(), [](auto row) { return row == 0; }));
        assert(new_buffers[0].pma_words == old_buffers[0].pma_words);
        assert(new_buffers[0].updates == old_buffers[0].updates);
        assert(new_buffers[0].binary_heads == old_buffers[0].binary_heads);
        auto invalid = new_plan;
        invalid.shards[0].row_words = vertices;
        bool rejected = false;
        try {
            (void)pack_weighted_pma_runtime_buffers(graph, invalid);
        } catch (const std::logic_error &) {
            rejected = true;
        }
        assert(rejected);
    }
}
