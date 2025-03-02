#pragma once

#include "doc/runtime.hpp"

#include <cstddef>
#include <deque>
#include <functional>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace doc {

// One target-to-origin authority binding: next_source in epoch t+1 receives
// previous_output from epoch t. Destinations are unique; unbound sources use
// the epoch template's declared source fact.
struct CarryBinding {
    StateId previous_output = 0;
    StateId next_source = 0;
};

struct EpochSnapshot {
    std::size_t epoch = 0;
    std::vector<Value> values;
};

// Demand-driven versioned recurrence. Every materialized epoch is an ordinary
// finite DOC graph; carry edges point strictly from epoch t to epoch t+1.
class RecurrentRuntime {
public:
    RecurrentRuntime(Graph epoch_template,
                     std::vector<CarryBinding> carry,
                     std::size_t retained_epochs = 0,
                     CutoffPolicy cutoff_policy = CutoffPolicy::Exact);

    bool demand_epoch(std::size_t epoch, std::string* error = nullptr);
    [[nodiscard]] std::optional<Value> observe(std::size_t epoch, StateId state,
                                                std::string* error = nullptr);

    [[nodiscard]] std::optional<std::size_t> run_until(
        StateId state,
        const std::function<bool(Value)>& predicate,
        std::size_t maximum_epoch,
        std::string* error = nullptr);

    [[nodiscard]] std::size_t materialized_through() const noexcept;
    [[nodiscard]] std::size_t first_retained_epoch() const noexcept;
    [[nodiscard]] std::size_t retained_epoch_count() const noexcept;
    [[nodiscard]] const Graph& epoch_template() const noexcept;

private:
    bool append_initial(std::string* error);
    bool append_next(std::string* error);
    void enforce_retention();
    [[nodiscard]] const EpochSnapshot* retained(std::size_t epoch) const noexcept;

    Graph graph_;
    std::vector<CarryBinding> carry_;
    std::size_t retention_limit_ = 0;
    CutoffPolicy cutoff_policy_ = CutoffPolicy::Exact;
    std::deque<EpochSnapshot> retained_;
    std::vector<Value> latest_values_;
    std::size_t materialized_through_ = static_cast<std::size_t>(-1);
};

}  // namespace doc
