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

struct SsspOracleResult {
    std::vector<uint32_t> prop;
    unsigned executed_supersteps = 0;
    bool converged = false;
};

[[noreturn]] void fail(const std::string &message)
{
    throw std::runtime_error(message);
}

unsigned parse_unsigned_arg(const std::string &text, const std::string &name)
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

SsspOracleResult run_weighted_sssp_oracle(std::size_t vertices,
                                          const FinalEdgeMap &edges,
                                          unsigned source,
                                          unsigned max_supersteps)
{
    std::vector<uint32_t> prop(vertices, kSsspInf);
    prop[source] = kActiveMask;

    SsspOracleResult result;
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

void usage(const char *argv0)
{
    std::cerr
        << "Usage: " << argv0
        << " <xclbin> <graph_file> <result_file> [source_external] [max_supersteps]\n"
        << "       " << argv0
        << " --prepare-only <graph_file> <result_file> [source_external] [max_supersteps]\n"
        << "\n"
        << "Runs weighted GraSU PMA -> AXIS adapter -> ReGraph SSSP.\n"
        << "Input: header 'V initial_edges updates'; initial rows 'src dst weight';\n"
        << "update rows 'src dst weight type', where type=0 deletes and type=1 inserts\n"
        << "or changes weight. Hardware mode writes 'external_vertex distance'.\n"
        << "--prepare-only validates input, weighted PMA packing/lowering, and an\n"
        << "independent external-ID synchronous SSSP oracle without loading xclbin.\n";
}

}  // namespace

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
        const SsspOracleResult oracle = run_weighted_sssp_oracle(
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
        std::cout << "WEIGHTED_PMA_NATIVE_INPUT"
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
            std::cout << "WEIGHTED_PMA_NATIVE_PREP"
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
                      << " max_distance=" << max_distance
                      << " partition_size=" << kPartitionSize
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
            prop_a[i] = kSsspInf;
            apply_prop[i] = kSsspInf;
        }
        prop_a[source_internal] = kActiveMask;
        apply_prop[source_internal] = kActiveMask;

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
        std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=launch_grasu" << std::endl;
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
        std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=enqueue_barrier" << std::endl;
        check_cl(pipeline_queue.enqueueTask(barrier, nullptr, &barrier_event),
                 "enqueue pma_completion_barrier");
        std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=enqueued_barrier" << std::endl;
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
            std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=launch_step step=" << (step + 1)
                      << std::endl;
            std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=enqueue_adapter step=" << (step + 1)
                      << std::endl;
            std::vector<cl::Event> adapter_wait_events;
            const std::vector<cl::Event> *adapter_wait_list = nullptr;
            if (step == 0) {
                adapter_wait_events.push_back(barrier_event);
                adapter_wait_list = &adapter_wait_events;
            }
            check_cl(pipeline_queue.enqueueTask(adapter, adapter_wait_list, &adapter_event),
                     "enqueue adapter");
            std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=enqueued_adapter step=" << (step + 1)
                      << std::endl;
            std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=enqueue_lksg step=" << (step + 1)
                      << std::endl;
            check_cl(pipeline_queue.enqueueTask(lksg, nullptr, &lksg_event), "enqueue lksg");
            std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=enqueued_lksg step=" << (step + 1)
                      << std::endl;
            std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=enqueue_hbm step=" << (step + 1)
                      << std::endl;
            check_cl(pipeline_queue.enqueueTask(hbm, nullptr, &hbm_event), "enqueue hbm");
            std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=enqueued_hbm step=" << (step + 1)
                      << std::endl;
            std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=enqueue_apply step=" << (step + 1)
                      << std::endl;
            check_cl(pipeline_queue.enqueueTask(apply, nullptr, &apply_event),
                     "enqueue apply");
            std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=enqueued_apply step=" << (step + 1)
                      << std::endl;

            std::vector<cl::Event> step_events{hbm_event, apply_event, lksg_event, adapter_event};
            std::cout << "WEIGHTED_PMA_NATIVE_HOST stage=wait_step step=" << (step + 1)
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
            std::cout << "WEIGHTED_PMA_NATIVE_SUPERSTEP step=" << (step + 1)
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
            const uint32_t expected = oracle.prop.at(external);
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
            result_out << external << ' ' << sssp_value((*read_host)[internal]) << '\n';
        }
        if (!result_out) {
            fail("failed while writing result file: " + result_path);
        }

        std::cout << "WEIGHTED_PMA_NATIVE_TIMING"
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
        std::cout << "WEIGHTED_PMA_NATIVE_RESULT"
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
                  << " conversion_cost=absent"
                  << std::endl;

        return pass ? EXIT_SUCCESS : EXIT_FAILURE;
    } catch (const std::exception &ex) {
        std::cerr << "ERROR: " << ex.what() << std::endl;
        return EXIT_FAILURE;
    }
}
