#include "doc/graph_versions.hpp"

#include <algorithm>
#include <atomic>
#include <limits>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

namespace doc {

namespace {

std::atomic<std::uint64_t> next_versioned_runtime_instance{1U};

std::vector<std::string> premise_names(const Graph& graph, StateId state) {
    std::vector<std::string> names;
    const auto& definition = graph.states.at(state).definition;
    if (!definition) {
        return names;
    }
    names.reserve(definition->premises.size());
    for (const auto premise : definition->premises) {
        names.push_back(graph.states.at(premise).name);
    }
    return names;
}

bool structurally_compatible(const Graph& old_graph, StateId old_state,
                             const Graph& next_graph, StateId next_state) {
    // This executable profile has one declared scalar Value domain and one
    // semantic equality, so direct domain identity is inherent. A multi-domain
    // realization must reject reuse before this check when domains or their
    // semantic equalities differ.
    const auto& old_definition = old_graph.states.at(old_state).definition;
    const auto& next_definition = next_graph.states.at(next_state).definition;
    if (!old_definition || !next_definition || old_definition->semantic_key.empty() ||
        old_definition->semantic_key != next_definition->semantic_key) {
        return false;
    }
    return premise_names(old_graph, old_state) == premise_names(next_graph, next_state);
}

}  // namespace

VersionedRuntime::VersionedRuntime(Graph initial, CutoffPolicy cutoff_policy)
    : cutoff_policy_(cutoff_policy),
      instance_id_(next_versioned_runtime_instance.fetch_add(1U, std::memory_order_relaxed)),
      runtime_(std::make_unique<Runtime>(std::move(initial), cutoff_policy_)) {
    if (instance_id_ == 0U) {
        throw std::overflow_error("versioned runtime instance identifier overflow");
    }
}

bool VersionedRuntime::stabilize(std::string* error) {
    std::lock_guard lock(mutex_);
    return runtime_->stabilize(error);
}

bool VersionedRuntime::update_batch(
    const std::vector<std::pair<std::string, Value>>& assignments,
    std::string* error) {
    std::lock_guard lock(mutex_);
    std::vector<std::pair<StateId, Value>> resolved;
    resolved.reserve(assignments.size());
    for (const auto& [name, value] : assignments) {
        const auto iterator = runtime_->graph().names.find(name);
        if (iterator == runtime_->graph().names.end()) {
            if (error) {
                *error = "source update names a state absent from the current graph version";
            }
            return false;
        }
        resolved.emplace_back(iterator->second, value);
    }
    return runtime_->update_batch(resolved, error);
}

std::optional<Value> VersionedRuntime::observe(const std::string& name,
                                                std::string* error) {
    std::lock_guard lock(mutex_);
    const auto iterator = runtime_->graph().names.find(name);
    if (iterator == runtime_->graph().names.end()) {
        if (error) {
            *error = "observation names a state absent from the current graph version";
        }
        return std::nullopt;
    }
    return runtime_->observe(iterator->second, error);
}

bool VersionedRuntime::commit(Graph next, GraphCommitReport* report,
                              std::string* error) {
    std::lock_guard lock(mutex_);
    try {
        // Validation must precede every read of the candidate's derived
        // indexes. A malformed candidate is rejected without stabilizing or
        // replacing the current version.
        validate_graph(next);
    } catch (const std::exception& exception) {
        if (error) {
            *error = std::string("graph-version candidate is invalid: ") + exception.what();
        }
        return false;
    }
    if (!runtime_->stabilize(error)) {
        return false;
    }

    const Graph old_graph = runtime_->graph();
    const auto old_snapshot = runtime_->snapshot();
    std::unordered_map<std::string, StateId> old_names = old_graph.names;

    RuntimeSeed seed;
    seed.values.resize(next.states.size());
    seed.active.assign(next.states.size(), 0U);
    std::vector<std::uint8_t> affected(next.states.size(), 0U);

    if (generation_ == std::numeric_limits<std::uint64_t>::max()) {
        if (error) {
            *error = "graph-version generation overflow";
        }
        return false;
    }
    GraphCommitReport local;
    local.generation = generation_ + 1U;

    for (const auto state : next.topological_states) {
        const auto& next_state = next.states.at(state);
        const auto old_iterator = old_names.find(next_state.name);
        const bool existed = old_iterator != old_names.end();
        if (!existed) {
            ++local.new_states;
        }

        if (next.is_source(state)) {
            const bool same_source_authority =
                existed && old_graph.is_source(old_iterator->second) &&
                old_snapshot.at(old_iterator->second).value.has_value();
            if (same_source_authority) {
                seed.values[state] = old_snapshot.at(old_iterator->second).value;
                ++local.reused_states;
                affected[state] = 0U;
            } else {
                // A new source, or a stable name that changed from derived to
                // source authority, takes the candidate's declared source fact.
                // Mark it affected so every compatible-looking descendant is
                // repaired from that new authority rather than retaining stale
                // values from the old graph.
                seed.values[state] = next_state.initial_value;
                affected[state] = 1U;
            }
            continue;
        }

        bool premise_affected = false;
        for (const auto premise : next_state.definition->premises) {
            if (affected.at(premise) != 0U) {
                premise_affected = true;
                break;
            }
        }

        bool compatible = false;
        if (existed && old_graph.is_derived(old_iterator->second)) {
            compatible = structurally_compatible(
                old_graph, old_iterator->second, next, state);
            if (old_snapshot.at(old_iterator->second).value) {
                // Retain even affected values so exact cutoff may prove that a
                // topology edit was observationally neutral.
                seed.values[state] = old_snapshot.at(old_iterator->second).value;
            }
        }

        const bool must_repair = !compatible || premise_affected;
        affected[state] = must_repair ? 1U : 0U;
        seed.active[state] = must_repair ? 1U : 0U;
        if (must_repair) {
            ++local.activated_states;
        } else {
            ++local.reused_states;
        }
    }

    for (const auto& old_state : old_graph.states) {
        if (!next.names.contains(old_state.name)) {
            ++local.retired_states;
        }
    }

    try {
        auto candidate = std::make_unique<Runtime>(std::move(next), std::move(seed), cutoff_policy_);
        if (!candidate->stabilize(error)) {
            return false;
        }
        runtime_ = std::move(candidate);
        ++generation_;
        if (report) {
            *report = local;
        }
        return true;
    } catch (const std::exception& exception) {
        if (error) {
            *error = std::string("graph-version commit failed: ") + exception.what();
        }
        return false;
    }
}

GraphVersionToken VersionedRuntime::capture() const {
    std::lock_guard lock(mutex_);
    return GraphVersionToken{instance_id_, generation_};
}

bool VersionedRuntime::may_publish(GraphVersionToken token) const {
    std::lock_guard lock(mutex_);
    return token.instance == instance_id_ && token.generation == generation_;
}

std::uint64_t VersionedRuntime::generation() const {
    std::lock_guard lock(mutex_);
    return generation_;
}

Graph VersionedRuntime::graph_snapshot() const {
    std::lock_guard lock(mutex_);
    return runtime_->graph();
}

std::vector<StateSnapshot> VersionedRuntime::snapshot() const {
    std::lock_guard lock(mutex_);
    return runtime_->snapshot();
}

}  // namespace doc
