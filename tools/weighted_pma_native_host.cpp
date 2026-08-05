#define CL_HPP_CL_1_2_DEFAULT_BUILD
#define CL_HPP_TARGET_OPENCL_VERSION 120
#define CL_HPP_MINIMUM_OPENCL_VERSION 120
#define CL_HPP_ENABLE_PROGRAM_CONSTRUCTION_FROM_ARRAY_COMPATIBILITY 1

#include <CL/cl2.hpp>
#include <CL/cl_ext.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "weighted_pma_graph.hpp"

#ifndef GRASU_MAX_CACHE_SEGMENT
#error "GRASU_MAX_CACHE_SEGMENT must match the generated GraSU kernels"
#endif


namespace {

constexpr uint32_t kPmaEmpty32 = 0x80000000u;
constexpr uint32_t kSsspInf = static_cast<uint32_t>(std::numeric_limits<int>::max() - 1);
constexpr uint32_t kActiveMask = 0x80000000u;
constexpr uint32_t kPropMask = 0x7fffffffu;
constexpr unsigned kPartitionSize = 65536;
constexpr unsigned kLittleDstBufferSize = 65536;
constexpr std::size_t kMaxCacheSegment = GRASU_MAX_CACHE_SEGMENT;
static_assert(kMaxCacheSegment <= std::numeric_limits<unsigned>::max());

#ifdef GRASU_REGRAPH_CONNECTED_COMPONENTS
constexpr bool kConnectedComponents = true;
constexpr const char *kAlgorithmName = "connected_components";
constexpr const char *kLogPrefix = "CC_PMA_NATIVE";
#else
constexpr bool kConnectedComponents = false;
constexpr const char *kAlgorithmName = "weighted_sssp";
constexpr const char *kLogPrefix = "WEIGHTED_PMA_NATIVE";
#endif

using grasu::integration::WeightedEdgeRecord;
using grasu::integration::WeightedPmaGraph;
using grasu::integration::build_weighted_pma_graph;
using grasu::integration::kWeightedPmaSegmentSlots;
using grasu::integration::kWeightedPmaWeightMask;

template <typename T>
class AlignedAllocator {
  public:
    using value_type = T;

    AlignedAllocator() = default;
    template <typename U>
    AlignedAllocator(const AlignedAllocator<U> &) {}

    T *allocate(std::size_t n)
    {
        void *ptr = nullptr;
        if (posix_memalign(&ptr, 4096, n * sizeof(T)) != 0) {
            throw std::bad_alloc();
        }
        return reinterpret_cast<T *>(ptr);
    }

    void deallocate(T *p, std::size_t) noexcept
    {
        free(p);
    }
};

template <typename T, typename U>
bool operator==(const AlignedAllocator<T> &, const AlignedAllocator<U> &)
{
    return true;
}

template <typename T, typename U>
bool operator!=(const AlignedAllocator<T> &, const AlignedAllocator<U> &)
{
    return false;
}

template <typename T>
using AlignedVector = std::vector<T, AlignedAllocator<T>>;

struct Dataset {
    std::size_t node_size = 0;
    std::vector<WeightedEdgeRecord> static_edges;
    std::vector<WeightedEdgeRecord> update_edges;
};

struct PreparedGraSU {
    std::array<AlignedVector<std::uint64_t>, 4> update_edges;
    std::array<AlignedVector<uint32_t>, 4> pma_words;
    std::array<AlignedVector<std::uint64_t>, 4> row_offsets;
    std::array<AlignedVector<std::uint64_t>, 4> binary;
    std::array<std::size_t, 4> update_counts{};
    std::array<std::size_t, 4> update_alloc_counts{};
    std::array<std::size_t, 2> sub_data_segments{};
    std::array<std::size_t, 2> sub_data_words{};
    std::size_t pma_slot_count = 0;
};

struct Timing {
    double grasu_ms = 0.0;
    double barrier_ms = 0.0;
    double adapter_ms = 0.0;
    double lksg_ms = 0.0;
    double apply_ms = 0.0;
    double hbm_ms = 0.0;
    double event_e2e_ms = 0.0;
    double convergence_readback_ms = 0.0;
    double setup_inclusive_ms = 0.0;
    double wall_ms = 0.0;
};

struct AlgorithmOracleResult {
    std::vector<uint32_t> prop;
    unsigned executed_supersteps = 0;
    bool converged = false;
};

[[noreturn]] void fail(const std::string &message)
{
    throw std::runtime_error(message);
}

[[maybe_unused]] unsigned parse_unsigned_arg(
    const std::string &text, const std::string &name)
{
    std::size_t consumed = 0;
    unsigned long long value = 0;
    try {
        value = std::stoull(text, &consumed, 10);
    } catch (const std::exception &) {
        fail("invalid " + name + ": " + text);
    }
    if (consumed != text.size() ||
        value > std::numeric_limits<unsigned>::max()) {
        fail("invalid " + name + ": " + text);
    }
    return static_cast<unsigned>(value);
}

void check_cl(cl_int err, const std::string &what)
{
    if (err != CL_SUCCESS) {
        fail(what + " failed with OpenCL error " + std::to_string(err));
    }
}

unsigned grasu_mem_bank(unsigned bank)
{
    return bank | XCL_MEM_TOPOLOGY;
}

cl_mem_ext_ptr_t ext_ptr(unsigned bank, void *host_ptr = nullptr)
{
    cl_mem_ext_ptr_t ext{};
    ext.obj = host_ptr;
    ext.param = nullptr;
    ext.flags = grasu_mem_bank(bank);
    return ext;
}

Dataset read_dataset(const std::string &path)
{
    std::ifstream in(path);
    if (!in) {
        fail("failed to open graph file: " + path);
    }

    std::size_t static_edge_size = 0;
    std::size_t update_edge_size = 0;
    Dataset dataset;
    in >> dataset.node_size >> static_edge_size >> update_edge_size;
    if (!in) {
        fail("invalid graph header: " + path);
    }
    if (dataset.node_size == 0 || dataset.node_size > kPartitionSize) {
        fail("first-stage pure pipeline requires 1 <= V <= 65536");
    }

    dataset.static_edges.resize(static_edge_size);
    for (std::size_t i = 0; i < static_edge_size; ++i) {
        unsigned source = 0;
        unsigned destination = 0;
        unsigned weight = 0;
        if (!(in >> source >> destination >> weight)) {
            fail("invalid weighted static edge " + std::to_string(i) +
                 " in " + path);
        }
        if (weight == 0 || weight > kWeightedPmaWeightMask) {
            fail("weighted static edge exceeds weight12 ABI or is zero");
        }
        dataset.static_edges[i] = {
            .source = source,
            .destination = destination,
            .weight = static_cast<std::uint16_t>(weight),
            .delete_op = false,
        };
    }

    dataset.update_edges.resize(update_edge_size);
    for (std::size_t i = 0; i < update_edge_size; ++i) {
        unsigned source = 0;
        unsigned destination = 0;
        unsigned weight = 0;
        unsigned type = 0;
        if (!(in >> source >> destination >> weight >> type)) {
            fail("invalid weighted update " + std::to_string(i) + " in " + path);
        }
        if (weight == 0 || weight > kWeightedPmaWeightMask || type > 1) {
            fail("weighted update exceeds weight12 ABI, is zero, or has invalid type");
        }
        dataset.update_edges[i] = {
            .source = source,
            .destination = destination,
            .weight = static_cast<std::uint16_t>(weight),
            .delete_op = type == 0,
        };
    }

    std::string trailing;
    if (in >> trailing) {
        fail("unexpected trailing token in graph file: " + path);
    }

    return dataset;
}

using FinalEdgeMap =
    std::map<std::pair<std::uint32_t, std::uint32_t>, std::uint16_t>;

FinalEdgeMap build_final_external_edges(const Dataset &dataset)
{
    FinalEdgeMap final_edges;
    for (const auto &edge : dataset.static_edges) {
        const auto key = std::make_pair(edge.source, edge.destination);
        if (edge.delete_op || !final_edges.emplace(key, edge.weight).second) {
            fail("duplicate or deleted edge in initial weighted graph");
        }
    }
    for (const auto &update : dataset.update_edges) {
        const auto key = std::make_pair(update.source, update.destination);
        const auto found = final_edges.find(key);
        if (update.delete_op) {
            if (found == final_edges.end() || found->second != update.weight) {
                fail("weighted delete target or weight does not match oracle state");
            }
            final_edges.erase(found);
        } else {
            if (found != final_edges.end() && found->second == update.weight) {
                fail("weighted insert target already exists with same weight");
            }
            final_edges[key] = update.weight;
        }
    }
    return final_edges;
}

uint32_t sssp_value(uint32_t prop)
{
    return prop & kPropMask;
}

bool is_active(uint32_t prop)
{
    return (prop & kActiveMask) != 0;
}

[[maybe_unused]] AlgorithmOracleResult run_weighted_sssp_oracle(
    std::size_t vertices,
    const FinalEdgeMap &edges,
    unsigned source,
    unsigned max_supersteps)
{
    std::vector<uint32_t> prop(vertices, kSsspInf);
    prop[source] = kActiveMask;

    AlgorithmOracleResult result;
    for (unsigned step = 0; step < max_supersteps; ++step) {
        std::vector<uint32_t> tmp(vertices, 0);
        for (const auto &[key, weight] : edges) {
            const unsigned src = key.first;
            const unsigned dst = key.second;
            if (src >= vertices || dst >= vertices) continue;
            if (!is_active(prop[src])) continue;

            const std::uint64_t candidate =
                static_cast<std::uint64_t>(sssp_value(prop[src])) + weight;
            const uint32_t next_dist =
                candidate >= kSsspInf ? kSsspInf : static_cast<uint32_t>(candidate);
            const uint32_t update = next_dist | kActiveMask;

            if (!is_active(tmp[dst]) || sssp_value(update) < sssp_value(tmp[dst])) {
                tmp[dst] = update;
            }
        }

        std::vector<uint32_t> next(vertices, 0);
        for (std::size_t v = 0; v < vertices; ++v) {
            const uint32_t old_dist = sssp_value(prop[v]);
            if (is_active(tmp[v]) && sssp_value(tmp[v]) < old_dist) {
                next[v] = tmp[v];
            } else {
                next[v] = old_dist;
            }
        }
        prop.swap(next);
        result.executed_supersteps = step + 1;

        const bool has_active = std::any_of(
            prop.begin(), prop.end(), [](uint32_t value) { return is_active(value); });
        if (!has_active) {
            result.converged = true;
            break;
        }
    }

    result.prop = std::move(prop);
    return result;
}

void require_reciprocal_cc_edges(const FinalEdgeMap &edges)
{
    for (const auto &[key, weight] : edges) {
        (void)weight;
        if (key.first == key.second) continue;
        if (edges.find({key.second, key.first}) == edges.end()) {
            fail("connected_components requires reciprocal directed edges");
        }
    }
}

[[maybe_unused]] AlgorithmOracleResult run_connected_components_oracle(
    std::size_t vertices,
    const FinalEdgeMap &external_edges,
    const WeightedPmaGraph &graph,
    unsigned max_supersteps)
{
    require_reciprocal_cc_edges(external_edges);

    std::vector<uint32_t> prop(vertices, 0);
    for (std::size_t internal = 0; internal < vertices; ++internal) {
        prop[internal] = static_cast<uint32_t>(internal) | kActiveMask;
    }

    AlgorithmOracleResult result;
    for (unsigned step = 0; step < max_supersteps; ++step) {
        std::vector<uint32_t> tmp(vertices, 0);
        for (const auto &[key, weight] : external_edges) {
            (void)weight;
            const unsigned src = graph.external_to_internal.at(key.first);
            const unsigned dst = graph.external_to_internal.at(key.second);
            if (!is_active(prop[src])) continue;

            const uint32_t candidate = sssp_value(prop[src]) | kActiveMask;
            if (!is_active(tmp[dst]) ||
                sssp_value(candidate) < sssp_value(tmp[dst])) {
                tmp[dst] = candidate;
            }
        }

        std::vector<uint32_t> next(vertices, 0);
        for (std::size_t vertex = 0; vertex < vertices; ++vertex) {
            const uint32_t old_label = sssp_value(prop[vertex]);
            if (is_active(tmp[vertex]) &&
                sssp_value(tmp[vertex]) < old_label) {
                next[vertex] = tmp[vertex];
            } else {
                next[vertex] = old_label;
            }
        }
        prop.swap(next);
        result.executed_supersteps = step + 1;

        const bool has_active = std::any_of(
            prop.begin(), prop.end(), [](uint32_t value) { return is_active(value); });
        if (!has_active) {
            result.converged = true;
            break;
        }
    }

    result.prop = std::move(prop);
    return result;
}

[[maybe_unused]] std::size_t count_components(
    const AlgorithmOracleResult &oracle)
{
    std::vector<uint32_t> labels;
    labels.reserve(oracle.prop.size());
    for (uint32_t value : oracle.prop) labels.push_back(sssp_value(value));
    std::sort(labels.begin(), labels.end());
    return static_cast<std::size_t>(
        std::unique(labels.begin(), labels.end()) - labels.begin());
}

struct FullPageRankOracleResult {
    std::vector<float> rank;
    std::vector<uint32_t> out_degree;
};

[[maybe_unused]] FullPageRankOracleResult run_full_pagerank_oracle(
    std::size_t vertices,
    const FinalEdgeMap &edges,
    unsigned rounds,
    float damping)
{
    FullPageRankOracleResult result;
    result.rank.assign(vertices, 1.0F / static_cast<float>(vertices));
    result.out_degree.assign(vertices, 0);
    for (const auto &[key, weight] : edges) {
        (void)weight;
        if (key.first < vertices && key.second < vertices) {
            result.out_degree[key.first]++;
        }
    }

    const float base = (1.0F - damping) / static_cast<float>(vertices);
    for (unsigned round = 0; round < rounds; ++round) {
        float dangling = 0.0F;
        for (std::size_t vertex = 0; vertex < vertices; ++vertex) {
            if (result.out_degree[vertex] == 0) dangling += result.rank[vertex];
        }
        std::vector<float> next(
            vertices, base + damping * dangling / static_cast<float>(vertices));
        for (const auto &[key, weight] : edges) {
            (void)weight;
            const unsigned src = key.first;
            const unsigned dst = key.second;
            if (src >= vertices || dst >= vertices || result.out_degree[src] == 0) {
                continue;
            }
            next[dst] += damping * result.rank[src] /
                         static_cast<float>(result.out_degree[src]);
        }
        result.rank.swap(next);
    }
    return result;
}

[[maybe_unused]] float word_to_float(uint32_t word)
{
    float value = 0.0F;
    static_assert(sizeof(value) == sizeof(word));
    std::memcpy(&value, &word, sizeof(value));
    return value;
}

PreparedGraSU prepare_grasu_inputs(const WeightedPmaGraph &graph)
{
    PreparedGraSU prepared;
    const auto &update_edges = graph.physical_updates;

    for (int i = 0; i < 4; ++i) {
        prepared.update_counts[i] = update_edges.size() / 4;
    }
    for (std::size_t i = 0; i < (update_edges.size() % 4); ++i) {
        prepared.update_counts[i]++;
    }
    for (int i = 0; i < 4; ++i) {
        prepared.update_alloc_counts[i] = std::max<std::size_t>(prepared.update_counts[i], 1);
        prepared.update_edges[i].assign(prepared.update_alloc_counts[i], 0);
    }
    for (std::size_t i = 0; i < update_edges.size(); ++i) {
        prepared.update_edges[i % 4][i / 4] = update_edges[i];
    }

    prepared.pma_slot_count = graph.initial_pma_words.size();
    const std::size_t data_segment_size =
        graph.initial_pma_words.size() / kWeightedPmaSegmentSlots;
    for (int i = 0; i < 2; ++i) {
        prepared.sub_data_segments[i] = data_segment_size >> 1;
    }
    for (std::size_t i = 0; i < (data_segment_size % 2); ++i) {
        prepared.sub_data_segments[i]++;
    }
    for (int i = 0; i < 2; ++i) {
        if (prepared.sub_data_segments[i] < kMaxCacheSegment) {
            prepared.sub_data_segments[i] = kMaxCacheSegment;
        }
        prepared.sub_data_words[i] =
            prepared.sub_data_segments[i] * kWeightedPmaSegmentSlots;
    }

    prepared.pma_words[0].assign(prepared.sub_data_words[0], kPmaEmpty32);
    prepared.pma_words[1].assign(prepared.sub_data_words[0], kPmaEmpty32);
    prepared.pma_words[2].assign(prepared.sub_data_words[1], kPmaEmpty32);
    prepared.pma_words[3].assign(prepared.sub_data_words[1], kPmaEmpty32);

    for (std::size_t i = 0; i < graph.initial_pma_words.size();
         i += kWeightedPmaSegmentSlots) {
        const std::size_t segment_index = i / kWeightedPmaSegmentSlots;
        std::size_t sub_index = segment_index % 2;
        sub_index <<= 1;
        const std::size_t local_base =
            (segment_index / 2) * kWeightedPmaSegmentSlots;
        for (std::size_t j = 0; j < kWeightedPmaSegmentSlots; ++j) {
            const uint32_t word = graph.initial_pma_words[i + j];
            prepared.pma_words[sub_index + 0][local_base + j] = word;
            prepared.pma_words[sub_index + 1][local_base + j] = word;
        }
    }

    const std::size_t row_count =
        std::max<std::size_t>(graph.row_bounds.size(), 1);
    for (int copy = 0; copy < 4; ++copy) {
        prepared.row_offsets[copy].assign(row_count, 0);
        std::copy(graph.row_bounds.begin(), graph.row_bounds.end(),
                  prepared.row_offsets[copy].begin());
    }

    const std::size_t binary_count =
        std::max<std::size_t>(graph.binary_heads.size(), 1);
    for (int copy = 0; copy < 4; ++copy) {
        prepared.binary[copy].assign(binary_count, 0);
        std::copy(graph.binary_heads.begin(), graph.binary_heads.end(),
                  prepared.binary[copy].begin());
    }

    return prepared;
}

std::vector<unsigned char> read_binary_file(const std::string &path)
{
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file) fail("failed to open xclbin: " + path);
    const std::streamsize size = file.tellg();
    file.seekg(0, std::ios::beg);
    std::vector<unsigned char> data(static_cast<std::size_t>(size));
    if (!file.read(reinterpret_cast<char *>(data.data()), size)) {
        fail("failed to read xclbin: " + path);
    }
    return data;
}

cl::Device select_xilinx_device()
{
    std::vector<cl::Platform> platforms;
    cl::Platform::get(&platforms);
    for (const cl::Platform &platform : platforms) {
        if (platform.getInfo<CL_PLATFORM_NAME>() != "Xilinx") continue;

        std::vector<cl::Device> devices;
        platform.getDevices(CL_DEVICE_TYPE_ACCELERATOR, &devices);
        if (devices.empty()) continue;

        std::size_t device_index = 0;
        if (const char *device_index_env = std::getenv("XCL_DEVICE_INDEX")) {
            char *end = nullptr;
            const unsigned long parsed = std::strtoul(device_index_env, &end, 10);
            if (end == device_index_env || *end != '\0' || parsed >= devices.size()) {
                fail("invalid XCL_DEVICE_INDEX=" + std::string(device_index_env));
            }
            device_index = static_cast<std::size_t>(parsed);
        }
        std::cout << "Using XCL_DEVICE_INDEX=" << device_index << std::endl;
        return devices[device_index];
    }
    fail("unable to find a Xilinx accelerator device");
}

double event_duration_ms(const cl::Event &event)
{
    const cl_ulong start = event.getProfilingInfo<CL_PROFILING_COMMAND_START>();
    const cl_ulong end = event.getProfilingInfo<CL_PROFILING_COMMAND_END>();
    return static_cast<double>(end - start) / 1000000.0;
}

double event_union_ms(const std::vector<cl::Event> &events)
{
    if (events.empty()) return 0.0;
    cl_ulong start = std::numeric_limits<cl_ulong>::max();
    cl_ulong end = 0;
    for (const cl::Event &event : events) {
        start = std::min(start, event.getProfilingInfo<CL_PROFILING_COMMAND_START>());
        end = std::max(end, event.getProfilingInfo<CL_PROFILING_COMMAND_END>());
    }
    return static_cast<double>(end - start) / 1000000.0;
}

cl::Buffer make_buffer(cl::Context &context,
                       cl_mem_flags flags,
                       std::size_t bytes,
                       cl_mem_ext_ptr_t *ext,
                       const std::string &name)
{
    cl_int err = CL_SUCCESS;
    cl::Buffer buffer(context, flags, bytes, ext, &err);
    check_cl(err, "create buffer " + name);
    return buffer;
}

[[maybe_unused]] void usage(const char *argv0)
{
    std::cerr
        << "Usage: " << argv0
        << " <xclbin> <graph_file> <result_file> [source_external] [max_supersteps]\n"
        << "       " << argv0
        << " --prepare-only <graph_file> <result_file> [source_external] [max_supersteps]\n"
        << "\n"
        << "Runs weighted GraSU PMA -> AXIS adapter -> ReGraph "
        << kAlgorithmName << ".\n"
        << "Input: header 'V initial_edges updates'; initial rows 'src dst weight';\n"
        << "update rows 'src dst weight type', where type=0 deletes and type=1 inserts\n"
        << "or changes weight. Hardware mode writes 'external_vertex value'.\n"
        << "--prepare-only validates input, weighted PMA packing/lowering, and an\n"
        << "independent synchronous algorithm oracle without loading xclbin.\n";
}

}  // namespace

#ifndef GRASU_REGRAPH_FULL_PAGERANK
int main(int argc, char **argv)
{
    try {
        const bool prepare_only = argc >= 2 && std::string(argv[1]) == "--prepare-only";
        if ((!prepare_only && (argc < 4 || argc > 6)) ||
            (prepare_only && (argc < 4 || argc > 6))) {
            usage(argv[0]);
            return EXIT_FAILURE;
        }

        int arg_index = prepare_only ? 2 : 1;
        const std::string xclbin_path = prepare_only ? "" : argv[arg_index++];
        const std::string graph_path = argv[arg_index++];
        const std::string result_path = argv[arg_index++];
        const unsigned source_external =
            argc > arg_index
                ? parse_unsigned_arg(argv[arg_index], "source_external")
                : 0;
        const unsigned max_supersteps =
            argc > arg_index + 1
                ? parse_unsigned_arg(argv[arg_index + 1], "max_supersteps")
                : 256;
        if (max_supersteps == 0) fail("max_supersteps must be >= 1");

        Dataset dataset = read_dataset(graph_path);
        if (source_external >= dataset.node_size) {
            fail("source vertex is outside the graph");
        }

        const FinalEdgeMap final_edges = build_final_external_edges(dataset);
        const WeightedPmaGraph graph = build_weighted_pma_graph(
            dataset.node_size, dataset.static_edges, dataset.update_edges);
        const unsigned source_internal = graph.external_to_internal[source_external];
        const AlgorithmOracleResult oracle = kConnectedComponents
            ? run_connected_components_oracle(
                  dataset.node_size, final_edges, graph, max_supersteps)
            : run_weighted_sssp_oracle(
                  dataset.node_size, final_edges, source_external, max_supersteps);

        PreparedGraSU prepared = prepare_grasu_inputs(graph);
        if (graph.physical_updates.size() >
            std::numeric_limits<unsigned>::max()) {
            fail("physical update count exceeds 32-bit kernel argument range");
        }
        if (prepared.pma_slot_count > std::numeric_limits<unsigned>::max()) {
            fail("PMA slot count exceeds 32-bit kernel argument range");
        }
        if (prepared.pma_slot_count == 0 ||
            prepared.pma_slot_count % kWeightedPmaSegmentSlots != 0) {
            fail("PMA stream must contain complete non-empty 16-slot segments");
        }
        std::cout << kLogPrefix << "_INPUT"
                  << " vertices=" << dataset.node_size
                  << " static_edges=" << dataset.static_edges.size()
                  << " logical_updates=" << dataset.update_edges.size()
                  << " physical_updates=" << graph.physical_updates.size()
                  << " final_edges=" << final_edges.size()
                  << " pma_slots=" << prepared.pma_slot_count
                  << " source_external=" << source_external
                  << " source_internal=" << source_internal
                  << " max_supersteps=" << max_supersteps
                  << " oracle_supersteps=" << oracle.executed_supersteps
                  << " oracle_converged=" << (oracle.converged ? 1 : 0)
                  << std::endl;

        if (prepare_only) {
            std::size_t reachable_vertices = 0;
            uint32_t max_distance = 0;
            for (uint32_t value : oracle.prop) {
                const uint32_t distance = sssp_value(value);
                if (distance < kSsspInf) {
                    reachable_vertices++;
                    max_distance = std::max(max_distance, distance);
                }
            }
            std::cout << kLogPrefix << "_PREP"
                      << " status=" << (oracle.converged ? "PASS" : "FAIL")
                      << " vertices=" << dataset.node_size
                      << " static_edges=" << dataset.static_edges.size()
                      << " logical_updates=" << dataset.update_edges.size()
                      << " physical_updates=" << graph.physical_updates.size()
                      << " final_edges=" << final_edges.size()
                      << " pma_slots=" << prepared.pma_slot_count
                      << " row_offset_words=" << prepared.row_offsets[0].size()
                      << " binary_segments=" << prepared.binary[0].size()
                      << " source_external=" << source_external
                      << " source_internal=" << source_internal
                      << " max_supersteps=" << max_supersteps
                      << " oracle_supersteps=" << oracle.executed_supersteps
                      << " oracle_converged=" << (oracle.converged ? 1 : 0)
                      << " reachable_vertices=" << reachable_vertices
                      << " max_distance=" << max_distance;
            if (kConnectedComponents) {
                std::cout << " components=" << count_components(oracle);
            }
            std::cout << " partition_size=" << kPartitionSize
                      << " little_dst_buffer=" << kLittleDstBufferSize
                      << " weighted_pma=1"
                      << " conversion_cost=absent"
                      << " weight_change_lowering=delete_then_insert"
                      << std::endl;
            return oracle.converged ? EXIT_SUCCESS : EXIT_FAILURE;
        }

        cl::Device device = select_xilinx_device();
        cl_int err = CL_SUCCESS;
        cl::Context context(device, nullptr, nullptr, nullptr, &err);
        check_cl(err, "create context");
        auto make_queue = [&](const std::string &name) {
            cl_int qerr = CL_SUCCESS;
            cl::CommandQueue q(context, device,
                               CL_QUEUE_PROFILING_ENABLE |
                                   CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE,
                               &qerr);
            check_cl(qerr, "create " + name);
            return q;
        };
        cl::CommandQueue transfer_queue = make_queue("transfer queue");
        cl::CommandQueue grasu_queue = make_queue("grasu queue");
        cl::CommandQueue pipeline_queue = make_queue("pipeline queue");

        std::vector<unsigned char> xclbin = read_binary_file(xclbin_path);
        cl::Program::Binaries bins{{xclbin.data(), xclbin.size()}};
        cl::Program program(context, {device}, bins, nullptr, &err);
        check_cl(err, "program device");

        cl::Kernel bin_search_1(program, "bin_search:{bin_search_1}", &err);
        check_cl(err, "create bin_search_1");
        cl::Kernel bin_search_2(program, "bin_search:{bin_search_2}", &err);
        check_cl(err, "create bin_search_2");
        cl::Kernel bin_search_3(program, "bin_search:{bin_search_3}", &err);
        check_cl(err, "create bin_search_3");
        cl::Kernel bin_search_4(program, "bin_search:{bin_search_4}", &err);
        check_cl(err, "create bin_search_4");
        cl::Kernel dispatch(program, "dispatch:{dispatch_1}", &err);
        check_cl(err, "create dispatch");
        cl::Kernel process_cache_1(program, "process_cache:{process_cache_1}", &err);
        check_cl(err, "create process_cache_1");
        cl::Kernel process_cache_2(program, "process_cache:{process_cache_2}", &err);
        check_cl(err, "create process_cache_2");
        cl::Kernel process_ddr_1(program, "process_ddr:{process_ddr_1}", &err);
        check_cl(err, "create process_ddr_1");
        cl::Kernel process_ddr_2(program, "process_ddr:{process_ddr_2}", &err);
        check_cl(err, "create process_ddr_2");
        cl::Kernel barrier(program, "pma_completion_barrier:{pma_completion_barrier_1}", &err);
        check_cl(err, "create pma_completion_barrier");
        cl::Kernel adapter(program, "pma_to_regraph_adapter:{pma_to_regraph_adapter_1}", &err);
        check_cl(err, "create pma_to_regraph_adapter");
        cl::Kernel lksg(program, "lksg_stream:{lksg_stream_1}", &err);
        check_cl(err, "create lksg_stream");
        cl::Kernel apply(program, "kernelApply:{kernelApply_1}", &err);
        check_cl(err, "create kernelApply");
        cl::Kernel hbm(program, "kernelHBMWrapper:{kernelHBMWrapper_1}", &err);
        check_cl(err, "create kernelHBMWrapper");

        std::array<cl_mem_ext_ptr_t, 4> update_ext{};
        std::array<cl_mem_ext_ptr_t, 4> pma_ext{};
        std::array<cl_mem_ext_ptr_t, 4> row_ext{};
        std::array<cl_mem_ext_ptr_t, 4> binary_ext{};
        std::array<cl::Buffer, 4> update_dev;
        std::array<cl::Buffer, 4> pma_dev;
        std::array<cl::Buffer, 4> row_dev;
        std::array<cl::Buffer, 4> binary_dev;

        for (int i = 0; i < 4; ++i) {
            update_ext[i] = ext_ptr(i, prepared.update_edges[i].data());
            pma_ext[i] = ext_ptr(i, prepared.pma_words[i].data());
            row_ext[i] = ext_ptr(i, prepared.row_offsets[i].data());
            binary_ext[i] = ext_ptr(i, prepared.binary[i].data());
            update_dev[i] = make_buffer(
                context,
                CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.update_edges[i].size() * sizeof(std::uint64_t),
                &update_ext[i], "update_edges_" + std::to_string(i));
            pma_dev[i] = make_buffer(
                context,
                CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.pma_words[i].size() * sizeof(uint32_t),
                &pma_ext[i], "pma_" + std::to_string(i));
            row_dev[i] = make_buffer(
                context,
                CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.row_offsets[i].size() * sizeof(std::uint64_t),
                &row_ext[i], "row_offset_" + std::to_string(i));
            binary_dev[i] = make_buffer(
                context,
                CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.binary[i].size() * sizeof(std::uint64_t),
                &binary_ext[i], "binary_" + std::to_string(i));
        }

        AlignedVector<uint32_t> prop_a(kLittleDstBufferSize, 0);
        AlignedVector<uint32_t> prop_b(kLittleDstBufferSize, 0);
        AlignedVector<uint32_t> apply_prop(kLittleDstBufferSize, 0);
        AlignedVector<uint32_t> active_count(1, 0);
        for (std::size_t i = 0; i < dataset.node_size; ++i) {
            const uint32_t initial_value = kConnectedComponents
                ? static_cast<uint32_t>(i) | kActiveMask
                : kSsspInf;
            prop_a[i] = initial_value;
            apply_prop[i] = initial_value;
        }
        if (!kConnectedComponents) {
            prop_a[source_internal] = kActiveMask;
            apply_prop[source_internal] = kActiveMask;
        }

        cl_mem_ext_ptr_t prop_a0_ext = ext_ptr(1, prop_a.data());
        cl_mem_ext_ptr_t prop_a1_ext = ext_ptr(3, prop_a.data());
        cl_mem_ext_ptr_t prop_b0_ext = ext_ptr(1, prop_b.data());
        cl_mem_ext_ptr_t prop_b1_ext = ext_ptr(3, prop_b.data());
        cl_mem_ext_ptr_t apply_prop_ext = ext_ptr(30, apply_prop.data());
        cl_mem_ext_ptr_t active_count_ext = ext_ptr(30, active_count.data());

        cl::Buffer prop_a0_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            prop_a.size() * sizeof(uint32_t), &prop_a0_ext, "prop_a0");
        cl::Buffer prop_a1_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            prop_a.size() * sizeof(uint32_t), &prop_a1_ext, "prop_a1");
        cl::Buffer prop_b0_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            prop_b.size() * sizeof(uint32_t), &prop_b0_ext, "prop_b0");
        cl::Buffer prop_b1_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            prop_b.size() * sizeof(uint32_t), &prop_b1_ext, "prop_b1");
        cl::Buffer apply_prop_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            apply_prop.size() * sizeof(uint32_t), &apply_prop_ext, "apply_prop");
        cl::Buffer active_count_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            active_count.size() * sizeof(uint32_t), &active_count_ext, "active_count");

        std::vector<cl::Memory> initial_mems;
        for (int i = 0; i < 4; ++i) {
            initial_mems.push_back(update_dev[i]);
            initial_mems.push_back(pma_dev[i]);
            initial_mems.push_back(row_dev[i]);
            initial_mems.push_back(binary_dev[i]);
        }
        initial_mems.push_back(prop_a0_dev);
        initial_mems.push_back(prop_a1_dev);
        initial_mems.push_back(prop_b0_dev);
        initial_mems.push_back(prop_b1_dev);
        initial_mems.push_back(apply_prop_dev);
        initial_mems.push_back(active_count_dev);
        check_cl(transfer_queue.enqueueMigrateMemObjects(initial_mems, 0),
                 "migrate initial buffers");
        transfer_queue.finish();

        auto set_bin_search_args = [&](cl::Kernel &kernel, int idx) {
            int arg = 0;
            check_cl(kernel.setArg(arg++, update_dev[idx]), "set bin_search edges");
            for (int i = 0; i < 4; ++i) {
                check_cl(kernel.setArg(arg++, binary_dev[idx]), "set bin_search binary");
            }
            for (int i = 0; i < 4; ++i) {
                check_cl(kernel.setArg(arg++, row_dev[idx]), "set bin_search row_offset");
            }
            check_cl(kernel.setArg(arg++, static_cast<unsigned>(prepared.update_counts[idx])),
                     "set bin_search edge_size");
        };

        set_bin_search_args(bin_search_1, 0);
        set_bin_search_args(bin_search_2, 1);
        set_bin_search_args(bin_search_3, 2);
        set_bin_search_args(bin_search_4, 3);

        check_cl(dispatch.setArg(0, static_cast<unsigned>(graph.physical_updates.size())),
                 "set dispatch size");
        check_cl(process_cache_1.setArg(0, pma_dev[0]), "set process_cache_1 pma");
        check_cl(process_cache_2.setArg(0, pma_dev[2]), "set process_cache_2 pma");
        for (int arg = 0; arg < 4; ++arg) {
            check_cl(process_ddr_1.setArg(arg, pma_dev[1]), "set process_ddr_1 pma");
            check_cl(process_ddr_2.setArg(arg, pma_dev[3]), "set process_ddr_2 pma");
        }

        check_cl(adapter.setArg(0, pma_dev[0]), "set adapter pma0");
        check_cl(adapter.setArg(1, pma_dev[1]), "set adapter pma1");
        check_cl(adapter.setArg(2, pma_dev[2]), "set adapter pma2");
        check_cl(adapter.setArg(3, pma_dev[3]), "set adapter pma3");
        check_cl(adapter.setArg(4, row_dev[0]), "set adapter row_offset");
        check_cl(adapter.setArg(5, static_cast<unsigned>(dataset.node_size)),
                 "set adapter node_count");
        check_cl(adapter.setArg(6, static_cast<unsigned>(prepared.pma_slot_count)),
                 "set adapter pma_slot_count");
        check_cl(adapter.setArg(7, static_cast<unsigned>(kMaxCacheSegment)),
                 "set adapter max_cache_segment");

        const unsigned num_dense = 1;
        const unsigned num_sparse = 0;
        const unsigned compressed_group_count = 0;
        const unsigned part_dst_offset = 0;
        const unsigned reg = 0;
        const unsigned part_edge_num = static_cast<unsigned>(prepared.pma_slot_count);

        std::array<cl::Buffer *, 2> read_props{&prop_a0_dev, &prop_a1_dev};
        std::array<cl::Buffer *, 2> write_props{&prop_b0_dev, &prop_b1_dev};
        AlignedVector<uint32_t> *read_host = &prop_a;
        AlignedVector<uint32_t> *write_host = &prop_b;

        Timing timing;
        auto wall_begin = std::chrono::high_resolution_clock::now();
        std::vector<cl::Event> all_events;
        std::vector<cl::Event> grasu_events;
        unsigned executed_supersteps = 0;
        bool hardware_converged = false;

        cl::Event pc1_event, pc2_event, pd1_event, pd2_event, dispatch_event;
        cl::Event bs1_event, bs2_event, bs3_event, bs4_event;
        std::cout << kLogPrefix << "_HOST stage=launch_grasu" << std::endl;
        check_cl(grasu_queue.enqueueTask(process_cache_1, nullptr, &pc1_event),
                 "enqueue process_cache_1");
        check_cl(grasu_queue.enqueueTask(process_cache_2, nullptr, &pc2_event),
                 "enqueue process_cache_2");
        check_cl(grasu_queue.enqueueTask(process_ddr_1, nullptr, &pd1_event),
                 "enqueue process_ddr_1");
        check_cl(grasu_queue.enqueueTask(process_ddr_2, nullptr, &pd2_event),
                 "enqueue process_ddr_2");
        check_cl(grasu_queue.enqueueTask(dispatch, nullptr, &dispatch_event),
                 "enqueue dispatch");
        check_cl(grasu_queue.enqueueTask(bin_search_1, nullptr, &bs1_event),
                 "enqueue bin_search_1");
        check_cl(grasu_queue.enqueueTask(bin_search_2, nullptr, &bs2_event),
                 "enqueue bin_search_2");
        check_cl(grasu_queue.enqueueTask(bin_search_3, nullptr, &bs3_event),
                 "enqueue bin_search_3");
        check_cl(grasu_queue.enqueueTask(bin_search_4, nullptr, &bs4_event),
                 "enqueue bin_search_4");
        grasu_queue.flush();
        grasu_events = {pc1_event, pc2_event, pd1_event, pd2_event,
                        dispatch_event, bs1_event, bs2_event, bs3_event, bs4_event};
        all_events.insert(all_events.end(), grasu_events.begin(), grasu_events.end());

        cl::Event barrier_event;
        std::cout << kLogPrefix << "_HOST stage=enqueue_barrier" << std::endl;
        check_cl(pipeline_queue.enqueueTask(barrier, nullptr, &barrier_event),
                 "enqueue pma_completion_barrier");
        std::cout << kLogPrefix << "_HOST stage=enqueued_barrier" << std::endl;
        all_events.push_back(barrier_event);

        for (unsigned step = 0; step < max_supersteps; ++step) {
            check_cl(hbm.setArg(0, *read_props[0]), "set hbm src_prop_1");
            check_cl(hbm.setArg(1, *read_props[1]), "set hbm src_prop_2");
            check_cl(hbm.setArg(2, *write_props[0]), "set hbm new_prop_1");
            check_cl(hbm.setArg(3, *write_props[1]), "set hbm new_prop_2");
            check_cl(hbm.setArg(4, num_dense), "set hbm num_dense");
            check_cl(hbm.setArg(5, num_sparse), "set hbm num_sparse");

            check_cl(apply.setArg(0, apply_prop_dev), "set apply vertex_prop");
            check_cl(apply.setArg(1, active_count_dev), "set apply active_count");
            check_cl(apply.setArg(2, num_dense), "set apply num_dense");
            check_cl(apply.setArg(3, num_sparse), "set apply num_sparse");
            check_cl(apply.setArg(4, reg), "set apply reg");

            check_cl(lksg.setArg(1, part_edge_num), "set lksg part_edge_num");
            check_cl(lksg.setArg(2, compressed_group_count),
                     "set lksg compressed_group_count");
            check_cl(lksg.setArg(3, part_dst_offset), "set lksg part_dst_offset");
            const bool reset_tmp_prop = (step == 0);
            check_cl(lksg.setArg(4, reset_tmp_prop), "set lksg reset_tmp_prop");

            cl::Event hbm_event, apply_event, lksg_event, adapter_event;
            std::cout << kLogPrefix << "_HOST stage=launch_step step=" << (step + 1)
                      << std::endl;
            std::cout << kLogPrefix << "_HOST stage=enqueue_adapter step=" << (step + 1)
                      << std::endl;
            std::vector<cl::Event> adapter_wait_events;
            const std::vector<cl::Event> *adapter_wait_list = nullptr;
            if (step == 0) {
                adapter_wait_events.push_back(barrier_event);
                adapter_wait_list = &adapter_wait_events;
            }
            check_cl(pipeline_queue.enqueueTask(adapter, adapter_wait_list, &adapter_event),
                     "enqueue adapter");
            std::cout << kLogPrefix << "_HOST stage=enqueued_adapter step=" << (step + 1)
                      << std::endl;
            std::cout << kLogPrefix << "_HOST stage=enqueue_lksg step=" << (step + 1)
                      << std::endl;
            check_cl(pipeline_queue.enqueueTask(lksg, nullptr, &lksg_event), "enqueue lksg");
            std::cout << kLogPrefix << "_HOST stage=enqueued_lksg step=" << (step + 1)
                      << std::endl;
            std::cout << kLogPrefix << "_HOST stage=enqueue_hbm step=" << (step + 1)
                      << std::endl;
            check_cl(pipeline_queue.enqueueTask(hbm, nullptr, &hbm_event), "enqueue hbm");
            std::cout << kLogPrefix << "_HOST stage=enqueued_hbm step=" << (step + 1)
                      << std::endl;
            std::cout << kLogPrefix << "_HOST stage=enqueue_apply step=" << (step + 1)
                      << std::endl;
            check_cl(pipeline_queue.enqueueTask(apply, nullptr, &apply_event),
                     "enqueue apply");
            std::cout << kLogPrefix << "_HOST stage=enqueued_apply step=" << (step + 1)
                      << std::endl;

            std::vector<cl::Event> step_events{hbm_event, apply_event, lksg_event, adapter_event};
            std::cout << kLogPrefix << "_HOST stage=wait_step step=" << (step + 1)
                      << std::endl;
            pipeline_queue.finish();

            timing.hbm_ms += event_duration_ms(hbm_event);
            timing.apply_ms += event_duration_ms(apply_event);
            timing.lksg_ms += event_duration_ms(lksg_event);
            timing.adapter_ms += event_duration_ms(adapter_event);
            all_events.insert(all_events.end(), step_events.begin(), step_events.end());

            const auto readback_begin = std::chrono::high_resolution_clock::now();
            check_cl(transfer_queue.enqueueMigrateMemObjects(
                         {active_count_dev}, CL_MIGRATE_MEM_OBJECT_HOST),
                     "migrate active count");
            transfer_queue.finish();
            const auto readback_end = std::chrono::high_resolution_clock::now();
            timing.convergence_readback_ms +=
                std::chrono::duration<double, std::milli>(
                    readback_end - readback_begin).count();
            executed_supersteps = step + 1;

            std::swap(read_props, write_props);
            std::swap(read_host, write_host);
            std::cout << kLogPrefix << "_SUPERSTEP step=" << (step + 1)
                      << " adapter_ms=" << std::fixed << std::setprecision(6)
                      << event_duration_ms(adapter_event)
                      << " lksg_ms=" << event_duration_ms(lksg_event)
                      << " apply_ms=" << event_duration_ms(apply_event)
                      << " hbm_ms=" << event_duration_ms(hbm_event)
                      << " active_vertices=" << active_count[0]
                      << std::endl;
            if (active_count[0] == 0) {
                hardware_converged = true;
                break;
            }
        }

        for (cl::Event &event : grasu_events) {
            event.wait();
        }
        grasu_queue.finish();
        pipeline_queue.finish();
        timing.grasu_ms = event_union_ms(grasu_events);
        timing.barrier_ms = event_duration_ms(barrier_event);
        timing.event_e2e_ms = event_union_ms(all_events);

        check_cl(transfer_queue.enqueueMigrateMemObjects({*read_props[0]},
                                                         CL_MIGRATE_MEM_OBJECT_HOST),
                 "migrate final result");
        transfer_queue.finish();
        auto wall_end = std::chrono::high_resolution_clock::now();
        timing.setup_inclusive_ms =
            std::chrono::duration<double, std::milli>(wall_end - wall_begin).count();
        timing.wall_ms = timing.setup_inclusive_ms;

        std::size_t mismatch_count = 0;
        for (std::size_t internal = 0; internal < dataset.node_size; ++internal) {
            const std::size_t external = graph.internal_to_external.at(internal);
            const uint32_t expected = oracle.prop.at(
                kConnectedComponents ? internal : external);
            if ((*read_host)[internal] != expected) {
                if (mismatch_count < 20) {
                    std::cerr << "mismatch external_vertex=" << external
                              << " internal_vertex=" << internal
                              << " expected=0x" << std::hex << expected
                              << " got=0x" << (*read_host)[internal] << std::dec
                              << std::endl;
                }
                mismatch_count++;
            }
        }

        std::ofstream result_out(result_path);
        if (!result_out) {
            fail("failed to open result file: " + result_path);
        }
        for (std::size_t external = 0; external < dataset.node_size; ++external) {
            const std::size_t internal = graph.external_to_internal.at(external);
            uint32_t value = sssp_value((*read_host)[internal]);
            if (kConnectedComponents) {
                value = static_cast<uint32_t>(graph.internal_to_external.at(value));
            }
            result_out << external << ' ' << value << '\n';
        }
        if (!result_out) {
            fail("failed while writing result file: " + result_path);
        }

        std::cout << kLogPrefix << "_TIMING"
                  << " grasu_ms=" << std::fixed << std::setprecision(6) << timing.grasu_ms
                  << " barrier_ms=" << timing.barrier_ms
                  << " adapter_ms=" << timing.adapter_ms
                  << " lksg_ms=" << timing.lksg_ms
                  << " apply_ms=" << timing.apply_ms
                  << " hbm_ms=" << timing.hbm_ms
                  << " event_e2e_ms=" << timing.event_e2e_ms
                  << " convergence_readback_ms=" << timing.convergence_readback_ms
                  << " setup_inclusive_ms=" << timing.setup_inclusive_ms
                  << " wall_ms=" << timing.wall_ms
                  << std::endl;

        const bool pass = mismatch_count == 0 && hardware_converged && oracle.converged;
        std::cout << kLogPrefix << "_RESULT"
                  << " status=" << (pass ? "PASS" : "FAIL")
                  << " mismatches=" << mismatch_count
                  << " vertices=" << dataset.node_size
                  << " final_edges=" << final_edges.size()
                  << " logical_updates=" << dataset.update_edges.size()
                  << " physical_updates=" << graph.physical_updates.size()
                  << " processed_edge_slots_per_superstep=" << part_edge_num
                  << " source_external=" << source_external
                  << " source_internal=" << source_internal
                  << " max_supersteps=" << max_supersteps
                  << " executed_supersteps=" << executed_supersteps
                  << " hardware_converged=" << (hardware_converged ? 1 : 0)
                  << " oracle_supersteps=" << oracle.executed_supersteps
                  << " oracle_converged=" << (oracle.converged ? 1 : 0)
                  << " final_active_vertices=" << active_count[0]
                  << " algorithm=" << kAlgorithmName
                  << " conversion_cost=absent"
                  << std::endl;

        return pass ? EXIT_SUCCESS : EXIT_FAILURE;
    } catch (const std::exception &ex) {
        std::cerr << "ERROR: " << ex.what() << std::endl;
        return EXIT_FAILURE;
    }
}
#endif
#ifdef GRASU_REGRAPH_FULL_PAGERANK
int main(int argc, char **argv)
{
    try {
        const bool prepare_only = argc >= 2 && std::string(argv[1]) == "--prepare-only";
        if ((!prepare_only && argc != 4) || (prepare_only && argc != 4)) {
            std::cerr
                << "Usage: " << argv[0]
                << " <xclbin> <graph_file> <result_file>\n"
                << "       " << argv[0]
                << " --prepare-only <graph_file> <result_file>\n";
            return EXIT_FAILURE;
        }

        int arg_index = prepare_only ? 2 : 1;
        const std::string xclbin_path = prepare_only ? "" : argv[arg_index++];
        const std::string graph_path = argv[arg_index++];
        const std::string result_path = argv[arg_index++];
        constexpr unsigned rounds = 3;
        constexpr float damping = 0.85F;
        constexpr float epsilon = 1.0e-6F;

        Dataset dataset = read_dataset(graph_path);
        const FinalEdgeMap final_edges = build_final_external_edges(dataset);
        const WeightedPmaGraph graph = build_weighted_pma_graph(
            dataset.node_size, dataset.static_edges, dataset.update_edges);
        const FullPageRankOracleResult oracle = run_full_pagerank_oracle(
            dataset.node_size, final_edges, rounds, damping);
        PreparedGraSU prepared = prepare_grasu_inputs(graph);

        if (graph.physical_updates.size() > std::numeric_limits<unsigned>::max()) {
            fail("physical update count exceeds 32-bit kernel argument range");
        }
        if (prepared.pma_slot_count == 0 ||
            prepared.pma_slot_count > std::numeric_limits<unsigned>::max() ||
            prepared.pma_slot_count % kWeightedPmaSegmentSlots != 0) {
            fail("PMA stream must contain complete 16-slot segments");
        }

        std::cout << "FULL_PR_PMA_NATIVE_INPUT"
                  << " vertices=" << dataset.node_size
                  << " static_edges=" << dataset.static_edges.size()
                  << " logical_updates=" << dataset.update_edges.size()
                  << " physical_updates=" << graph.physical_updates.size()
                  << " final_edges=" << final_edges.size()
                  << " pma_slots=" << prepared.pma_slot_count
                  << " rounds=" << rounds
                  << " damping=" << damping
                  << std::endl;

        if (prepare_only) {
            float rank_sum = 0.0F;
            for (float value : oracle.rank) rank_sum += value;
            std::cout << "FULL_PR_PMA_NATIVE_PREP status=PASS"
                      << " vertices=" << dataset.node_size
                      << " final_edges=" << final_edges.size()
                      << " physical_updates=" << graph.physical_updates.size()
                      << " rounds=" << rounds
                      << " rank_sum=" << std::fixed << std::setprecision(7)
                      << rank_sum
                      << " conversion_cost=absent"
                      << std::endl;
            return EXIT_SUCCESS;
        }

        cl::Device device = select_xilinx_device();
        cl_int err = CL_SUCCESS;
        cl::Context context(device, nullptr, nullptr, nullptr, &err);
        check_cl(err, "create context");
        auto make_queue = [&](const std::string &name) {
            cl_int qerr = CL_SUCCESS;
            cl::CommandQueue queue(
                context, device,
                CL_QUEUE_PROFILING_ENABLE | CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE,
                &qerr);
            check_cl(qerr, "create " + name);
            return queue;
        };
        cl::CommandQueue transfer_queue = make_queue("transfer queue");
        cl::CommandQueue grasu_queue = make_queue("grasu queue");
        cl::CommandQueue pipeline_queue = make_queue("pipeline queue");

        std::vector<unsigned char> xclbin = read_binary_file(xclbin_path);
        cl::Program::Binaries bins{{xclbin.data(), xclbin.size()}};
        cl::Program program(context, {device}, bins, nullptr, &err);
        check_cl(err, "program device");

        auto make_kernel = [&](const std::string &name) {
            cl_int kernel_err = CL_SUCCESS;
            cl::Kernel kernel(program, name.c_str(), &kernel_err);
            check_cl(kernel_err, "create " + name);
            return kernel;
        };
        cl::Kernel bin_search_1 = make_kernel("bin_search:{bin_search_1}");
        cl::Kernel bin_search_2 = make_kernel("bin_search:{bin_search_2}");
        cl::Kernel bin_search_3 = make_kernel("bin_search:{bin_search_3}");
        cl::Kernel bin_search_4 = make_kernel("bin_search:{bin_search_4}");
        cl::Kernel dispatch = make_kernel("dispatch_degree:{dispatch_degree_1}");
        cl::Kernel process_cache_1 = make_kernel("process_cache:{process_cache_1}");
        cl::Kernel process_cache_2 = make_kernel("process_cache:{process_cache_2}");
        cl::Kernel process_ddr_1 = make_kernel("process_ddr:{process_ddr_1}");
        cl::Kernel process_ddr_2 = make_kernel("process_ddr:{process_ddr_2}");
        cl::Kernel degree_update =
            make_kernel("grasu_degree_update:{grasu_degree_update_1}");
        cl::Kernel adapter =
            make_kernel("pma_to_regraph_adapter:{pma_to_regraph_adapter_1}");
        cl::Kernel lksg = make_kernel("lksg_stream:{lksg_stream_1}");
        cl::Kernel apply =
            make_kernel("regraph_pagerank_apply:{regraph_pagerank_apply_1}");
        cl::Kernel source_prepare =
            make_kernel("regraph_pagerank_source_prepare:{pr_source_1}");
        cl::Kernel hbm = make_kernel("kernelHBMWrapper:{kernelHBMWrapper_1}");

        std::array<cl_mem_ext_ptr_t, 4> update_ext{};
        std::array<cl_mem_ext_ptr_t, 4> pma_ext{};
        std::array<cl_mem_ext_ptr_t, 4> row_ext{};
        std::array<cl_mem_ext_ptr_t, 4> binary_ext{};
        std::array<cl::Buffer, 4> update_dev;
        std::array<cl::Buffer, 4> pma_dev;
        std::array<cl::Buffer, 4> row_dev;
        std::array<cl::Buffer, 4> binary_dev;
        for (int index = 0; index < 4; ++index) {
            update_ext[index] = ext_ptr(index, prepared.update_edges[index].data());
            pma_ext[index] = ext_ptr(index, prepared.pma_words[index].data());
            row_ext[index] = ext_ptr(index, prepared.row_offsets[index].data());
            binary_ext[index] = ext_ptr(index, prepared.binary[index].data());
            update_dev[index] = make_buffer(
                context,
                CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.update_edges[index].size() * sizeof(std::uint64_t),
                &update_ext[index], "update_edges_" + std::to_string(index));
            pma_dev[index] = make_buffer(
                context,
                CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.pma_words[index].size() * sizeof(uint32_t),
                &pma_ext[index], "pma_" + std::to_string(index));
            row_dev[index] = make_buffer(
                context,
                CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.row_offsets[index].size() * sizeof(std::uint64_t),
                &row_ext[index], "row_offset_" + std::to_string(index));
            binary_dev[index] = make_buffer(
                context,
                CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.binary[index].size() * sizeof(std::uint64_t),
                &binary_ext[index], "binary_" + std::to_string(index));
        }

        AlignedVector<uint32_t> degree(kLittleDstBufferSize, 0);
        for (const auto &edge : dataset.static_edges) {
            const unsigned src = graph.external_to_internal.at(edge.source);
            degree[src]++;
        }
        AlignedVector<uint32_t> degree_status(16, 0);
        AlignedVector<float> rank(kLittleDstBufferSize, 0.0F);
        for (std::size_t vertex = 0; vertex < dataset.node_size; ++vertex) {
            rank[vertex] = 1.0F / static_cast<float>(dataset.node_size);
        }
        AlignedVector<uint32_t> round_stats(16, 0);
        AlignedVector<float> source_a(kLittleDstBufferSize, 0.0F);
        AlignedVector<float> source_b(kLittleDstBufferSize, 0.0F);

        cl_mem_ext_ptr_t degree_ext = ext_ptr(6, degree.data());
        cl_mem_ext_ptr_t degree_status_ext = ext_ptr(6, degree_status.data());
        cl_mem_ext_ptr_t rank_ext = ext_ptr(4, rank.data());
        cl_mem_ext_ptr_t stats_ext = ext_ptr(6, round_stats.data());
        cl_mem_ext_ptr_t source_a1_ext = ext_ptr(1, source_a.data());
        cl_mem_ext_ptr_t source_a2_ext = ext_ptr(3, source_a.data());
        cl_mem_ext_ptr_t source_b1_ext = ext_ptr(1, source_b.data());
        cl_mem_ext_ptr_t source_b2_ext = ext_ptr(3, source_b.data());
        cl::Buffer degree_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            degree.size() * sizeof(uint32_t), &degree_ext, "out_degree");
        cl::Buffer degree_status_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            degree_status.size() * sizeof(uint32_t), &degree_status_ext,
            "degree_status");
        cl::Buffer rank_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            rank.size() * sizeof(float), &rank_ext, "rank_state");
        cl::Buffer stats_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            round_stats.size() * sizeof(uint32_t), &stats_ext, "round_stats");
        cl::Buffer source_a1_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            source_a.size() * sizeof(float), &source_a1_ext, "source_a1");
        cl::Buffer source_a2_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            source_a.size() * sizeof(float), &source_a2_ext, "source_a2");
        cl::Buffer source_b1_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            source_b.size() * sizeof(float), &source_b1_ext, "source_b1");
        cl::Buffer source_b2_dev = make_buffer(
            context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            source_b.size() * sizeof(float), &source_b2_ext, "source_b2");

        std::vector<cl::Memory> initial_mems;
        for (int index = 0; index < 4; ++index) {
            initial_mems.push_back(update_dev[index]);
            initial_mems.push_back(pma_dev[index]);
            initial_mems.push_back(row_dev[index]);
            initial_mems.push_back(binary_dev[index]);
        }
        initial_mems.insert(initial_mems.end(), {
            degree_dev, degree_status_dev, rank_dev, stats_dev,
            source_a1_dev, source_a2_dev, source_b1_dev, source_b2_dev});
        check_cl(transfer_queue.enqueueMigrateMemObjects(initial_mems, 0),
                 "migrate initial buffers");
        transfer_queue.finish();

        auto set_bin_search_args = [&](cl::Kernel &kernel, int index) {
            int arg = 0;
            check_cl(kernel.setArg(arg++, update_dev[index]), "set bin_search edges");
            for (int copy = 0; copy < 4; ++copy) {
                check_cl(kernel.setArg(arg++, binary_dev[index]),
                         "set bin_search binary");
            }
            for (int copy = 0; copy < 4; ++copy) {
                check_cl(kernel.setArg(arg++, row_dev[index]),
                         "set bin_search row_offset");
            }
            check_cl(kernel.setArg(
                         arg++, static_cast<unsigned>(prepared.update_counts[index])),
                     "set bin_search edge_size");
        };
        set_bin_search_args(bin_search_1, 0);
        set_bin_search_args(bin_search_2, 1);
        set_bin_search_args(bin_search_3, 2);
        set_bin_search_args(bin_search_4, 3);
        const unsigned physical_updates =
            static_cast<unsigned>(graph.physical_updates.size());
        check_cl(dispatch.setArg(0, physical_updates), "set dispatch size");
        check_cl(process_cache_1.setArg(0, pma_dev[0]), "set process_cache_1");
        check_cl(process_cache_2.setArg(0, pma_dev[2]), "set process_cache_2");
        for (int arg = 0; arg < 4; ++arg) {
            check_cl(process_ddr_1.setArg(arg, pma_dev[1]), "set process_ddr_1");
            check_cl(process_ddr_2.setArg(arg, pma_dev[3]), "set process_ddr_2");
        }
        check_cl(degree_update.setArg(0, sizeof(cl_mem), nullptr),
                 "set degree connected stream");
        check_cl(degree_update.setArg(1, degree_dev), "set degree out_degree");
        check_cl(degree_update.setArg(2, degree_status_dev), "set degree status");
        check_cl(degree_update.setArg(
                     3, static_cast<unsigned>(dataset.node_size)),
                 "set degree vertices");
        check_cl(degree_update.setArg(4, physical_updates),
                 "set degree update_count");
        check_cl(adapter.setArg(0, pma_dev[0]), "set adapter pma0");
        check_cl(adapter.setArg(1, pma_dev[1]), "set adapter pma1");
        check_cl(adapter.setArg(2, pma_dev[2]), "set adapter pma2");
        check_cl(adapter.setArg(3, pma_dev[3]), "set adapter pma3");
        check_cl(adapter.setArg(4, row_dev[0]), "set adapter row_offset");
        check_cl(adapter.setArg(5, static_cast<unsigned>(dataset.node_size)),
                 "set adapter node_count");
        check_cl(adapter.setArg(6, static_cast<unsigned>(prepared.pma_slot_count)),
                 "set adapter pma_slot_count");
        check_cl(adapter.setArg(7, static_cast<unsigned>(kMaxCacheSegment)),
                 "set adapter max_cache_segment");

        constexpr unsigned burst_count = kLittleDstBufferSize / 16;
        const unsigned vertices = static_cast<unsigned>(dataset.node_size);
        const unsigned part_edge_num = static_cast<unsigned>(prepared.pma_slot_count);
        const float base = (1.0F - damping) / static_cast<float>(vertices);
        check_cl(source_prepare.setArg(0, rank_dev), "set source rank");
        check_cl(source_prepare.setArg(1, degree_dev), "set source degree");
        check_cl(source_prepare.setArg(2, source_a1_dev), "set source prop1");
        check_cl(source_prepare.setArg(3, source_a2_dev), "set source prop2");
        check_cl(source_prepare.setArg(4, stats_dev), "set source stats");
        check_cl(source_prepare.setArg(5, burst_count), "set source bursts");
        check_cl(source_prepare.setArg(6, vertices), "set source vertices");
        check_cl(source_prepare.setArg(7, damping), "set source damping");
        check_cl(source_prepare.setArg(8, epsilon), "set source epsilon");

        auto wall_begin = std::chrono::high_resolution_clock::now();
        std::vector<cl::Event> all_events;
        cl::Event pc1_event, pc2_event, pd1_event, pd2_event, degree_event;
        cl::Event dispatch_event, bs1_event, bs2_event, bs3_event, bs4_event;
        check_cl(grasu_queue.enqueueTask(process_cache_1, nullptr, &pc1_event),
                 "enqueue process_cache_1");
        check_cl(grasu_queue.enqueueTask(process_cache_2, nullptr, &pc2_event),
                 "enqueue process_cache_2");
        check_cl(grasu_queue.enqueueTask(process_ddr_1, nullptr, &pd1_event),
                 "enqueue process_ddr_1");
        check_cl(grasu_queue.enqueueTask(process_ddr_2, nullptr, &pd2_event),
                 "enqueue process_ddr_2");
        check_cl(grasu_queue.enqueueTask(degree_update, nullptr, &degree_event),
                 "enqueue degree_update");
        check_cl(grasu_queue.enqueueTask(dispatch, nullptr, &dispatch_event),
                 "enqueue dispatch_degree");
        check_cl(grasu_queue.enqueueTask(bin_search_1, nullptr, &bs1_event),
                 "enqueue bin_search_1");
        check_cl(grasu_queue.enqueueTask(bin_search_2, nullptr, &bs2_event),
                 "enqueue bin_search_2");
        check_cl(grasu_queue.enqueueTask(bin_search_3, nullptr, &bs3_event),
                 "enqueue bin_search_3");
        check_cl(grasu_queue.enqueueTask(bin_search_4, nullptr, &bs4_event),
                 "enqueue bin_search_4");
        grasu_queue.finish();
        std::vector<cl::Event> update_events{
            pc1_event, pc2_event, pd1_event, pd2_event, degree_event,
            dispatch_event, bs1_event, bs2_event, bs3_event, bs4_event};
        all_events.insert(all_events.end(), update_events.begin(), update_events.end());

        check_cl(transfer_queue.enqueueMigrateMemObjects(
                     {degree_status_dev}, CL_MIGRATE_MEM_OBJECT_HOST),
                 "read degree status");
        transfer_queue.finish();
        if (degree_status[0] != 0 || degree_status[1] != physical_updates) {
            fail("device degree update status failed: status=" +
                 std::to_string(degree_status[0]) + " processed=" +
                 std::to_string(degree_status[1]));
        }

        cl::Event source_event;
        check_cl(pipeline_queue.enqueueTask(source_prepare, nullptr, &source_event),
                 "enqueue source_prepare");
        pipeline_queue.finish();
        all_events.push_back(source_event);
        check_cl(transfer_queue.enqueueMigrateMemObjects(
                     {stats_dev}, CL_MIGRATE_MEM_OBJECT_HOST),
                 "read source stats");
        transfer_queue.finish();
        if (round_stats[0] != 0) fail("source_prepare capacity status failed");
        float dangling = word_to_float(round_stats[3]);

        std::array<cl::Buffer *, 2> current_source{
            &source_a1_dev, &source_a2_dev};
        std::array<cl::Buffer *, 2> next_source{
            &source_b1_dev, &source_b2_dev};
        double adapter_ms = 0.0;
        double lksg_ms = 0.0;
        double apply_ms = 0.0;
        double hbm_ms = 0.0;
        for (unsigned round = 0; round < rounds; ++round) {
            check_cl(hbm.setArg(0, *current_source[0]), "set hbm src1");
            check_cl(hbm.setArg(1, *current_source[1]), "set hbm src2");
            check_cl(hbm.setArg(2, *next_source[0]), "set hbm next1");
            check_cl(hbm.setArg(3, *next_source[1]), "set hbm next2");
            check_cl(hbm.setArg(4, 1U), "set hbm dense");
            check_cl(hbm.setArg(5, 0U), "set hbm sparse");
            check_cl(lksg.setArg(1, part_edge_num), "set lksg edges");
            check_cl(lksg.setArg(2, 0U), "set lksg compressed groups");
            check_cl(lksg.setArg(3, 0U), "set lksg destination offset");
            check_cl(lksg.setArg(4, round == 0), "set lksg reset");
            check_cl(apply.setArg(0, rank_dev), "set apply rank");
            check_cl(apply.setArg(1, degree_dev), "set apply degree");
            check_cl(apply.setArg(2, stats_dev), "set apply stats");
            check_cl(apply.setArg(3, burst_count), "set apply bursts");
            check_cl(apply.setArg(4, vertices), "set apply vertices");
            check_cl(apply.setArg(5, damping), "set apply damping");
            check_cl(apply.setArg(6, epsilon), "set apply epsilon");
            check_cl(apply.setArg(7, base), "set apply base");
            check_cl(apply.setArg(
                         8, damping * dangling / static_cast<float>(vertices)),
                     "set apply dangling_share");

            cl::Event adapter_event, lksg_event, hbm_event, apply_event;
            check_cl(pipeline_queue.enqueueTask(adapter, nullptr, &adapter_event),
                     "enqueue adapter");
            check_cl(pipeline_queue.enqueueTask(lksg, nullptr, &lksg_event),
                     "enqueue lksg");
            check_cl(pipeline_queue.enqueueTask(hbm, nullptr, &hbm_event),
                     "enqueue hbm");
            check_cl(pipeline_queue.enqueueTask(apply, nullptr, &apply_event),
                     "enqueue apply");
            pipeline_queue.finish();
            adapter_ms += event_duration_ms(adapter_event);
            lksg_ms += event_duration_ms(lksg_event);
            hbm_ms += event_duration_ms(hbm_event);
            apply_ms += event_duration_ms(apply_event);
            all_events.insert(all_events.end(), {
                adapter_event, lksg_event, hbm_event, apply_event});

            check_cl(transfer_queue.enqueueMigrateMemObjects(
                         {stats_dev}, CL_MIGRATE_MEM_OBJECT_HOST),
                     "read round stats");
            transfer_queue.finish();
            if (round_stats[0] != 0 || round_stats[4] != vertices) {
                fail("PageRank apply status failed at round " +
                     std::to_string(round + 1));
            }
            dangling = word_to_float(round_stats[3]);
            std::swap(current_source, next_source);
            std::cout << "FULL_PR_PMA_NATIVE_ROUND round=" << (round + 1)
                      << " l1_error=" << word_to_float(round_stats[2])
                      << " dangling=" << dangling
                      << " active_vertices=" << round_stats[1]
                      << std::endl;
        }

        check_cl(transfer_queue.enqueueMigrateMemObjects(
                     {rank_dev, degree_dev}, CL_MIGRATE_MEM_OBJECT_HOST),
                 "read final rank and degree");
        transfer_queue.finish();
        const auto wall_end = std::chrono::high_resolution_clock::now();
        const double setup_inclusive_ms =
            std::chrono::duration<double, std::milli>(wall_end - wall_begin).count();

        std::size_t rank_mismatches = 0;
        std::size_t degree_mismatches = 0;
        float max_abs_error = 0.0F;
        for (std::size_t internal = 0; internal < dataset.node_size; ++internal) {
            const std::size_t external = graph.internal_to_external.at(internal);
            const float expected = oracle.rank.at(external);
            const float actual = rank[internal];
            const float abs_error = std::abs(actual - expected);
            max_abs_error = std::max(max_abs_error, abs_error);
            if (abs_error > 1.0e-4F + 1.0e-3F * std::abs(expected)) {
                if (rank_mismatches < 20) {
                    std::cerr << "rank mismatch external=" << external
                              << " expected=" << expected
                              << " actual=" << actual << std::endl;
                }
                rank_mismatches++;
            }
            if (degree[internal] != oracle.out_degree.at(external)) {
                degree_mismatches++;
            }
        }

        std::ofstream result_out(result_path);
        if (!result_out) fail("failed to open result file: " + result_path);
        result_out << std::setprecision(9);
        for (std::size_t external = 0; external < dataset.node_size; ++external) {
            const std::size_t internal = graph.external_to_internal.at(external);
            result_out << external << ' ' << rank[internal] << '\n';
        }
        if (!result_out) fail("failed while writing result file");

        std::cout << "FULL_PR_PMA_NATIVE_TIMING"
                  << " update_ms=" << event_union_ms(update_events)
                  << " source_prepare_ms=" << event_duration_ms(source_event)
                  << " adapter_ms=" << adapter_ms
                  << " lksg_ms=" << lksg_ms
                  << " apply_ms=" << apply_ms
                  << " hbm_ms=" << hbm_ms
                  << " device_e2e_ms=" << event_union_ms(all_events)
                  << " setup_inclusive_ms=" << setup_inclusive_ms
                  << std::endl;
        const bool pass = rank_mismatches == 0 && degree_mismatches == 0;
        std::cout << "FULL_PR_PMA_NATIVE_RESULT"
                  << " status=" << (pass ? "PASS" : "FAIL")
                  << " rank_mismatches=" << rank_mismatches
                  << " degree_mismatches=" << degree_mismatches
                  << " max_abs_error=" << max_abs_error
                  << " rounds=" << rounds
                  << " vertices=" << dataset.node_size
                  << " final_edges=" << final_edges.size()
                  << " logical_updates=" << dataset.update_edges.size()
                  << " physical_updates=" << graph.physical_updates.size()
                  << " conversion_cost=absent"
                  << std::endl;
        return pass ? EXIT_SUCCESS : EXIT_FAILURE;
    } catch (const std::exception &ex) {
        std::cerr << "ERROR: " << ex.what() << std::endl;
        return EXIT_FAILURE;
    }
}
#endif
