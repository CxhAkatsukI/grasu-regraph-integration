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
                               );

namespace {
void check(unsigned count, bool conflict = false) {
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
    const unsigned row = conflict ? 0 : i % 16;
    const unsigned occurrence = conflict ? i : i / 16;
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
  process_cache(memory.data(), updates, completion);
  if (completion.size() != 1) throw std::runtime_error("Cache completion count");
  const auto token = completion.read();
  if (token.data != 1 || !token.last || token.keep != decltype(token.keep)(-1) ||
      token.strb != decltype(token.strb)(-1))
    throw std::runtime_error("Cache completion payload/sidebands");
  constexpr unsigned token_present = 1;
#else
  process_cache(memory.data(), updates);
  constexpr unsigned token_present = 0;
#endif
  if (!updates.empty()) throw std::runtime_error("Cache input not drained");
  for (unsigned row = 0; row < MAX_CACHE_SEGMENT; ++row)
    for (unsigned lane = 0; lane < 16; ++lane)
      if (memory[row].range(lane * 32 + 31, lane * 32).to_uint() != oracle[row][lane])
        throw std::runtime_error("Full cache state mismatch");
  std::cout << "PRODUCTION_CACHE_PASS updates=" << count << " conflict=" << conflict
            << " capacity=" << MAX_CACHE_SEGMENT << " token=" << token_present << '\n';
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
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
