#pragma once

#include <chrono>
#include <exception>
#include <functional>
#include <thread>

namespace integration_check {
// Cache C simulation allocates its full URAM image on the host stack. Give only
// these top-level tasks a larger stack; search's finite-FIFO workers keep 1 MiB.
class LargeStackTask {
public:
  explicit LargeStackTask(std::function<void()> function) : function_(function) {
    pthread_attr_t attributes;
    if (pthread_attr_init(&attributes)) throw std::runtime_error("task attributes");
    const int stack = pthread_attr_setstacksize(&attributes, 32 * 1024 * 1024);
    const int start = stack ? stack : pthread_create(&thread_, &attributes, entry, this);
    pthread_attr_destroy(&attributes);
    if (start) throw std::runtime_error("start bounded integration task");
  }
  LargeStackTask(const LargeStackTask&) = delete;
  LargeStackTask& operator=(const LargeStackTask&) = delete;
  ~LargeStackTask() { if (!joined_) pthread_join(thread_, nullptr); }
  void join() {
    if (pthread_join(thread_, nullptr)) throw std::runtime_error("join integration task");
    joined_ = true;
    if (error_) std::rethrow_exception(error_);
  }
private:
  static void* entry(void* value) {
    auto& task = *static_cast<LargeStackTask*>(value);
    try { task.function_(); } catch (...) { task.error_ = std::current_exception(); }
    return nullptr;
  }
  std::function<void()> function_;
  std::exception_ptr error_;
  pthread_t thread_{};
  bool joined_ = false;
};

struct Channels {
  hls::stream<pipe_type_96> search[4], hot[2], cold[2];
  hls::stream<grasu_done_pkt_t> completion[4];
  search_pipeline::HostNetwork external;
  Channels() {
    for (auto& channel : search) external.bind(channel, 2);
    for (auto& channel : hot) external.bind(channel, 2);
    for (auto& channel : cold) external.bind(channel, 2);
    for (auto& channel : completion) external.bind(channel, 1);
  }
};

inline unsigned long execute(State& state,
    const std::array<std::vector<unsigned long>, 4>& updates, unsigned count) {
  Channels channels;
  search_pipeline::HostReport search_reports[4];
  std::vector<std::unique_ptr<LargeStackTask>> consumers;
  for (unsigned half = 0; half < 2; ++half) {
    consumers.emplace_back(new LargeStackTask([&, half] {
      std::this_thread::sleep_for(std::chrono::milliseconds(50));
      process_cache(state.hot[half].memory.data(), channels.hot[half], channels.completion[half]);
    }));
    consumers.emplace_back(new LargeStackTask([&, half] {
      std::this_thread::sleep_for(std::chrono::milliseconds(50));
      auto* first = state.cold[half][0].memory.data();
      auto* second = state.cold[half][1].memory.data();
      process_ddr(first, second, first, second, channels.cold[half], channels.completion[half + 2]);
    }));
  }
  channels.external.launch([&] {
    if (count >= 63)
      for (auto& channel : channels.search)
        while (channel.size() < 2) std::this_thread::yield();
    std::this_thread::sleep_for(std::chrono::milliseconds(25));
    dispatch(count, channels.search[0], channels.search[1], channels.search[2], channels.search[3],
             channels.hot[0], channels.hot[1], channels.cold[0], channels.cold[1]);
  });
  for (unsigned lane = 0; lane < 4; ++lane)
    channels.external.launch([&, lane] {
      const auto* binary = state.binary.data();
      const auto* rows = state.rows.data();
      bin_search(updates[lane].data(), binary, binary, binary, binary,
                 rows, rows, rows, rows, updates[lane].size(), channels.search[lane]);
      search_reports[lane] = search_pipeline::last_host_report();
    });
  for (auto& consumer : consumers) consumer->join();
  for (auto& channel : channels.completion) {
    const auto token = channel.read();
    if (token.data != 1 || !token.last || token.keep != decltype(token.keep)(-1) ||
        token.strb != decltype(token.strb)(-1))
      throw std::runtime_error("integrated completion payload/sidebands");
  }
  channels.external.join();
  unsigned long blocked = 0, search_writes = 0, process_writes = 0;
  const auto& report = search_pipeline::last_host_report();
  if (report.channels.size() != 12) throw std::runtime_error("external FIFO topology");
  for (unsigned i = 0; i < report.channels.size(); ++i) {
    const auto& stats = report.channels[i];
    blocked += stats.blocked_writes;
    if (i < 4) search_writes += stats.writes;
    else if (i < 8) process_writes += stats.writes;
    else if (stats.writes != 1) throw std::runtime_error("completion token count");
  }
  if (search_writes != count || process_writes != count + 4)
    throw std::runtime_error("external update/END conservation");
  if (count >= 63 && !blocked) throw std::runtime_error("backpressure was not exercised");
  for (unsigned lane = 0; lane < 4; ++lane) {
    const auto& internal = search_reports[lane].channels;
    if (internal.size() != 339 || internal[337].capacity != 32 ||
        internal[338].capacity != 32 || internal[337].writes != 2 * updates[lane].size() + 1 ||
        internal[338].writes != internal[337].writes)
      throw std::runtime_error("integrated metadata credit/conservation");
  }
  return blocked;
}
}  // namespace integration_check
