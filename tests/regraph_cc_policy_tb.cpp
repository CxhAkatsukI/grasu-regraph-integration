#include <ap_int.h>

#include <array>
#include <cassert>
#include <utility>

#include "../include/regraph_cc/l2.h"

int main()
{
    constexpr unsigned kVertices = 6;
    constexpr unsigned kActiveMask = 0x80000000U;
    const std::array<std::pair<unsigned, unsigned>, 6> edges = {{
        {0, 1}, {1, 0}, {1, 2}, {2, 1}, {3, 4}, {4, 3},
    }};

    std::array<prop_t, kVertices> labels{};
    for (unsigned vertex = 0; vertex < kVertices; ++vertex) {
        labels[vertex] = kActiveMask | vertex;
    }

    bool converged = false;
    for (unsigned round = 0; round < kVertices; ++round) {
        std::array<prop_t, kVertices> reduced{};
        for (const auto &[source, destination] : edges) {
            reduced[destination] = gatherFunc(
                reduced[destination], scatterFunc(labels[source], 0));
        }

        unsigned active = 0;
        for (unsigned vertex = 0; vertex < kVertices; ++vertex) {
            labels[vertex] = applyFunc(reduced[vertex], labels[vertex], 0, 0);
            active += regraph_cc_is_active(labels[vertex]) ? 1U : 0U;
        }
        if (active == 0) {
            converged = true;
            break;
        }
    }

    assert(converged);
    const std::array<unsigned, kVertices> expected = {0, 0, 0, 3, 3, 5};
    for (unsigned vertex = 0; vertex < kVertices; ++vertex) {
        assert(regraph_cc_label(labels[vertex]) == expected[vertex]);
        assert(!regraph_cc_is_active(labels[vertex]));
    }
    return 0;
}
