#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iterator>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
#include <utility>
#include <vector>

namespace grasu::integration {

constexpr std::uint32_t kWeightedPmaEmpty = 0x80000000U;
constexpr std::uint64_t kWeightedPmaDelete = 0x8000000000000000ULL;
constexpr std::uint32_t kWeightedPmaDestinationMask = 0x7ffffU;
constexpr std::uint32_t kWeightedPmaWeightMask = 0xfffU;
constexpr std::uint32_t kWeightedPmaWeightShift = 19U;
constexpr std::size_t kWeightedPmaSegmentSlots = 16;

struct WeightedEdgeRecord {
    std::uint32_t source{};
    std::uint32_t destination{};
    std::uint16_t weight{1};
    bool delete_op{};
};

struct WeightedPmaGraph {
    std::size_t vertices{};
    std::vector<std::uint32_t> external_to_internal;
    std::vector<std::uint32_t> internal_to_external;
    std::vector<std::uint64_t> row_bounds;
    std::vector<std::uint64_t> binary_heads;
    std::vector<std::uint32_t> initial_pma_words;
    std::vector<std::uint64_t> physical_updates;
    std::vector<WeightedEdgeRecord> initial_internal;
    std::vector<WeightedEdgeRecord> final_internal;
};

struct WeightedPmaShard {
    std::size_t source_vertices{};
    std::uint32_t destination_base{};
    std::size_t destination_vertices{};
    std::vector<std::uint64_t> row_bounds;
    std::vector<std::uint64_t> binary_heads;
    std::vector<std::uint32_t> initial_pma_words;
    std::vector<std::uint64_t> physical_updates;
    std::vector<WeightedEdgeRecord> initial_internal;
    std::vector<WeightedEdgeRecord> final_internal;
};

struct WeightedPartitionedPmaGraph {
    std::size_t vertices{};
    std::size_t partition_vertices{};
    std::vector<std::uint32_t> external_to_internal;
    std::vector<std::uint32_t> internal_to_external;
    std::vector<WeightedEdgeRecord> initial_internal;
    std::vector<WeightedEdgeRecord> physical_internal;
    std::vector<WeightedEdgeRecord> final_internal;
    std::vector<WeightedPmaShard> shards;
};

inline std::uint32_t encode_weighted_pma_word(std::uint32_t destination,
                                              std::uint16_t weight)
{
    if (destination > kWeightedPmaDestinationMask || weight == 0 ||
        weight > kWeightedPmaWeightMask) {
        throw std::invalid_argument("weighted PMA edge exceeds dst19/weight12 ABI");
    }
    return destination |
           (static_cast<std::uint32_t>(weight) << kWeightedPmaWeightShift);
}

inline std::uint32_t decode_weighted_pma_destination(std::uint32_t word)
{
    return word & kWeightedPmaDestinationMask;
}

inline std::uint16_t decode_weighted_pma_weight(std::uint32_t word)
{
    return static_cast<std::uint16_t>(
        (word >> kWeightedPmaWeightShift) & kWeightedPmaWeightMask);
}

inline std::uint64_t pack_weighted_update(std::uint32_t source,
                                          std::uint32_t word,
                                          bool delete_op)
{
    if ((word & kWeightedPmaEmpty) != 0 || source >= (1U << 31)) {
        throw std::invalid_argument("weighted PMA update exceeds packed ABI");
    }
    const std::uint64_t packed =
        (static_cast<std::uint64_t>(source) << 32) | word;
    return delete_op ? packed | kWeightedPmaDelete : packed;
}

namespace detail {

using EdgeKey = std::pair<std::uint32_t, std::uint32_t>;

inline std::size_t round_up_segments(std::size_t records)
{
    return records == 0
               ? 0
               : (records + kWeightedPmaSegmentSlots - 1) /
                     kWeightedPmaSegmentSlots;
}

inline void validate_record(const WeightedEdgeRecord &edge,
                            std::size_t vertices)
{
    if (edge.source >= vertices || edge.destination >= vertices) {
        throw std::invalid_argument("weighted PMA edge vertex is out of range");
    }
    (void)encode_weighted_pma_word(edge.destination, edge.weight);
}

inline WeightedEdgeRecord map_record(
    const WeightedEdgeRecord &edge,
    const std::vector<std::uint32_t> &external_to_internal)
{
    return {
        .source = external_to_internal.at(edge.source),
        .destination = external_to_internal.at(edge.destination),
        .weight = edge.weight,
        .delete_op = edge.delete_op,
    };
}

}  // namespace detail

inline WeightedPmaGraph build_weighted_pma_graph(
    std::size_t vertices,
    const std::vector<WeightedEdgeRecord> &initial,
    const std::vector<WeightedEdgeRecord> &updates)
{
    if (vertices == 0 || vertices > kWeightedPmaDestinationMask + 1ULL) {
        throw std::invalid_argument("weighted PMA graph exceeds one dst19 partition");
    }
    std::map<detail::EdgeKey, std::uint16_t> state;
    std::vector<std::set<std::pair<std::uint32_t, std::uint16_t>>>
        reserved_variants(vertices);
    for (const auto &edge : initial) {
        detail::validate_record(edge, vertices);
        if (edge.delete_op ||
            !state.emplace(detail::EdgeKey{edge.source, edge.destination},
                           edge.weight)
                 .second) {
            throw std::invalid_argument("invalid duplicate initial weighted edge");
        }
        reserved_variants.at(edge.source).insert(
            {edge.destination, edge.weight});
    }

    std::vector<WeightedEdgeRecord> physical_external;
    for (const auto &update : updates) {
        detail::validate_record(update, vertices);
        const detail::EdgeKey key{update.source, update.destination};
        const auto found = state.find(key);
        if (update.delete_op) {
            if (found == state.end() || found->second != update.weight) {
                throw std::invalid_argument(
                    "weighted PMA delete target or weight does not match");
            }
            physical_external.push_back(update);
            state.erase(found);
            continue;
        }

        reserved_variants.at(update.source).insert(
            {update.destination, update.weight});
        if (found == state.end()) {
            physical_external.push_back(update);
            state.emplace(key, update.weight);
        } else if (found->second != update.weight) {
            physical_external.push_back({
                .source = update.source,
                .destination = update.destination,
                .weight = found->second,
                .delete_op = true,
            });
            physical_external.push_back(update);
            found->second = update.weight;
        } else {
            throw std::invalid_argument(
                "weighted PMA insert target already exists with same weight");
        }
    }

    std::vector<std::uint32_t> physical_update_count(vertices, 0);
    for (const auto &update : physical_external) {
        ++physical_update_count.at(update.source);
    }

    std::vector<std::pair<std::uint32_t, double>> reorder;
    reorder.reserve(vertices);
    for (std::uint32_t vertex = 0; vertex < vertices; ++vertex) {
        const std::size_t segments =
            detail::round_up_segments(reserved_variants[vertex].size());
        const double density =
            segments == 0
                ? -1.0
                : static_cast<double>(physical_update_count[vertex]) /
                      static_cast<double>(segments);
        reorder.emplace_back(vertex, density);
    }
    std::sort(reorder.begin(), reorder.end(),
              [](const auto &left, const auto &right) {
                  if (left.second != right.second) {
                      return left.second > right.second;
                  }
                  return left.first < right.first;
              });

    WeightedPmaGraph result;
    result.vertices = vertices;
    result.external_to_internal.resize(vertices);
    result.internal_to_external.resize(vertices);
    for (std::uint32_t internal = 0; internal < vertices; ++internal) {
        const std::uint32_t external = reorder[internal].first;
        result.external_to_internal[external] = internal;
        result.internal_to_external[internal] = external;
    }

    std::vector<std::vector<std::uint32_t>> reserved_words(vertices);
    for (std::uint32_t external_source = 0; external_source < vertices;
         ++external_source) {
        const std::uint32_t internal_source =
            result.external_to_internal[external_source];
        auto &words = reserved_words[internal_source];
        for (const auto &[external_destination, weight] :
             reserved_variants[external_source]) {
            words.push_back(encode_weighted_pma_word(
                result.external_to_internal[external_destination], weight));
        }
        std::sort(words.begin(), words.end());
    }

    result.row_bounds.resize(vertices + 1, 0);
    std::size_t total_slots = 0;
    for (std::uint32_t source = 0; source < vertices; ++source) {
        const std::size_t begin = total_slots;
        std::size_t source_segments =
            detail::round_up_segments(reserved_words[source].size());
        // ReGraph's stream consumer performs at least one blocking read. Keep a
        // protocol-visible dummy segment even when the entire graph is empty.
        if (source == 0 && total_slots == 0 && source_segments == 0) {
            source_segments = 1;
        }
        total_slots += source_segments * kWeightedPmaSegmentSlots;
        if (total_slots > std::numeric_limits<std::uint32_t>::max()) {
            throw std::overflow_error("weighted PMA row offsets exceed 32 bits");
        }
        result.row_bounds[source] =
            (static_cast<std::uint64_t>(begin) << 32) | total_slots;
    }
    result.row_bounds[vertices] =
        (static_cast<std::uint64_t>(total_slots) << 32) | total_slots;
    result.initial_pma_words.assign(total_slots, kWeightedPmaEmpty);
    result.binary_heads.assign(total_slots / kWeightedPmaSegmentSlots, 0);

    std::vector<std::vector<std::uint32_t>> initial_words(vertices);
    for (const auto &edge : initial) {
        const auto mapped = detail::map_record(edge, result.external_to_internal);
        result.initial_internal.push_back(mapped);
        initial_words[mapped.source].push_back(
            encode_weighted_pma_word(mapped.destination, mapped.weight));
    }
    for (auto &[key, weight] : state) {
        result.final_internal.push_back(detail::map_record(
            {.source = key.first,
             .destination = key.second,
             .weight = weight,
             .delete_op = false},
            result.external_to_internal));
    }

    for (std::uint32_t source = 0; source < vertices; ++source) {
        const std::size_t row_begin = result.row_bounds[source] >> 32;
        const auto &reserved = reserved_words[source];
        for (std::size_t offset = 0; offset < reserved.size();
             offset += kWeightedPmaSegmentSlots) {
            const std::size_t segment =
                (row_begin + offset) / kWeightedPmaSegmentSlots;
            result.binary_heads[segment] =
                (static_cast<std::uint64_t>(source) << 32) | reserved[offset];
        }
        std::sort(initial_words[source].begin(), initial_words[source].end());
        for (const std::uint32_t word : initial_words[source]) {
            const auto reserved_position =
                std::lower_bound(reserved.begin(), reserved.end(), word);
            if (reserved_position == reserved.end() || *reserved_position != word) {
                throw std::logic_error("initial weighted edge lacks a reserved slot");
            }
            const std::size_t reserved_offset =
                static_cast<std::size_t>(reserved_position - reserved.begin());
            const std::size_t segment_begin =
                row_begin +
                (reserved_offset / kWeightedPmaSegmentSlots) *
                    kWeightedPmaSegmentSlots;
            auto first = result.initial_pma_words.begin() + segment_begin;
            auto last = first + kWeightedPmaSegmentSlots;
            auto output = std::find(first, last, kWeightedPmaEmpty);
            if (output == last) {
                throw std::logic_error("initial weighted PMA segment overflowed");
            }
            *output = word;
            std::sort(first, last);
        }
    }

    for (const auto &edge : physical_external) {
        const auto mapped = detail::map_record(edge, result.external_to_internal);
        result.physical_updates.push_back(pack_weighted_update(
            mapped.source,
            encode_weighted_pma_word(mapped.destination, mapped.weight),
            mapped.delete_op));
    }
    return result;
}

inline WeightedPartitionedPmaGraph build_weighted_partitioned_pma_graph(
    std::size_t vertices,
    std::size_t partition_vertices,
    const std::vector<WeightedEdgeRecord> &initial,
    const std::vector<WeightedEdgeRecord> &updates)
{
    if (vertices == 0 ||
        vertices > std::numeric_limits<std::uint32_t>::max() ||
        partition_vertices == 0 ||
        partition_vertices > kWeightedPmaDestinationMask + 1ULL) {
        throw std::invalid_argument("invalid weighted partitioned PMA dimensions");
    }

    std::map<detail::EdgeKey, std::uint16_t> state;
    std::vector<std::set<std::pair<std::uint32_t, std::uint16_t>>>
        reserved_variants(vertices);
    for (const auto &edge : initial) {
        if (edge.source >= vertices || edge.destination >= vertices ||
            edge.weight == 0 || edge.weight > kWeightedPmaWeightMask ||
            edge.delete_op ||
            !state.emplace(detail::EdgeKey{edge.source, edge.destination},
                           edge.weight)
                 .second) {
            throw std::invalid_argument(
                "invalid initial edge for weighted partitioned PMA");
        }
        reserved_variants.at(edge.source).insert(
            {edge.destination, edge.weight});
    }

    std::vector<WeightedEdgeRecord> physical_external;
    for (const auto &update : updates) {
        if (update.source >= vertices || update.destination >= vertices ||
            update.weight == 0 || update.weight > kWeightedPmaWeightMask) {
            throw std::invalid_argument(
                "invalid update for weighted partitioned PMA");
        }
        const detail::EdgeKey key{update.source, update.destination};
        const auto found = state.find(key);
        if (update.delete_op) {
            if (found == state.end() || found->second != update.weight) {
                throw std::invalid_argument(
                    "weighted partitioned PMA delete target or weight does not match");
            }
            physical_external.push_back(update);
            state.erase(found);
            continue;
        }

        reserved_variants.at(update.source).insert(
            {update.destination, update.weight});
        if (found == state.end()) {
            physical_external.push_back(update);
            state.emplace(key, update.weight);
        } else if (found->second != update.weight) {
            physical_external.push_back({
                .source = update.source,
                .destination = update.destination,
                .weight = found->second,
                .delete_op = true,
            });
            physical_external.push_back(update);
            found->second = update.weight;
        } else {
            throw std::invalid_argument(
                "weighted partitioned PMA insert already exists with same weight");
        }
    }

    std::vector<std::uint32_t> physical_update_count(vertices, 0);
    for (const auto &update : physical_external) {
        if (physical_update_count.at(update.source) ==
            std::numeric_limits<std::uint32_t>::max()) {
            throw std::overflow_error(
                "weighted partitioned PMA per-source update count overflow");
        }
        ++physical_update_count[update.source];
    }

    std::vector<std::pair<std::uint32_t, double>> reorder;
    reorder.reserve(vertices);
    for (std::uint32_t vertex = 0; vertex < vertices; ++vertex) {
        const std::size_t segments =
            detail::round_up_segments(reserved_variants[vertex].size());
        const double density =
            segments == 0
                ? -1.0
                : static_cast<double>(physical_update_count[vertex]) /
                      static_cast<double>(segments);
        reorder.emplace_back(vertex, density);
    }
    std::sort(reorder.begin(), reorder.end(),
              [](const auto &left, const auto &right) {
                  if (left.second != right.second) {
                      return left.second > right.second;
                  }
                  return left.first < right.first;
              });

    WeightedPartitionedPmaGraph result;
    result.vertices = vertices;
    result.partition_vertices = partition_vertices;
    result.external_to_internal.resize(vertices);
    result.internal_to_external.resize(vertices);
    for (std::uint32_t internal = 0; internal < vertices; ++internal) {
        const std::uint32_t external = reorder[internal].first;
        result.external_to_internal[external] = internal;
        result.internal_to_external[internal] = external;
    }
    const auto remap = [&result](const WeightedEdgeRecord &edge) {
        WeightedEdgeRecord mapped = edge;
        mapped.source = result.external_to_internal.at(edge.source);
        mapped.destination = result.external_to_internal.at(edge.destination);
        return mapped;
    };
    result.initial_internal.reserve(initial.size());
    std::transform(initial.begin(), initial.end(),
                   std::back_inserter(result.initial_internal), remap);
    result.physical_internal.reserve(physical_external.size());
    std::transform(physical_external.begin(), physical_external.end(),
                   std::back_inserter(result.physical_internal), remap);
    result.final_internal.reserve(state.size());
    for (const auto &[key, weight] : state) {
        result.final_internal.push_back(remap({
            .source = key.first,
            .destination = key.second,
            .weight = weight,
            .delete_op = false,
        }));
    }

    const std::size_t partition_count =
        (vertices + partition_vertices - 1) / partition_vertices;
    std::vector<std::vector<WeightedEdgeRecord>> initial_by_shard(partition_count);
    std::vector<std::vector<WeightedEdgeRecord>> updates_by_shard(partition_count);
    std::vector<std::vector<WeightedEdgeRecord>> final_by_shard(partition_count);
    for (const auto &edge : result.initial_internal) {
        initial_by_shard.at(edge.destination / partition_vertices).push_back(edge);
    }
    for (const auto &edge : result.physical_internal) {
        updates_by_shard.at(edge.destination / partition_vertices).push_back(edge);
    }
    for (const auto &edge : result.final_internal) {
        final_by_shard.at(edge.destination / partition_vertices).push_back(edge);
    }

    result.shards.reserve(partition_count);
    for (std::size_t partition = 0; partition < partition_count; ++partition) {
        WeightedPmaShard shard;
        shard.source_vertices = vertices;
        shard.destination_base =
            static_cast<std::uint32_t>(partition * partition_vertices);
        shard.destination_vertices =
            std::min(partition_vertices, vertices - shard.destination_base);
        shard.initial_internal = std::move(initial_by_shard[partition]);
        shard.final_internal = std::move(final_by_shard[partition]);

        std::vector<std::set<std::uint32_t>> reserved_words(vertices);
        std::vector<std::vector<std::uint32_t>> initial_words(vertices);
        for (const auto &edge : shard.initial_internal) {
            const std::uint32_t local = edge.destination - shard.destination_base;
            const std::uint32_t word =
                encode_weighted_pma_word(local, edge.weight);
            reserved_words.at(edge.source).insert(word);
            initial_words.at(edge.source).push_back(word);
        }
        for (const auto &edge : updates_by_shard[partition]) {
            if (!edge.delete_op) {
                reserved_words.at(edge.source).insert(encode_weighted_pma_word(
                    edge.destination - shard.destination_base, edge.weight));
            }
        }

        shard.row_bounds.resize(vertices + 1, 0);
        std::size_t total_slots = 0;
        for (std::uint32_t source = 0; source < vertices; ++source) {
            const std::size_t begin = total_slots;
            std::size_t source_segments =
                detail::round_up_segments(reserved_words[source].size());
            if (source == 0 && total_slots == 0 && source_segments == 0) {
                source_segments = 1;
            }
            total_slots += source_segments * kWeightedPmaSegmentSlots;
            if (total_slots > std::numeric_limits<std::uint32_t>::max()) {
                throw std::overflow_error(
                    "weighted partitioned PMA shard offsets exceed 32 bits");
            }
            shard.row_bounds[source] =
                (static_cast<std::uint64_t>(begin) << 32) | total_slots;
        }
        shard.row_bounds[vertices] =
            (static_cast<std::uint64_t>(total_slots) << 32) | total_slots;
        shard.initial_pma_words.assign(total_slots, kWeightedPmaEmpty);
        shard.binary_heads.assign(total_slots / kWeightedPmaSegmentSlots, 0);

        for (std::uint32_t source = 0; source < vertices; ++source) {
            const std::size_t row_begin = shard.row_bounds[source] >> 32;
            const std::vector<std::uint32_t> reserved(
                reserved_words[source].begin(), reserved_words[source].end());
            for (std::size_t offset = 0; offset < reserved.size();
                 offset += kWeightedPmaSegmentSlots) {
                const std::size_t segment =
                    (row_begin + offset) / kWeightedPmaSegmentSlots;
                shard.binary_heads[segment] =
                    (static_cast<std::uint64_t>(source) << 32) |
                    reserved[offset];
            }
            std::sort(initial_words[source].begin(), initial_words[source].end());
            for (const std::uint32_t word : initial_words[source]) {
                const auto reserved_position =
                    std::lower_bound(reserved.begin(), reserved.end(), word);
                if (reserved_position == reserved.end() ||
                    *reserved_position != word) {
                    throw std::logic_error(
                        "initial partitioned PMA edge lacks a reserved slot");
                }
                const std::size_t reserved_offset =
                    static_cast<std::size_t>(reserved_position - reserved.begin());
                const std::size_t segment_begin =
                    row_begin +
                    (reserved_offset / kWeightedPmaSegmentSlots) *
                        kWeightedPmaSegmentSlots;
                auto first = shard.initial_pma_words.begin() + segment_begin;
                auto last = first + kWeightedPmaSegmentSlots;
                auto output = std::find(first, last, kWeightedPmaEmpty);
                if (output == last) {
                    throw std::logic_error(
                        "initial weighted partitioned PMA segment overflowed");
                }
                *output = word;
                std::sort(first, last);
            }
        }

        shard.physical_updates.reserve(updates_by_shard[partition].size());
        for (const auto &edge : updates_by_shard[partition]) {
            shard.physical_updates.push_back(pack_weighted_update(
                edge.source,
                encode_weighted_pma_word(
                    edge.destination - shard.destination_base, edge.weight),
                edge.delete_op));
        }
        result.shards.push_back(std::move(shard));
    }
    return result;
}

}  // namespace grasu::integration
