#include "doc/recurrence.hpp"

#include <limits>
#include <stdexcept>
#include <unordered_set>

namespace doc {

namespace {

RuntimeSeed make_initial_seed(const Graph& graph) {
    RuntimeSeed seed;
    seed.values.resize(graph.states.size());
    seed.active.assign(graph.states.size(), 0U);
    for (StateId state = 0; state < graph.states.size(); ++state) {
        if (graph.is_source(state)) {
            seed.values[state] = graph.states[state].initial_value;
        } else {
            seed.active[state] = 1U;
        }
    }
    return seed;
}

std::vector<Value> complete_values(const Runtime& runtime) {
    const auto states = runtime.snapshot();
    std::vector<Value> values;
    values.reserve(states.size());
    for (const auto& state : states) {
        if (!state.value) {
            throw std::logic_error("stabilized epoch contains an unavailable state");
        }
        values.push_back(*state.value);
    }
    return values;
}

}  // namespace

RecurrentRuntime::RecurrentRuntime(Graph epoch_template,
                                   std::vector<CarryBinding> carry,
                                   std::size_t retained_epochs,
                                   CutoffPolicy cutoff_policy)
    : graph_(std::move(epoch_template)),
      carry_(std::move(carry)),
      retention_limit_(retained_epochs),
      cutoff_policy_(cutoff_policy) {
    validate_graph(graph_);
    std::unordered_set<StateId> next_sources;
    for (const auto& binding : carry_) {
        if (binding.previous_output >= graph_.states.size() ||
            binding.next_source >= graph_.states.size()) {
            throw std::invalid_argument("recurrence carry binding is outside the epoch graph");
        }
        if (!graph_.is_source(binding.next_source)) {
            throw std::invalid_argument("recurrence carry destination must be a source");
        }
        if (!next_sources.insert(binding.next_source).second) {
            throw std::invalid_argument("recurrence carries more than one value into one source");
        }
    }
}

bool RecurrentRuntime::append_initial(std::string* error) {
    try {
        Runtime runtime(graph_, make_initial_seed(graph_), cutoff_policy_);
        if (!runtime.stabilize(error)) {
            return false;
        }
        latest_values_ = complete_values(runtime);
        materialized_through_ = 0U;
        retained_.push_back(EpochSnapshot{0U, latest_values_});
        enforce_retention();
        return true;
    } catch (const std::exception& exception) {
        if (error) {
            *error = std::string("initial recurrence epoch failed: ") + exception.what();
        }
        return false;
    }
}

bool RecurrentRuntime::append_next(std::string* error) {
    if (materialized_through_ == static_cast<std::size_t>(-1)) {
        return append_initial(error);
    }
    try {
        auto seed = make_initial_seed(graph_);
        for (const auto& binding : carry_) {
            seed.values[binding.next_source] = latest_values_.at(binding.previous_output);
        }
        Runtime runtime(graph_, std::move(seed), cutoff_policy_);
        if (!runtime.stabilize(error)) {
            return false;
        }
        latest_values_ = complete_values(runtime);
        if (materialized_through_ == std::numeric_limits<std::size_t>::max()) {
            if (error) {
                *error = "recurrence epoch index overflow";
            }
            return false;
        }
        ++materialized_through_;
        retained_.push_back(EpochSnapshot{materialized_through_, latest_values_});
        enforce_retention();
        return true;
    } catch (const std::exception& exception) {
        if (error) {
            *error = std::string("recurrence epoch failed: ") + exception.what();
        }
        return false;
    }
}

bool RecurrentRuntime::demand_epoch(std::size_t epoch, std::string* error) {
    if (materialized_through_ == static_cast<std::size_t>(-1) && !append_initial(error)) {
        return false;
    }
    while (materialized_through_ < epoch) {
        if (!append_next(error)) {
            return false;
        }
    }
    return true;
}

std::optional<Value> RecurrentRuntime::observe(std::size_t epoch, StateId state,
                                               std::string* error) {
    if (state >= graph_.states.size()) {
        if (error) {
            *error = "recurrence observation names an invalid state";
        }
        return std::nullopt;
    }
    if (!demand_epoch(epoch, error)) {
        return std::nullopt;
    }
    const auto* snapshot = retained(epoch);
    if (snapshot == nullptr) {
        if (error) {
            *error = "requested epoch has been released by the retention policy";
        }
        return std::nullopt;
    }
    return snapshot->values.at(state);
}

std::optional<std::size_t> RecurrentRuntime::run_until(
    StateId state,
    const std::function<bool(Value)>& predicate,
    std::size_t maximum_epoch,
    std::string* error) {
    if (!predicate) {
        if (error) {
            *error = "recurrence stopping predicate is empty";
        }
        return std::nullopt;
    }
    if (state >= graph_.states.size()) {
        if (error) {
            *error = "recurrence stopping predicate names an invalid state";
        }
        return std::nullopt;
    }
    for (std::size_t epoch = 0; epoch <= maximum_epoch; ++epoch) {
        if (!demand_epoch(epoch, error)) {
            return std::nullopt;
        }
        const auto* snapshot = retained(epoch);
        if (snapshot == nullptr) {
            if (error) {
                *error = "stopping scan requires an epoch released by the retention policy";
            }
            return std::nullopt;
        }
        const Value value = snapshot->values.at(state);
        if (predicate(value)) {
            return epoch;
        }
        if (epoch == maximum_epoch) {
            break;
        }
    }
    if (error) {
        *error = "stopping predicate was not satisfied within the demanded prefix";
    }
    return std::nullopt;
}

std::size_t RecurrentRuntime::materialized_through() const noexcept {
    return materialized_through_;
}

std::size_t RecurrentRuntime::first_retained_epoch() const noexcept {
    return retained_.empty() ? 0U : retained_.front().epoch;
}

std::size_t RecurrentRuntime::retained_epoch_count() const noexcept {
    return retained_.size();
}

const Graph& RecurrentRuntime::epoch_template() const noexcept {
    return graph_;
}

void RecurrentRuntime::enforce_retention() {
    if (retention_limit_ == 0U) {
        return;
    }
    while (retained_.size() > retention_limit_) {
        retained_.pop_front();
    }
}

const EpochSnapshot* RecurrentRuntime::retained(std::size_t epoch) const noexcept {
    if (retained_.empty() || epoch < retained_.front().epoch || epoch > retained_.back().epoch) {
        return nullptr;
    }
    const auto offset = epoch - retained_.front().epoch;
    return offset < retained_.size() ? &retained_[offset] : nullptr;
}

}  // namespace doc
