#include "../grasu_complete/search_binding/top.cpp"
#include "../grasu_complete/process_cache.cpp"
#include "../upstream/kernel_dispatch.cpp"
#include "../upstream/kernel_process_ddr.cpp"
#include "state.hpp"
#include "execution.hpp"
#include <iostream>
#include <string>

int main(int argc, char** argv) {
  try {
    const bool stale = argc == 2 && std::string(argv[1]) == "--stale-metadata";
    if (argc > 1 && !stale) throw std::runtime_error("unknown fixture argument");
    search_pipeline::configure_host_threads();
    integration_check::State state;
    const auto* binary = state.binary.data();
    const auto* rows = state.rows.data();
    const auto* memory = state.hot[0].memory.data();
    // State and metadata allocations survive every transaction; only their
    // contents change. This is not an XRT/device-BO refresh test.
    for (const unsigned count : {0u, 1u, 63u, 64u, 65u, 127u, 128u, 129u, 257u})
      for (unsigned generation = 0; generation < 2; ++generation) {
        if (!stale || generation == 0) state.metadata(generation);
        const auto updates = state.updates(count, generation);
        const auto blocked = integration_check::execute(state, updates, count);
        state.verify();
        if (state.binary.data() != binary || state.rows.data() != rows ||
            state.hot[0].memory.data() != memory)
          throw std::runtime_error("integration buffer address changed");
        std::cout << "PRODUCTION_CONNECTED_PASS updates=" << count << " generation=" << generation
                  << " capacity=" << MAX_CACHE_SEGMENT << " search=4 cache=2 cold=2"
                  << " external_channels=12 internal_channels=1356 completions=4"
                  << " blocked=" << blocked << " same_addresses=1\n";
      }
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
