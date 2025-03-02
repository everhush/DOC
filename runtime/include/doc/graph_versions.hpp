#pragma once

#include "doc/runtime.hpp"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace doc {

struct GraphVersionToken {
    std::uint64_t instance = 0;
    std::uint64_t generation = 0;
};

struct GraphCommitReport {
    std::uint64_t generation = 0;
    std::size_t reused_states = 0;
    std::size_t activated_states = 0;
    std::size_t new_states = 0;
    std::size_t retired_states = 0;
};

// Immutable topology versions. A new graph is validated and stabilized
// privately, then atomically replaces the prior version. Compatible stable
// regions may retain values; structurally affected regions are conservatively
// reactivated and pass through the ordinary cutoff semantics.
class VersionedRuntime {
public:
    explicit VersionedRuntime(Graph initial,
                              CutoffPolicy cutoff_policy = CutoffPolicy::Exact);

    bool stabilize(std::string* error = nullptr);
    // Cross-version operations resolve stable logical names. Numeric StateId
    // values remain private to one immutable graph snapshot.
    bool update_batch(const std::vector<std::pair<std::string, Value>>& assignments,
                      std::string* error = nullptr);
    [[nodiscard]] std::optional<Value> observe(const std::string& name,
                                                std::string* error = nullptr);

    bool commit(Graph next, GraphCommitReport* report = nullptr,
                std::string* error = nullptr);

    [[nodiscard]] GraphVersionToken capture() const;
    [[nodiscard]] bool may_publish(GraphVersionToken token) const;
    [[nodiscard]] std::uint64_t generation() const;
    [[nodiscard]] Graph graph_snapshot() const;
    [[nodiscard]] std::vector<StateSnapshot> snapshot() const;

private:
    mutable std::mutex mutex_;
    CutoffPolicy cutoff_policy_ = CutoffPolicy::Exact;
    std::uint64_t instance_id_ = 0;
    std::uint64_t generation_ = 0;
    std::unique_ptr<Runtime> runtime_;
};

}  // namespace doc
