#include "kernel_config.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

static_assert(MAX_CACHE_SEGMENT == 131072, "Reduced cache is not an accepted control");

extern "C" void process_cache(ap_uint<512>*, hls::stream<pipe_type_96>&
#ifdef GRASU_ENABLE_COMPLETION_TOKEN
                               , hls::stream<grasu_done_pkt_t>&
#endif
#ifdef GRASU_CACHE_VALID_EXTENT
                               , unsigned
#endif
                               );

namespace {
void check(unsigned count, bool conflict = false,
           unsigned valid_segments = MAX_CACHE_SEGMENT) {
  std::vector<ap_uint<512>> memory(MAX_CACHE_SEGMENT);
  std::vector<std::array<std::uint32_t, 16>> oracle(MAX_CACHE_SEGMENT);
  for (unsigned row = 0; row < MAX_CACHE_SEGMENT; ++row) {
    for (unsigned lane = 0; lane < 16; ++lane) {
      const std::uint32_t value = lane < 15 ? 2 * lane + 2 : 0x80000000u;
      oracle[row][lane] = value;
      memory[row].range(lane * 32 + 31, lane * 32) = value;
    }
  }
  hls::stream<pipe_type_96> updates;
  for (unsigned i = 0; i < count; ++i) {
    const unsigned lanes = std::min(16u, valid_segments);
    const unsigned row = conflict ? valid_segments - 1 : i % lanes;
    const unsigned occurrence = conflict ? i : i / lanes;
    const bool erase = occurrence & 1;
    auto& state = oracle[row];
    const auto position = std::lower_bound(state.begin(), state.end(), 17u);
    if (erase) {
      if (*position != 17) throw std::runtime_error("Invalid cache delete fixture");
      std::move(position + 1, state.end(), position);
      state.back() = 0x80000000u;
    } else {
      if (*position == 17) throw std::runtime_error("Invalid cache insert fixture");
      std::move_backward(position, state.end() - 1, state.end());
      *position = 17;
    }
    pipe_type_96 packet{};
    packet.data = std::uint32_t(row << 5);
    packet.data.range(63, 32) = 17;
    packet.data[95] = erase;
    updates.write(packet);
  }
  pipe_type_96 end{};
  end.data = END_EDGE;
  updates.write(end);
#ifdef GRASU_ENABLE_COMPLETION_TOKEN
  hls::stream<grasu_done_pkt_t> completion;
  process_cache(memory.data(), updates, completion
#ifdef GRASU_CACHE_VALID_EXTENT
                , valid_segments
#endif
                );
  if (completion.size() != 1) throw std::runtime_error("Cache completion count");
  const auto token = completion.read();
  if (token.data != 1 || !token.last || token.keep != decltype(token.keep)(-1) ||
      token.strb != decltype(token.strb)(-1))
    throw std::runtime_error("Cache completion payload/sidebands");
  constexpr unsigned token_present = 1;
#else
  process_cache(memory.data(), updates
#ifdef GRASU_CACHE_VALID_EXTENT
                , valid_segments
#endif
                );
  constexpr unsigned token_present = 0;
#endif
  if (!updates.empty()) throw std::runtime_error("Cache input not drained");
  for (unsigned row = 0; row < MAX_CACHE_SEGMENT; ++row)
    for (unsigned lane = 0; lane < 16; ++lane)
      if (memory[row].range(lane * 32 + 31, lane * 32).to_uint() != oracle[row][lane])
        throw std::runtime_error("Full cache state mismatch");
  std::cout << "PRODUCTION_CACHE_PASS updates=" << count << " conflict=" << conflict
            << " capacity=" << MAX_CACHE_SEGMENT << " token=" << token_present;
#ifdef GRASU_CACHE_VALID_EXTENT
  std::cout << " valid_segments=" << valid_segments;
#endif
  std::cout << '\n';
}
}  // namespace

int main() {
  try {
    check(0);
    check(16);
    check(64);
    check(4096);
    check(65536);
    check(4096, true);
#ifdef GRASU_CACHE_VALID_EXTENT
    check(0, false, 0);
    for (const unsigned extent : {1u, 15u, 16u, 17u, 131071u, 131072u}) {
      check(64, true, extent);
      check(64, false, extent);
    }
    check(16, true, 1);
    check(16, true, MAX_CACHE_SEGMENT);
#endif
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
