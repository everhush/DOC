#include "doc/network_runtime.hpp"

#include <algorithm>
#include <chrono>
#include <stdexcept>
#include <unordered_set>

namespace doc {

NetworkPlacedRuntime::NetworkPlacedRuntime(Graph graph,
                                           std::vector<std::string> resources,
                                           CutoffPolicy cutoff_policy)
    : graph_(std::move(graph)),
      cutoff_policy_(cutoff_policy),
      values_(graph_.states.size()),
      active_(graph_.states.size(), 0U) {
    validate_graph(graph_);
    if (resources.empty()) {
        throw std::invalid_argument("placed runtime requires at least one resource");
    }
    std::sort(resources.begin(), resources.end());
    resources.erase(std::unique(resources.begin(), resources.end()), resources.end());
    for (const auto& resource : resources) {
        if (resource.empty() || !placement_.join(resource)) {
            throw std::invalid_argument("placed runtime resource names must be non-empty and unique");
        }
        channels_.emplace(resource, std::make_unique<LoopbackTcpChannel>());
        inboxes_.try_emplace(resource);
    }
    for (StateId state = 0; state < graph_.states.size(); ++state) {
        if (graph_.is_source(state)) {
            values_[state] = graph_.states[state].initial_value;
        } else {
            active_[state] = 1U;
        }
    }
    std::string error;
    if (!rebalance_locked(&error)) {
        throw std::invalid_argument(error);
    }
}

bool NetworkPlacedRuntime::update_batch(
    const std::vector<std::pair<StateId, Value>>& assignments,
    std::string* error) {
    std::lock_guard lock(mutex_);
    std::unordered_set<StateId> seen;
    for (const auto& [state, value] : assignments) {
        (void)value;
        if (state >= graph_.states.size() || !graph_.is_source(state) ||
            !seen.insert(state).second) {
            if (error) {
                *error = "placed source batch is invalid";
            }
            return false;
        }
    }

    std::vector<StateId> changed;
    for (const auto& [state, value] : assignments) {
        const bool proven_equal = values_[state] && *values_[state] == value;
        if (cutoff_policy_ == CutoffPolicy::Exact && proven_equal) {
            continue;
        }
        values_[state] = value;
        changed.push_back(state);
    }
    if (changed.empty()) {
        return true;
    }
    ++source_epoch_;
    ++stats_.source_epochs;
    for (const auto source : changed) {
        for (const auto user : graph_.users[source]) {
            active_[user] = 1U;
        }
    }
    return true;
}

bool NetworkPlacedRuntime::stabilize(std::string* error) {
    std::lock_guard lock(mutex_);
    return stabilize_locked(error);
}

std::optional<Value> NetworkPlacedRuntime::observe(StateId state,
                                                    std::string* error) {
    std::lock_guard lock(mutex_);
    if (state >= graph_.states.size()) {
        if (error) {
            *error = "placed observation names an invalid state";
        }
        return std::nullopt;
    }
    if (!stabilize_locked(error)) {
        return std::nullopt;
    }
    if (!values_[state]) {
        if (error) {
            *error = "placed observation is unavailable after stabilization";
        }
        return std::nullopt;
    }
    return values_[state];
}

bool NetworkPlacedRuntime::join_resource(std::string resource,
                                         std::string* error) {
    std::lock_guard lock(mutex_);
    if (resource.empty() || channels_.contains(resource)) {
        if (error) {
            *error = "joined resource must be non-empty and new";
        }
        return false;
    }
    try {
        auto channel = std::make_unique<LoopbackTcpChannel>();
        if (!placement_.join(resource)) {
            if (error) {
                *error = "placement table rejected joined resource";
            }
            return false;
        }
        channels_.emplace(resource, std::move(channel));
        inboxes_.try_emplace(resource);
        if (!rebalance_locked(error)) {
            channels_.erase(resource);
            inboxes_.erase(resource);
            (void)placement_.fail(resource);
            return false;
        }
        ++stats_.joins;
        return true;
    } catch (const std::exception& exception) {
        if (error) {
            *error = std::string("resource join failed: ") + exception.what();
        }
        return false;
    }
}

bool NetworkPlacedRuntime::drain_resource(const std::string& resource,
                                          std::string* error) {
    std::lock_guard lock(mutex_);
    if (channels_.size() <= 1U || !channels_.contains(resource)) {
        if (error) {
            *error = "cannot drain the absent or final placed resource";
        }
        return false;
    }
    if (!placement_.begin_drain(resource)) {
        if (error) {
            *error = "placement table rejected resource drain";
        }
        return false;
    }
    if (!rebalance_locked(error)) {
        return false;
    }
    if (!placement_.finish_drain(resource)) {
        if (error) {
            *error = "placement table could not finish resource drain";
        }
        return false;
    }
    channels_.erase(resource);
    inboxes_.erase(resource);
    ++stats_.drains;
    return true;
}

bool NetworkPlacedRuntime::fail_resource(const std::string& resource,
                                         std::string* error) {
    std::lock_guard lock(mutex_);
    if (channels_.size() <= 1U || !channels_.contains(resource)) {
        if (error) {
            *error = "cannot fail the absent or final placed resource";
        }
        return false;
    }
    const auto lost_roles = placement_.roles_on_resource(resource);
    if (!placement_.fail(resource)) {
        if (error) {
            *error = "placement table rejected fail-stop loss";
        }
        return false;
    }
    channels_.erase(resource);
    inboxes_.erase(resource);
    activate_failed_region_locked(lost_roles);
    if (!rebalance_locked(error)) {
        return false;
    }
    ++stats_.failures;
    return stabilize_locked(error);
}

std::optional<std::string> NetworkPlacedRuntime::resource_for(StateId state) const {
    std::lock_guard lock(mutex_);
    if (state >= graph_.states.size() || graph_.is_source(state)) {
        return std::nullopt;
    }
    const auto token = placement_.capture(role_for(state));
    return token ? std::optional<std::string>{token->resource} : std::nullopt;
}

std::size_t NetworkPlacedRuntime::resource_count() const {
    std::lock_guard lock(mutex_);
    return channels_.size();
}

std::vector<StateSnapshot> NetworkPlacedRuntime::snapshot() const {
    std::lock_guard lock(mutex_);
    std::vector<StateSnapshot> output;
    output.reserve(graph_.states.size());
    for (StateId state = 0; state < graph_.states.size(); ++state) {
        output.push_back(StateSnapshot{
            graph_.states[state].name,
            graph_.is_source(state),
            active_[state] != 0U,
            values_[state],
        });
    }
    return output;
}

NetworkRuntimeStats NetworkPlacedRuntime::stats() const {
    std::lock_guard lock(mutex_);
    return stats_;
}

std::string NetworkPlacedRuntime::role_for(StateId state) const {
    return std::string("eval:") + graph_.states.at(state).name;
}

std::optional<StateId> NetworkPlacedRuntime::state_for_role(const std::string& role) const {
    constexpr const char* prefix = "eval:";
    if (!role.starts_with(prefix)) {
        return std::nullopt;
    }
    const auto iterator = graph_.names.find(role.substr(5U));
    if (iterator == graph_.names.end() || graph_.is_source(iterator->second)) {
        return std::nullopt;
    }
    return iterator->second;
}

std::vector<StateId> NetworkPlacedRuntime::ready_frontier_locked() const {
    std::vector<std::uint8_t> blocked(graph_.states.size(), 0U);
    std::vector<StateId> ready;
    for (const auto state : graph_.topological_states) {
        if (graph_.is_source(state)) {
            continue;
        }
        bool has_active_ancestor = false;
        for (const auto premise : graph_.states[state].definition->premises) {
            if (graph_.is_derived(premise) &&
                (active_[premise] != 0U || blocked[premise] != 0U)) {
                has_active_ancestor = true;
                break;
            }
        }
        blocked[state] = has_active_ancestor ? 1U : 0U;
        if (active_[state] != 0U && !has_active_ancestor) {
            ready.push_back(state);
        }
    }
    return ready;
}

bool NetworkPlacedRuntime::stabilize_locked(std::string* error) {
    while (std::any_of(active_.begin(), active_.end(), [](std::uint8_t flag) {
        return flag != 0U;
    })) {
        const auto frontier = ready_frontier_locked();
        if (frontier.empty()) {
            if (error) {
                *error = "placed active graph has no ready frontier";
            }
            return false;
        }

        std::vector<Candidate> candidates;
        candidates.reserve(frontier.size());
        try {
            for (const auto state : frontier) {
                const auto role = role_for(state);
                const auto token = placement_.capture(role);
                if (!token || !channels_.contains(token->resource)) {
                    throw std::runtime_error("ready definition has no live placement");
                }
                const auto role_key = placement_role_key(role);
                std::vector<Value> inputs;
                inputs.reserve(graph_.states[state].definition->premises.size());
                for (const auto premise : graph_.states[state].definition->premises) {
                    if (!values_[premise]) {
                        throw std::runtime_error("ready definition has an unavailable premise");
                    }
                    const ValueEnvelope envelope{
                        premise,
                        source_epoch_,
                        role_key,
                        token->generation,
                        *values_[premise],
                    };
                    auto& channel = *channels_.at(token->resource);
                    std::string transport_error;
                    if (!channel.send(envelope, &transport_error)) {
                        throw std::runtime_error(transport_error);
                    }
                    const auto received = channel.receive(
                        std::chrono::milliseconds(2000), &transport_error);
                    if (!received) {
                        throw std::runtime_error(transport_error);
                    }
                    const auto admission = inboxes_.at(token->resource).admit(
                        *received, role_key, token->generation);
                    if (admission != AdmissionResult::Accepted &&
                        admission != AdmissionResult::Duplicate) {
                        throw std::runtime_error("transport admission rejected a current premise");
                    }
                    inputs.push_back(received->value);
                    ++stats_.transported_values;
                }
                const auto value = graph_.states[state].definition->function(inputs);
                candidates.push_back(Candidate{state, value, source_epoch_, *token});
                ++stats_.evaluations;
            }
        } catch (const std::exception& exception) {
            if (error) {
                *error = std::string("placed frontier failed before publication: ") +
                         exception.what();
            }
            return false;
        }

        const auto publication_frontier = ready_frontier_locked();
        std::vector<std::uint8_t> publication_ready(graph_.states.size(), 0U);
        for (const auto state : publication_frontier) {
            publication_ready[state] = 1U;
        }
        for (const auto& candidate : candidates) {
            if (candidate.source_epoch != source_epoch_) {
                if (error) {
                    *error = "placed frontier candidate belongs to a stale source epoch";
                }
                return false;
            }
            if (candidate.state >= graph_.states.size() ||
                active_[candidate.state] == 0U ||
                publication_ready[candidate.state] == 0U) {
                if (error) {
                    *error = "placed frontier candidate is not a current logical-ready obligation";
                }
                return false;
            }
            if (!placement_.may_publish(candidate.token)) {
                if (error) {
                    *error = "placed frontier candidate lost generation authority";
                }
                return false;
            }
        }

        for (const auto state : frontier) {
            active_[state] = 0U;
        }
        for (const auto& candidate : candidates) {
            const bool proven_equal = values_[candidate.state] &&
                                      *values_[candidate.state] == candidate.value;
            if (cutoff_policy_ == CutoffPolicy::Exact && proven_equal) {
                ++stats_.equality_cutoffs;
                continue;
            }
            values_[candidate.state] = candidate.value;
            ++stats_.publications;
            for (const auto user : graph_.users[candidate.state]) {
                active_[user] = 1U;
            }
        }
    }
    return true;
}

bool NetworkPlacedRuntime::rebalance_locked(std::string* error) {
    std::vector<std::string> resources;
    resources.reserve(channels_.size());
    for (const auto& [resource, channel] : channels_) {
        (void)channel;
        if (!placement_.is_draining(resource)) {
            resources.push_back(resource);
        }
    }
    std::sort(resources.begin(), resources.end());
    if (resources.empty()) {
        if (error) {
            *error = "placed runtime has no assignable resource";
        }
        return false;
    }
    std::size_t index = 0;
    for (const auto state : graph_.topological_states) {
        if (!graph_.is_derived(state)) {
            continue;
        }
        const auto& resource = resources[index % resources.size()];
        if (!placement_.assign(role_for(state), resource)) {
            if (error) {
                *error = "placed runtime could not assign a definition role";
            }
            return false;
        }
        ++index;
    }
    return true;
}

void NetworkPlacedRuntime::activate_failed_region_locked(
    const std::vector<std::string>& roles) {
    std::vector<StateId> queue;
    std::vector<std::uint8_t> reached(graph_.states.size(), 0U);
    for (const auto& role : roles) {
        const auto state = state_for_role(role);
        if (!state || reached[*state] != 0U) {
            continue;
        }
        values_[*state] = std::nullopt;
        reached[*state] = 1U;
        queue.push_back(*state);
    }
    for (std::size_t index = 0; index < queue.size(); ++index) {
        const auto state = queue[index];
        active_[state] = 1U;
        for (const auto user : graph_.users[state]) {
            if (reached[user] == 0U) {
                reached[user] = 1U;
                queue.push_back(user);
            }
        }
    }
}

}  // namespace doc
