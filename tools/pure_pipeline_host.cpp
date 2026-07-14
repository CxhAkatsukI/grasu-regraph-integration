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
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include "pma_dynamic_graph.hpp"

bool cmp(std::pair<unsigned int, double> a, std::pair<unsigned int, double> b)
{
    return a.second > b.second;
}

namespace {

constexpr uint32_t kPmaEmpty32 = 0x80000000u;
constexpr uint32_t kSsspInf = static_cast<uint32_t>(std::numeric_limits<int>::max() - 1);
constexpr uint32_t kActiveMask = 0x80000000u;
constexpr uint32_t kPropMask = 0x7fffffffu;
constexpr unsigned kPartitionSize = 65536;
constexpr unsigned kLittleDstBufferSize = 65536;

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
    std::vector<unsigned long> static_edges;
    std::vector<unsigned long> update_edges;
};

struct PreparedGraSU {
    std::array<AlignedVector<unsigned long>, 4> update_edges;
    std::array<AlignedVector<uint32_t>, 4> pma_words;
    std::array<AlignedVector<unsigned long>, 4> row_offsets;
    std::array<AlignedVector<unsigned long>, 4> binary;
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
    double wall_ms = 0.0;
};

[[noreturn]] void fail(const std::string &message)
{
    throw std::runtime_error(message);
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
        unsigned begin = 0;
        unsigned end = 0;
        in >> begin >> end;
        dataset.static_edges[i] =
            (static_cast<unsigned long>(begin) << 32) | static_cast<unsigned long>(end);
    }

    dataset.update_edges.resize(update_edge_size);
    for (std::size_t i = 0; i < update_edge_size; ++i) {
        unsigned begin = 0;
        unsigned end = 0;
        unsigned type = 0;
        in >> begin >> end >> type;
        unsigned long edge =
            (static_cast<unsigned long>(begin) << 32) | static_cast<unsigned long>(end);
        if (type == 0) edge |= EMPTY;
        dataset.update_edges[i] = edge;
    }

    if (!in && !in.eof()) {
        fail("failed while reading graph file: " + path);
    }

    return dataset;
}

std::set<unsigned long> build_final_internal_edges(
    const std::vector<unsigned long> &static_edges,
    const std::vector<unsigned long> &update_edges)
{
    std::set<unsigned long> final_edges;
    for (unsigned long edge : static_edges) {
        final_edges.insert(edge & ~EMPTY);
    }
    for (unsigned long raw_update : update_edges) {
        const unsigned long edge = raw_update & ~EMPTY;
        if ((raw_update & EMPTY) != 0) {
            final_edges.erase(edge);
        } else {
            final_edges.insert(edge);
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

std::vector<uint32_t> run_unit_sssp_oracle(std::size_t vertices,
                                           const std::set<unsigned long> &edges,
                                           unsigned source,
                                           unsigned supersteps)
{
    std::vector<uint32_t> prop(vertices, kSsspInf);
    prop[source] = kActiveMask;

    for (unsigned step = 0; step < supersteps; ++step) {
        std::vector<uint32_t> tmp(vertices, 0);
        for (unsigned long edge : edges) {
            const unsigned src = static_cast<unsigned>(edge >> 32);
            const unsigned dst = static_cast<unsigned>(edge & 0xffffffffUL);
            if (src >= vertices || dst >= vertices) continue;
            if (!is_active(prop[src])) continue;

            uint32_t next_dist = sssp_value(prop[src]) + 1;
            if (next_dist >= kSsspInf) next_dist = kSsspInf;
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
    }

    return prop;
}

PreparedGraSU prepare_grasu_inputs(const pma_dynamic_graph &graph,
                                   const std::vector<unsigned long> &update_edges)
{
    PreparedGraSU prepared;

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

    prepared.pma_slot_count = graph.data.size();
    const std::size_t data_segment_size = graph.data.size() / SEGMENT_SIZE;
    for (int i = 0; i < 2; ++i) {
        prepared.sub_data_segments[i] = data_segment_size >> 1;
    }
    for (std::size_t i = 0; i < (data_segment_size % 2); ++i) {
        prepared.sub_data_segments[i]++;
    }
    for (int i = 0; i < 2; ++i) {
        if (prepared.sub_data_segments[i] < MAX_CACHE_SEGMENT) {
            prepared.sub_data_segments[i] = MAX_CACHE_SEGMENT;
        }
        prepared.sub_data_words[i] = prepared.sub_data_segments[i] * SEGMENT_SIZE;
    }

    prepared.pma_words[0].assign(prepared.sub_data_words[0], kPmaEmpty32);
    prepared.pma_words[1].assign(prepared.sub_data_words[0], kPmaEmpty32);
    prepared.pma_words[2].assign(prepared.sub_data_words[1], kPmaEmpty32);
    prepared.pma_words[3].assign(prepared.sub_data_words[1], kPmaEmpty32);

    for (std::size_t i = 0; i < graph.data.size(); i += SEGMENT_SIZE) {
        const std::size_t segment_index = i / SEGMENT_SIZE;
        std::size_t sub_index = segment_index % 2;
        sub_index <<= 1;
        const std::size_t local_base = (segment_index / 2) * SEGMENT_SIZE;
        for (int j = 0; j < SEGMENT_SIZE; ++j) {
            uint32_t dst = static_cast<uint32_t>(graph.data[i + j] & 0xffffffffUL);
            if ((graph.data[i + j] & EMPTY) != 0) dst |= kPmaEmpty32;
            prepared.pma_words[sub_index + 0][local_base + j] = dst;
            prepared.pma_words[sub_index + 1][local_base + j] = dst;
        }
    }

    const std::size_t row_count = std::max<std::size_t>(graph.row_offset.size(), 1);
    for (int copy = 0; copy < 4; ++copy) {
        prepared.row_offsets[copy].assign(row_count, 0);
    }
    for (std::size_t i = 0; i + 1 < graph.row_offset.size(); ++i) {
        const unsigned long packed =
            (graph.row_offset[i] << 32) | static_cast<unsigned long>(graph.row_offset[i + 1]);
        for (int copy = 0; copy < 4; ++copy) {
            prepared.row_offsets[copy][i] = packed;
        }
    }
    if (!graph.row_offset.empty()) {
        const unsigned long last = graph.row_offset.back();
        const unsigned long packed_last = (last << 32) | last;
        for (int copy = 0; copy < 4; ++copy) {
            prepared.row_offsets[copy].back() = packed_last;
        }
    }

    const std::size_t binary_count = std::max<std::size_t>(graph.binary_search.size(), 1);
    for (int copy = 0; copy < 4; ++copy) {
        prepared.binary[copy].assign(binary_count, 0);
        for (std::size_t i = 0; i < graph.binary_search.size(); ++i) {
            prepared.binary[copy][i] = graph.binary_search[i];
        }
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
        << " <xclbin> <graph_file> <result_file> [source_external] [supersteps]\n"
        << "       " << argv0
        << " --prepare-only <graph_file> <result_file> [source_external] [supersteps]\n"
        << "\n"
        << "Runs the first-stage GraSU -> PMA adapter -> ReGraph little-GS pure pipeline.\n"
        << "The result file is accepted for CLI compatibility; CPU SSSP oracle is built\n"
        << "from GraSU's internal post-update graph.\n"
        << "--prepare-only validates graph ingest, V<=65536 bounds, GraSU PMA packing,\n"
        << "and the CPU oracle without loading an xclbin.\n";
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
        (void)result_path;
        const unsigned source_external =
            argc > arg_index ? static_cast<unsigned>(std::stoul(argv[arg_index])) : 0;
        const unsigned supersteps =
            argc > arg_index + 1 ? static_cast<unsigned>(std::stoul(argv[arg_index + 1])) : 1;
        if (supersteps == 0) fail("supersteps must be >= 1");

        Dataset dataset = read_dataset(graph_path);
        if (source_external >= dataset.node_size) {
            fail("source vertex is outside the graph");
        }

        pma_dynamic_graph graph(static_cast<int>(dataset.node_size),
                                dataset.static_edges.data(),
                                dataset.static_edges.size(),
                                dataset.update_edges.data(),
                                dataset.update_edges.size());
        const unsigned source_internal = graph.node_map[source_external];
        const std::set<unsigned long> final_edges =
            build_final_internal_edges(dataset.static_edges, dataset.update_edges);
        const std::vector<uint32_t> oracle =
            run_unit_sssp_oracle(dataset.node_size, final_edges, source_internal, supersteps);

        PreparedGraSU prepared = prepare_grasu_inputs(graph, dataset.update_edges);
        std::cout << "PURE_PIPELINE_INPUT"
                  << " vertices=" << dataset.node_size
                  << " static_edges=" << dataset.static_edges.size()
                  << " update_edges=" << dataset.update_edges.size()
                  << " final_edges=" << final_edges.size()
                  << " pma_slots=" << prepared.pma_slot_count
                  << " source_external=" << source_external
                  << " source_internal=" << source_internal
                  << " supersteps=" << supersteps
                  << std::endl;

        if (prepare_only) {
            std::size_t reachable_vertices = 0;
            uint32_t max_distance = 0;
            for (uint32_t value : oracle) {
                const uint32_t distance = sssp_value(value);
                if (distance < kSsspInf) {
                    reachable_vertices++;
                    max_distance = std::max(max_distance, distance);
                }
            }
            std::cout << "PURE_PIPELINE_PREP"
                      << " status=PASS"
                      << " vertices=" << dataset.node_size
                      << " static_edges=" << dataset.static_edges.size()
                      << " update_edges=" << dataset.update_edges.size()
                      << " final_edges=" << final_edges.size()
                      << " pma_slots=" << prepared.pma_slot_count
                      << " row_offset_words=" << prepared.row_offsets[0].size()
                      << " binary_segments=" << prepared.binary[0].size()
                      << " source_external=" << source_external
                      << " source_internal=" << source_internal
                      << " supersteps=" << supersteps
                      << " reachable_vertices=" << reachable_vertices
                      << " max_distance=" << max_distance
                      << " partition_size=" << kPartitionSize
                      << " little_dst_buffer=" << kLittleDstBufferSize
                      << " unit_weight=1"
                      << std::endl;
            return EXIT_SUCCESS;
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
                prepared.update_edges[i].size() * sizeof(unsigned long),
                &update_ext[i], "update_edges_" + std::to_string(i));
            pma_dev[i] = make_buffer(
                context,
                CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.pma_words[i].size() * sizeof(uint32_t),
                &pma_ext[i], "pma_" + std::to_string(i));
            row_dev[i] = make_buffer(
                context,
                CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.row_offsets[i].size() * sizeof(unsigned long),
                &row_ext[i], "row_offset_" + std::to_string(i));
            binary_dev[i] = make_buffer(
                context,
                CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
                prepared.binary[i].size() * sizeof(unsigned long),
                &binary_ext[i], "binary_" + std::to_string(i));
        }

        AlignedVector<uint32_t> prop_a(kLittleDstBufferSize, 0);
        AlignedVector<uint32_t> prop_b(kLittleDstBufferSize, 0);
        AlignedVector<uint32_t> apply_prop(kLittleDstBufferSize, 0);
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

        check_cl(dispatch.setArg(0, static_cast<unsigned>(dataset.update_edges.size())),
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
        check_cl(adapter.setArg(7, static_cast<unsigned>(MAX_CACHE_SEGMENT)),
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

        cl::Event pc1_event, pc2_event, pd1_event, pd2_event, dispatch_event;
        cl::Event bs1_event, bs2_event, bs3_event, bs4_event;
        std::cout << "PURE_PIPELINE_HOST stage=launch_grasu" << std::endl;
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
        std::cout << "PURE_PIPELINE_HOST stage=enqueue_barrier" << std::endl;
        check_cl(pipeline_queue.enqueueTask(barrier, nullptr, &barrier_event),
                 "enqueue pma_completion_barrier");
        std::cout << "PURE_PIPELINE_HOST stage=enqueued_barrier" << std::endl;
        all_events.push_back(barrier_event);

        for (unsigned step = 0; step < supersteps; ++step) {
            check_cl(hbm.setArg(0, *read_props[0]), "set hbm src_prop_1");
            check_cl(hbm.setArg(1, *read_props[1]), "set hbm src_prop_2");
            check_cl(hbm.setArg(2, *write_props[0]), "set hbm new_prop_1");
            check_cl(hbm.setArg(3, *write_props[1]), "set hbm new_prop_2");
            check_cl(hbm.setArg(4, num_dense), "set hbm num_dense");
            check_cl(hbm.setArg(5, num_sparse), "set hbm num_sparse");

            check_cl(apply.setArg(0, apply_prop_dev), "set apply vertex_prop");
            check_cl(apply.setArg(1, num_dense), "set apply num_dense");
            check_cl(apply.setArg(2, num_sparse), "set apply num_sparse");
            check_cl(apply.setArg(3, reg), "set apply reg");

            check_cl(lksg.setArg(1, part_edge_num), "set lksg part_edge_num");
            check_cl(lksg.setArg(2, compressed_group_count),
                     "set lksg compressed_group_count");
            check_cl(lksg.setArg(3, part_dst_offset), "set lksg part_dst_offset");
            const bool reset_tmp_prop = (step == 0);
            check_cl(lksg.setArg(4, reset_tmp_prop), "set lksg reset_tmp_prop");

            cl::Event hbm_event, apply_event, lksg_event, adapter_event;
            std::cout << "PURE_PIPELINE_HOST stage=launch_step step=" << (step + 1)
                      << std::endl;
            std::cout << "PURE_PIPELINE_HOST stage=enqueue_adapter step=" << (step + 1)
                      << std::endl;
            std::vector<cl::Event> adapter_wait_events;
            const std::vector<cl::Event> *adapter_wait_list = nullptr;
            if (step == 0) {
                adapter_wait_events.push_back(barrier_event);
                adapter_wait_list = &adapter_wait_events;
            }
            check_cl(pipeline_queue.enqueueTask(adapter, adapter_wait_list, &adapter_event),
                     "enqueue adapter");
            std::cout << "PURE_PIPELINE_HOST stage=enqueued_adapter step=" << (step + 1)
                      << std::endl;
            std::cout << "PURE_PIPELINE_HOST stage=enqueue_lksg step=" << (step + 1)
                      << std::endl;
            check_cl(pipeline_queue.enqueueTask(lksg, nullptr, &lksg_event), "enqueue lksg");
            std::cout << "PURE_PIPELINE_HOST stage=enqueued_lksg step=" << (step + 1)
                      << std::endl;
            std::cout << "PURE_PIPELINE_HOST stage=enqueue_hbm step=" << (step + 1)
                      << std::endl;
            check_cl(pipeline_queue.enqueueTask(hbm, nullptr, &hbm_event), "enqueue hbm");
            std::cout << "PURE_PIPELINE_HOST stage=enqueued_hbm step=" << (step + 1)
                      << std::endl;
            std::cout << "PURE_PIPELINE_HOST stage=enqueue_apply step=" << (step + 1)
                      << std::endl;
            check_cl(pipeline_queue.enqueueTask(apply, nullptr, &apply_event),
                     "enqueue apply");
            std::cout << "PURE_PIPELINE_HOST stage=enqueued_apply step=" << (step + 1)
                      << std::endl;

            std::vector<cl::Event> step_events{hbm_event, apply_event, lksg_event, adapter_event};
            std::cout << "PURE_PIPELINE_HOST stage=wait_step step=" << (step + 1)
                      << std::endl;
            pipeline_queue.finish();

            timing.hbm_ms += event_duration_ms(hbm_event);
            timing.apply_ms += event_duration_ms(apply_event);
            timing.lksg_ms += event_duration_ms(lksg_event);
            timing.adapter_ms += event_duration_ms(adapter_event);
            all_events.insert(all_events.end(), step_events.begin(), step_events.end());

            std::swap(read_props, write_props);
            std::swap(read_host, write_host);
            std::cout << "PURE_PIPELINE_SUPERSTEP step=" << (step + 1)
                      << " adapter_ms=" << std::fixed << std::setprecision(6)
                      << event_duration_ms(adapter_event)
                      << " lksg_ms=" << event_duration_ms(lksg_event)
                      << " apply_ms=" << event_duration_ms(apply_event)
                      << " hbm_ms=" << event_duration_ms(hbm_event)
                      << std::endl;
        }

        for (cl::Event &event : grasu_events) {
            event.wait();
        }
        grasu_queue.finish();
        pipeline_queue.finish();
        auto wall_end = std::chrono::high_resolution_clock::now();

        timing.grasu_ms = event_union_ms(grasu_events);
        timing.barrier_ms = event_duration_ms(barrier_event);
        timing.event_e2e_ms = event_union_ms(all_events);
        timing.wall_ms = std::chrono::duration<double, std::milli>(wall_end - wall_begin).count();

        check_cl(transfer_queue.enqueueMigrateMemObjects({*read_props[0]},
                                                         CL_MIGRATE_MEM_OBJECT_HOST),
                 "migrate final result");
        transfer_queue.finish();

        std::size_t mismatch_count = 0;
        for (std::size_t i = 0; i < dataset.node_size; ++i) {
            if ((*read_host)[i] != oracle[i]) {
                if (mismatch_count < 20) {
                    std::cerr << "mismatch vertex=" << i
                              << " expected=0x" << std::hex << oracle[i]
                              << " got=0x" << (*read_host)[i] << std::dec
                              << std::endl;
                }
                mismatch_count++;
            }
        }

        std::cout << "PURE_PIPELINE_TIMING"
                  << " grasu_ms=" << std::fixed << std::setprecision(6) << timing.grasu_ms
                  << " barrier_ms=" << timing.barrier_ms
                  << " adapter_ms=" << timing.adapter_ms
                  << " lksg_ms=" << timing.lksg_ms
                  << " apply_ms=" << timing.apply_ms
                  << " hbm_ms=" << timing.hbm_ms
                  << " event_e2e_ms=" << timing.event_e2e_ms
                  << " wall_ms=" << timing.wall_ms
                  << std::endl;

        const bool pass = mismatch_count == 0;
        std::cout << "PURE_PIPELINE_RESULT"
                  << " status=" << (pass ? "PASS" : "FAIL")
                  << " mismatches=" << mismatch_count
                  << " vertices=" << dataset.node_size
                  << " final_edges=" << final_edges.size()
                  << " processed_edge_slots_per_superstep=" << part_edge_num
                  << " source_external=" << source_external
                  << " source_internal=" << source_internal
                  << " supersteps=" << supersteps
                  << std::endl;

        return pass ? EXIT_SUCCESS : EXIT_FAILURE;
    } catch (const std::exception &ex) {
        std::cerr << "ERROR: " << ex.what() << std::endl;
        return EXIT_FAILURE;
    }
}
