#include "sharded_event_trace.hpp"

#include <cassert>
#include <sstream>

int main()
{
    using Trace = grasu_regraph::ShardedEventTrace<int>;
    const auto read = [](int event) {
        return std::array<std::uint64_t, 4>{0, 1, 2, 3 + unsigned(event)};
    };
    Trace disabled(false);
    disabled.remember("adapter", 0, 0, 0, 1);
    std::ostringstream empty;
    disabled.emit(empty, [](int) -> std::array<std::uint64_t, 4> {
        throw std::runtime_error("disabled trace must not query events");
    });
    assert(empty.str().empty());

    Trace trace(true);
    trace.remember_round(2, 1, 2, {3, 4, 5, 6, 7}, {3, 4, 5, 6, 7},
                         {3, 4, 5, 6, 7});
    std::ostringstream out;
    trace.emit(out, read);
    const std::string text = out.str();
    assert(text.find("stage=adapter round=2 shard=4 worker=0") != std::string::npos);
    assert(text.find("stage=hbm round=2 shard=-1 worker=-1") != std::string::npos);
    bool rejected = false;
    try {
        trace.remember_round(0, 0, 0, {1}, {}, {});
    } catch (const std::invalid_argument &) {
        rejected = true;
    }
    assert(rejected);
    rejected = false;
    try {
        trace.emit(out, [](int) {
            return std::array<std::uint64_t, 4>{0, 3, 2, 4};
        });
    } catch (const std::runtime_error &) {
        rejected = true;
    }
    assert(rejected);
    unsetenv("GRASU_SHARDED_EVENT_TRACE");
    assert(!grasu_regraph::sharded_event_trace_enabled());
    setenv("GRASU_SHARDED_EVENT_TRACE", "1", 1);
    assert(grasu_regraph::sharded_event_trace_enabled());
    setenv("GRASU_SHARDED_EVENT_TRACE", "invalid", 1);
    rejected = false;
    try {
        grasu_regraph::sharded_event_trace_enabled();
    } catch (const std::invalid_argument &) {
        rejected = true;
    }
    assert(rejected);
}
