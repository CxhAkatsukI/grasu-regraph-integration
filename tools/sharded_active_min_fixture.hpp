#pragma once

#include "weighted_pma_graph.hpp"

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <vector>

namespace grasu_regraph::active_min {
constexpr std::uint32_t active = 0x80000000u;
constexpr std::uint32_t infinity = 0x7ffffffeu;
constexpr std::uint32_t partition = 65536;
constexpr std::uint32_t guard = 0xa55a5aa5u;
constexpr std::size_t guard_words = 16;

using Words = std::vector<std::uint32_t>;

inline void require(bool condition, const char *message)
{
    if (!condition) throw std::runtime_error(message);
}

inline std::ifstream open(const std::filesystem::path &path)
{
    require(std::filesystem::is_regular_file(std::filesystem::symlink_status(path)),
            "active-min fixture files must be regular");
    std::ifstream stream(path, std::ios::binary);
    require(static_cast<bool>(stream), "cannot open active-min fixture input");
    return stream;
}

inline Words read(std::ifstream &stream, std::size_t count)
{
    static_assert(__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__, "active-min fixture uses u32le");
    Words words(count);
    require(static_cast<bool>(stream.read(reinterpret_cast<char *>(words.data()),
                                         words.size() * sizeof(words[0]))),
            "truncated active-min fixture input");
    return words;
}

inline Words read_exact(const std::filesystem::path &path, std::size_t count)
{
    auto stream = open(path);
    auto words = read(stream, count);
    require(stream.peek() == std::ifstream::traits_type::eof() && stream.eof(),
            "active-min fixture has unexpected trailing data");
    return words;
}

struct Fixture {
    unsigned vertices{}, aligned{}, active_outputs{};
    Words initial, expected;
    std::vector<grasu::integration::WeightedEdgeRecord> edges;

    static Fixture load(const std::filesystem::path &directory,
                        const std::filesystem::path &reference, bool cc)
    {
        Fixture result;
        auto descriptor = open(directory / "execution.u32le");
        auto header = read(descriptor, 8);
        require(header[0] == 0x3447524fu && header[1] == 1 && header[7] > 0 &&
                    header[7] <= 255 && header[4] == header[7] * partition &&
                    header[5] == header[4] && header[2] <= header[4] &&
                    header[2] > header[4] - partition &&
                    header[3] > 0 && header[3] <= (1u << 26),
                "unsupported active-min reference geometry");
        result.vertices = header[2];
        result.aligned = header[4];
        const auto offsets = read_exact(directory / "csr_offsets.u32le", result.vertices + 1);
        const auto targets = read_exact(directory / "csr_destinations.u32le", header[3]);
        const auto weights = cc ? Words{} : read_exact(directory / "sssp_weights.u32le", header[3]);
        result.initial = read_exact(directory / (cc ? "cc_initial.u32le" : "sssp_initial.u32le"),
                                    result.aligned);
        result.expected = read_exact(reference, result.aligned + guard_words);
        require(std::all_of(result.expected.begin() + result.aligned, result.expected.end(),
                            [](auto word) { return word == guard; }),
                "reference output guard differs");
        result.expected.resize(result.aligned);
        auto replay = result.initial;
        for (unsigned vertex = 0; vertex < result.aligned; ++vertex) {
            auto &value = replay[vertex];
            require(vertex < result.vertices ? (value & ~active) < (cc ? result.vertices : infinity + 1)
                                             : value == 0,
                    "active-min state outside numeric domain");
            value &= ~active;
        }
        require(offsets.front() == 0 && offsets.back() == targets.size(), "invalid active-min CSR endpoints");
        result.edges.reserve(targets.size());
        Words sorted_row;
        for (unsigned source = 0; source < result.vertices; ++source) {
            const auto begin = offsets[source], end = offsets[source + 1];
            require(begin <= end && end <= targets.size(), "invalid active-min CSR bounds");
            sorted_row.assign(targets.begin() + begin, targets.begin() + end);
            std::sort(sorted_row.begin(), sorted_row.end());
            require(std::adjacent_find(sorted_row.begin(), sorted_row.end()) == sorted_row.end(),
                    "duplicate edges are not admitted in active-min comparison");
            for (auto i = begin; i < end; ++i) {
                const auto destination = targets[i], weight = cc ? 1u : weights[i];
                require(destination < result.vertices && weight > 0 && weight < 4096,
                        "active-min edge outside PMA domain");
                result.edges.push_back({source, destination, static_cast<std::uint16_t>(weight), false});
                const auto value = result.initial[source] & ~active;
                if (!(result.initial[source] & active) || (!cc && value == infinity)) continue;
                const auto candidate = value + (cc ? 0u : weight);
                require(candidate < infinity, "active-min candidate reaches infinity");
                if (candidate < (replay[destination] & ~active)) replay[destination] = candidate | active;
            }
        }
        require(replay == result.expected, "candidate CSR oracle differs from pinned A4 oracle");
        result.active_outputs = std::count_if(replay.begin(), replay.end(),
                                              [](auto word) { return word & active; });
        require(result.active_outputs != 0, "empty propagation is not a retention fixture");
        return result;
    }

    void write(const std::filesystem::path &path, const Words &words) const
    {
        require(!std::filesystem::exists(std::filesystem::symlink_status(path)),
                "active-min output must be fresh");
        std::ofstream stream(path, std::ios::binary);
        stream.write(reinterpret_cast<const char *>(words.data()), words.size() * sizeof(words[0]));
        stream.close();
        require(static_cast<bool>(stream), "failed to write active-min output");
    }

    template <class Buffer>
    Words externalize(const Buffer &buffer, const Words &external_to_internal) const
    {
        require(buffer.size() == aligned && external_to_internal.size() == vertices,
                "candidate active-min publication extent differs");
        Words words(aligned);
        for (unsigned v = 0; v < vertices; ++v) words[v] = buffer.at(external_to_internal.at(v));
        std::copy(buffer.begin() + vertices, buffer.end(), words.begin() + vertices);
        return words;
    }
};
}  // namespace grasu_regraph::active_min
