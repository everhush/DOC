#include "doc/runtime.hpp"

#include <algorithm>
#include <cerrno>
#include <charconv>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <limits>
#include <queue>
#include <sched.h>
#include <sstream>
#include <stdexcept>
#include <unordered_set>

namespace doc {

namespace {

std::size_t affinity_capacity() {
    cpu_set_t set;
    CPU_ZERO(&set);
    if (sched_getaffinity(0, sizeof(set), &set) == 0) {
        const int count = CPU_COUNT(&set);
        if (count > 0) {
            return static_cast<std::size_t>(count);
        }
    }
    const auto fallback = std::thread::hardware_concurrency();
    return fallback == 0U ? 1U : static_cast<std::size_t>(fallback);
}

std::optional<std::size_t> cgroup_capacity() {
    std::ifstream input("/sys/fs/cgroup/cpu.max");
    if (!input) {
        return std::nullopt;
    }
    std::string quota_text;
    std::uint64_t period = 0;
    input >> quota_text >> period;
    if (!input || quota_text == "max" || period == 0) {
        return std::nullopt;
    }
    std::uint64_t quota = 0;
    const auto result = std::from_chars(quota_text.data(), quota_text.data() + quota_text.size(), quota);
    if (result.ec != std::errc{} || quota == 0) {
        return std::nullopt;
    }
    const auto rounded_up = (quota + period - 1U) / period;
    return static_cast<std::size_t>(std::max<std::uint64_t>(1U, rounded_up));
}

std::optional<std::size_t> environment_cap() {
    const char* text = std::getenv("DOC_MAX_WORKERS");
    if (text == nullptr || *text == '\0') {
        return std::nullopt;
    }
    std::uint64_t value = 0;
    const std::string value_text(text);
    const auto result = std::from_chars(value_text.data(), value_text.data() + value_text.size(), value);
    if (result.ec != std::errc{} || value == 0) {
        return std::nullopt;
    }
    return static_cast<std::size_t>(value);
}

}  // namespace

bool Graph::is_source(StateId id) const {
    return id < states.size() && !states[id].definition.has_value();
}

bool Graph::is_derived(StateId id) const {
    return id < states.size() && states[id].definition.has_value();
}

StateId GraphBuilder::source(std::string name, Value initial_value) {
    if (name.empty() || names_.contains(name)) {
        throw std::invalid_argument("state name must be non-empty and unique");
    }
    if (states_.size() >= static_cast<std::size_t>(std::numeric_limits<StateId>::max())) {
        throw std::overflow_error("too many states");
    }
    const auto id = static_cast<StateId>(states_.size());
    names_.emplace(name, id);
    states_.push_back(StateDefinition{std::move(name), initial_value, std::nullopt});
    return id;
}

StateId GraphBuilder::derived(std::string name, std::vector<StateId> premises, Function function,
                              std::string semantic_key) {
    if (name.empty() || names_.contains(name)) {
        throw std::invalid_argument("state name must be non-empty and unique");
    }
    if (!function) {
        throw std::invalid_argument("derived state requires a function");
    }
    for (const auto premise : premises) {
        if (premise >= states_.size()) {
            throw std::invalid_argument("premise does not name an existing state");
        }
    }
    if (states_.size() >= static_cast<std::size_t>(std::numeric_limits<StateId>::max())) {
        throw std::overflow_error("too many states");
    }
    const auto id = static_cast<StateId>(states_.size());
    names_.emplace(name, id);
    states_.push_back(StateDefinition{
        std::move(name), std::nullopt,
        Definition{std::move(premises), std::move(function), std::move(semantic_key)}});
    return id;
}

Graph GraphBuilder::build() const {
    Graph graph;
    graph.states = states_;
    graph.names = names_;
    graph.users.resize(graph.states.size());
    graph.level.assign(graph.states.size(), 0U);

    std::vector<std::size_t> indegree(graph.states.size(), 0U);
    for (StateId id = 0; id < graph.states.size(); ++id) {
        const auto& state = graph.states[id];
        if (!state.definition) {
            if (!state.initial_value) {
                throw std::invalid_argument("source lacks initial value");
            }
            continue;
        }
        for (const auto premise : state.definition->premises) {
            if (premise >= graph.states.size()) {
                throw std::invalid_argument("premise outside graph");
            }
            graph.users[premise].push_back(id);
            ++indegree[id];
        }
    }

    std::queue<StateId> queue;
    for (StateId id = 0; id < graph.states.size(); ++id) {
        if (indegree[id] == 0U) {
            queue.push(id);
        }
    }

    while (!queue.empty()) {
        const auto current = queue.front();
        queue.pop();
        graph.topological_states.push_back(current);
        for (const auto user : graph.users[current]) {
            graph.level[user] = std::max(graph.level[user], graph.level[current] + 1U);
            if (--indegree[user] == 0U) {
                queue.push(user);
            }
        }
    }

    if (graph.topological_states.size() != graph.states.size()) {
        throw std::invalid_argument("dependency graph must be acyclic");
    }
    validate_graph(graph);
    return graph;
}

void validate_graph(const Graph& graph) {
    if (graph.states.size() > static_cast<std::size_t>(std::numeric_limits<StateId>::max())) {
        throw std::invalid_argument("graph has too many states");
    }
    if (graph.users.size() != graph.states.size() ||
        graph.level.size() != graph.states.size() ||
        graph.topological_states.size() != graph.states.size() ||
        graph.names.size() != graph.states.size()) {
        throw std::invalid_argument("graph indexes do not match the state family");
    }

    std::unordered_set<std::string> names;
    std::vector<std::vector<StateId>> expected_users(graph.states.size());
    std::vector<std::size_t> indegree(graph.states.size(), 0U);
    for (StateId state = 0; state < graph.states.size(); ++state) {
        const auto& definition = graph.states[state];
        if (definition.name.empty() || !names.insert(definition.name).second) {
            throw std::invalid_argument("graph state names must be non-empty and unique");
        }
        const auto mapped = graph.names.find(definition.name);
        if (mapped == graph.names.end() || mapped->second != state) {
            throw std::invalid_argument("graph name index is inconsistent");
        }
        if (!definition.definition) {
            if (!definition.initial_value) {
                throw std::invalid_argument("source lacks an initial value");
            }
            continue;
        }
        if (definition.initial_value || !definition.definition->function) {
            throw std::invalid_argument("derived state has an invalid definition record");
        }
        for (const auto premise : definition.definition->premises) {
            if (premise >= graph.states.size()) {
                throw std::invalid_argument("definition premise is outside the graph");
            }
            expected_users[premise].push_back(state);
            ++indegree[state];
        }
    }
    if (expected_users != graph.users) {
        throw std::invalid_argument("graph user index is inconsistent");
    }

    std::queue<StateId> queue;
    std::vector<std::size_t> expected_level(graph.states.size(), 0U);
    for (StateId state = 0; state < graph.states.size(); ++state) {
        if (indegree[state] == 0U) {
            queue.push(state);
        }
    }
    std::vector<StateId> expected_order;
    while (!queue.empty()) {
        const auto state = queue.front();
        queue.pop();
        expected_order.push_back(state);
        for (const auto user : expected_users[state]) {
            expected_level[user] = std::max(expected_level[user], expected_level[state] + 1U);
            if (--indegree[user] == 0U) {
                queue.push(user);
            }
        }
    }
    if (expected_order.size() != graph.states.size()) {
        throw std::invalid_argument("dependency graph must be acyclic");
    }
    if (expected_order != graph.topological_states || expected_level != graph.level) {
        throw std::invalid_argument("graph topological indexes are inconsistent");
    }
}

WorkerPool::WorkerPool(std::size_t participant_capacity)
    : participant_capacity_(std::max<std::size_t>(1U, participant_capacity)) {
    const auto count = participant_capacity_ - 1U;
    workers_.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
        workers_.emplace_back([this] { worker_loop(); });
    }
}

WorkerPool::~WorkerPool() {
    {
        std::lock_guard lock(mutex_);
        stopping_ = true;
        ++generation_;
    }
    start_cv_.notify_all();
    for (auto& worker : workers_) {
        if (worker.joinable()) {
            worker.join();
        }
    }
}

std::size_t WorkerPool::participant_capacity() const noexcept {
    return participant_capacity_;
}

std::size_t WorkerPool::worker_threads() const noexcept {
    return workers_.size();
}

std::uint64_t WorkerPool::generation() const noexcept {
    std::lock_guard lock(mutex_);
    return generation_;
}

void WorkerPool::parallel_for(
    std::size_t count,
    const std::function<void(std::size_t, bool)>& function) {
    if (count == 0U) {
        return;
    }
    if (count == 1U || workers_.empty()) {
        {
            std::lock_guard lock(mutex_);
            ++generation_;
            completed_generation_ = generation_;
        }
        for (std::size_t i = 0; i < count; ++i) {
            function(i, false);
        }
        return;
    }

    {
        std::lock_guard lock(mutex_);
        if (job_active_) {
            throw std::logic_error("worker pool already has an active job");
        }
        job_active_ = true;
        function_ = function;
        exception_ = nullptr;
        queue_.clear();
        for (std::size_t i = 1U; i < count; ++i) {
            queue_.push_back(i);
        }
        outstanding_ = count - 1U;
        ++generation_;
    }
    start_cv_.notify_all();

    // Task zero is reserved for the epoch owner, so owner participation is
    // guaranteed. The owner then helps drain the same queue. Keep the queue
    // lock across completion bookkeeping and the next claim so each
    // additional owner task needs only one synchronization round-trip.
    execute_task(0U, false);

    std::unique_lock lock(mutex_);
    while (true) {
        if (!queue_.empty()) {
            const auto index = queue_.front();
            queue_.pop_front();
            lock.unlock();
            execute_task(index, false);
            lock.lock();
            --outstanding_;
            if (outstanding_ == 0U) {
                done_cv_.notify_all();
            }
        } else if (outstanding_ == 0U) {
            completed_generation_ = generation_;
            job_active_ = false;
            function_ = {};
            break;
        } else {
            done_cv_.wait(lock, [this] { return !queue_.empty() || outstanding_ == 0U; });
        }
    }
    lock.unlock();

    if (exception_) {
        std::rethrow_exception(exception_);
    }
}

void WorkerPool::execute_task(std::size_t index, bool worker_thread) {
    // function_ is installed before workers are released and is not replaced
    // until outstanding_ reaches zero. A task therefore may invoke it
    // directly without taking the queue mutex or copying std::function.
    try {
        function_(index, worker_thread);
    } catch (...) {
        std::lock_guard lock(mutex_);
        if (!exception_) {
            exception_ = std::current_exception();
        }
    }
}

void WorkerPool::worker_loop() {
    std::unique_lock lock(mutex_);
    while (true) {
        start_cv_.wait(lock, [this] { return stopping_ || !queue_.empty(); });
        if (stopping_) {
            return;
        }

        // Once awake, finish-and-claim under one lock acquisition per task.
        // This preserves the shared dynamic queue (and therefore load
        // balancing) while removing the extra callable-copy lock and one
        // lock/unlock pair from the hot path.
        while (!queue_.empty()) {
            const auto index = queue_.front();
            queue_.pop_front();
            lock.unlock();
            execute_task(index, true);
            lock.lock();

            --outstanding_;
            if (outstanding_ == 0U) {
                done_cv_.notify_all();
            }
        }
    }
}

Runtime::Runtime(Graph graph, CutoffPolicy cutoff_policy)
    : graph_(std::move(graph)),
      values_(graph_.states.size()),
      active_(graph_.states.size(), 0U),
      cutoff_policy_(cutoff_policy),
      pool_(detect_participant_capacity()) {
    validate_graph(graph_);
    for (StateId id = 0; id < graph_.states.size(); ++id) {
        const auto& state = graph_.states[id];
        if (state.definition) {
            active_[id] = 1U;
        } else {
            values_[id] = state.initial_value;
        }
    }
}

Runtime::Runtime(Graph graph, RuntimeSeed seed, CutoffPolicy cutoff_policy)
    : graph_(std::move(graph)),
      values_(std::move(seed.values)),
      active_(std::move(seed.active)),
      cutoff_policy_(cutoff_policy),
      pool_(detect_participant_capacity()) {
    validate_graph(graph_);
    if (values_.size() != graph_.states.size() || active_.size() != graph_.states.size()) {
        throw std::invalid_argument("runtime seed shape does not match graph");
    }
    for (StateId id = 0; id < graph_.states.size(); ++id) {
        if (active_[id] > 1U) {
            throw std::invalid_argument("runtime seed active flags must be Boolean");
        }
        if (graph_.is_source(id)) {
            if (!values_[id]) {
                throw std::invalid_argument("runtime seed omits a source value");
            }
            if (active_[id] != 0U) {
                throw std::invalid_argument("runtime seed cannot activate a source state");
            }
            continue;
        }
        if (active_[id] != 0U) {
            continue;
        }
        if (!values_[id]) {
            throw std::invalid_argument("unmaterialized derived seed must be active");
        }
        const auto& definition = *graph_.states[id].definition;
        std::vector<Value> inputs;
        inputs.reserve(definition.premises.size());
        for (const auto premise : definition.premises) {
            if (!values_[premise]) {
                throw std::invalid_argument(
                    "inactive derived seed has an unmaterialized premise");
            }
            inputs.push_back(*values_[premise]);
        }
        Value expected = 0;
        try {
            expected = definition.function(inputs);
        } catch (...) {
            throw std::invalid_argument(
                "inactive derived seed could not be checked for local satisfaction");
        }
        if (*values_[id] != expected) {
            throw std::invalid_argument(
                "inactive derived seed is not locally satisfied");
        }
    }
}

const Graph& Runtime::graph() const noexcept {
    return graph_;
}

std::size_t Runtime::participant_capacity() const noexcept {
    return pool_.participant_capacity();
}

std::size_t Runtime::detect_participant_capacity() {
    auto capacity = affinity_capacity();
    if (const auto cgroup = cgroup_capacity()) {
        capacity = std::min(capacity, *cgroup);
    }
    if (const auto cap = environment_cap()) {
        capacity = std::min(capacity, *cap);
    }
    return std::max<std::size_t>(1U, capacity);
}

bool Runtime::valid_state(StateId state) const noexcept {
    return state < graph_.states.size();
}

std::vector<StateId> Runtime::ready_frontier_locked() const {
    std::vector<std::uint8_t> has_active_ancestor(graph_.states.size(), 0U);
    std::vector<StateId> frontier;
    frontier.reserve(graph_.states.size());

    for (const auto state : graph_.topological_states) {
        const auto& definition = graph_.states[state].definition;
        if (!definition) {
            continue;
        }
        bool blocked = false;
        for (const auto premise : definition->premises) {
            if (graph_.is_derived(premise) &&
                (active_[premise] != 0U || has_active_ancestor[premise] != 0U)) {
                blocked = true;
                break;
            }
        }
        has_active_ancestor[state] = blocked ? 1U : 0U;
        if (active_[state] != 0U && !blocked) {
            frontier.push_back(state);
        }
    }
    return frontier;
}

bool Runtime::stabilize(std::string* error) {
    std::lock_guard lock(epoch_mutex_);
    return stabilize_locked(error);
}

bool Runtime::stabilize_locked(std::string* error) {
    while (true) {
        const auto frontier = ready_frontier_locked();
        const bool any_active = std::any_of(active_.begin(), active_.end(), [](std::uint8_t value) {
            return value != 0U;
        });
        if (frontier.empty()) {
            if (any_active) {
                if (error) {
                    *error = "active definitions have no ready frontier";
                }
                return false;
            }
            return true;
        }

        std::vector<Candidate> candidates(frontier.size());
        std::vector<std::vector<Value>> inputs(frontier.size());
        for (std::size_t i = 0; i < frontier.size(); ++i) {
            const auto state = frontier[i];
            const auto& definition = *graph_.states[state].definition;
            auto& values = inputs[i];
            values.reserve(definition.premises.size());
            for (const auto premise : definition.premises) {
                if (!values_[premise]) {
                    if (error) {
                        *error = "ready definition has an unmaterialized premise";
                    }
                    return false;
                }
                values.push_back(*values_[premise]);
            }
        }

        std::atomic<std::uint64_t> owner_jobs{0};
        std::atomic<std::uint64_t> worker_jobs{0};
        try {
            pool_.parallel_for(frontier.size(), [&](std::size_t i, bool worker_thread) {
                const auto state = frontier[i];
                const auto& definition = *graph_.states[state].definition;
                candidates[i] = Candidate{state, definition.function(inputs[i])};
                if (worker_thread) {
                    worker_jobs.fetch_add(1U, std::memory_order_relaxed);
                } else {
                    owner_jobs.fetch_add(1U, std::memory_order_relaxed);
                }
            });
        } catch (const std::exception& exception) {
            if (error) {
                *error = std::string("frontier evaluation failed before publication: ") + exception.what();
            }
            return false;
        } catch (...) {
            if (error) {
                *error = "frontier evaluation failed before publication";
            }
            return false;
        }

        ++stats_.frontiers;
        stats_.evaluations += static_cast<std::uint64_t>(frontier.size());
        stats_.owner_jobs += owner_jobs.load(std::memory_order_relaxed);
        stats_.worker_jobs += worker_jobs.load(std::memory_order_relaxed);

        for (const auto state : frontier) {
            active_[state] = 0U;
        }
        for (const auto& candidate : candidates) {
            const bool proven_same =
                cutoff_policy_ == CutoffPolicy::Exact &&
                values_[candidate.state].has_value() &&
                *values_[candidate.state] == candidate.value;
            if (!proven_same) {
                values_[candidate.state] = candidate.value;
                ++stats_.publications;
                for (const auto user : graph_.users[candidate.state]) {
                    active_[user] = 1U;
                }
            } else {
                ++stats_.equality_cutoffs;
            }
        }
    }
}

bool Runtime::update_batch(
    const std::vector<std::pair<StateId, Value>>& assignments,
    std::string* error) {
    std::lock_guard lock(epoch_mutex_);
    std::unordered_set<StateId> seen;
    seen.reserve(assignments.size());
    for (const auto& [state, ignored] : assignments) {
        (void)ignored;
        if (!valid_state(state)) {
            if (error) {
                *error = "source batch names an invalid state";
            }
            return false;
        }
        if (!graph_.is_source(state)) {
            if (error) {
                *error = "source batch targets a derived state";
            }
            return false;
        }
        if (!seen.insert(state).second) {
            if (error) {
                *error = "source batch contains a duplicate target";
            }
            return false;
        }
    }

    for (const auto& [state, next] : assignments) {
        const bool proven_same =
            cutoff_policy_ == CutoffPolicy::Exact &&
            values_[state].has_value() &&
            *values_[state] == next;
        if (!proven_same) {
            values_[state] = next;
            ++stats_.source_changes;
            for (const auto user : graph_.users[state]) {
                active_[user] = 1U;
            }
        }
    }
    return stabilize_locked(error);
}

std::optional<Value> Runtime::observe(StateId state, std::string* error) {
    std::lock_guard lock(epoch_mutex_);
    if (!valid_state(state)) {
        if (error) {
            *error = "observation names an invalid state";
        }
        return std::nullopt;
    }
    if (!stabilize_locked(error)) {
        return std::nullopt;
    }
    return values_[state];
}

std::optional<Value> Runtime::value(StateId state) const {
    std::lock_guard lock(epoch_mutex_);
    if (!valid_state(state)) {
        return std::nullopt;
    }
    return values_[state];
}

std::vector<StateSnapshot> Runtime::snapshot() const {
    std::lock_guard lock(epoch_mutex_);
    std::vector<StateSnapshot> output;
    output.reserve(graph_.states.size());
    for (StateId state = 0; state < graph_.states.size(); ++state) {
        output.push_back(StateSnapshot{
            graph_.states[state].name,
            graph_.is_source(state),
            active_[state] != 0U,
            values_[state]});
    }
    return output;
}

RuntimeStats Runtime::stats() const {
    std::lock_guard lock(epoch_mutex_);
    return stats_;
}

void Runtime::reset_stats() {
    std::lock_guard lock(epoch_mutex_);
    stats_ = {};
}

std::uint64_t Runtime::pool_generation() const noexcept {
    return pool_.generation();
}

std::vector<Value> evaluate_from_scratch(
    const Graph& graph,
    const std::vector<Value>& source_values) {
    const auto source_count = static_cast<std::size_t>(std::count_if(
        graph.states.begin(), graph.states.end(), [](const StateDefinition& state) {
            return !state.definition.has_value();
        }));
    if (source_values.size() != source_count) {
        throw std::invalid_argument("wrong number of source values");
    }

    std::vector<std::optional<Value>> values(graph.states.size());
    std::size_t source_index = 0;
    for (const auto state : graph.topological_states) {
        const auto& definition = graph.states[state].definition;
        if (!definition) {
            values[state] = source_values[source_index++];
            continue;
        }
        std::vector<Value> inputs;
        inputs.reserve(definition->premises.size());
        for (const auto premise : definition->premises) {
            if (!values[premise]) {
                throw std::logic_error("oracle encountered an unmaterialized premise");
            }
            inputs.push_back(*values[premise]);
        }
        values[state] = definition->function(inputs);
    }

    std::vector<Value> output;
    output.reserve(values.size());
    for (const auto& value : values) {
        if (!value) {
            throw std::logic_error("oracle did not materialize every state");
        }
        output.push_back(*value);
    }
    return output;
}

}  // namespace doc
