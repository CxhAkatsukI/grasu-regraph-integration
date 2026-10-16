#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace integration_check {
using Word = ap_uint<512>;
using Row = std::array<std::uint32_t, 16>;
constexpr unsigned cold_size = MAX_CACHE_SEGMENT + 8;
static_assert(MAX_CACHE_SEGMENT == 131072, "Full production cache required");

struct Bank {
  std::vector<Word> memory;
  std::vector<Row> expected;
  explicit Bank(unsigned size) : memory(size), expected(size) {
    for (unsigned row = 0; row < size; ++row)
      for (unsigned lane = 0; lane < 16; ++lane) {
        const std::uint32_t value = lane < 15 ? 2 * lane + 2 : 0x80000000u;
        expected[row][lane] = value;
        memory[row].range(lane * 32 + 31, lane * 32) = value;
      }
  }
  void verify() const {
    for (unsigned row = 0; row < memory.size(); ++row)
      for (unsigned lane = 0; lane < 16; ++lane)
        if (memory[row].range(lane * 32 + 31, lane * 32).to_uint() != expected[row][lane])
          throw std::runtime_error("integrated PMA state mismatch");
  }
};

struct State {
  Bank hot[2] = {Bank(MAX_CACHE_SEGMENT), Bank(MAX_CACHE_SEGMENT)};
  Bank cold[2][2] = {{Bank(cold_size), Bank(cold_size)},
                     {Bank(cold_size), Bank(cold_size)}};
  std::vector<search_pipeline::Raw> binary =
      std::vector<search_pipeline::Raw>(2 * cold_size);
  std::array<search_pipeline::Raw, 8> rows{};

  static unsigned word(unsigned source, unsigned generation) {
    const unsigned mapped = source ^ (generation ? 4 : 0);
    return mapped < 4 ? mapped : MAX_CACHE_SEGMENT + mapped - 4;
  }
  void metadata(unsigned generation) {
    for (unsigned source = 0; source < 8; ++source) {
      const unsigned begin = 2 * word(source, generation);
      rows[source] = (std::uint64_t(begin * 16) << 32) | ((begin + 2) * 16);
      binary[begin] = std::uint64_t(source) << 32;
      binary[begin + 1] = (std::uint64_t(source) << 32) | 100;
    }
  }
  std::array<std::vector<unsigned long>, 4> updates(unsigned count, unsigned generation) {
    std::array<std::vector<unsigned long>, 4> lanes;
    for (unsigned i = 0; i < count; ++i) {
      const unsigned source = i % 8, half = (i / 8) % 2;
      const unsigned address = word(source, generation);
      const std::uint32_t key = half ? 117 : 17;
      Bank& bank = address < MAX_CACHE_SEGMENT ? hot[half] : cold[half][address & 1];
      Row& row = bank.expected[address];
      const auto position = std::lower_bound(row.begin(), row.end(), key);
      const bool erase = position != row.end() && *position == key;
      if (erase) {
        std::move(position + 1, row.end(), position);
        row.back() = 0x80000000u;
      } else {
        if (position == row.end() || row.back() != 0x80000000u)
          throw std::runtime_error("invalid integrated insertion fixture");
        std::move_backward(position, row.end() - 1, row.end());
        *position = key;
      }
      lanes[i % 4].push_back((std::uint64_t(erase) << 63) |
                            (std::uint64_t(source) << 32) | key);
    }
    return lanes;
  }
  void verify() const {
    for (const auto& bank : hot) bank.verify();
    for (const auto& half : cold) for (const auto& bank : half) bank.verify();
  }
};
}  // namespace integration_check
