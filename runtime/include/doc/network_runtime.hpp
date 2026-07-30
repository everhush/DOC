#pragma once

#include "doc/placement.hpp"
#include "doc/runtime.hpp"
#include "doc/transport.hpp"

#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace doc {

struct NetworkRuntimeStats {
    std::uint64_t source_epochs = 0;
    std::uint64_t evaluations = 0;
    std::uint64_t publications = 0;
    std::uint64_t equality_cutoffs = 0;
    std::uint64_t transported_values = 0;
    std::uint64_t joins = 0;
    std::uint64_t drains = 0;
    std::uint64_t failures = 0;
};

// A bounded placed-execution witness. Logical values and source authority stay
// in one coordinator process, while every definition receives its premises
// through an actual loopback TCP channel belonging to its assigned resource.
// Resource join, graceful drain, and fail-stop loss change placement only; the
// application graph and source facts are unchanged.
class NetworkPlacedRuntime {
public:
    NetworkPlacedRuntime(Graph graph,
                         std::vector<std::string> resources,
                         CutoffPolicy cutoff_policy = CutoffPolicy::Exact);

    bool update_batch(const std::vector<std::pair<StateId, Value>>& assignments,
                      std::string* error = nullptr);
    bool stabilize(std::string* error = nullptr);
    [[nodiscard]] std::optional<Value> observe(StateId state,
                                                std::string* error = nullptr);

    bool join_resource(std::string resource, std::string* error = nullptr);
    bool drain_resource(const std::string& resource,
                        std::string* error = nullptr);
    bool fail_resource(const std::string& resource,
                       std::string* error = nullptr);

    [[nodiscard]] std::optional<std::string> resource_for(StateId state) const;
    [[nodiscard]] std::size_t resource_count() const;
    [[nodiscard]] std::vector<StateSnapshot> snapshot() const;
    [[nodiscard]] NetworkRuntimeStats stats() const;

private:
    struct Candidate {
        StateId state = 0;
        Value value = 0;
        std::uint64_t source_epoch = 0;
        PlacementToken token;
    };

    [[nodiscard]] std::string role_for(StateId state) const;
    [[nodiscard]] std::optional<StateId> state_for_role(const std::string& role) const;
    [[nodiscard]] std::vector<StateId> ready_frontier_locked() const;
    bool stabilize_locked(std::string* error);
    bool rebalance_locked(std::string* error);
    void activate_failed_region_locked(const std::vector<std::string>& roles);

    Graph graph_;
    CutoffPolicy cutoff_policy_ = CutoffPolicy::Exact;
    mutable std::mutex mutex_;
    std::vector<std::optional<Value>> values_;
    std::vector<std::uint8_t> active_;
    std::uint64_t source_epoch_ = 0;
    PlacementTable placement_;
    std::unordered_map<std::string, std::unique_ptr<LoopbackTcpChannel>> channels_;
    std::unordered_map<std::string, ValueInbox> inboxes_;
    NetworkRuntimeStats stats_;
};

}  // namespace doc
