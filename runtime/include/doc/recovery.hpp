#pragma once

#include "doc/runtime.hpp"

#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace doc {

// Bounded fail-stop reconstruction profile. Authoritative source facts may be
// kept in memory for worker-loss tests or persisted in an append-only,
// fsync-backed snapshot journal for process-restart tests. Pure derived values
// are reconstructible caches. Public operations serialize on one mutex, so
// authoritative source facts remain fixed throughout each reconstruction interval.
class RecoverableRuntime {
public:
    explicit RecoverableRuntime(Graph graph,
                                CutoffPolicy cutoff_policy = CutoffPolicy::Exact);
    RecoverableRuntime(Graph graph, std::string source_journal_path,
                       CutoffPolicy cutoff_policy = CutoffPolicy::Exact);

    bool stabilize(std::string* error = nullptr);
    bool commit_sources(const std::vector<std::pair<StateId, Value>>& assignments,
                        std::string* error = nullptr);
    [[nodiscard]] std::optional<Value> observe(StateId state,
                                                std::string* error = nullptr);

    // Simulate loss of all volatile derived materialization and reconstruct it
    // from the surviving authoritative source facts. The replacement
    // generation becomes the only generation allowed to publish.
    bool fail_stop_and_reconstruct(std::string* error = nullptr);

    [[nodiscard]] std::uint64_t generation() const;
    [[nodiscard]] bool may_publish(std::uint64_t generation) const;
    [[nodiscard]] std::vector<StateSnapshot> snapshot() const;
    [[nodiscard]] bool file_backed() const noexcept;

private:
    RuntimeSeed source_seed() const;
    bool initialize_journal(std::string* error);
    bool load_journal(std::string* error);
    bool append_source_snapshot(const std::vector<std::optional<Value>>& sources,
                                std::uint64_t epoch,
                                std::string* error) const;

    mutable std::mutex mutex_;
    Graph graph_;
    CutoffPolicy cutoff_policy_ = CutoffPolicy::Exact;
    std::vector<std::optional<Value>> durable_sources_;
    std::unique_ptr<Runtime> runtime_;
    std::uint64_t generation_ = 0;
    std::uint64_t source_journal_epoch_ = 0;
    std::optional<std::string> source_journal_path_;
};

}  // namespace doc
