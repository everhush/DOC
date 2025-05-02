#pragma once

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <exception>
#include <functional>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

namespace doc {

using StateId = std::uint32_t;
using Value = std::int64_t;
using Function = std::function<Value(const std::vector<Value>&)>;

enum class CutoffPolicy {
    Exact,
    Conservative,
};

struct Definition {
    std::vector<StateId> premises;
    Function function;
    // Stable semantic identifier used only when deciding whether a retained
    // value can cross an immutable graph-version boundary. An empty key means
    // "do not assume compatibility across versions".
    std::string semantic_key;
};

struct StateDefinition {
    std::string name;
    std::optional<Value> initial_value;
    std::optional<Definition> definition;
};

struct Graph {
    std::vector<StateDefinition> states;
    std::vector<std::vector<StateId>> users;
    std::vector<StateId> topological_states;
    std::vector<std::size_t> level;
    std::unordered_map<std::string, StateId> names;

    [[nodiscard]] bool is_source(StateId id) const;
    [[nodiscard]] bool is_derived(StateId id) const;
};

// Rejects malformed or internally inconsistent graph representations,
// including forged indexes. All runtime entry points call this before using a
// Graph, so GraphBuilder is convenient rather than a hidden trust boundary.
void validate_graph(const Graph& graph);

class GraphBuilder {
public:
    StateId source(std::string name, Value initial_value);
    StateId derived(std::string name, std::vector<StateId> premises, Function function,
                    std::string semantic_key = {});
    [[nodiscard]] Graph build() const;

private:
    std::vector<StateDefinition> states_;
    std::unordered_map<std::string, StateId> names_;
};

struct RuntimeStats {
    std::uint64_t source_changes = 0;
    std::uint64_t frontiers = 0;
    std::uint64_t evaluations = 0;
    std::uint64_t publications = 0;
    std::uint64_t equality_cutoffs = 0;
    std::uint64_t owner_jobs = 0;
    std::uint64_t worker_jobs = 0;
};


struct RuntimeSeed {
    std::vector<std::optional<Value>> values;
    std::vector<std::uint8_t> active;
};

struct StateSnapshot {
    std::string name;
    bool source = false;
    bool active = false;
    std::optional<Value> value;
};

class WorkerPool {
public:
    explicit WorkerPool(std::size_t participant_capacity);
    ~WorkerPool();

    WorkerPool(const WorkerPool&) = delete;
    WorkerPool& operator=(const WorkerPool&) = delete;

    [[nodiscard]] std::size_t participant_capacity() const noexcept;
    [[nodiscard]] std::size_t worker_threads() const noexcept;
    [[nodiscard]] std::uint64_t generation() const noexcept;

    void parallel_for(std::size_t count,
                      const std::function<void(std::size_t, bool)>& function);

private:
    void worker_loop();
    void execute_task(std::size_t index, bool worker_thread);

    std::size_t participant_capacity_ = 1;
    std::vector<std::thread> workers_;

    mutable std::mutex mutex_;
    std::condition_variable start_cv_;
    std::condition_variable done_cv_;
    bool stopping_ = false;
    std::uint64_t generation_ = 0;
    std::uint64_t completed_generation_ = 0;
    std::deque<std::size_t> queue_;
    std::size_t outstanding_ = 0;
    bool job_active_ = false;
    std::function<void(std::size_t, bool)> function_;
    std::exception_ptr exception_;
};

class Runtime {
public:
    explicit Runtime(Graph graph, CutoffPolicy cutoff_policy = CutoffPolicy::Exact);
    Runtime(Graph graph, RuntimeSeed seed,
            CutoffPolicy cutoff_policy = CutoffPolicy::Exact);

    Runtime(const Runtime&) = delete;
    Runtime& operator=(const Runtime&) = delete;

    [[nodiscard]] const Graph& graph() const noexcept;
    [[nodiscard]] std::size_t participant_capacity() const noexcept;

    bool stabilize(std::string* error = nullptr);
    bool update_batch(const std::vector<std::pair<StateId, Value>>& assignments,
                      std::string* error = nullptr);
    std::optional<Value> observe(StateId state, std::string* error = nullptr);

    [[nodiscard]] std::optional<Value> value(StateId state) const;
    [[nodiscard]] std::vector<StateSnapshot> snapshot() const;
    [[nodiscard]] RuntimeStats stats() const;
    void reset_stats();
    [[nodiscard]] std::uint64_t pool_generation() const noexcept;

    static std::size_t detect_participant_capacity();

private:
    struct Candidate {
        StateId state = 0;
        Value value = 0;
    };

    bool stabilize_locked(std::string* error);
    [[nodiscard]] std::vector<StateId> ready_frontier_locked() const;
    [[nodiscard]] bool valid_state(StateId state) const noexcept;

    Graph graph_;
    mutable std::mutex epoch_mutex_;
    std::vector<std::optional<Value>> values_;
    std::vector<std::uint8_t> active_;
    CutoffPolicy cutoff_policy_ = CutoffPolicy::Exact;
    WorkerPool pool_;
    RuntimeStats stats_;
};

[[nodiscard]] std::vector<Value> evaluate_from_scratch(
    const Graph& graph,
    const std::vector<Value>& source_values);

}  // namespace doc
