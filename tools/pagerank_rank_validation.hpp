#pragma once

#include <cmath>
#include <cstddef>

namespace grasu_regraph {

// A per-vertex absolute tolerance alone can accept an all-zero large graph.
struct PageRankValidation {
    double expected_l1 = 0.0;
    double error_l1 = 0.0;
    std::size_t nonfinite = 0;

    void observe(double expected, double actual)
    {
        if (!std::isfinite(expected) || !std::isfinite(actual)) {
            ++nonfinite;
            return;
        }
        expected_l1 += std::abs(expected);
        error_l1 += std::abs(actual - expected);
    }

    double error_limit() const { return 1.0e-4 + 1.0e-3 * expected_l1; }

    bool passes() const
    {
        return nonfinite == 0 && std::isfinite(error_l1) &&
               std::isfinite(expected_l1) && error_l1 <= error_limit();
    }
};

}  // namespace grasu_regraph
