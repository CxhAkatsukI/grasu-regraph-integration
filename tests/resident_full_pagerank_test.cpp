#include "../tools/resident_full_pagerank.hpp"

#include <iostream>
#include <limits>
#include <map>
#include <utility>

namespace pr = grasu::integration::resident_pr;
using Edges = std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint16_t>;

void check(bool condition, const char *message)
{
    if (!condition) throw std::runtime_error(message);
}

template <typename Function>
void rejects(Function function)
{
    try { function(); }
    catch (const std::runtime_error &) { return; }
    throw std::runtime_error("missing FullPR rejection");
}

int main()
{
    Edges dangling{{{0, 1}, 1}};
    auto single = pr::converge(2, dangling, {0.5F, 0.5F}, 0.85F, 1.0e-6, 1);
    check(!single.converged && single.rounds == 1 &&
              std::fabs(single.rank[0] - 0.2875F) < 1.0e-6F &&
              std::fabs(single.rank[1] - 0.7125F) < 1.0e-6F,
          "incorrect dangling redistribution or convergence");
    Edges cycle{{{0, 1}, 1}, {{1, 2}, 1}, {{2, 0}, 1}};
    const std::vector<float> uniform(3, 1.0F / 3.0F);
    auto old = pr::converge(3, cycle, uniform, 0.85F, 1.0e-6, 128);
    check(old.converged && old.rounds == 1, "old cycle is not stationary");
    cycle[{0, 2}] = 17;
    const auto updated = pr::converge(3, cycle, old.rank, 0.85F, 1.0e-6, 256);
    check(updated.converged && updated.rounds > 3 &&
              updated.out_degree == std::vector<std::uint32_t>({2, 1, 1}),
          "resident reference is a fixed-three-round or wrong-degree result");
    const auto verify = pr::converge(3, cycle, updated.rank, 0.85F, 1.0e-6, 1);
    check(verify.converged && pr::l1(updated.rank, verify.rank) <= 1.0e-6,
          "final state is not a fixed point");
    double mass = 0.0;
    for (float rank : updated.rank) mass += rank;
    check(std::fabs(mass - 1.0) < 1.0e-5, "probability mass is not conserved");
    for (auto &edge : cycle) edge.second = 1;
    check(pr::l1(updated.rank,
                  pr::converge(3, cycle, old.rank, 0.85F, 1.0e-6, 256).rank) == 0.0,
          "PageRank must ignore edge weights");
    rejects([&] { pr::converge(0, cycle, {}, 0.85F, 1.0e-6, 256); });
    rejects([&] { pr::converge(2, cycle, {0.5F, 0.5F}, 0.85F, 1.0e-6, 256); });
    rejects([&] { pr::converge(3, cycle, uniform, 0.85F, 1.0e-6, 0); });
    rejects([&] { pr::converge(3, cycle, uniform, 1.0F, 1.0e-6, 256); });
    rejects([&] { pr::converge(3, cycle, uniform, 0.85F, -1.0, 256); });
    rejects([&] { pr::converge(3, cycle, {0.3F, -0.1F, 0.8F},
                              0.85F, 1.0e-6, 256); });
    rejects([&] { pr::l1({std::numeric_limits<float>::quiet_NaN()}, {1.0F}); });
    rejects([&] { pr::l1({1.0F}, {}); });
    std::cout << "FULLPR_REFERENCE_TEST_PASS scope=cpu_only_not_fpga\n";
}
