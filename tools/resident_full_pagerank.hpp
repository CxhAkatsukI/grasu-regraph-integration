#ifndef GRASU_REGRAPH_RESIDENT_FULL_PAGERANK_HPP
#define GRASU_REGRAPH_RESIDENT_FULL_PAGERANK_HPP

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

namespace grasu::integration::resident_pr {

inline double l1(const std::vector<float> &left,
                 const std::vector<float> &right)
{
    if (left.size() != right.size()) {
        throw std::runtime_error("FullPR rank extent mismatch");
    }
    double error = 0.0;
    for (std::size_t vertex = 0; vertex < left.size(); ++vertex) {
        if (!std::isfinite(left[vertex]) || left[vertex] < 0.0F ||
            !std::isfinite(right[vertex]) || right[vertex] < 0.0F) {
            throw std::runtime_error("FullPR invalid rank");
        }
        error += std::fabs(static_cast<double>(left[vertex]) - right[vertex]);
    }
    return error;
}

struct Reference {
    std::vector<float> rank;
    std::vector<std::uint32_t> out_degree;
    unsigned rounds = 0;
    bool converged = false;
};

// Edge weights do not enter PageRank; each map key denotes one directed edge.
template <typename Edges>
Reference converge(std::size_t vertices, const Edges &edges,
                   const std::vector<float> &initial, float damping,
                   double epsilon, unsigned limit)
{
    if (vertices == 0 || initial.size() != vertices || limit == 0 ||
        !std::isfinite(damping) || damping < 0.0F || damping >= 1.0F ||
        !std::isfinite(epsilon) || epsilon <= 0.0) {
        throw std::runtime_error("FullPR invalid convergence configuration");
    }
    l1(initial, initial);
    Reference result;
    result.rank = initial;
    result.out_degree.assign(vertices, 0);
    for (const auto &edge : edges) {
        if (edge.first.first >= vertices || edge.first.second >= vertices) {
            throw std::runtime_error("FullPR edge out of domain");
        }
        ++result.out_degree[edge.first.first];
    }
    for (unsigned round = 0; round < limit; ++round) {
        float dangling = 0.0F;
        for (std::size_t vertex = 0; vertex < vertices; ++vertex) {
            if (result.out_degree[vertex] == 0) dangling += result.rank[vertex];
        }
        std::vector<float> next(vertices,
            (1.0F - damping) / static_cast<float>(vertices) +
            damping * dangling / static_cast<float>(vertices));
        for (const auto &edge : edges) {
            const auto source = edge.first.first;
            next[edge.first.second] += damping * result.rank[source] /
                static_cast<float>(result.out_degree[source]);
        }
        result.converged = l1(next, result.rank) <= epsilon;
        result.rank = std::move(next);
        result.rounds = round + 1;
        if (result.converged) break;
    }
    return result;
}

}  // namespace grasu::integration::resident_pr

#endif
