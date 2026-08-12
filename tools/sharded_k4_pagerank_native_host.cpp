#define GRASU_REGRAPH_SHARDED_K4_NO_MAIN 1
#include "sharded_k4_native_host.cpp"

#if !defined(GRASU_REGRAPH_FULL_PAGERANK) && \
    !defined(GRASU_REGRAPH_RESIDUAL_PAGERANK)
#error "sharded K4 PageRank host requires a PageRank algorithm macro"
#endif

namespace {

constexpr float kPageRankDamping = 0.85F;
constexpr float kPageRankEpsilon = 1.0e-6F;
constexpr unsigned kFullPageRankRounds = 3;
constexpr unsigned kResidualPageRankMaxRounds = 256;

#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
constexpr const char *kShardedPageRankPrefix =
    "RESIDUAL_PR_PMA_NATIVE_SHARDED";
#else
constexpr const char *kShardedPageRankPrefix =
    "FULL_PR_PMA_NATIVE_SHARDED";
#endif

struct PageRankTiming {
    double update_ms{};
    double source_prepare_ms{};
    double adapter_ms{};
    double lksg_ms{};
    double mux_ms{};
    double apply_ms{};
    double hbm_ms{};
    double device_e2e_ms{};
    double setup_inclusive_ms{};
};

void pagerank_usage(const char *program)
{
    std::cerr << "Usage: " << program
              << " <xclbin> <graph_file> <result_file>\n"
              << "       " << program
              << " --prepare-only <graph_file> <result_file>\n"
              << "       " << program
              << " --update-only <xclbin> <graph_file> <result_file>\n";
}

std::vector<DeviceShard> allocate_page_rank_shards(
    cl::Context &context,
    cl::CommandQueue &transfer_queue,
    const WeightedPartitionedPmaGraph &graph,
    const WeightedPmaRuntimePlan &runtime_plan,
    const std::vector<WeightedPmaPackedShardBuffers> &packed)
{
    std::vector<DeviceShard> device_shards(graph.shards.size());
    for (std::size_t shard = 0; shard < graph.shards.size(); ++shard) {
        DeviceShard &device_shard = device_shards[shard];
        const auto &host = packed[shard];
        for (std::size_t lane = 0; lane < 4; ++lane) {
            const unsigned update_bank = static_cast<unsigned>(
                find_weighted_pma_region(
                    runtime_plan, shard, "update" + std::to_string(lane))
                    .channel);
            const unsigned pma_bank = static_cast<unsigned>(
                find_weighted_pma_region(
                    runtime_plan, shard, "pma" + std::to_string(lane))
                    .channel);
            device_shard.update_ext[lane] = ext_ptr(update_bank);
            device_shard.pma_ext[lane] = ext_ptr(pma_bank);
            device_shard.update_dev[lane] = make_buffer(
                context, CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX,
                host.updates[lane].size() * sizeof(std::uint64_t),
                &device_shard.update_ext[lane],
                "shard" + std::to_string(shard) + "_update" +
                    std::to_string(lane));
            device_shard.pma_dev[lane] = make_buffer(
                context, CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX,
                host.pma_words[lane].size() * sizeof(std::uint32_t),
                &device_shard.pma_ext[lane],
                "shard" + std::to_string(shard) + "_pma" +
                    std::to_string(lane));
            write_device_buffer(
                transfer_queue, device_shard.update_dev[lane],
                host.updates[lane].size() * sizeof(std::uint64_t),
                host.updates[lane].data(), "update" + std::to_string(lane));
            write_device_buffer(
                transfer_queue, device_shard.pma_dev[lane],
                host.pma_words[lane].size() * sizeof(std::uint32_t),
                host.pma_words[lane].data(), "pma" + std::to_string(lane));
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
    return device_shards;
}

}  // namespace

int main(int argc, char **argv)
{
    try {
        const bool prepare_only =
            argc >= 2 && std::string(argv[1]) == "--prepare-only";
        const bool update_only =
            argc >= 2 && std::string(argv[1]) == "--update-only";
        if ((prepare_only && argc != 4) ||
            (update_only && argc != 5) ||
            (!prepare_only && !update_only && argc != 4)) {
            pagerank_usage(argv[0]);
            return EXIT_FAILURE;
        }
        int arg_index = (prepare_only || update_only) ? 2 : 1;
        const std::string xclbin_path = prepare_only ? "" : argv[arg_index++];
        const std::string graph_path = argv[arg_index++];
        const std::string result_path = argv[arg_index++];

        Dataset dataset = read_dataset(graph_path);
        // Keep the PMA builder's transient state disjoint from the two
        // full-graph oracle maps.  This is a host-memory optimization only;
        // graph contents, kernel arguments, and measured device work do not
        // change.
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

        FullPageRankOracleResult warm_oracle;
        if (!update_only) {
            const FinalEdgeMap static_edges =
                build_static_external_edges(dataset);
            warm_oracle = run_full_pagerank_oracle(
                dataset.node_size, static_edges, 128, kPageRankDamping);
        }
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
        ResidualPageRankOracleResult oracle;
#else
        FullPageRankOracleResult oracle;
#endif
        std::size_t final_edge_count = dataset.static_edges.size();
        if (!update_only) {
            const FinalEdgeMap final_edges = build_final_external_edges(dataset);
            final_edge_count = final_edges.size();
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
            oracle = run_residual_pagerank_oracle(
                dataset.node_size, final_edges, warm_oracle.rank,
                kResidualPageRankMaxRounds, kPageRankDamping,
                kPageRankEpsilon);
#else
            oracle = run_full_pagerank_oracle(
                dataset.node_size, final_edges, kFullPageRankRounds,
                kPageRankDamping);
#endif
        }
        const std::vector<WeightedPmaPackedShardBuffers> packed =
            pack_weighted_pma_runtime_buffers(graph, runtime_plan);

        if (graph.shards.empty() || graph.shards.size() > 255) {
            fail("ReGraph sharded PageRank ABI requires 1..255 partitions");
        }
        for (std::size_t shard = 0; shard < graph.shards.size(); ++shard) {
            if (graph.shards[shard].initial_pma_words.empty() ||
                graph.shards[shard].initial_pma_words.size() %
                        kWeightedPmaSegmentSlots !=
                    0 ||
                graph.shards[shard].initial_pma_words.size() >
                    std::numeric_limits<unsigned>::max() ||
                graph.shards[shard].physical_updates.size() >
                    std::numeric_limits<unsigned>::max()) {
                fail("sharded PageRank PMA exceeds the kernel control ABI");
            }
        }

        float oracle_rank_sum = 0.0F;
        for (float rank : oracle.rank) oracle_rank_sum += rank;
        std::cout << kShardedPageRankPrefix << "_INPUT"
                  << " vertices=" << dataset.node_size
                  << " static_edges=" << dataset.static_edges.size()
                  << " logical_updates=" << dataset.update_edges.size()
                  << " physical_updates=" << graph.physical_internal.size()
                  << " final_edges=" << final_edge_count
                  << " destination_partitions=" << graph.shards.size()
                  << " pma_slots_total=" << total_pma_slots(graph)
                  << " hbm_graph_allocated_bytes="
                  << runtime_plan.total_allocated_bytes
                  << " damping=" << kPageRankDamping
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
                  << " epsilon=" << kPageRankEpsilon
                  << " threshold_semantics=direct_per_vertex"
                  << " oracle_propagation_rounds="
                  << (update_only ? 0 : oracle.propagation_rounds)
                  << " oracle_converged=" << (oracle.converged ? 1 : 0)
#else
                  << " rounds=" << kFullPageRankRounds
#endif
                  << std::endl;

        print_shard_update_layout(graph, "GRASU_SHARDED_UPDATE_LAYOUT");

        if (prepare_only) {
            std::cout << kShardedPageRankPrefix << "_PREP"
                      << " status="
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
                      << (oracle.converged ? "PASS" : "FAIL")
#else
                      << "PASS"
#endif
                      << " vertices=" << dataset.node_size
                      << " destination_partitions=" << graph.shards.size()
                      << " pma_slots_total=" << total_pma_slots(graph)
                      << " pma_slots_max_shard="
                      << max_shard_pma_slots(graph)
                      << " rank_sum=" << std::fixed << std::setprecision(7)
                      << oracle_rank_sum
                      << " pma_destination_abi=local_dst19"
                      << " k4_frontends=" << kK4Frontends
                      << " shared_regraph_downstream=1"
                      << " conversion_cost=absent"
                      << std::endl;
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
            return oracle.converged ? EXIT_SUCCESS : EXIT_FAILURE;
#else
            return EXIT_SUCCESS;
#endif
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
        cl::Kernel dispatch =
            make_kernel("dispatch_degree:{dispatch_degree_1}");
        cl::Kernel process_cache_1 =
            make_kernel("process_cache:{process_cache_1}");
        cl::Kernel process_cache_2 =
            make_kernel("process_cache:{process_cache_2}");
        cl::Kernel process_ddr_1 =
            make_kernel("process_ddr:{process_ddr_1}");
        cl::Kernel process_ddr_2 =
            make_kernel("process_ddr:{process_ddr_2}");
        cl::Kernel degree_update =
            make_kernel("grasu_degree_update:{grasu_degree_update_1}");
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
        cl::Kernel apply =
            make_kernel("regraph_pagerank_apply:{regraph_pagerank_apply_1}");
        cl::Kernel source_prepare = make_kernel(
            "regraph_pagerank_source_prepare:{pr_source_1}");
        cl::Kernel hbm =
            make_kernel("kernelHBMWrapper:{kernelHBMWrapper_1}");

        std::vector<DeviceShard> device_shards = allocate_page_rank_shards(
            context, transfer_queue, graph, runtime_plan, packed);
        const unsigned destination_partitions =
            static_cast<unsigned>(graph.shards.size());
        const std::size_t state_capacity =
            static_cast<std::size_t>(destination_partitions) * kPartitionSize;
        const unsigned burst_count =
            static_cast<unsigned>(state_capacity / 16);
        const unsigned vertices = static_cast<unsigned>(dataset.node_size);

        AlignedVector<std::uint32_t> degree(state_capacity, 0);
        for (const WeightedEdgeRecord &edge : dataset.static_edges) {
            ++degree[graph.external_to_internal.at(edge.source)];
        }
        const AlignedVector<std::uint32_t> initial_degree = degree;
        AlignedVector<std::uint32_t> degree_status(16, 0);
        AlignedVector<float> rank(state_capacity, 0.0F);
        for (std::size_t internal = 0; internal < dataset.node_size;
             ++internal) {
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
            const std::size_t external =
                graph.internal_to_external.at(internal);
            rank[internal] = update_only ? 0.0F
                                         : warm_oracle.rank.at(external);
#else
            rank[internal] = 1.0F / static_cast<float>(dataset.node_size);
#endif
        }
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
        AlignedVector<float> residual(state_capacity, 0.0F);
#endif
        AlignedVector<std::uint32_t> round_stats(16, 0);
        AlignedVector<float> source_a(state_capacity, 0.0F);
        AlignedVector<float> source_b(state_capacity, 0.0F);

        cl_mem_ext_ptr_t degree_ext = ext_ptr(27, degree.data());
        cl_mem_ext_ptr_t degree_status_ext =
            ext_ptr(27, degree_status.data());
        cl_mem_ext_ptr_t rank_ext = ext_ptr(25, rank.data());
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
        cl_mem_ext_ptr_t residual_ext = ext_ptr(26, residual.data());
#endif
        cl_mem_ext_ptr_t stats_ext = ext_ptr(27, round_stats.data());
        cl_mem_ext_ptr_t source_a0_ext = ext_ptr(23, source_a.data());
        cl_mem_ext_ptr_t source_a1_ext = ext_ptr(24, source_a.data());
        cl_mem_ext_ptr_t source_b0_ext = ext_ptr(23, source_b.data());
        cl_mem_ext_ptr_t source_b1_ext = ext_ptr(24, source_b.data());
        cl::Buffer degree_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            degree.size() * sizeof(std::uint32_t), &degree_ext, "out_degree");
        cl::Buffer degree_status_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            degree_status.size() * sizeof(std::uint32_t), &degree_status_ext,
            "degree_status");
        cl::Buffer rank_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            rank.size() * sizeof(float), &rank_ext, "rank_state");
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
        cl::Buffer residual_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            residual.size() * sizeof(float), &residual_ext, "residual_state");
#endif
        cl::Buffer stats_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            round_stats.size() * sizeof(std::uint32_t), &stats_ext,
            "round_stats");
        cl::Buffer source_a0_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            source_a.size() * sizeof(float), &source_a0_ext, "source_a0");
        cl::Buffer source_a1_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            source_a.size() * sizeof(float), &source_a1_ext, "source_a1");
        cl::Buffer source_b0_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            source_b.size() * sizeof(float), &source_b0_ext, "source_b0");
        cl::Buffer source_b1_dev = make_buffer(
            context,
            CL_MEM_READ_WRITE | CL_MEM_EXT_PTR_XILINX | CL_MEM_USE_HOST_PTR,
            source_b.size() * sizeof(float), &source_b1_ext, "source_b1");
        std::vector<cl::Memory> state_memories{
            degree_dev, degree_status_dev, rank_dev, stats_dev,
            source_a0_dev, source_a1_dev, source_b0_dev, source_b1_dev};
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
        state_memories.push_back(residual_dev);
#endif
        check_cl(transfer_queue.enqueueMigrateMemObjects(state_memories, 0),
                 "migrate PageRank state");
        transfer_queue.finish();

        PageRankTiming timing;
        const auto wall_begin = std::chrono::high_resolution_clock::now();
        std::vector<cl::Event> all_events;
        std::vector<cl::Event> update_events;
        const unsigned update_repeats = update_repeat_count();
        std::cout << "GRASU_SHARDED_UPDATE_REPEAT_CONFIG repeats="
                  << update_repeats
                  << " restore_pma_between_repeats=1 restore_degree=1"
                  << std::endl;

        for (unsigned repeat = 0; repeat < update_repeats; ++repeat) {
          if (repeat != 0) {
            restore_device_shard_pma(transfer_queue, packed, device_shards);
            std::fill(degree_status.begin(), degree_status.end(), 0);
            write_device_buffer(
                transfer_queue, degree_dev,
                initial_degree.size() * sizeof(std::uint32_t),
                initial_degree.data(),
                "restore_degree");
            write_device_buffer(
                transfer_queue, degree_status_dev,
                degree_status.size() * sizeof(std::uint32_t),
                degree_status.data(), "restore_degree_status");
            transfer_queue.finish();
          }
          std::vector<cl::Event> repeat_update_events;
          cl_ulong previous_update_shard_end = 0;
          const bool final_repeat = repeat + 1 == update_repeats;
          const char *event_prefix = final_repeat
              ? "GRASU_SHARDED_UPDATE_EVENTS"
              : "GRASU_SHARDED_UPDATE_DIAGNOSTIC_EVENTS";

          for (std::size_t shard = 0; shard < graph.shards.size(); ++shard) {
            const auto &shard_graph = graph.shards[shard];
            if (shard_graph.physical_updates.empty()) continue;
            DeviceShard &buffers = device_shards[shard];
            const auto &shard_plan = runtime_plan.shards[shard];
            for (std::size_t lane = 0; lane < 4; ++lane) {
                int arg = 0;
                check_cl(bin_search[lane].setArg(
                             arg++, buffers.update_dev[lane]),
                         "set PageRank bin_search edges");
                for (int copy = 0; copy < 4; ++copy) {
                    check_cl(bin_search[lane].setArg(
                                 arg++, buffers.binary_dev),
                             "set PageRank bin_search binary");
                }
                for (int copy = 0; copy < 4; ++copy) {
                    check_cl(bin_search[lane].setArg(arg++, buffers.row_dev),
                             "set PageRank bin_search row");
                }
                check_cl(bin_search[lane].setArg(
                             arg++, static_cast<unsigned>(
                                        shard_plan.update_counts[lane])),
                         "set PageRank bin_search size");
            }
            const unsigned physical_updates = static_cast<unsigned>(
                shard_graph.physical_updates.size());
            check_cl(dispatch.setArg(0, physical_updates),
                     "set PageRank dispatch size");
            check_cl(process_cache_1.setArg(0, buffers.pma_dev[0]),
                     "set PageRank cache0");
            check_cl(process_cache_2.setArg(0, buffers.pma_dev[2]),
                     "set PageRank cache1");
            for (int arg = 0; arg < 4; ++arg) {
                check_cl(process_ddr_1.setArg(arg, buffers.pma_dev[1]),
                         "set PageRank ddr0");
                check_cl(process_ddr_2.setArg(arg, buffers.pma_dev[3]),
                         "set PageRank ddr1");
            }
            check_cl(degree_update.setArg(0, sizeof(cl_mem), nullptr),
                     "set connected degree stream");
            check_cl(degree_update.setArg(1, degree_dev),
                     "set degree state");
            check_cl(degree_update.setArg(2, degree_status_dev),
                     "set degree status");
            check_cl(degree_update.setArg(3, vertices),
                     "set degree vertices");
            check_cl(degree_update.setArg(4, physical_updates),
                     "set degree update count");

            std::array<cl::Event, 10> shard_events;
            check_cl(grasu_queue.enqueueTask(
                         process_cache_1, nullptr, &shard_events[0]),
                     "enqueue PageRank cache0");
            check_cl(grasu_queue.enqueueTask(
                         process_cache_2, nullptr, &shard_events[1]),
                     "enqueue PageRank cache1");
            check_cl(grasu_queue.enqueueTask(
                         process_ddr_1, nullptr, &shard_events[2]),
                     "enqueue PageRank ddr0");
            check_cl(grasu_queue.enqueueTask(
                         process_ddr_2, nullptr, &shard_events[3]),
                     "enqueue PageRank ddr1");
            check_cl(grasu_queue.enqueueTask(
                         degree_update, nullptr, &shard_events[4]),
                     "enqueue PageRank degree update");
            check_cl(grasu_queue.enqueueTask(
                         dispatch, nullptr, &shard_events[5]),
                     "enqueue PageRank dispatch");
            for (std::size_t lane = 0; lane < 4; ++lane) {
                check_cl(grasu_queue.enqueueTask(
                             bin_search[lane], nullptr,
                             &shard_events[6 + lane]),
                         "enqueue PageRank bin_search");
            }
            grasu_queue.finish();
            previous_update_shard_end = print_shard_update_events(
                event_prefix, shard, shard_events,
                std::array<const char *, 10>{
                    "cache0", "cache1", "ddr0", "ddr1", "degree",
                    "dispatch", "search0", "search1", "search2",
                    "search3"},
                previous_update_shard_end);
            repeat_update_events.insert(repeat_update_events.end(),
                                        shard_events.begin(),
                                        shard_events.end());
            check_cl(transfer_queue.enqueueMigrateMemObjects(
                         {degree_status_dev}, CL_MIGRATE_MEM_OBJECT_HOST),
                     "read PageRank degree status");
            transfer_queue.finish();
            if (degree_status[0] != 0 ||
                degree_status[1] != physical_updates) {
                fail("device degree update failed for shard " +
                     std::to_string(shard));
            }
          }
          std::cout << "GRASU_SHARDED_UPDATE_REPEAT repeat=" << repeat
                    << " final=" << (final_repeat ? 1 : 0)
                    << " update_ms=" << event_union_ms(repeat_update_events)
                    << std::endl;
          if (final_repeat) {
            update_events = std::move(repeat_update_events);
          }
        }
        timing.update_ms = event_union_ms(update_events);
        all_events.insert(all_events.end(), update_events.begin(),
                          update_events.end());

        if (update_only) {
            const PmaUpdateValidation pma_validation =
                validate_device_pma_updates(
                    transfer_queue, graph, kMaxCacheSegment, device_shards);
            std::map<std::uint32_t, std::uint32_t> expected_degree;
            for (const auto &shard : graph.shards) {
                for (const std::uint64_t update : shard.physical_updates) {
                    const std::uint32_t source = static_cast<std::uint32_t>(
                        (update >> 32) & 0x7fffffffULL);
                    auto [entry, inserted] = expected_degree.try_emplace(
                        source, initial_degree.at(source));
                    if ((update &
                         grasu::integration::kWeightedPmaDelete) != 0) {
                        if (entry->second == 0) {
                            fail("update-only expected degree underflow");
                        }
                        --entry->second;
                    } else {
                        ++entry->second;
                    }
                }
            }
            std::size_t degree_mismatches = 0;
            for (const auto &[source, expected] : expected_degree) {
                std::uint32_t actual = 0;
                check_cl(transfer_queue.enqueueReadBuffer(
                             degree_dev, CL_TRUE,
                             source * sizeof(std::uint32_t),
                             sizeof(actual), &actual),
                         "read touched degree");
                if (actual != expected) {
                    if (degree_mismatches < 20) {
                        std::cerr << "degree update mismatch source=" << source
                                  << " expected=" << expected
                                  << " actual=" << actual << std::endl;
                    }
                    ++degree_mismatches;
                }
            }
            const bool pass = pma_validation.mismatches == 0 &&
                              degree_mismatches == 0;
            std::ofstream result_out(result_path);
            if (!result_out) {
                fail("failed to open update-only result file: " + result_path);
            }
            result_out << "status=" << (pass ? "PASS" : "FAIL")
                       << " touched_segments="
                       << pma_validation.touched_segments
                       << " checked_words=" << pma_validation.checked_words
                       << " pma_mismatches=" << pma_validation.mismatches
                       << " degree_sources=" << expected_degree.size()
                       << " degree_mismatches=" << degree_mismatches << '\n';
            std::cout << "GRASU_SHARDED_UPDATE_ONLY_RESULT"
                      << " status=" << (pass ? "PASS" : "FAIL")
                      << " algorithm=" << kShardedPageRankPrefix
                      << " update_ms=" << timing.update_ms
                      << " touched_segments="
                      << pma_validation.touched_segments
                      << " checked_words=" << pma_validation.checked_words
                      << " pma_mismatches=" << pma_validation.mismatches
                      << " degree_sources=" << expected_degree.size()
                      << " degree_mismatches=" << degree_mismatches
                      << " repeats=" << update_repeats
                      << " measurement_window=same_process_update_events"
                      << " first_repeat=cold_diagnostic"
                      << " conversion_cost=absent" << std::endl;
            return pass ? EXIT_SUCCESS : EXIT_FAILURE;
        }

        int source_arg = 0;
        check_cl(source_prepare.setArg(source_arg++, rank_dev),
                 "set source rank");
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
        check_cl(source_prepare.setArg(source_arg++, residual_dev),
                 "set source residual");
#endif
        check_cl(source_prepare.setArg(source_arg++, degree_dev),
                 "set source degree");
        check_cl(source_prepare.setArg(source_arg++, source_a0_dev),
                 "set source mirror0");
        check_cl(source_prepare.setArg(source_arg++, source_a1_dev),
                 "set source mirror1");
        check_cl(source_prepare.setArg(source_arg++, stats_dev),
                 "set source stats");
        check_cl(source_prepare.setArg(source_arg++, burst_count),
                 "set source burst count");
        check_cl(source_prepare.setArg(source_arg++, vertices),
                 "set source vertices");
        check_cl(source_prepare.setArg(source_arg++, kPageRankDamping),
                 "set source damping");
        check_cl(source_prepare.setArg(source_arg++, kPageRankEpsilon),
                 "set source epsilon");
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
        check_cl(source_prepare.setArg(source_arg++, true),
                 "set source correction mode");
#endif
        cl::Event source_event;
        check_cl(pipeline_queue.enqueueTask(
                     source_prepare, nullptr, &source_event),
                 "enqueue PageRank source prepare");
        pipeline_queue.finish();
        timing.source_prepare_ms = event_duration_ms(source_event);
        all_events.push_back(source_event);
        check_cl(transfer_queue.enqueueMigrateMemObjects(
                     {stats_dev}, CL_MIGRATE_MEM_OBJECT_HOST),
                 "read PageRank source stats");
        transfer_queue.finish();
        if (round_stats[0] != 0) {
            fail("PageRank source preparation exceeded state capacity");
        }
        float dangling = word_to_float(round_stats[3]);

        std::array<cl::Buffer *, 2> current_source{
            &source_a0_dev, &source_a1_dev};
        std::array<cl::Buffer *, 2> next_source{
            &source_b0_dev, &source_b1_dev};
        std::array<unsigned, 4> worker_partitions{};
        for (unsigned partition = 0; partition < destination_partitions;
             ++partition) {
            ++worker_partitions[partition % kK4Frontends];
        }
        const float base =
            (1.0F - kPageRankDamping) / static_cast<float>(vertices);
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
        const unsigned execution_limit = kResidualPageRankMaxRounds + 1;
        bool hardware_converged = false;
        unsigned executed_propagation_rounds = 0;
#else
        const unsigned execution_limit = kFullPageRankRounds;
#endif
        unsigned pipeline_executions = 0;
        for (unsigned round = 0; round < execution_limit; ++round) {
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
            const bool correction_mode = round == 0;
#endif
            check_cl(hbm.setArg(0, *current_source[0]), "set hbm src1");
            check_cl(hbm.setArg(1, *current_source[1]), "set hbm src2");
            check_cl(hbm.setArg(2, *current_source[0]), "set hbm src3");
            check_cl(hbm.setArg(3, *current_source[1]), "set hbm src4");
            check_cl(hbm.setArg(4, *next_source[0]), "set hbm next1");
            check_cl(hbm.setArg(5, *next_source[1]), "set hbm next2");
            for (std::size_t worker = 0; worker < kK4Frontends; ++worker) {
                check_cl(hbm.setArg(6 + worker, worker_partitions[worker]),
                         "set hbm worker partition count");
            }
            int apply_arg = 0;
            check_cl(apply.setArg(apply_arg++, rank_dev), "set apply rank");
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
            check_cl(apply.setArg(apply_arg++, residual_dev),
                     "set apply residual");
#endif
            check_cl(apply.setArg(apply_arg++, degree_dev),
                     "set apply degree");
            check_cl(apply.setArg(apply_arg++, stats_dev),
                     "set apply stats");
            check_cl(apply.setArg(apply_arg++, burst_count),
                     "set apply bursts");
            check_cl(apply.setArg(apply_arg++, vertices),
                     "set apply vertices");
            check_cl(apply.setArg(apply_arg++, kPageRankDamping),
                     "set apply damping");
            check_cl(apply.setArg(apply_arg++, kPageRankEpsilon),
                     "set apply epsilon");
            check_cl(apply.setArg(apply_arg++, base), "set apply base");
            check_cl(apply.setArg(
                         apply_arg++, kPageRankDamping * dangling /
                                          static_cast<float>(vertices)),
                     "set apply dangling share");
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
            check_cl(apply.setArg(apply_arg++, correction_mode),
                     "set apply correction mode");
#endif

            cl::Event hbm_event;
            cl::Event apply_event;
            check_cl(pipeline_queue.enqueueTask(hbm, nullptr, &hbm_event),
                     "enqueue sharded PageRank hbm");
            check_cl(pipeline_queue.enqueueTask(apply, nullptr, &apply_event),
                     "enqueue sharded PageRank apply");
            std::vector<cl::Event> adapter_events(destination_partitions);
            std::vector<cl::Event> lksg_events(destination_partitions);
            std::vector<cl::Event> mux_events(destination_partitions);
            std::array<int, 4> previous_partition{{-1, -1, -1, -1}};
            for (unsigned partition = 0;
                 partition < destination_partitions; ++partition) {
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
                check_cl(adapter[worker].setArg(5, vertices),
                         "set adapter vertices");
                check_cl(adapter[worker].setArg(
                             6, static_cast<unsigned>(
                                    shard_plan.pma_slot_count)),
                         "set adapter slots");
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
                         "set lksg slots");
                check_cl(lksg[worker].setArg(2, 0U),
                         "set lksg compressed groups");
                check_cl(lksg[worker].setArg(3, shard.destination_base),
                         "set lksg destination base");
                check_cl(lksg[worker].setArg(4, true), "set lksg reset");
                check_cl(frontend_mux.setArg(4, worker),
                         "set frontend mux worker");
                check_cl(frontend_mux.setArg(5, kGatherPacketsPerPartition),
                         "set frontend mux packets");

                std::vector<cl::Event> adapter_wait;
                std::vector<cl::Event> lksg_wait;
                if (previous_partition[worker] >= 0) {
                    adapter_wait.push_back(
                        adapter_events[previous_partition[worker]]);
                    lksg_wait.push_back(
                        lksg_events[previous_partition[worker]]);
                }
                check_cl(pipeline_queue.enqueueTask(
                             adapter[worker],
                             adapter_wait.empty() ? nullptr : &adapter_wait,
                             &adapter_events[partition]),
                         "enqueue PageRank adapter");
                check_cl(pipeline_queue.enqueueTask(
                             lksg[worker],
                             lksg_wait.empty() ? nullptr : &lksg_wait,
                             &lksg_events[partition]),
                         "enqueue PageRank lksg");
                std::vector<cl::Event> mux_wait;
                if (partition != 0) {
                    mux_wait.push_back(mux_events[partition - 1]);
                }
                check_cl(pipeline_queue.enqueueTask(
                             frontend_mux,
                             mux_wait.empty() ? nullptr : &mux_wait,
                             &mux_events[partition]),
                         "enqueue PageRank frontend mux");
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
            for (const cl::Event &event : mux_events) {
                timing.mux_ms += event_duration_ms(event);
            }
            all_events.push_back(hbm_event);
            all_events.push_back(apply_event);
            all_events.insert(all_events.end(), adapter_events.begin(),
                              adapter_events.end());
            all_events.insert(all_events.end(), lksg_events.begin(),
                              lksg_events.end());
            all_events.insert(all_events.end(), mux_events.begin(),
                              mux_events.end());

            check_cl(transfer_queue.enqueueMigrateMemObjects(
                         {stats_dev}, CL_MIGRATE_MEM_OBJECT_HOST),
                     "read PageRank round stats");
            transfer_queue.finish();
            if (round_stats[0] != 0 || round_stats[4] != vertices) {
                fail("PageRank apply status failed at execution " +
                     std::to_string(round + 1));
            }
            pipeline_executions = round + 1;
            dangling = word_to_float(round_stats[3]);
            std::swap(current_source, next_source);
            std::cout << kShardedPageRankPrefix << "_ROUND"
                      << " round=" << (round + 1)
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
                      << " phase="
                      << (correction_mode ? "correction" : "propagation")
#endif
                      << " l1_error=" << word_to_float(round_stats[2])
                      << " dangling=" << dangling
                      << " active_vertices=" << round_stats[1]
                      << std::endl;
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
            if (!correction_mode) executed_propagation_rounds = round;
            if (round_stats[1] == 0) {
                hardware_converged = true;
                break;
            }
#endif
        }

        std::vector<cl::Memory> final_memories{rank_dev, degree_dev};
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
        final_memories.push_back(residual_dev);
#endif
        check_cl(transfer_queue.enqueueMigrateMemObjects(
                     final_memories, CL_MIGRATE_MEM_OBJECT_HOST),
                 "read final sharded PageRank state");
        transfer_queue.finish();
        const auto wall_end = std::chrono::high_resolution_clock::now();
        timing.device_e2e_ms = event_union_ms(all_events);
        timing.setup_inclusive_ms =
            std::chrono::duration<double, std::milli>(wall_end - wall_begin)
                .count();

        std::size_t rank_mismatches = 0;
        std::size_t degree_mismatches = 0;
        float max_abs_error = 0.0F;
        for (std::size_t internal = 0; internal < dataset.node_size;
             ++internal) {
            const std::size_t external =
                graph.internal_to_external.at(internal);
            const float expected = oracle.rank.at(external);
            const float actual = rank[internal];
            const float error = std::abs(actual - expected);
            max_abs_error = std::max(max_abs_error, error);
            if (error > 1.0e-4F + 1.0e-3F * std::abs(expected)) {
                if (rank_mismatches < 20) {
                    std::cerr << "rank mismatch external=" << external
                              << " expected=" << expected
                              << " actual=" << actual << std::endl;
                }
                ++rank_mismatches;
            }
            if (degree[internal] != oracle.out_degree.at(external)) {
                ++degree_mismatches;
            }
        }

        std::ofstream result_out(result_path);
        if (!result_out) fail("failed to open result file: " + result_path);
        result_out << std::setprecision(9);
        for (std::size_t external = 0; external < dataset.node_size;
             ++external) {
            const std::size_t internal =
                graph.external_to_internal.at(external);
            result_out << external << ' ' << rank[internal] << '\n';
        }
        if (!result_out) fail("failed while writing PageRank result");

        bool pass = rank_mismatches == 0 && degree_mismatches == 0;
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
        pass = pass && hardware_converged && oracle.converged;
#endif
        std::cout << kShardedPageRankPrefix << "_TIMING"
                  << " update_ms=" << std::fixed << std::setprecision(6)
                  << timing.update_ms
                  << " source_prepare_ms=" << timing.source_prepare_ms
                  << " adapter_ms=" << timing.adapter_ms
                  << " lksg_ms=" << timing.lksg_ms
                  << " mux_ms=" << timing.mux_ms
                  << " apply_ms=" << timing.apply_ms
                  << " hbm_ms=" << timing.hbm_ms
                  << " device_e2e_ms=" << timing.device_e2e_ms
                  << " setup_inclusive_ms=" << timing.setup_inclusive_ms
                  << std::endl;
        std::cout << kShardedPageRankPrefix << "_RESULT"
                  << " status=" << (pass ? "PASS" : "FAIL")
                  << " rank_mismatches=" << rank_mismatches
                  << " degree_mismatches=" << degree_mismatches
                  << " max_abs_error=" << max_abs_error
                  << " pipeline_executions=" << pipeline_executions
#ifdef GRASU_REGRAPH_RESIDUAL_PAGERANK
                  << " propagation_rounds="
                  << executed_propagation_rounds
                  << " hardware_converged="
                  << (hardware_converged ? 1 : 0)
                  << " oracle_propagation_rounds="
                  << oracle.propagation_rounds
                  << " oracle_converged=" << (oracle.converged ? 1 : 0)
                  << " epsilon=" << kPageRankEpsilon
                  << " threshold_semantics=direct_per_vertex"
#else
                  << " rounds=" << kFullPageRankRounds
#endif
                  << " vertices=" << dataset.node_size
                  << " final_edges=" << final_edge_count
                  << " logical_updates=" << dataset.update_edges.size()
                  << " physical_updates=" << graph.physical_internal.size()
                  << " destination_partitions=" << destination_partitions
                  << " k4_frontends=" << kK4Frontends
                  << " shared_regraph_downstream=1"
                  << " pma_slots_total=" << total_pma_slots(graph)
                  << " processed_edge_slots_per_execution="
                  << total_pma_slots(graph)
                  << " resident_state=old_graph_converged"
                  << " conversion_cost=absent"
                  << std::endl;
        return pass ? EXIT_SUCCESS : EXIT_FAILURE;
    } catch (const std::exception &exception) {
        std::cerr << "ERROR: " << exception.what() << std::endl;
        return EXIT_FAILURE;
    }
}
