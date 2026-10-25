#pragma once

// Included after the native host's OpenCL/error helpers and DeviceShard.
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
