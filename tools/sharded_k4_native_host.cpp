#define GRASU_REGRAPH_NO_MAIN 1
#define GRASU_REGRAPH_SHARDED_K4_HOST 1
#include "weighted_pma_native_host.cpp"

#include "weighted_pma_runtime_plan.hpp"

#include <numeric>

namespace {

using grasu::integration::WeightedPartitionedPmaGraph;
using grasu::integration::WeightedPmaPackedShardBuffers;
using grasu::integration::WeightedPmaRuntimePlan;
using grasu::integration::WeightedPmaChannelPolicy;
using grasu::integration::build_weighted_partitioned_pma_graph;
using grasu::integration::build_weighted_pma_runtime_plan;
using grasu::integration::find_weighted_pma_region;
using grasu::integration::pack_weighted_pma_runtime_buffers;

constexpr unsigned kK4Frontends = 4;
constexpr unsigned kGatherPacketsPerPartition = kLittleDstBufferSize / 2;

struct DeviceShard {
    std::array<cl_mem_ext_ptr_t, 4> update_ext{};
    std::array<cl_mem_ext_ptr_t, 4> pma_ext{};
    cl_mem_ext_ptr_t row_ext{};
    cl_mem_ext_ptr_t binary_ext{};
    std::array<cl::Buffer, 4> update_dev;
    std::array<cl::Buffer, 4> pma_dev;
    cl::Buffer row_dev;
    cl::Buffer binary_dev;
};

std::size_t total_pma_slots(const WeightedPartitionedPmaGraph &graph)
{
    return std::accumulate(
        graph.shards.begin(), graph.shards.end(), std::size_t{0},
        [](std::size_t total, const auto &shard) {
            return total + shard.initial_pma_words.size();
        });
}

std::size_t max_shard_pma_slots(const WeightedPartitionedPmaGraph &graph)
{
    return std::max_element(
               graph.shards.begin(), graph.shards.end(),
               [](const auto &left, const auto &right) {
                   return left.initial_pma_words.size() <
                          right.initial_pma_words.size();
               })
        ->initial_pma_words.size();
}

void write_device_buffer(cl::CommandQueue &queue,
                         cl::Buffer &buffer,
                         std::size_t bytes,
                         const void *data,
                         const std::string &name)
{
    check_cl(queue.enqueueWriteBuffer(buffer, CL_FALSE, 0, bytes, data),
             "write buffer " + name);
}

[[maybe_unused]] void print_prepare_result(const Dataset &dataset,
                          const WeightedPartitionedPmaGraph &graph,
                          const WeightedPmaRuntimePlan &plan,
                          const AlgorithmOracleResult &oracle,
                          unsigned source_external,
                          unsigned source_internal,
                          unsigned max_supersteps)
{
    std::size_t reachable_vertices = 0;
    uint32_t max_value = 0;
    for (uint32_t value : oracle.prop) {
        const uint32_t prop = sssp_value(value);
        if (prop < kSsspInf) {
            ++reachable_vertices;
            max_value = std::max(max_value, prop);
        }
    }
    std::cout << kLogPrefix << "_SHARDED_PREP"
              << " status=" << (oracle.converged ? "PASS" : "FAIL")
              << " vertices=" << dataset.node_size
              << " static_edges=" << dataset.static_edges.size()
              << " logical_updates=" << dataset.update_edges.size()
              << " physical_updates=" << graph.physical_internal.size()
              << " destination_partitions=" << graph.shards.size()
              << " pma_slots_total=" << total_pma_slots(graph)
              << " pma_slots_max_shard=" << max_shard_pma_slots(graph)
              << " hbm_graph_channels=" << plan.channel_load_bytes.size()
              << " hbm_graph_allocated_bytes=" << plan.total_allocated_bytes
              << " hbm_max_channel_bytes="
              << *std::max_element(plan.channel_load_bytes.begin(),
                                   plan.channel_load_bytes.end())
              << " source_external=" << source_external
              << " source_internal=" << source_internal
              << " max_supersteps=" << max_supersteps
              << " oracle_supersteps=" << oracle.executed_supersteps
              << " oracle_converged=" << (oracle.converged ? 1 : 0)
              << " reachable_vertices=" << reachable_vertices
              << " max_value=" << max_value;
    if (kConnectedComponents) {
        std::cout << " components=" << count_components(oracle);
    }
    std::cout << " pma_destination_abi=local_dst19"
              << " partition_size=" << kPartitionSize
              << " k4_frontends=" << kK4Frontends
              << " shared_regraph_downstream=1"
              << " conversion_cost=absent"
              << std::endl;
}

}  // namespace

#ifndef GRASU_REGRAPH_SHARDED_K4_NO_MAIN
int main(int argc, char **argv)
{
    try {
        const bool prepare_only =
            argc >= 2 && std::string(argv[1]) == "--prepare-only";
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

        // Build the PMA before materializing the two oracle maps.  Each map is
        // full-graph sized; overlapping both with the builder's transient
        // state multiplies host memory on 100M-edge inputs without changing
        // any device-visible data.
        const WeightedPartitionedPmaGraph graph =
            build_weighted_partitioned_pma_graph(
                dataset.node_size, kPartitionSize, dataset.static_edges,
                dataset.update_edges);
        const WeightedPmaRuntimePlan runtime_plan =
            build_weighted_pma_runtime_plan(
                graph, kMaxCacheSegment,
                grasu::integration::kWeightedPmaRuntimeChannels,
                grasu::integration::kU55cHbmPseudoChannelBytes,
                WeightedPmaChannelPolicy::lane_aware_u55c);
        const unsigned source_internal =
            graph.external_to_internal.at(source_external);

        bool resident_mode = false;
        AlgorithmOracleResult resident_oracle;
        {
            const FinalEdgeMap static_edges =
                build_static_external_edges(dataset);
            resident_mode = std::all_of(
                dataset.update_edges.begin(), dataset.update_edges.end(),
                [&](const WeightedEdgeRecord &update) {
                    if (update.delete_op) return false;
                    if (kConnectedComponents) return true;
                    const auto found = static_edges.find(
                        std::make_pair(update.source, update.destination));
                    return found == static_edges.end() ||
                           update.weight <= found->second;
                });
            resident_oracle = kConnectedComponents
                ? run_connected_components_oracle(
                      dataset.node_size, static_edges, graph, max_supersteps)
                : run_weighted_sssp_oracle(
                      dataset.node_size, static_edges, source_external,
                      max_supersteps);
        }
        const std::vector<unsigned> update_sources =
            update_source_vertices(dataset);
        AlgorithmOracleResult oracle;
        std::size_t final_edge_count = 0;
        {
            const FinalEdgeMap final_edges = build_final_external_edges(dataset);
            final_edge_count = final_edges.size();
            oracle = resident_mode
                ? run_resident_relaxation_oracle(
                      dataset.node_size, final_edges, graph, resident_oracle,
                      update_sources, max_supersteps, kConnectedComponents)
                : (kConnectedComponents
                       ? run_connected_components_oracle(
                             dataset.node_size, final_edges, graph,
                             max_supersteps)
                       : run_weighted_sssp_oracle(
                             dataset.node_size, final_edges, source_external,
                             max_supersteps));
        }
        const std::vector<WeightedPmaPackedShardBuffers> packed =
            pack_weighted_pma_runtime_buffers(graph, runtime_plan);

        if (graph.shards.empty() || graph.shards.size() > 255) {
            fail("ReGraph sharded control ABI requires 1..255 partitions");
        }
        for (std::size_t shard = 0; shard < graph.shards.size(); ++shard) {
            const auto &pma = graph.shards[shard].initial_pma_words;
            if (pma.empty() || pma.size() % kWeightedPmaSegmentSlots != 0 ||
                pma.size() > std::numeric_limits<unsigned>::max() ||
                graph.shards[shard].physical_updates.size() >
                    std::numeric_limits<unsigned>::max()) {
                fail("sharded PMA exceeds the adapter/update control ABI");
            }
        }

        std::cout << kLogPrefix << "_SHARDED_INPUT"
                  << " vertices=" << dataset.node_size
                  << " static_edges=" << dataset.static_edges.size()
                  << " logical_updates=" << dataset.update_edges.size()
                  << " physical_updates=" << graph.physical_internal.size()
                  << " final_edges=" << final_edge_count
                  << " destination_partitions=" << graph.shards.size()
                  << " pma_slots_total=" << total_pma_slots(graph)
                  << " hbm_graph_allocated_bytes="
                  << runtime_plan.total_allocated_bytes
                  << " source_external=" << source_external
                  << " source_internal=" << source_internal
                  << " oracle_supersteps=" << oracle.executed_supersteps
                  << " oracle_converged=" << (oracle.converged ? 1 : 0)
                  << " resident_state="
                  << (resident_mode ? "old_graph_converged" : "cold_fallback")
                  << std::endl;

        if (prepare_only) {
            print_prepare_result(dataset, graph, runtime_plan, oracle,
                                 source_external, source_internal,
                                 max_supersteps);
            return oracle.converged ? EXIT_SUCCESS : EXIT_FAILURE;
        }

        cl::Device device = select_xilinx_device();
        cl_int err = CL_SUCCESS;
        cl::Context context(device, nullptr, nullptr, nullptr, &err);
        check_cl(err, "create context");
        auto make_queue = [&](const std::string &name) {
            cl_int queue_error = CL_SUCCESS;
            cl::CommandQueue queue(
                context, device,
                CL_QUEUE_PROFILING_ENABLE |
                    CL_QUEUE_OUT_OF_ORDER_EXEC_MODE_ENABLE,
                &queue_error);
            check_cl(queue_error, "create " + name);
            return queue;
        };
        cl::CommandQueue transfer_queue = make_queue("transfer queue");
        cl::CommandQueue grasu_queue = make_queue("grasu queue");
        cl::CommandQueue pipeline_queue = make_queue("pipeline queue");

        const std::vector<unsigned char> xclbin =
            read_binary_file(xclbin_path);
        cl::Program::Binaries binaries{{xclbin.data(), xclbin.size()}};
        cl::Program program(context, {device}, binaries, nullptr, &err);
        check_cl(err, "program device");
        auto make_kernel = [&](const std::string &name) {
            cl_int kernel_error = CL_SUCCESS;
            cl::Kernel kernel(program, name.c_str(), &kernel_error);
            check_cl(kernel_error, "create " + name);
            return kernel;
        };

        std::array<cl::Kernel, 4> bin_search{
            make_kernel("bin_search:{bin_search_1}"),
            make_kernel("bin_search:{bin_search_2}"),
            make_kernel("bin_search:{bin_search_3}"),
            make_kernel("bin_search:{bin_search_4}")};
        cl::Kernel dispatch = make_kernel("dispatch:{dispatch_1}");
        cl::Kernel process_cache_1 =
            make_kernel("process_cache:{process_cache_1}");
        cl::Kernel process_cache_2 =
            make_kernel("process_cache:{process_cache_2}");
        cl::Kernel process_ddr_1 =
            make_kernel("process_ddr:{process_ddr_1}");
        cl::Kernel process_ddr_2 =
            make_kernel("process_ddr:{process_ddr_2}");
        cl::Kernel barrier =
            make_kernel("pma_completion_barrier:{pma_completion_barrier_1}");
        std::array<cl::Kernel, 4> adapter{
            make_kernel("pma_to_regraph_adapter:{pma_to_regraph_adapter_1}"),
            make_kernel("pma_to_regraph_adapter:{pma_to_regraph_adapter_2}"),
            make_kernel("pma_to_regraph_adapter:{pma_to_regraph_adapter_3}"),
            make_kernel("pma_to_regraph_adapter:{pma_to_regraph_adapter_4}")};
        std::array<cl::Kernel, 4> lksg{
            make_kernel("lksg_stream:{lksg_stream_1}"),
            make_kernel("lksg_stream:{lksg_stream_2}"),
            make_kernel("lksg_stream:{lksg_stream_3}"),
            make_kernel("lksg_stream:{lksg_stream_4}")};
        cl::Kernel frontend_mux =
            make_kernel("regraph_frontend_mux:{regraph_frontend_mux_1}");
        cl::Kernel apply = make_kernel("kernelApply:{kernelApply_1}");
        cl::Kernel hbm =
            make_kernel("kernelHBMWrapper:{kernelHBMWrapper_1}");

        std::vector<DeviceShard> device_shards(graph.shards.size());
        for (std::size_t shard = 0; shard < graph.shards.size(); ++shard) {
            DeviceShard &device_shard = device_shards[shard];
            const auto &host = packed[shard];
            for (std::size_t lane = 0; lane < 4; ++lane) {
                const unsigned update_bank = static_cast<unsigned>(
                    find_weighted_pma_region(
                        runtime_plan, shard,
                        "update" + std::to_string(lane))
                        .channel);
                const unsigned pma_bank = static_cast<unsigned>(
                    find_weighted_pma_region(
                        runtime_plan, shard, "pma" + std::to_string(lane))
                        .channel);
                device_shard.update_ext[lane] = ext_ptr(update_bank);
                device_shard.pma_ext[lane] = ext_ptr(pma_bank);
                device_shard.update_dev[lane] = make_buffer(
                    context,
                    CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX,
                    host.updates[lane].size() * sizeof(std::uint64_t),
                    &device_shard.update_ext[lane],
                    "shard" + std::to_string(shard) + "_update" +
                        std::to_string(lane));
                device_shard.pma_dev[lane] = make_buffer(
                    context,
                    CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX,
                    host.pma_words[lane].size() * sizeof(std::uint32_t),
                    &device_shard.pma_ext[lane],
                    "shard" + std::to_string(shard) + "_pma" +
                        std::to_string(lane));
                write_device_buffer(
                    transfer_queue, device_shard.update_dev[lane],
                    host.updates[lane].size() * sizeof(std::uint64_t),
                    host.updates[lane].data(),
                    "update" + std::to_string(lane));
                write_device_buffer(
                    transfer_queue, device_shard.pma_dev[lane],
                    host.pma_words[lane].size() * sizeof(std::uint32_t),
                    host.pma_words[lane].data(),
                    "pma" + std::to_string(lane));
            }
            const unsigned row_bank = static_cast<unsigned>(
                find_weighted_pma_region(runtime_plan, shard, "row").channel);
            const unsigned binary_bank = static_cast<unsigned>(
                find_weighted_pma_region(runtime_plan, shard, "binary").channel);
            device_shard.row_ext = ext_ptr(row_bank);
            device_shard.binary_ext = ext_ptr(binary_bank);
            device_shard.row_dev = make_buffer(
                context, CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX,
                host.row_bounds.size() * sizeof(std::uint64_t),
                &device_shard.row_ext,
                "shard" + std::to_string(shard) + "_row");
            device_shard.binary_dev = make_buffer(
                context, CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX,
                host.binary_heads.size() * sizeof(std::uint64_t),
                &device_shard.binary_ext,
                "shard" + std::to_string(shard) + "_binary");
            write_device_buffer(
                transfer_queue, device_shard.row_dev,
                host.row_bounds.size() * sizeof(std::uint64_t),
                host.row_bounds.data(), "row");
            write_device_buffer(
                transfer_queue, device_shard.binary_dev,
                host.binary_heads.size() * sizeof(std::uint64_t),
                host.binary_heads.data(), "binary");
        }
        transfer_queue.finish();

        const unsigned destination_partitions =
            static_cast<unsigned>(graph.shards.size());
        const std::size_t state_capacity =
            static_cast<std::size_t>(destination_partitions) * kPartitionSize;
        AlignedVector<uint32_t> prop_a(state_capacity, 0);
        AlignedVector<uint32_t> prop_b(state_capacity, 0);
        AlignedVector<uint32_t> apply_prop(state_capacity, 0);
        AlignedVector<uint32_t> active_count(1, 0);
        for (std::size_t internal = 0; internal < dataset.node_size; ++internal) {
            const std::size_t external = graph.internal_to_external.at(internal);
            const uint32_t initial_value = resident_mode
                ? resident_oracle.prop.at(kConnectedComponents ? internal
                                                               : external)
                : (kConnectedComponents
                       ? static_cast<uint32_t>(internal) | kActiveMask
                       : kSsspInf);
            prop_a[internal] = initial_value;
            apply_prop[internal] = initial_value;
        }
        if (resident_mode) {
            for (const unsigned external : update_sources) {
                prop_a[graph.external_to_internal.at(external)] |= kActiveMask;
            }
        } else if (!kConnectedComponents) {
            prop_a[source_internal] = kActiveMask;
            apply_prop[source_internal] = kActiveMask;
        }

        cl_mem_ext_ptr_t prop_a0_ext = ext_ptr(23, prop_a.data());
        cl_mem_ext_ptr_t prop_a1_ext = ext_ptr(24, prop_a.data());
        cl_mem_ext_ptr_t prop_b0_ext = ext_ptr(23, prop_b.data());
        cl_mem_ext_ptr_t prop_b1_ext = ext_ptr(24, prop_b.data());
        cl_mem_ext_ptr_t apply_prop_ext = ext_ptr(30, apply_prop.data());
        cl_mem_ext_ptr_t active_count_ext = ext_ptr(30, active_count.data());
        cl::Buffer prop_a0_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            prop_a.size() * sizeof(uint32_t), &prop_a0_ext, "prop_a0");
        cl::Buffer prop_a1_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            prop_a.size() * sizeof(uint32_t), &prop_a1_ext, "prop_a1");
        cl::Buffer prop_b0_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            prop_b.size() * sizeof(uint32_t), &prop_b0_ext, "prop_b0");
        cl::Buffer prop_b1_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            prop_b.size() * sizeof(uint32_t), &prop_b1_ext, "prop_b1");
        cl::Buffer apply_prop_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            apply_prop.size() * sizeof(uint32_t), &apply_prop_ext,
            "apply_prop");
        cl::Buffer active_count_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            active_count.size() * sizeof(uint32_t), &active_count_ext,
            "active_count");
        check_cl(transfer_queue.enqueueMigrateMemObjects(
                     {prop_a0_dev, prop_a1_dev, prop_b0_dev, prop_b1_dev,
                      apply_prop_dev, active_count_dev},
                     0),
                 "migrate initial state buffers");
        transfer_queue.finish();

        Timing timing;
        const auto wall_begin = std::chrono::high_resolution_clock::now();
        std::vector<cl::Event> all_events;
        std::vector<cl::Event> grasu_events;
        std::vector<cl::Event> barrier_events;

        for (std::size_t shard = 0; shard < graph.shards.size(); ++shard) {
            const auto &shard_graph = graph.shards[shard];
            if (shard_graph.physical_updates.empty()) continue;
            DeviceShard &buffers = device_shards[shard];
            const auto &shard_plan = runtime_plan.shards[shard];
            for (std::size_t lane = 0; lane < 4; ++lane) {
                int arg = 0;
                check_cl(bin_search[lane].setArg(arg++, buffers.update_dev[lane]),
                         "set sharded bin_search edges");
                for (int copy = 0; copy < 4; ++copy) {
                    check_cl(bin_search[lane].setArg(arg++, buffers.binary_dev),
                             "set sharded bin_search binary");
                }
                for (int copy = 0; copy < 4; ++copy) {
                    check_cl(bin_search[lane].setArg(arg++, buffers.row_dev),
                             "set sharded bin_search row");
                }
                check_cl(bin_search[lane].setArg(
                             arg++, static_cast<unsigned>(
                                        shard_plan.update_counts[lane])),
                         "set sharded bin_search size");
            }
            check_cl(dispatch.setArg(
                         0, static_cast<unsigned>(
                                shard_graph.physical_updates.size())),
                     "set sharded dispatch size");
            check_cl(process_cache_1.setArg(0, buffers.pma_dev[0]),
                     "set sharded cache0");
            check_cl(process_cache_2.setArg(0, buffers.pma_dev[2]),
                     "set sharded cache1");
            for (int arg = 0; arg < 4; ++arg) {
                check_cl(process_ddr_1.setArg(arg, buffers.pma_dev[1]),
                         "set sharded ddr0");
                check_cl(process_ddr_2.setArg(arg, buffers.pma_dev[3]),
                         "set sharded ddr1");
            }

            std::array<cl::Event, 9> update_events;
            check_cl(grasu_queue.enqueueTask(process_cache_1, nullptr,
                                             &update_events[0]),
                     "enqueue sharded process_cache_1");
            check_cl(grasu_queue.enqueueTask(process_cache_2, nullptr,
                                             &update_events[1]),
                     "enqueue sharded process_cache_2");
            check_cl(grasu_queue.enqueueTask(process_ddr_1, nullptr,
                                             &update_events[2]),
                     "enqueue sharded process_ddr_1");
            check_cl(grasu_queue.enqueueTask(process_ddr_2, nullptr,
                                             &update_events[3]),
                     "enqueue sharded process_ddr_2");
            check_cl(grasu_queue.enqueueTask(dispatch, nullptr,
                                             &update_events[4]),
                     "enqueue sharded dispatch");
            for (std::size_t lane = 0; lane < 4; ++lane) {
                check_cl(grasu_queue.enqueueTask(bin_search[lane], nullptr,
                                                 &update_events[5 + lane]),
                         "enqueue sharded bin_search");
            }
            cl::Event barrier_event;
            check_cl(pipeline_queue.enqueueTask(barrier, nullptr,
                                                &barrier_event),
                     "enqueue sharded completion barrier");
            grasu_queue.finish();
            pipeline_queue.finish();
            grasu_events.insert(grasu_events.end(), update_events.begin(),
                                update_events.end());
            barrier_events.push_back(barrier_event);
        }
        all_events.insert(all_events.end(), grasu_events.begin(),
                          grasu_events.end());
        all_events.insert(all_events.end(), barrier_events.begin(),
                          barrier_events.end());

        std::array<cl::Buffer *, 2> read_props{&prop_a0_dev, &prop_a1_dev};
        std::array<cl::Buffer *, 2> write_props{&prop_b0_dev, &prop_b1_dev};
        AlignedVector<uint32_t> *read_host = &prop_a;
        AlignedVector<uint32_t> *write_host = &prop_b;
        const unsigned num_sparse = 0;
        const unsigned reg = 0;
        std::array<unsigned, 4> worker_partitions{};
        for (unsigned partition = 0; partition < destination_partitions;
             ++partition) {
            ++worker_partitions[partition % kK4Frontends];
        }

        unsigned executed_supersteps = 0;
        bool hardware_converged = false;
        for (unsigned step = 0; step < max_supersteps; ++step) {
            check_cl(hbm.setArg(0, *read_props[0]), "set hbm src1");
            check_cl(hbm.setArg(1, *read_props[1]), "set hbm src2");
            check_cl(hbm.setArg(2, *read_props[0]), "set hbm src3");
            check_cl(hbm.setArg(3, *read_props[1]), "set hbm src4");
            check_cl(hbm.setArg(4, *write_props[0]), "set hbm new1");
            check_cl(hbm.setArg(5, *write_props[1]), "set hbm new2");
            for (std::size_t worker = 0; worker < 4; ++worker) {
                check_cl(hbm.setArg(6 + worker, worker_partitions[worker]),
                         "set hbm worker partition count");
            }
            check_cl(apply.setArg(0, apply_prop_dev), "set apply vertex_prop");
            check_cl(apply.setArg(1, active_count_dev), "set apply active_count");
            check_cl(apply.setArg(2, destination_partitions),
                     "set apply dense partitions");
            check_cl(apply.setArg(3, num_sparse), "set apply sparse partitions");
            check_cl(apply.setArg(4, reg), "set apply reg");

            cl::Event hbm_event;
            cl::Event apply_event;
            check_cl(pipeline_queue.enqueueTask(hbm, nullptr, &hbm_event),
                     "enqueue sharded hbm");
            check_cl(pipeline_queue.enqueueTask(apply, nullptr, &apply_event),
                     "enqueue sharded apply");

            std::vector<cl::Event> adapter_events(destination_partitions);
            std::vector<cl::Event> lksg_events(destination_partitions);
            std::vector<cl::Event> mux_events(destination_partitions);
            std::array<int, 4> previous_partition{{-1, -1, -1, -1}};
            for (unsigned partition = 0; partition < destination_partitions;
                 ++partition) {
                const unsigned worker = partition % kK4Frontends;
                const auto &shard = graph.shards[partition];
                const auto &shard_plan = runtime_plan.shards[partition];
                DeviceShard &buffers = device_shards[partition];
                check_cl(adapter[worker].setArg(0, buffers.pma_dev[0]),
                         "set adapter pma0");
                check_cl(adapter[worker].setArg(1, buffers.pma_dev[1]),
                         "set adapter pma1");
                check_cl(adapter[worker].setArg(2, buffers.pma_dev[2]),
                         "set adapter pma2");
                check_cl(adapter[worker].setArg(3, buffers.pma_dev[3]),
                         "set adapter pma3");
                check_cl(adapter[worker].setArg(4, buffers.row_dev),
                         "set adapter row");
                check_cl(adapter[worker].setArg(
                             5, static_cast<unsigned>(dataset.node_size)),
                         "set adapter nodes");
                check_cl(adapter[worker].setArg(
                             6, static_cast<unsigned>(
                                    shard_plan.pma_slot_count)),
                         "set adapter pma slots");
                check_cl(adapter[worker].setArg(
                             7, static_cast<unsigned>(kMaxCacheSegment)),
                         "set adapter cache segments");
                check_cl(adapter[worker].setArg(8, shard.destination_base),
                         "set adapter destination base");
                check_cl(adapter[worker].setArg(
                             9, static_cast<unsigned>(
                                    shard.destination_vertices)),
                         "set adapter destination vertices");
                check_cl(lksg[worker].setArg(
                             1, static_cast<unsigned>(
                                    shard_plan.pma_slot_count)),
                         "set lksg edge slots");
                check_cl(lksg[worker].setArg(2, 0U),
                         "set lksg compressed groups");
                check_cl(lksg[worker].setArg(3, shard.destination_base),
                         "set lksg destination base");
                check_cl(lksg[worker].setArg(4, true),
                         "set lksg reset");
                check_cl(frontend_mux.setArg(4, worker),
                         "set frontend mux worker");
                check_cl(frontend_mux.setArg(5, kGatherPacketsPerPartition),
                         "set frontend mux packets");

                std::vector<cl::Event> adapter_wait;
                std::vector<cl::Event> lksg_wait;
                if (previous_partition[worker] >= 0) {
                    adapter_wait.push_back(
                        adapter_events[previous_partition[worker]]);
                    lksg_wait.push_back(lksg_events[previous_partition[worker]]);
                }
                check_cl(pipeline_queue.enqueueTask(
                             adapter[worker],
                             adapter_wait.empty() ? nullptr : &adapter_wait,
                             &adapter_events[partition]),
                         "enqueue sharded adapter");
                check_cl(pipeline_queue.enqueueTask(
                             lksg[worker],
                             lksg_wait.empty() ? nullptr : &lksg_wait,
                             &lksg_events[partition]),
                         "enqueue sharded lksg");
                std::vector<cl::Event> mux_wait;
                if (partition != 0) {
                    mux_wait.push_back(mux_events[partition - 1]);
                }
                check_cl(pipeline_queue.enqueueTask(
                             frontend_mux,
                             mux_wait.empty() ? nullptr : &mux_wait,
                             &mux_events[partition]),
                         "enqueue shared frontend mux");
                previous_partition[worker] = static_cast<int>(partition);
            }
            pipeline_queue.finish();

            timing.hbm_ms += event_duration_ms(hbm_event);
            timing.apply_ms += event_duration_ms(apply_event);
            for (const cl::Event &event : adapter_events) {
                timing.adapter_ms += event_duration_ms(event);
            }
            for (const cl::Event &event : lksg_events) {
                timing.lksg_ms += event_duration_ms(event);
            }
            all_events.push_back(hbm_event);
            all_events.push_back(apply_event);
            all_events.insert(all_events.end(), adapter_events.begin(),
                              adapter_events.end());
            all_events.insert(all_events.end(), lksg_events.begin(),
                              lksg_events.end());
            all_events.insert(all_events.end(), mux_events.begin(),
                              mux_events.end());

            const auto readback_begin =
                std::chrono::high_resolution_clock::now();
            check_cl(transfer_queue.enqueueMigrateMemObjects(
                         {active_count_dev}, CL_MIGRATE_MEM_OBJECT_HOST),
                     "migrate active count");
            transfer_queue.finish();
            const auto readback_end =
                std::chrono::high_resolution_clock::now();
            timing.convergence_readback_ms +=
                std::chrono::duration<double, std::milli>(
                    readback_end - readback_begin)
                    .count();
            executed_supersteps = step + 1;
            std::swap(read_props, write_props);
            std::swap(read_host, write_host);
            std::cout << kLogPrefix << "_SHARDED_SUPERSTEP"
                      << " step=" << executed_supersteps
                      << " active_vertices=" << active_count[0]
                      << std::endl;
            if (active_count[0] == 0) {
                hardware_converged = true;
                break;
            }
        }

        timing.grasu_ms = event_union_ms(grasu_events);
        timing.barrier_ms = event_union_ms(barrier_events);
        timing.event_e2e_ms = event_union_ms(all_events);
        check_cl(transfer_queue.enqueueMigrateMemObjects(
                     {*read_props[0]}, CL_MIGRATE_MEM_OBJECT_HOST),
                 "migrate final result");
        transfer_queue.finish();
        const auto wall_end = std::chrono::high_resolution_clock::now();
        timing.setup_inclusive_ms =
            std::chrono::duration<double, std::milli>(wall_end - wall_begin)
                .count();
        timing.wall_ms = timing.setup_inclusive_ms;

        std::size_t mismatch_count = 0;
        for (std::size_t internal = 0; internal < dataset.node_size;
             ++internal) {
            const std::size_t external =
                graph.internal_to_external.at(internal);
            const uint32_t expected =
                oracle.prop.at(kConnectedComponents ? internal : external);
            if ((*read_host)[internal] != expected) {
                if (mismatch_count < 20) {
                    std::cerr << "mismatch external_vertex=" << external
                              << " internal_vertex=" << internal
                              << " expected=0x" << std::hex << expected
                              << " got=0x" << (*read_host)[internal]
                              << std::dec << std::endl;
                }
                ++mismatch_count;
            }
        }

        std::ofstream result_out(result_path);
        if (!result_out) fail("failed to open result file: " + result_path);
        for (std::size_t external = 0; external < dataset.node_size;
             ++external) {
            const std::size_t internal =
                graph.external_to_internal.at(external);
            uint32_t value = sssp_value((*read_host)[internal]);
            if (kConnectedComponents) {
                value = static_cast<uint32_t>(
                    graph.internal_to_external.at(value));
            }
            result_out << external << ' ' << value << '\n';
        }
        if (!result_out) fail("failed while writing result file");

        const bool pass = mismatch_count == 0 && hardware_converged &&
                          oracle.converged;
        std::cout << kLogPrefix << "_SHARDED_TIMING"
                  << " grasu_ms=" << std::fixed << std::setprecision(6)
                  << timing.grasu_ms
                  << " barrier_ms=" << timing.barrier_ms
                  << " adapter_ms=" << timing.adapter_ms
                  << " lksg_ms=" << timing.lksg_ms
                  << " apply_ms=" << timing.apply_ms
                  << " hbm_ms=" << timing.hbm_ms
                  << " event_e2e_ms=" << timing.event_e2e_ms
                  << " convergence_readback_ms="
                  << timing.convergence_readback_ms
                  << " setup_inclusive_ms=" << timing.setup_inclusive_ms
                  << std::endl;
        std::cout << kLogPrefix << "_SHARDED_RESULT"
                  << " status=" << (pass ? "PASS" : "FAIL")
                  << " mismatches=" << mismatch_count
                  << " vertices=" << dataset.node_size
                  << " final_edges=" << final_edge_count
                  << " logical_updates=" << dataset.update_edges.size()
                  << " physical_updates=" << graph.physical_internal.size()
                  << " destination_partitions=" << destination_partitions
                  << " k4_frontends=" << kK4Frontends
                  << " shared_regraph_downstream=1"
                  << " pma_slots_total=" << total_pma_slots(graph)
                  << " processed_edge_slots_per_superstep="
                  << total_pma_slots(graph)
                  << " source_external=" << source_external
                  << " source_internal=" << source_internal
                  << " executed_supersteps=" << executed_supersteps
                  << " hardware_converged="
                  << (hardware_converged ? 1 : 0)
                  << " oracle_supersteps=" << oracle.executed_supersteps
                  << " oracle_converged=" << (oracle.converged ? 1 : 0)
                  << " resident_state="
                  << (resident_mode ? "old_graph_converged" : "cold_fallback")
                  << " conversion_cost=absent"
                  << std::endl;
        return pass ? EXIT_SUCCESS : EXIT_FAILURE;
    } catch (const std::exception &exception) {
        std::cerr << "ERROR: " << exception.what() << std::endl;
        return EXIT_FAILURE;
    }
}
#endif  // GRASU_REGRAPH_SHARDED_K4_NO_MAIN
