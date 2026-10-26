#pragma once

// Included after the native host's OpenCL/error helpers and DeviceShard.
inline grasu::integration::WeightedPmaRuntimePlan configure_sharded_metadata(
    grasu::integration::WeightedPmaRuntimePlan plan)
{
    const char *policy = std::getenv("GRASU_SHARDED_METADATA_REPLICAS");
    if (policy && std::string(policy) != "1" && std::string(policy) != "4") {
        fail("GRASU_SHARDED_METADATA_REPLICAS must be 1 or 4");
    }
    if (!policy || std::string(policy) == "1") return plan;
    plan = grasu::integration::replicate_weighted_pma_metadata(std::move(plan));
    std::size_t used = 0, replicated = 0;
    for (const auto bytes : plan.channel_load_bytes) used += bytes != 0;
    for (const auto &shard : plan.shards) {
        replicated += grasu::integration::weighted_pma_shard_has_updates(shard);
    }
    std::cout << "SHARDED_METADATA_POLICY replicas=4 updated_shards=" << replicated
              << " used_banks=" << used << " allocated_bytes=" << plan.total_allocated_bytes
              << " placement=" << (used <= 4 ? "fixed_four" : "capacity_lane_aware_23")
              << " selection=capacity_only" << std::endl;
    return plan;
}

inline void allocate_sharded_metadata_replicas(
    cl::Context &context, cl::CommandQueue &queue,
    const grasu::integration::WeightedPmaRuntimePlan &plan, std::size_t shard,
    const grasu::integration::WeightedPmaPackedShardBuffers &host, DeviceShard &device)
{
    const char *policy = std::getenv("GRASU_SHARDED_METADATA_REPLICAS");
    if (!policy || std::string(policy) != "4" ||
        !grasu::integration::weighted_pma_shard_has_updates(plan.shards[shard])) return;
    for (std::size_t lane = 1; lane < 4; ++lane) {
        const auto label = "shard" + std::to_string(shard) + "_replica" + std::to_string(lane);
        device.row_replica_ext[lane - 1] = ext_ptr(static_cast<unsigned>(
            find_weighted_pma_region(plan, shard, "row" + std::to_string(lane)).channel));
        device.binary_replica_ext[lane - 1] = ext_ptr(static_cast<unsigned>(
            find_weighted_pma_region(plan, shard, "binary" + std::to_string(lane)).channel));
        device.row_replica_dev[lane - 1] = make_buffer(
            context, CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX,
            host.row_bounds.size() * sizeof(std::uint64_t), &device.row_replica_ext[lane - 1], label + "_row");
        device.binary_replica_dev[lane - 1] = make_buffer(
            context, CL_MEM_READ_ONLY | CL_MEM_EXT_PTR_XILINX,
            host.binary_heads.size() * sizeof(std::uint64_t), &device.binary_replica_ext[lane - 1], label + "_binary");
        write_device_buffer(queue, device.row_replica_dev[lane - 1],
            host.row_bounds.size() * sizeof(std::uint64_t), host.row_bounds.data(), label + "_row");
        write_device_buffer(queue, device.binary_replica_dev[lane - 1],
            host.binary_heads.size() * sizeof(std::uint64_t), host.binary_heads.data(), label + "_binary");
    }
    device.metadata_replicated = true;
}

inline const cl::Buffer &sharded_search_row(const DeviceShard &shard, std::size_t lane)
{
    return shard.metadata_replicated && lane ? shard.row_replica_dev.at(lane - 1) : shard.row_dev;
}

inline const cl::Buffer &sharded_search_binary(const DeviceShard &shard, std::size_t lane)
{
    return shard.metadata_replicated && lane ? shard.binary_replica_dev.at(lane - 1) : shard.binary_dev;
}

inline void bind_sharded_cache_extent(
    cl::Kernel &kernel,
    const grasu::integration::WeightedPmaShardRuntimePlan &shard,
    std::size_t half, unsigned legacy_arguments)
{
    const unsigned arguments = kernel.getInfo<CL_KERNEL_NUM_ARGS>();
    if (arguments == legacy_arguments) return;
    if (arguments != legacy_arguments + 1) fail("unrecognized process_cache ABI");
    const unsigned extent = grasu::integration::weighted_pma_cache_valid_segments(
        shard, half, GRASU_MAX_CACHE_SEGMENT);
    check_cl(kernel.setArg(legacy_arguments, extent), "set sharded cache valid extent");
}

inline void premigrate_sharded_inputs(
    cl::CommandQueue &queue, const std::vector<DeviceShard> &shards)
{
    const char *policy = std::getenv("GRASU_SHARDED_PREMIGRATE_INPUTS");
    if (policy && std::string(policy) != "0" && std::string(policy) != "1") {
        fail("GRASU_SHARDED_PREMIGRATE_INPUTS must be 0 or 1");
    }
    if (policy && std::string(policy) == "0") return;
    std::vector<cl::Memory> inputs;
    std::size_t bytes = 0;
    for (const auto &shard : shards) {
        for (std::size_t lane = 0; lane < 4; ++lane) {
            inputs.push_back(shard.update_dev[lane]);
            inputs.push_back(shard.pma_dev[lane]);
        }
        inputs.push_back(shard.row_dev);
        inputs.push_back(shard.binary_dev);
        if (shard.metadata_replicated) {
            for (std::size_t lane = 0; lane < 3; ++lane) {
                inputs.push_back(shard.row_replica_dev[lane]);
                inputs.push_back(shard.binary_replica_dev[lane]);
            }
        }
    }
    for (const auto &buffer : inputs) bytes += buffer.getInfo<CL_MEM_SIZE>();
    // This is initial residency, never a post-update overwrite of the PMA.
    const auto begin = std::chrono::steady_clock::now();
    cl::Event event;
    check_cl(queue.enqueueMigrateMemObjects(inputs, 0, nullptr, &event),
             "premigrate initial sharded inputs");
    queue.finish();
    const double wall_ms = std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - begin).count();
    std::cout << "SHARDED_INPUT_RESIDENCY policy=premigrate buffers=" << inputs.size()
              << " bytes=" << bytes << " wall_ms=" << wall_ms
              << " event_ms=" << event_duration_ms(event)
              << " boundary=initial_setup_before_updates" << std::endl;
}
