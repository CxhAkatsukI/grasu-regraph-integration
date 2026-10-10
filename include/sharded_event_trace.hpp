#ifndef GRASU_REGRAPH_SHARDED_EVENT_TRACE_HPP
#define GRASU_REGRAPH_SHARDED_EVENT_TRACE_HPP

#include <array>
#include <cstdint>
#include <cstdlib>
#include <ostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace grasu_regraph {

inline bool sharded_event_trace_enabled()
{
    const char *value = std::getenv("GRASU_SHARDED_EVENT_TRACE");
    if (!value || std::string(value) == "0") return false;
    if (std::string(value) == "1") return true;
    throw std::invalid_argument("GRASU_SHARDED_EVENT_TRACE must be 0 or 1");
}

// Retain event handles in the timed region; query and print only afterwards.
template <typename Event>
class ShardedEventTrace {
public:
    explicit ShardedEventTrace(bool enabled) : enabled_(enabled) {}

    void remember(const char *stage, unsigned round, int shard, int worker,
                  const Event &event)
    {
        if (enabled_) entries_.push_back({stage, round, shard, worker, event});
    }

    void remember_round(unsigned round, const Event &hbm, const Event &apply,
                        const std::vector<Event> &adapters,
                        const std::vector<Event> &gathers,
                        const std::vector<Event> &muxes)
    {
        if (!enabled_) return;
        if (adapters.size() != gathers.size() || adapters.size() != muxes.size()) {
            throw std::invalid_argument("incomplete sharded event round");
        }
        remember("hbm", round, -1, -1, hbm);
        remember("apply", round, -1, -1, apply);
        for (std::size_t shard = 0; shard < adapters.size(); ++shard) {
            const int partition = static_cast<int>(shard);
            const int worker = partition % 4;
            remember("adapter", round, partition, worker, adapters[shard]);
            remember("gather", round, partition, worker, gathers[shard]);
            remember("mux", round, partition, worker, muxes[shard]);
        }
    }

    template <typename ReadTimestamps>
    void emit(std::ostream &out, ReadTimestamps read) const
    {
        for (const auto &entry : entries_) {
            const auto times = read(entry.event);
            if (!(times[0] <= times[1] && times[1] <= times[2] &&
                  times[2] < times[3])) {
                throw std::runtime_error("invalid OpenCL event timestamps");
            }
            out << "SHARDED_DEVICE_EVENT stage=" << entry.stage
                << " round=" << entry.round << " shard=" << entry.shard
                << " worker=" << entry.worker
                << " queued_ns=" << times[0] << " submit_ns=" << times[1]
                << " start_ns=" << times[2] << " end_ns=" << times[3] << '\n';
        }
    }

private:
    struct Entry {
        const char *stage;
        unsigned round;
        int shard;
        int worker;
        Event event;
    };
    bool enabled_;
    std::vector<Entry> entries_;
};

}  // namespace grasu_regraph
#endif
