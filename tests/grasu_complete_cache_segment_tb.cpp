#include "../kernels/grasu_complete/cache_lane.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>

namespace {
std::uint32_t random_word(std::uint32_t& state) {
  state ^= state << 13;
  state ^= state >> 17;
  state ^= state << 5;
  return state;
}

void check(std::array<std::uint32_t, 16> words, std::uint32_t key) {
  std::sort(words.begin(), words.end());
  CacheWord before = 0;
  for (unsigned i = 0; i < words.size(); ++i)
    before.range(32 * i + 31, 32 * i) = words[i];
  const auto comparisons = cache_probe_detail::compare_lanes(before, key);
  for (unsigned i = 0; i < words.size(); ++i)
    if (bool(comparisons[i]) != (words[i] < key))
      throw std::runtime_error("Comparison-stage mismatch");
  const unsigned position = std::lower_bound(words.begin(), words.end(), key) - words.begin();
  for (bool erase : {false, true}) {
    auto expected = words;
    if (position != words.size()) {
      if (erase) {
        std::move(expected.begin() + position + 1, expected.end(), expected.begin() + position);
        expected.back() = 0x80000000u;
      } else {
        std::move_backward(expected.begin() + position, expected.end() - 1, expected.end());
        expected[position] = key;
      }
    }
    const auto actual = cache_probe_detail::edit_segment(before, key, erase);
    for (unsigned i = 0; i < words.size(); ++i)
      if (actual.range(32 * i + 31, 32 * i).to_uint() != expected[i])
        throw std::runtime_error("Segment oracle mismatch");
  }
}
}  // namespace

int main() {
  try {
    std::uint32_t state = 0x6410abe3u;
    unsigned checks = 0;
    for (unsigned occupancy = 0; occupancy <= 16; ++occupancy) {
      for (unsigned sample = 0; sample < 256; ++sample) {
        std::array<std::uint32_t, 16> words;
        words.fill(0x80000000u);
        for (unsigned i = 0; i < occupancy; ++i)
          words[i] = random_word(state) & 0x7fffffffu;
        for (const std::uint32_t key : {0u, 1u, 0x7fffffffu, 0x80000000u,
                                       0xffffffffu, random_word(state)}) {
          check(words, key);
          ++checks;
        }
      }
    }
    std::cout << "CACHE_SEGMENT_ORACLE_PASS cases=" << checks << '\n';
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
