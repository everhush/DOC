#include "doc/effect.hpp"
#include "doc/graph_versions.hpp"
#include "doc/placement.hpp"
#include "doc/network_runtime.hpp"
#include "doc/recovery.hpp"
#include "doc/recurrence.hpp"
#include "doc/runtime.hpp"
#include "doc/transport.hpp"
#include "doc/typed_value.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <mutex>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

std::uint64_t test_checksum(std::string_view text) {
    std::uint64_t hash = 1469598103934665603ULL;
    for (const unsigned char byte : text) {
        hash ^= byte;
        hash *= 1099511628211ULL;
    }
    return hash;
}

std::string checked_effect_line(const std::string& payload) {
    return payload + "\t" + std::to_string(test_checksum(payload)) + "\n";
}

doc::Function add_function() {
    return [](const std::vector<doc::Value>& values) {
        doc::Value total = 0;
        for (const auto value : values) {
            total += value;
        }
        return total;
    };
}

void test_representation_and_initialization() {
    doc::GraphBuilder builder;
    const auto a = builder.source("a", 2);
    const auto b = builder.source("b", 3);
    const auto sum = builder.derived("sum", {a, b}, add_function());
    const auto graph = builder.build();
    require(graph.states.size() == 3U, "expected three states");
    require(graph.is_source(a) && graph.is_source(b), "sources not derived structurally");
    require(graph.is_derived(sum), "definition key should induce derived state");
    require(graph.users[a] == std::vector<doc::StateId>{sum}, "users not induced");

    doc::Runtime runtime(graph);
    require(runtime.value(sum) == std::nullopt, "derived state should start unmaterialized");
    std::string error;
    require(runtime.stabilize(&error), error);
    require(runtime.value(sum) == 5, "initial stabilization failed");

    auto forged = graph;
    forged.users[a].clear();
    bool rejected = false;
    try {
        doc::Runtime invalid(std::move(forged));
        (void)invalid;
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    require(rejected, "runtime accepted a forged graph index");
}

void test_zero_premise_definition() {
    doc::GraphBuilder builder;
    const auto constant = builder.derived("constant", {}, [](const std::vector<doc::Value>& values) {
        require(values.empty(), "zero-premise function received input");
        return 42;
    });
    doc::Runtime runtime(builder.build());
    std::string error;
    require(runtime.observe(constant, &error) == 42, error);
}

void test_equal_source_noop_and_atomic_rejection() {
    doc::GraphBuilder builder;
    const auto source = builder.source("source", 7);
    const auto derived = builder.derived("derived", {source}, [](const std::vector<doc::Value>& values) {
        return values.at(0) * 2;
    });
    doc::Runtime runtime(builder.build());
    std::string error;
    require(runtime.observe(derived, &error) == 14, error);
    runtime.reset_stats();
    require(runtime.update_batch({{source, 7}}, &error), error);
    const auto noop_stats = runtime.stats();
    require(noop_stats.source_changes == 0U && noop_stats.evaluations == 0U,
            "equal source assignment should be a complete no-op");

    const auto before = runtime.snapshot();
    require(!runtime.update_batch({{source, 8}, {source, 9}}, &error),
            "duplicate source targets should be rejected");
    require(runtime.snapshot().at(source).value == before.at(source).value,
            "invalid batch partially changed a source");
    require(!runtime.update_batch({{derived, 99}}, &error),
            "derived target should be rejected");
    require(runtime.snapshot().at(source).value == before.at(source).value,
            "invalid derived-target batch partially changed state");
}

void test_locality_and_equality_cutoff() {
    doc::GraphBuilder builder;
    const auto a = builder.source("a", 2);
    const auto b = builder.source("b", 3);
    const auto sum = builder.derived("sum", {a, b}, add_function());
    const auto doubled = builder.derived("doubled", {sum}, [](const std::vector<doc::Value>& values) {
        return values.at(0) * 2;
    });
    const auto unrelated_source = builder.source("unrelated_source", 10);
    const auto unrelated = builder.derived("unrelated", {unrelated_source}, [](const std::vector<doc::Value>& values) {
        return values.at(0) + 1;
    });

    doc::Runtime runtime(builder.build());
    std::string error;
    require(runtime.stabilize(&error), error);
    require(runtime.value(doubled) == 10 && runtime.value(unrelated) == 11,
            "initial values wrong");

    runtime.reset_stats();
    require(runtime.update_batch({{a, 4}, {b, 1}}, &error), error);
    const auto stats = runtime.stats();
    require(stats.evaluations == 1U, "cutoff should evaluate only the immediate producer");
    require(stats.equality_cutoffs == 1U, "equal intermediate should record one cutoff");
    require(runtime.value(doubled) == 10, "downstream retained value changed incorrectly");
    require(runtime.value(unrelated) == 11, "disconnected region was disturbed");
}

void test_conservative_always_propagate_profile() {
    doc::GraphBuilder builder;
    const auto source = builder.source("source", 1);
    const auto parity = builder.derived("parity", {source}, [](const std::vector<doc::Value>& v) {
        return v.at(0) % 2;
    });
    const auto result = builder.derived("result", {parity}, [](const std::vector<doc::Value>& v) {
        return v.at(0) * 10;
    });
    const auto graph = builder.build();

    doc::Runtime exact(graph, doc::CutoffPolicy::Exact);
    doc::Runtime conservative(graph, doc::CutoffPolicy::Conservative);
    std::string error;
    require(exact.stabilize(&error) && conservative.stabilize(&error), error);

    exact.reset_stats();
    conservative.reset_stats();
    require(exact.update_batch({{source, 3}}, &error), error);
    require(conservative.update_batch({{source, 3}}, &error), error);

    require(exact.value(result) == 10 && conservative.value(result) == 10,
            "cutoff profiles changed the stable result");
    const auto exact_stats = exact.stats();
    const auto conservative_stats = conservative.stats();
    require(exact_stats.evaluations == 1U && exact_stats.equality_cutoffs == 1U,
            "exact cutoff profile did not stop at the equal intermediate");
    require(conservative_stats.evaluations == 2U && conservative_stats.equality_cutoffs == 0U,
            "conservative profile did not propagate through the equal intermediate");

    const auto oracle = doc::evaluate_from_scratch(graph, {3});
    require(conservative.value(result) == oracle.at(result),
            "conservative propagation disagreed with complete reevaluation");
}

void test_multiple_contributors_through_explicit_merge() {
    doc::GraphBuilder builder;
    const auto proposal_a = builder.source("proposal_a", 2);
    const auto proposal_b = builder.source("proposal_b", 5);
    const auto resolved = builder.derived(
        "resolved", {proposal_a, proposal_b}, [](const std::vector<doc::Value>& v) {
            return std::max(v.at(0), v.at(1));
        });
    const auto observed = builder.derived(
        "observed", {resolved}, [](const std::vector<doc::Value>& v) {
            return v.at(0) * 2;
        });

    doc::Runtime runtime(builder.build());
    std::string error;
    require(runtime.stabilize(&error), error);
    require(runtime.value(observed) == 10, "initial explicit merge is wrong");
    require(runtime.update_batch({{proposal_a, 9}, {proposal_b, 4}}, &error), error);
    require(runtime.value(resolved) == 9 && runtime.value(observed) == 18,
            "multiple contributors were not resolved by the explicit merge definition");
}

void test_transitive_ready_frontier() {
    doc::GraphBuilder builder;
    const auto s = builder.source("s", 1);
    const auto x = builder.source("x", 10);
    const auto e = builder.derived("e", {s}, [](const std::vector<doc::Value>& v) { return v.at(0) + 1; });
    const auto p = builder.derived("p", {e}, [](const std::vector<doc::Value>& v) { return v.at(0) * 10; });
    const auto d = builder.derived("d", {p, x}, add_function());
    doc::Runtime runtime(builder.build());
    std::string error;
    require(runtime.observe(d, &error) == 30, error);
    require(runtime.update_batch({{s, 2}, {x, 20}}, &error), error);
    require(runtime.value(d) == 50,
            "a node active through one premise ran before a transitive active ancestor of another premise");
}

void test_multipath_activation_and_expansion() {
    doc::GraphBuilder opaque_builder;
    const auto oa = opaque_builder.source("a", 3);
    const auto ob = opaque_builder.source("b", 4);
    const auto opaque = opaque_builder.derived("result", {oa, ob}, [](const std::vector<doc::Value>& v) {
        return (v.at(0) + v.at(1)) * (v.at(0) - v.at(1));
    });

    doc::GraphBuilder expanded_builder;
    const auto ea = expanded_builder.source("a", 3);
    const auto eb = expanded_builder.source("b", 4);
    const auto plus = expanded_builder.derived("plus", {ea, eb}, add_function());
    const auto minus = expanded_builder.derived("minus", {ea, eb}, [](const std::vector<doc::Value>& v) {
        return v.at(0) - v.at(1);
    });
    const auto expanded = expanded_builder.derived("result", {plus, minus}, [](const std::vector<doc::Value>& v) {
        return v.at(0) * v.at(1);
    });

    doc::Runtime opaque_runtime(opaque_builder.build());
    doc::Runtime expanded_runtime(expanded_builder.build());
    std::string error;
    require(opaque_runtime.observe(opaque, &error) == expanded_runtime.observe(expanded, &error),
            "opaque and expanded initial boundaries differ");
    for (doc::Value i = 0; i < 50; ++i) {
        require(opaque_runtime.update_batch({{oa, i}, {ob, 50 - i}}, &error), error);
        require(expanded_runtime.update_batch({{ea, i}, {eb, 50 - i}}, &error), error);
        require(opaque_runtime.value(opaque) == expanded_runtime.value(expanded),
                "boundary-equivalent expansion diverged");
    }
}


void test_one_evaluation_per_epoch() {
    std::atomic<int> p_calls{0};
    std::atomic<int> q_calls{0};
    std::atomic<int> r_calls{0};
    std::atomic<int> out_calls{0};

    doc::GraphBuilder builder;
    const auto a = builder.source("a", 1);
    const auto b = builder.source("b", 2);
    const auto p_state = builder.derived("p", {a}, [&](const std::vector<doc::Value>& v) {
        p_calls.fetch_add(1, std::memory_order_relaxed);
        return v.at(0) + 10;
    });
    const auto q_state = builder.derived("q", {b}, [&](const std::vector<doc::Value>& v) {
        q_calls.fetch_add(1, std::memory_order_relaxed);
        return v.at(0) + 20;
    });
    const auto r_state = builder.derived("r", {p_state, q_state}, [&](const std::vector<doc::Value>& v) {
        r_calls.fetch_add(1, std::memory_order_relaxed);
        return v.at(0) + v.at(1);
    });
    const auto output = builder.derived("output", {r_state}, [&](const std::vector<doc::Value>& v) {
        out_calls.fetch_add(1, std::memory_order_relaxed);
        return v.at(0) * 2;
    });

    doc::Runtime runtime(builder.build());
    std::string error;
    require(runtime.observe(output, &error).has_value(), error);
    p_calls = 0;
    q_calls = 0;
    r_calls = 0;
    out_calls = 0;
    runtime.reset_stats();

    require(runtime.update_batch({{a, 3}, {b, 5}}, &error), error);
    require(p_calls.load() == 1 && q_calls.load() == 1 &&
            r_calls.load() == 1 && out_calls.load() == 1,
            "a definition evaluated more than once in one source epoch");
    require(runtime.stats().evaluations == 4U,
            "unexpected evaluation count for one-evaluation-per-epoch graph");
}

struct RandomGraphCase {
    doc::Graph graph;
    std::vector<doc::StateId> sources;
};

RandomGraphCase make_random_graph(std::mt19937_64& random, std::size_t source_count, std::size_t derived_count) {
    doc::GraphBuilder builder;
    std::vector<doc::StateId> sources;
    std::vector<doc::StateId> all;
    for (std::size_t i = 0; i < source_count; ++i) {
        const auto id = builder.source("s" + std::to_string(i), static_cast<doc::Value>(random() % 101U));
        sources.push_back(id);
        all.push_back(id);
    }
    for (std::size_t i = 0; i < derived_count; ++i) {
        const auto arity = 1U + static_cast<std::size_t>(random() % 3U);
        std::vector<doc::StateId> premises;
        premises.reserve(arity);
        for (std::size_t p = 0; p < arity; ++p) {
            premises.push_back(all.at(static_cast<std::size_t>(random() % all.size())));
        }
        const auto salt = static_cast<doc::Value>(random() % 17U);
        const auto id = builder.derived("d" + std::to_string(i), premises,
            [salt](const std::vector<doc::Value>& values) {
                doc::Value result = salt;
                for (const auto value : values) {
                    result = (result * 131 + value * 17 + 97) % 1000003;
                }
                return result;
            });
        all.push_back(id);
    }
    return RandomGraphCase{builder.build(), sources};
}

void test_randomized_differential_9600_epochs() {
    std::mt19937_64 random(0xD0C2026ULL);
    constexpr std::size_t graph_count = 40U;
    constexpr std::size_t epochs_per_graph = 240U;
    for (std::size_t graph_index = 0; graph_index < graph_count; ++graph_index) {
        auto generated = make_random_graph(random, 4U, 8U);
        doc::Runtime runtime(generated.graph);
        std::vector<doc::Value> source_values;
        for (const auto source : generated.sources) {
            source_values.push_back(*generated.graph.states[source].initial_value);
        }
        std::string error;
        require(runtime.stabilize(&error), error);
        for (std::size_t epoch = 0; epoch < epochs_per_graph; ++epoch) {
            std::vector<std::pair<doc::StateId, doc::Value>> batch;
            const auto changes = 1U + static_cast<std::size_t>(random() % generated.sources.size());
            std::vector<std::size_t> indices(generated.sources.size());
            for (std::size_t i = 0; i < indices.size(); ++i) indices[i] = i;
            std::shuffle(indices.begin(), indices.end(), random);
            for (std::size_t i = 0; i < changes; ++i) {
                const auto index = indices[i];
                const auto next = static_cast<doc::Value>(random() % 101U);
                source_values[index] = next;
                batch.emplace_back(generated.sources[index], next);
            }
            require(runtime.update_batch(batch, &error), error);
            const auto oracle = doc::evaluate_from_scratch(generated.graph, source_values);
            const auto snapshot = runtime.snapshot();
            require(snapshot.size() == oracle.size(), "oracle size mismatch");
            for (std::size_t state = 0; state < oracle.size(); ++state) {
                require(snapshot[state].value == oracle[state],
                        "randomized active-set result disagrees with complete reevaluation");
                require(!snapshot[state].active, "runtime remained active at stable boundary");
            }
        }
    }
}


void test_random_frontier_subset_schedule_agreement() {
    std::mt19937_64 random(0x51B5E7ULL);
    constexpr std::size_t graph_count = 20U;
    constexpr std::size_t epochs_per_graph = 100U;

    for (std::size_t graph_index = 0; graph_index < graph_count; ++graph_index) {
        auto generated = make_random_graph(random, 4U, 12U);
        const auto& graph = generated.graph;
        std::vector<std::optional<doc::Value>> values(graph.states.size());
        std::vector<std::uint8_t> active(graph.states.size(), 0U);
        std::vector<doc::Value> source_values;
        source_values.reserve(generated.sources.size());
        for (doc::StateId state = 0; state < graph.states.size(); ++state) {
            if (graph.is_source(state)) {
                values[state] = graph.states[state].initial_value;
                source_values.push_back(*values[state]);
            } else {
                active[state] = 1U;
            }
        }

        const auto stabilize_random_subsets = [&] {
            std::vector<std::uint8_t> selected_count(graph.states.size(), 0U);
            while (std::any_of(active.begin(), active.end(), [](std::uint8_t v) { return v != 0U; })) {
                std::vector<std::uint8_t> has_active_ancestor(graph.states.size(), 0U);
                std::vector<doc::StateId> frontier;
                for (const auto state : graph.topological_states) {
                    const auto& definition = graph.states[state].definition;
                    if (!definition) continue;
                    bool blocked = false;
                    for (const auto premise : definition->premises) {
                        if (graph.is_derived(premise) &&
                            (active[premise] != 0U || has_active_ancestor[premise] != 0U)) {
                            blocked = true;
                            break;
                        }
                    }
                    has_active_ancestor[state] = blocked ? 1U : 0U;
                    if (active[state] != 0U && !blocked) frontier.push_back(state);
                }
                require(!frontier.empty(), "random subset semantics reached active deadlock");
                std::shuffle(frontier.begin(), frontier.end(), random);
                const auto take = 1U + static_cast<std::size_t>(random() % frontier.size());
                frontier.resize(take);

                std::vector<std::pair<doc::StateId, doc::Value>> candidates;
                candidates.reserve(frontier.size());
                for (const auto state : frontier) {
                    require(++selected_count[state] == 1U,
                            "random subset semantics selected a definition twice in one epoch");
                    std::vector<doc::Value> inputs;
                    for (const auto premise : graph.states[state].definition->premises) {
                        require(values[premise].has_value(),
                                "random subset frontier had an unmaterialized premise");
                        inputs.push_back(*values[premise]);
                    }
                    candidates.emplace_back(state, graph.states[state].definition->function(inputs));
                }

                for (const auto state : frontier) active[state] = 0U;
                for (const auto& [state, candidate] : candidates) {
                    if (!values[state] || *values[state] != candidate) {
                        values[state] = candidate;
                        for (const auto user : graph.users[state]) active[user] = 1U;
                    }
                }
            }
        };

        stabilize_random_subsets();
        auto compare_oracle = [&] {
            const auto oracle = doc::evaluate_from_scratch(graph, source_values);
            require(oracle.size() == values.size(), "random subset oracle size mismatch");
            for (std::size_t i = 0; i < oracle.size(); ++i) {
                require(values[i] && *values[i] == oracle[i],
                        "random frontier subset schedule changed the stable valuation");
            }
        };
        compare_oracle();

        for (std::size_t epoch = 0; epoch < epochs_per_graph; ++epoch) {
            std::vector<std::size_t> indices(generated.sources.size());
            for (std::size_t i = 0; i < indices.size(); ++i) indices[i] = i;
            std::shuffle(indices.begin(), indices.end(), random);
            const auto change_count = 1U + static_cast<std::size_t>(random() % indices.size());
            for (std::size_t i = 0; i < change_count; ++i) {
                const auto source_index = indices[i];
                const auto source = generated.sources[source_index];
                const auto next = static_cast<doc::Value>(random() % 101U);
                if (!values[source] || *values[source] != next) {
                    values[source] = next;
                    source_values[source_index] = next;
                    for (const auto user : graph.users[source]) active[user] = 1U;
                }
            }
            stabilize_random_subsets();
            compare_oracle();
        }
    }
}

void test_sequential_parallel_agreement() {
    std::mt19937_64 random(42U);
    auto generated = make_random_graph(random, 6U, 30U);

    const char* previous = std::getenv("DOC_MAX_WORKERS");
    const std::string saved = previous ? previous : "";
    setenv("DOC_MAX_WORKERS", "1", 1);
    doc::Runtime sequential(generated.graph);
    setenv("DOC_MAX_WORKERS", "4", 1);
    doc::Runtime parallel(generated.graph);
    if (previous) setenv("DOC_MAX_WORKERS", saved.c_str(), 1); else unsetenv("DOC_MAX_WORKERS");

    std::string error;
    require(sequential.stabilize(&error) && parallel.stabilize(&error), error);
    for (std::size_t epoch = 0; epoch < 100U; ++epoch) {
        const auto source_index = epoch % generated.sources.size();
        const auto assignment = std::pair{generated.sources[source_index], static_cast<doc::Value>(epoch * 3U)};
        require(sequential.update_batch({assignment}, &error), error);
        require(parallel.update_batch({assignment}, &error), error);
        const auto left = sequential.snapshot();
        const auto right = parallel.snapshot();
        require(left.size() == right.size(), "snapshot size differs");
        for (std::size_t i = 0; i < left.size(); ++i) {
            require(left[i].value == right[i].value, "sequential and parallel stable values differ");
        }
    }
}

void test_source_epoch_serialization() {
    doc::GraphBuilder builder;
    const auto source = builder.source("source", 0);
    const auto result = builder.derived("result", {source}, [](const std::vector<doc::Value>& v) {
        return v.at(0) * 2;
    });
    doc::Runtime runtime(builder.build());
    std::string initial_error;
    require(runtime.stabilize(&initial_error), initial_error);

    std::atomic<bool> failed{false};
    std::mutex message_mutex;
    std::string message;
    std::vector<std::thread> threads;
    for (int thread = 0; thread < 6; ++thread) {
        threads.emplace_back([&, thread] {
            for (int iteration = 0; iteration < 50; ++iteration) {
                std::string error;
                if (!runtime.update_batch({{source, thread * 1000 + iteration}}, &error)) {
                    failed.store(true);
                    std::lock_guard lock(message_mutex);
                    message = error;
                    return;
                }
            }
        });
    }
    for (auto& thread : threads) thread.join();
    require(!failed.load(), message);
    const auto source_value = runtime.value(source);
    const auto result_value = runtime.value(result);
    require(source_value && result_value && *result_value == *source_value * 2,
            "serialized source epochs did not leave a stable result");
}

void test_observation_waits_for_committed_epoch() {
    std::mutex gate_mutex;
    std::condition_variable gate_cv;
    bool candidate_entered = false;
    bool release_candidate = false;

    doc::GraphBuilder builder;
    const auto source = builder.source("source", 0);
    const auto result = builder.derived("result", {source}, [&](const std::vector<doc::Value>& values) {
        if (values.at(0) == 1) {
            std::unique_lock lock(gate_mutex);
            candidate_entered = true;
            gate_cv.notify_all();
            gate_cv.wait(lock, [&] { return release_candidate; });
        }
        return values.at(0) * 2;
    });

    doc::Runtime runtime(builder.build());
    std::string error;
    require(runtime.stabilize(&error), error);

    std::string update_error;
    std::thread updater([&] {
        require(runtime.update_batch({{source, 1}}, &update_error), update_error);
    });

    {
        std::unique_lock lock(gate_mutex);
        gate_cv.wait(lock, [&] { return candidate_entered; });
    }

    std::atomic<bool> observer_finished{false};
    std::optional<doc::Value> observed;
    std::string observe_error;
    std::thread observer([&] {
        observed = runtime.observe(result, &observe_error);
        observer_finished.store(true, std::memory_order_release);
    });

    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    require(!observer_finished.load(std::memory_order_acquire),
            "observation escaped while a source epoch was privately evaluating");

    {
        std::lock_guard lock(gate_mutex);
        release_candidate = true;
    }
    gate_cv.notify_all();
    updater.join();
    observer.join();

    require(observed && *observed == 2, observe_error.empty() ?
            "observation did not return the committed stable epoch" : observe_error);
}

void test_persistent_pool_and_owner_participation() {
    doc::GraphBuilder builder;
    std::vector<doc::StateId> leaves;
    for (int i = 0; i < 64; ++i) {
        const auto source = builder.source("s" + std::to_string(i), i);
        leaves.push_back(builder.derived("d" + std::to_string(i), {source}, [](const std::vector<doc::Value>& v) {
            return v.at(0) * v.at(0) + 1;
        }));
    }
    const auto root = builder.derived("root", leaves, add_function());
    doc::Runtime runtime(builder.build());
    const auto before_generation = runtime.pool_generation();
    std::string error;
    require(runtime.observe(root, &error).has_value(), error);
    const auto after_first = runtime.pool_generation();
    runtime.reset_stats();
    std::vector<std::pair<doc::StateId, doc::Value>> batch;
    for (int i = 0; i < 64; ++i) batch.emplace_back(static_cast<doc::StateId>(i * 2), i + 1);
    require(runtime.update_batch(batch, &error), error);
    const auto after_second = runtime.pool_generation();
    const auto stats = runtime.stats();
    require(after_first > before_generation && after_second > after_first,
            "persistent pool did not serve multiple generations");
    require(stats.owner_jobs > 0U, "epoch owner did not participate in frontier work");
    require(stats.owner_jobs + stats.worker_jobs == stats.evaluations,
            "frontier job accounting does not match the evaluation count");
}


void test_accepted_source_persists_across_frontier_failure() {
    doc::GraphBuilder builder;
    const auto source = builder.source("source", 0);
    const auto good = builder.derived("good", {source}, [](const std::vector<doc::Value>& v) {
        return v.at(0) + 10;
    });
    const auto guarded = builder.derived("guarded", {source}, [](const std::vector<doc::Value>& v) {
        if (v.at(0) == 1) {
            throw std::runtime_error("intentional update failure");
        }
        return v.at(0) + 20;
    });

    doc::Runtime runtime(builder.build());
    std::string error;
    require(runtime.stabilize(&error), error);
    require(runtime.value(good) == 10 && runtime.value(guarded) == 20,
            "initial failure-boundary values are wrong");

    require(!runtime.update_batch({{source, 1}}, &error),
            "failing downstream frontier unexpectedly stabilized");
    const auto failed = runtime.snapshot();
    require(failed.at(source).value == 1,
            "accepted source fact was incorrectly rolled back");
    require(failed.at(good).value == 10 && failed.at(guarded).value == 20,
            "a frontier candidate published despite peer failure");
    require(failed.at(good).active && failed.at(guarded).active,
            "failed frontier obligations were not retained");

    require(runtime.update_batch({{source, 0}}, &error), error);
    const auto recovered = runtime.snapshot();
    require(!recovered.at(good).active && !recovered.at(guarded).active,
            "runtime did not recover after a later valid source epoch");
    require(recovered.at(good).value == 10 && recovered.at(guarded).value == 20,
            "recovery changed stable values incorrectly");
}

void test_private_frontier_failure() {
    doc::GraphBuilder builder;
    const auto a = builder.source("a", 1);
    const auto b = builder.source("b", 2);
    const auto good = builder.derived("good", {a}, [](const std::vector<doc::Value>& v) {
        return v.at(0) + 10;
    });
    const auto bad = builder.derived("bad", {b}, [](const std::vector<doc::Value>&) -> doc::Value {
        throw std::runtime_error("intentional failure");
    });
    doc::Runtime runtime(builder.build());
    std::string error;
    require(!runtime.stabilize(&error), "failing frontier unexpectedly stabilized");
    const auto snapshot = runtime.snapshot();
    require(!snapshot[good].value && !snapshot[bad].value,
            "one candidate published despite peer failure before the barrier");
    require(snapshot[good].active && snapshot[bad].active,
            "failed frontier obligations were lost");
}

void test_placement_generation_join_and_drain() {
    doc::PlacementTable placement;
    require(placement.join("A") && placement.join("B"), "resource join failed");
    require(placement.assign("eval(result)", "A"), "initial assignment failed");
    const auto old = placement.capture("eval(result)");
    require(old && placement.may_publish(*old), "current token rejected");
    require(placement.assign("eval(result)", "B"), "reassignment failed");
    require(!placement.may_publish(*old), "old placement generation still allowed to publish");
    const auto current = placement.capture("eval(result)");
    require(current && placement.may_publish(*current), "new generation rejected");
    require(placement.begin_drain("B"), "drain failed");
    require(!placement.may_publish(*current), "drained placement still allowed to publish");
    require(placement.finish_drain("B") && !placement.contains_resource("B"),
            "draining resource did not leave");
}


void test_versioned_recurrence_factorial_and_retention() {
    doc::GraphBuilder builder;
    const auto n = builder.source("n", 5);
    const auto acc = builder.source("acc", 1);
    const auto next_n = builder.derived("next_n", {n}, [](const std::vector<doc::Value>& v) {
        return v.at(0) == 0 ? 0 : v.at(0) - 1;
    }, "factorial.next-n.v1");
    const auto next_acc = builder.derived("next_acc", {n, acc}, [](const std::vector<doc::Value>& v) {
        return v.at(0) == 0 ? v.at(1) : v.at(0) * v.at(1);
    }, "factorial.next-acc.v1");

    doc::RecurrentRuntime recurrence(
        builder.build(), {{next_n, n}, {next_acc, acc}}, 3U);
    std::string error;
    const auto stop = recurrence.run_until(
        next_n, [](doc::Value value) { return value == 0; }, 10U, &error);
    require(stop && *stop == 4U, error);
    require(recurrence.observe(*stop, next_acc, &error) == 120, error);

    require(recurrence.demand_epoch(6U, &error), error);
    require(recurrence.materialized_through() == 6U,
            "recurrence did not instantiate the demanded finite prefix");
    require(recurrence.retained_epoch_count() == 3U &&
            recurrence.first_retained_epoch() == 4U,
            "recurrence retention window did not release old epochs");
    require(!recurrence.observe(0U, next_acc, &error),
            "released recurrence history remained observable");
}

void test_versioned_recurrence_multiple_state_step() {
    doc::GraphBuilder builder;
    const auto pc = builder.source("pc", 0);
    const auto counter = builder.source("counter", 3);
    const auto next_pc = builder.derived("next_pc", {pc, counter}, [](const std::vector<doc::Value>& v) {
        return v.at(1) == 0 ? 1 : v.at(0);
    }, "machine.pc.v1");
    const auto next_counter = builder.derived("next_counter", {counter}, [](const std::vector<doc::Value>& v) {
        return v.at(0) == 0 ? 0 : v.at(0) - 1;
    }, "machine.counter.v1");
    doc::RecurrentRuntime machine(
        builder.build(), {{next_pc, pc}, {next_counter, counter}});
    std::string error;
    require(machine.observe(3U, next_counter, &error) == 0, error);
    require(machine.observe(4U, next_pc, &error) == 1, error);

    std::mt19937_64 rng(0xD0C211ULL);
    std::uniform_int_distribution<doc::Value> value_dist(-40, 40);
    std::uniform_int_distribution<int> epoch_dist(0, 18);
    for (int trial = 0; trial < 80; ++trial) {
        const auto initial = value_dist(rng);
        auto delta = value_dist(rng);
        if (delta == 0) {
            delta = 1;
        }
        const auto demanded = static_cast<std::size_t>(epoch_dist(rng));
        doc::GraphBuilder affine;
        const auto x = affine.source("x", initial);
        const auto next_x = affine.derived(
            "next_x", {x}, [delta](const std::vector<doc::Value>& v) {
                return v.at(0) + delta;
            }, "affine.step.v1");
        doc::RecurrentRuntime repeated(affine.build(), {{next_x, x}});
        const auto observed = repeated.observe(demanded, next_x, &error);
        const auto expected = initial + static_cast<doc::Value>(demanded + 1U) * delta;
        require(observed && *observed == expected,
                "demanded recurrence prefix disagreed with direct iteration");
    }
}

struct CounterMachineConfiguration {
    doc::Value pc = 0;
    doc::Value first = 0;
    doc::Value second = 0;
};

CounterMachineConfiguration counter_machine_step(CounterMachineConfiguration state) {
    switch (state.pc) {
        case 0:
            ++state.first;
            state.pc = 1;
            break;
        case 1:
            ++state.second;
            state.pc = 2;
            break;
        case 2:
            if (state.first == 0) {
                state.pc = 4;
            } else {
                --state.first;
                state.pc = 3;
            }
            break;
        case 3:
            if (state.second == 0) {
                state.pc = 2;
            } else {
                --state.second;
                state.pc = 2;
            }
            break;
        case 4:
            break;
        default:
            throw std::runtime_error("reference counter machine reached an invalid instruction");
    }
    return state;
}

void test_two_counter_machine_recurrence_conformance() {
    doc::GraphBuilder builder;
    const auto pc = builder.source("pc", 0);
    const auto first = builder.source("first", 0);
    const auto second = builder.source("second", 0);
    const std::vector<doc::StateId> premises{pc, first, second};

    const auto component = [](std::size_t index) {
        return [index](const std::vector<doc::Value>& values) {
            const auto next = counter_machine_step(
                CounterMachineConfiguration{values.at(0), values.at(1), values.at(2)});
            if (index == 0U) return next.pc;
            if (index == 1U) return next.first;
            return next.second;
        };
    };

    const auto next_pc = builder.derived("next_pc", premises, component(0));
    const auto next_first = builder.derived("next_first", premises, component(1));
    const auto next_second = builder.derived("next_second", premises, component(2));

    doc::RecurrentRuntime recurrent(
        builder.build(),
        {{next_pc, pc}, {next_first, first}, {next_second, second}});

    CounterMachineConfiguration expected;
    std::string error;
    for (std::size_t epoch = 0; epoch < 9U; ++epoch) {
        const auto observed_pc = recurrent.observe(epoch, pc, &error);
        const auto observed_first = recurrent.observe(epoch, first, &error);
        const auto observed_second = recurrent.observe(epoch, second, &error);
        require(observed_pc && observed_first && observed_second, error);
        require(*observed_pc == expected.pc && *observed_first == expected.first &&
                    *observed_second == expected.second,
                "recurrent DOC prefix disagreed with the direct two-counter interpreter");
        expected = counter_machine_step(expected);
    }
}

void test_immutable_graph_versions() {
    doc::GraphBuilder initial;
    const auto a0 = initial.source("a", 2);
    const auto b0 = initial.source("b", 3);
    const auto sum0 = initial.derived("sum", {a0, b0}, add_function(), "add.v1");
    initial.derived("doubled", {sum0}, [](const std::vector<doc::Value>& v) {
        return v.at(0) * 2;
    }, "mul2.v1");

    doc::VersionedRuntime runtime(initial.build());
    std::string error;
    require(runtime.observe("doubled", &error) == 10, error);
    const auto old_token = runtime.capture();

    doc::GraphBuilder extended;
    const auto a1 = extended.source("a", 999);  // current source authority must be retained.
    const auto b1 = extended.source("b", 999);
    const auto sum1 = extended.derived("sum", {a1, b1}, add_function(), "add.v1");
    extended.derived("doubled", {sum1}, [](const std::vector<doc::Value>& v) {
        return v.at(0) * 2;
    }, "mul2.v1");
    const auto c1 = extended.source("c", 10);
    extended.derived("bonus", {c1}, [](const std::vector<doc::Value>& v) {
        return v.at(0) + 1;
    }, "bonus.v1");

    auto invalid_candidate = extended.build();
    invalid_candidate.users.at(a1).clear();
    const auto generation_before_rejection = runtime.generation();
    require(!runtime.commit(std::move(invalid_candidate), nullptr, &error),
            "forged graph-version candidate was accepted");
    require(runtime.generation() == generation_before_rejection &&
                runtime.observe("doubled", &error) == 10,
            "invalid graph-version candidate changed the current version");

    doc::GraphCommitReport first_report;
    require(runtime.commit(extended.build(), &first_report, &error), error);
    require(!runtime.may_publish(old_token),
            "candidate from an obsolete graph generation remained publishable");
    require(runtime.observe("doubled", &error) == 10, error);
    require(runtime.observe("bonus", &error) == 11, error);
    require(runtime.update_batch(
                std::vector<std::pair<std::string, doc::Value>>{{"c", 20}}, &error),
            error);
    require(runtime.observe("bonus", &error) == 21,
            "stable-name source update failed after a graph-version commit");
    require(first_report.reused_states >= 4U && first_report.new_states == 2U,
            "compatible graph region was not retained across extension");

    doc::GraphBuilder changed;
    const auto a2 = changed.source("a", 0);
    const auto b2 = changed.source("b", 0);
    const auto sum2 = changed.derived("sum", {a2, b2}, [](const std::vector<doc::Value>& v) {
        return v.at(0) - v.at(1);
    }, "subtract.v1");
    changed.derived("doubled", {sum2}, [](const std::vector<doc::Value>& v) {
        return v.at(0) * 2;
    }, "mul2.v1");

    doc::GraphCommitReport second_report;
    require(runtime.commit(changed.build(), &second_report, &error), error);
    require(runtime.observe("doubled", &error) == -2, error);
    require(second_report.activated_states >= 2U && second_report.retired_states == 2U,
            "changed and retired topology was not classified correctly");

    std::mt19937_64 rng(0x6A7A211ULL);
    std::uniform_int_distribution<doc::Value> source_dist(-20, 20);
    std::uniform_int_distribution<int> mode_dist(0, 2);
    for (int trial = 0; trial < 60; ++trial) {
        const auto x_value = source_dist(rng);
        const auto y_value = source_dist(rng);

        doc::GraphBuilder base;
        const auto x0 = base.source("x", x_value);
        const auto y0 = base.source("y", y_value);
        const auto combined0 = base.derived("combined", {x0, y0}, add_function(), "combine.add.v1");
        base.derived("out", {combined0}, [](const std::vector<doc::Value>& v) {
            return v.at(0) * 2;
        }, "scale.two.v1");
        doc::VersionedRuntime versions(base.build());
        require(versions.observe("out", &error) == (x_value + y_value) * 2, error);

        const int mode = mode_dist(rng);
        doc::GraphBuilder next;
        const auto x1 = next.source("x", 777);
        const auto y1 = next.source("y", 888);
        doc::StateId combined1 = 0;
        doc::Value combined_expected = 0;
        if (mode == 0) {
            combined1 = next.derived("combined", {x1, y1}, add_function(), "combine.add.v1");
            combined_expected = x_value + y_value;
        } else if (mode == 1) {
            combined1 = next.derived("combined", {x1, y1}, [](const std::vector<doc::Value>& v) {
                return v.at(0) - v.at(1);
            }, "combine.subtract.v1");
            combined_expected = x_value - y_value;
        } else {
            combined1 = next.derived("combined", {y1, x1}, add_function(), "combine.add-swapped.v1");
            combined_expected = y_value + x_value;
        }
        const auto scale = static_cast<doc::Value>(trial % 5 + 1);
        next.derived("out", {combined1}, [scale](const std::vector<doc::Value>& v) {
            return v.at(0) * scale;
        }, "scale." + std::to_string(scale) + ".v1");
        if ((trial % 3) == 0) {
            const auto extra = next.source("extra", 9);
            next.derived("extra_out", {extra}, [](const std::vector<doc::Value>& v) {
                return v.at(0) + 1;
            }, "extra.v1");
        }

        require(versions.commit(next.build(), nullptr, &error), error);
        require(versions.observe("out", &error) == combined_expected * scale,
                "graph-version commit disagreed with from-scratch interpretation");
    }
}

void test_finite_interaction_trace_conformance() {
    auto build_graph = [](doc::Value multiplier, std::string semantic_key) {
        doc::GraphBuilder builder;
        const auto a = builder.source("a", 2);
        const auto b = builder.source("b", 3);
        const auto sum = builder.derived("sum", {a, b}, add_function(), "sum-v1");
        const auto output = builder.derived(
            "output", {sum},
            [multiplier](const std::vector<doc::Value>& values) {
                return values.at(0) * multiplier;
            },
            std::move(semantic_key));
        return std::pair{builder.build(), output};
    };

    auto [initial_graph, initial_output] = build_graph(2, "output-times-two");
    doc::VersionedRuntime physical(initial_graph);
    std::string error;
    require(physical.stabilize(&error), error);

    std::vector<doc::Value> physical_observations;
    std::vector<doc::Value> abstract_observations;
    auto observe_and_compare = [&](const doc::Graph& graph, doc::StateId output,
                                   const std::vector<doc::Value>& sources) {
        const auto physical_value = physical.observe("output", &error);
        require(physical_value.has_value(), error);
        physical_observations.push_back(*physical_value);
        abstract_observations.push_back(
            doc::evaluate_from_scratch(graph, sources).at(output));
    };

    observe_and_compare(initial_graph, initial_output, {2, 3});
    require(physical.update_batch({{"a", 4}, {"b", 1}}, &error), error);
    observe_and_compare(initial_graph, initial_output, {4, 1});

    auto [next_graph, next_output] = build_graph(3, "output-times-three");
    doc::GraphCommitReport report;
    require(physical.commit(next_graph, &report, &error), error);
    observe_and_compare(next_graph, next_output, {4, 1});

    require(physical.update_batch({{"b", 2}}, &error), error);
    observe_and_compare(next_graph, next_output, {4, 2});

    require(physical_observations == abstract_observations,
            "physical observations diverged from abstract DOC over the finite interaction trace");
}

void test_transport_serialization_admission_and_tcp() {
    const auto role_key = doc::placement_role_key("eval:result");
    const doc::ValueEnvelope envelope{7U, 12U, role_key, 4U, -991};
    const auto bytes = doc::serialize(envelope);
    std::string error;
    const auto decoded = doc::deserialize(bytes, &error);
    require(decoded && decoded->state == envelope.state &&
            decoded->source_epoch == envelope.source_epoch &&
            decoded->role_key == envelope.role_key &&
            decoded->placement_generation == envelope.placement_generation &&
            decoded->value == envelope.value,
            error.empty() ? "transport round trip changed an envelope" : error);

    auto corrupted = bytes;
    corrupted.at(10) ^= 0x1U;
    require(!doc::deserialize(corrupted, &error),
            "corrupted transport envelope passed checksum validation");

    doc::ValueInbox inbox;
    require(inbox.admit(envelope, role_key, 4U) == doc::AdmissionResult::Accepted,
            "current transport message was not admitted");
    require(inbox.admit(envelope, role_key, 4U) == doc::AdmissionResult::Duplicate,
            "duplicate transport message was not identified");
    auto stale = envelope;
    stale.source_epoch = 11U;
    require(inbox.admit(stale, role_key, 4U) == doc::AdmissionResult::Stale,
            "older transport message was not rejected");
    auto conflict = envelope;
    conflict.value = 992;
    require(inbox.admit(conflict, role_key, 4U) == doc::AdmissionResult::Conflict,
            "same-epoch conflicting value was not rejected");
    require(inbox.admit(envelope, role_key, 5U) == doc::AdmissionResult::StaleGeneration,
            "obsolete placement generation was not rejected");
    require(inbox.admit(envelope, doc::placement_role_key("eval:other"), 4U) ==
                doc::AdmissionResult::WrongRole,
            "transport envelope was admitted for the wrong placement role");

    doc::LoopbackTcpChannel channel;
    require(channel.port() != 0U, "loopback TCP channel did not bind a port");
    require(channel.send(envelope, &error), error);
    const auto received = channel.receive(std::chrono::milliseconds(2000), &error);
    require(received && received->state == envelope.state && received->value == envelope.value,
            error.empty() ? "loopback TCP transport changed an envelope" : error);
}

void test_bounded_fail_stop_reconstruction() {
    doc::GraphBuilder builder;
    const auto source = builder.source("source", 3);
    const auto doubled = builder.derived("doubled", {source}, [](const std::vector<doc::Value>& v) {
        return v.at(0) * 2;
    }, "double.v1");
    const auto result = builder.derived("result", {doubled}, [](const std::vector<doc::Value>& v) {
        return v.at(0) + 2;
    }, "plus-two.v1");

    const auto graph = builder.build();
    doc::RecoverableRuntime runtime(graph);
    std::string error;
    require(runtime.observe(result, &error) == 8, error);
    require(runtime.commit_sources({{source, 7}}, &error), error);
    require(runtime.observe(result, &error) == 16, error);
    const auto failed_generation = runtime.generation();
    require(runtime.fail_stop_and_reconstruct(&error), error);
    require(!runtime.may_publish(failed_generation),
            "failed generation remained authoritative after reconstruction");
    require(runtime.observe(result, &error) == 16,
            "reconstruction from authoritative source facts changed the logical result");

    const auto journal = std::filesystem::temp_directory_path() /
                         "doc-durable-source-runtime-test.log";
    std::filesystem::remove(journal);
    {
        doc::RecoverableRuntime persisted(graph, journal.string());
        require(persisted.file_backed(), "file-backed recovery profile was not enabled");
        require(persisted.observe(result, &error) == 8, error);
        require(persisted.commit_sources({{source, 11}}, &error), error);
        require(persisted.observe(result, &error) == 24, error);
    }
    {
        std::ofstream torn(journal, std::ios::app | std::ios::binary);
        torn << "incomplete-final-source-record";  // no newline: ignored on replay.
    }
    {
        doc::RecoverableRuntime restarted(graph, journal.string());
        require(restarted.observe(result, &error) == 24,
                "process restart did not restore the durably acknowledged source snapshot");
        require(restarted.fail_stop_and_reconstruct(&error), error);
        require(restarted.observe(result, &error) == 24,
                "post-restart reconstruction changed the stable result");
    }
    std::filesystem::remove(journal);
}

void test_abrupt_placement_failure() {
    doc::PlacementTable placement;
    require(placement.join("A") && placement.join("B"), "resource join failed");
    require(placement.assign("role-1", "A") && placement.assign("role-2", "A"),
            "role assignment failed");
    const auto old = placement.capture("role-1");
    require(old && placement.fail("A"), "abrupt resource failure was not admitted");
    require(!placement.may_publish(*old),
            "failed resource generation remained publishable");
    const auto roles = placement.unassigned_roles();
    require(roles.size() == 2U, "failed resource roles were not exposed for reassignment");
    require(placement.assign("role-1", "B") && placement.assign("role-2", "B"),
            "failed roles could not be reassigned");
}



void test_network_placed_runtime_join_drain_and_fail_stop() {
    doc::GraphBuilder builder;
    const auto a = builder.source("a", 2);
    const auto b = builder.source("b", 3);
    const auto left = builder.derived("left", {a}, [](const std::vector<doc::Value>& v) {
        return v.at(0) * 10;
    }, "times-ten.v1");
    const auto right = builder.derived("right", {b}, [](const std::vector<doc::Value>& v) {
        return v.at(0) + 7;
    }, "plus-seven.v1");
    const auto result = builder.derived("result", {left, right}, [](const std::vector<doc::Value>& v) {
        return v.at(0) + v.at(1);
    }, "add.v1");

    doc::NetworkPlacedRuntime runtime(builder.build(), {"node-a", "node-b"});
    std::string error;
    require(runtime.observe(result, &error) == 30, error);
    const auto initial_stats = runtime.stats();
    require(initial_stats.transported_values >= 4U,
            "placed execution did not move premises through TCP transport");

    require(runtime.join_resource("node-c", &error), error);
    require(runtime.resource_count() == 3U, "live resource join did not add capacity");
    require(runtime.update_batch({{a, 4}, {b, 5}}, &error), error);
    require(runtime.observe(result, &error) == 52, error);

    const auto left_resource = runtime.resource_for(left);
    require(left_resource.has_value(), "placed definition lost its resource assignment");
    require(runtime.drain_resource(*left_resource, &error), error);
    require(runtime.resource_count() == 2U, "graceful drain did not remove the resource");
    require(runtime.observe(result, &error) == 52,
            "graceful drain changed the logical observation");

    const auto failed_resource = runtime.resource_for(right);
    require(failed_resource.has_value(), "placed definition lost its resource before failure test");
    require(runtime.fail_resource(*failed_resource, &error), error);
    require(runtime.resource_count() == 1U, "fail-stop loss did not remove the resource");
    require(runtime.observe(result, &error) == 52,
            "fail-stop reconstruction changed the logical observation");
    const auto final_stats = runtime.stats();
    require(final_stats.joins == 1U && final_stats.drains == 1U &&
                final_stats.failures == 1U,
            "placed runtime did not record join, drain, and failure transitions");
}


void test_network_placed_runtime_respects_logical_frontier() {
    std::atomic<doc::Value> latest_a{-1};

    doc::GraphBuilder builder;
    const auto source = builder.source("source", 1);
    const auto a = builder.derived("a", {source}, [&latest_a](const std::vector<doc::Value>& v) {
        const auto value = v.at(0) + 1;
        latest_a.store(value, std::memory_order_release);
        return value;
    }, "plus-one.v1");
    const auto b = builder.derived("b", {a}, [&latest_a](const std::vector<doc::Value>& v) {
        if (v.at(0) != latest_a.load(std::memory_order_acquire)) {
            throw std::runtime_error(
                "placed descendant evaluated before its active premise published");
        }
        return v.at(0) * 10;
    }, "times-ten.v1");

    doc::NetworkPlacedRuntime runtime(builder.build(), {"node-a", "node-b"});
    std::string error;
    require(runtime.observe(b, &error) == 20, error);
    require(runtime.update_batch({{source, 4}}, &error), error);
    require(runtime.observe(b, &error) == 50, error);
}

void test_recovery_serializes_source_changes() {
    std::mutex gate_mutex;
    std::condition_variable gate_cv;
    bool reconstruction_entered = false;
    bool release_reconstruction = false;
    std::atomic<int> calls{0};

    doc::GraphBuilder builder;
    const auto source = builder.source("source", 1);
    const auto result = builder.derived(
        "result", {source},
        [&](const std::vector<doc::Value>& v) {
            const int call = calls.fetch_add(1, std::memory_order_acq_rel) + 1;
            if (call == 2) {
                std::unique_lock lock(gate_mutex);
                reconstruction_entered = true;
                gate_cv.notify_all();
                gate_cv.wait(lock, [&] { return release_reconstruction; });
            }
            return v.at(0) * 2;
        },
        "double.v1");

    doc::RecoverableRuntime runtime(builder.build());
    std::string error;
    require(runtime.observe(result, &error) == 2, error);

    bool recovery_ok = false;
    std::string recovery_error;
    std::thread recovery([&] {
        recovery_ok = runtime.fail_stop_and_reconstruct(&recovery_error);
    });

    {
        std::unique_lock lock(gate_mutex);
        gate_cv.wait(lock, [&] { return reconstruction_entered; });
    }

    std::atomic<bool> update_attempted{false};
    std::atomic<bool> update_finished{false};
    bool update_ok = false;
    std::string update_error;
    std::thread update([&] {
        update_attempted.store(true, std::memory_order_release);
        update_ok = runtime.commit_sources({{source, 5}}, &update_error);
        update_finished.store(true, std::memory_order_release);
    });

    while (!update_attempted.load(std::memory_order_acquire)) {
        std::this_thread::yield();
    }
    require(!update_finished.load(std::memory_order_acquire),
            "authoritative source facts changed inside the recovery interval");

    {
        std::lock_guard lock(gate_mutex);
        release_reconstruction = true;
    }
    gate_cv.notify_all();
    recovery.join();
    update.join();

    require(recovery_ok, recovery_error);
    require(update_ok, update_error);
    require(runtime.observe(result, &error) == 10,
            "serialized post-recovery source update produced the wrong result");
}

void test_effect_journal_explicit_boundary() {
    const auto path = std::filesystem::temp_directory_path() /
                      "doc-effect-journal-runtime-test.log";
    std::filesystem::remove(path);
    std::string error;
    {
        doc::EffectJournal journal(path.string());
        require(journal.request("mail-1", "email", "hello", &error), error);
        require(journal.request("mail-1", "email", "hello", &error),
                "idempotent request replay was rejected");
        require(!journal.request("mail-1", "email", "different", &error),
                "conflicting request reused an idempotency key");
        require(journal.authorize("mail-1", &error), error);
        int calls = 0;
        require(journal.execute("mail-1", [&] { ++calls; }, &error), error);
        require(calls == 1, "authorized external action did not execute exactly once in-process");
        const auto record = journal.lookup("mail-1");
        require(record && record->status == doc::EffectStatus::Committed &&
                    record->attempts == 1U,
                "effect journal did not commit the successful action");

        require(journal.request("payment-uncertain", "payment", "42", &error), error);
        require(journal.authorize("payment-uncertain", &error), error);
        require(journal.begin("payment-uncertain", &error), error);
    }
    {
        std::ofstream torn(path, std::ios::app | std::ios::binary);
        torn << "incomplete-final-effect-record";  // no newline: ignored on replay.
    }
    {
        doc::EffectJournal reopened(path.string());
        const auto uncertain = reopened.lookup("payment-uncertain");
        require(uncertain && uncertain->status == doc::EffectStatus::InFlight,
                "journal restart hid an uncertain in-flight external effect");
        require(reopened.resolve_inflight("payment-uncertain", false,
                                          "operator confirmed no charge", &error), error);
        const auto resolved = reopened.lookup("payment-uncertain");
        require(resolved && resolved->status == doc::EffectStatus::Failed,
                "explicit effect uncertainty was not resolved");
    }
    std::filesystem::remove(path);

    const auto malformed = std::filesystem::temp_directory_path() /
                           "doc-effect-journal-malformed-test.log";
    {
        std::ofstream output(malformed, std::ios::binary);
        output << checked_effect_line("R\t78\t6b\t70\t");
        output << checked_effect_line("C\t78\t6b\t70\t");  // commit without authorize/begin
    }
    bool rejected = false;
    try {
        doc::EffectJournal invalid(malformed.string());
        (void)invalid;
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    require(rejected, "journal replay accepted an impossible effect transition");
    std::filesystem::remove(malformed);


    const auto corrupt = std::filesystem::temp_directory_path() /
                         "doc-effect-journal-checksum-test.log";
    {
        std::ofstream output(corrupt, std::ios::binary);
        output << "R\t78\t6b\t70\t\t0\n";
    }
    rejected = false;
    try {
        doc::EffectJournal invalid(corrupt.string());
        (void)invalid;
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    require(rejected, "journal replay accepted a checksum-corrupted effect record");
    std::filesystem::remove(corrupt);
}

void test_typed_immutable_publication_and_reclamation() {
    doc::ImmutableObjectStore store;
    doc::ImmutableStateSlot slot;

    auto first = store.construct(doc::TypedValue::tuple({
        doc::TypedValue(std::int64_t{7}),
        doc::TypedValue::tagged("ok", doc::TypedValue(std::int64_t{9})),
    }));
    auto equal = store.construct(doc::TypedValue::tuple({
        doc::TypedValue(std::int64_t{7}),
        doc::TypedValue::tagged("ok", doc::TypedValue(std::int64_t{9})),
    }));
    require(*first == *equal, "typed structural equality rejected equal immutable values");

    slot.publish(first);
    first.reset();
    auto pin = slot.pin();
    require(pin && store.live_objects() == 2U,
            "published immutable value was not protected by the state slot");

    auto replacement = store.construct(doc::TypedValue::tagged(
        "error", doc::TypedValue(std::int64_t{5})));
    slot.publish(replacement);
    replacement.reset();
    equal.reset();
    store.collect();
    require(store.live_objects() == 2U,
            "active read pin did not protect the replaced immutable value");

    pin.reset();
    store.collect();
    require(store.live_objects() == 1U && store.tracked_objects() == 1U,
            "unreachable immutable publications were not reclaimed automatically");
}

void test_logical_availability_with_eviction_and_reconstruction() {
    doc::ImmutableObjectStore store;
    const doc::TypedValue expected = doc::TypedValue::tuple({
        doc::TypedValue(std::int64_t{4}),
        doc::TypedValue::tagged("derived", doc::TypedValue(std::int64_t{10})),
    });

    std::size_t reconstructions = 0U;
    doc::ReconstructibleStateSlot slot([&] {
        ++reconstructions;
        return store.construct(doc::TypedValue::tuple({
            doc::TypedValue(std::int64_t{4}),
            doc::TypedValue::tagged("derived", doc::TypedValue(std::int64_t{10})),
        }));
    });

    slot.publish(store.construct(expected));
    auto active_pin = slot.pin();
    require(active_pin && *active_pin == expected && slot.resident(),
            "initial reconstructible publication was not resident and observable");

    slot.evict();
    require(!slot.resident() && *active_pin == expected,
            "eviction invalidated a value already protected by an active observation");

    auto reconstructed = slot.pin();
    require(reconstructed && *reconstructed == expected && slot.resident(),
            "logical value was not reconstructed before observation");
    require(reconstructed.get() != active_pin.get() && reconstructions == 1U,
            "evicted state did not receive one fresh immutable reconstruction");

    active_pin.reset();
    store.collect();
    require(store.live_objects() == 1U,
            "obsolete evicted materialization survived after its active pin was released");

    slot.evict();
    reconstructed.reset();
    store.collect();
    require(store.live_objects() == 0U,
            "unresident reconstructible state retained an unnecessary physical object");
}


void test_repair_admissible_seed_validation() {
    doc::GraphBuilder builder;
    const auto source = builder.source("source", 1);
    const auto derived = builder.derived(
        "derived", {source}, [](const std::vector<doc::Value>& values) {
            return values.at(0) + 1;
        }, "plus-one.v1");
    const auto graph = builder.build();

    auto seed_with = [&](doc::Value source_value, std::optional<doc::Value> derived_value,
                         std::uint8_t active) {
        doc::RuntimeSeed seed;
        seed.values.resize(graph.states.size());
        seed.active.assign(graph.states.size(), 0U);
        seed.values[source] = source_value;
        seed.values[derived] = derived_value;
        seed.active[derived] = active;
        return seed;
    };

    bool rejected = false;
    try {
        doc::Runtime invalid(graph, seed_with(1, 999, 0U));
        (void)invalid;
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    require(rejected, "locally inconsistent inactive runtime seed was accepted");

    rejected = false;
    try {
        auto source_active = seed_with(1, 2, 0U);
        source_active.active[source] = 1U;
        doc::Runtime invalid(graph, std::move(source_active));
        (void)invalid;
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    require(rejected, "runtime seed activated a source state");

    doc::Runtime stable(graph, seed_with(1, 2, 0U));
    std::string error;
    require(stable.observe(derived, &error) == 2, error);

    doc::Runtime repair(graph, seed_with(1, 999, 1U));
    require(repair.observe(derived, &error) == 2,
            "active repair seed did not restore local satisfaction");
}

void test_recurrence_historical_stopping_and_carry_authority() {
    doc::GraphBuilder builder;
    const auto source = builder.source("source", 0);
    const auto fixed = builder.source("fixed", 7);
    const auto next = builder.derived(
        "next", {source}, [](const std::vector<doc::Value>& values) {
            return values.at(0) + 1;
        }, "increment.v1");
    const auto observed_fixed = builder.derived(
        "observed_fixed", {fixed}, [](const std::vector<doc::Value>& values) {
            return values.at(0);
        }, "identity.v1");
    const auto graph = builder.build();

    doc::RecurrentRuntime recurrence(graph, {{next, source}});
    std::string error;
    require(recurrence.observe(5U, next, &error) == 6, error);
    const auto found = recurrence.run_until(
        next, [](doc::Value value) { return value == 1; }, 5U, &error);
    require(found && *found == 0U,
            "stopping scan read the latest epoch instead of the named historical epoch");
    require(recurrence.observe(5U, observed_fixed, &error) == 7,
            "uncarried recurrence source did not use its declared epoch-local fact");

    bool rejected = false;
    try {
        doc::RecurrentRuntime duplicate(
            graph, {{next, source}, {observed_fixed, source}});
        (void)duplicate;
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    require(rejected, "recurrence accepted two carry authorities for one next source");

    doc::RecurrentRuntime retained(graph, {{next, source}}, 2U);
    require(retained.observe(5U, next, &error) == 6, error);
    error.clear();
    require(!retained.run_until(
                next, [](doc::Value value) { return value == 1; }, 5U, &error),
            "stopping scan silently inspected released recurrence history");
    require(error.find("released") != std::string::npos,
            "released-history stopping scan did not report its retention boundary");
}

void test_graph_version_authority_transitions_and_tokens() {
    std::string error;
    doc::GraphBuilder old_builder;
    const auto old_a = old_builder.source("a", 1);
    const auto old_x = old_builder.derived(
        "x", {old_a}, [](const std::vector<doc::Value>& values) {
            return values.at(0) + 1;
        }, "x.plus-one.v1");
    old_builder.derived(
        "out", {old_x}, [](const std::vector<doc::Value>& values) {
            return values.at(0) * 10;
        }, "out.times-ten.v1");

    doc::VersionedRuntime runtime(old_builder.build());
    require(runtime.observe("out", &error) == 20, error);

    doc::GraphBuilder next_builder;
    const auto next_x = next_builder.source("x", 7);
    next_builder.derived(
        "out", {next_x}, [](const std::vector<doc::Value>& values) {
            return values.at(0) * 10;
        }, "out.times-ten.v1");
    doc::GraphCommitReport report;
    require(runtime.commit(next_builder.build(), &report, &error), error);
    require(runtime.observe("out", &error) == 70,
            "derived-to-source graph replacement retained a stale descendant");
    require(report.activated_states >= 1U,
            "authority-role transition did not activate its descendant region");

    const auto token = runtime.capture();
    doc::GraphBuilder other_builder;
    other_builder.source("x", 7);
    doc::VersionedRuntime other(other_builder.build());
    require(!other.may_publish(token),
            "graph-generation token from another runtime instance was accepted");

    doc::GraphBuilder reordered;
    reordered.source("inserted", 2);
    const auto reordered_x = reordered.source("x", 0);
    reordered.derived(
        "out", {reordered_x}, [](const std::vector<doc::Value>& values) {
            return values.at(0) * 10;
        }, "out.times-ten.v1");
    require(runtime.commit(reordered.build(), nullptr, &error), error);
    require(runtime.observe("out", &error) == 70,
            "stable-name observation failed after numeric graph indexes changed");
}

void test_reconstruction_publication_serialization() {
    doc::ImmutableObjectStore store;
    const auto old_value = store.construct(doc::TypedValue(std::int64_t{1}));
    const auto new_value = store.construct(doc::TypedValue(std::int64_t{2}));

    std::mutex mutex;
    std::condition_variable cv;
    bool reconstruction_started = false;
    bool may_finish = false;
    doc::ReconstructibleStateSlot slot([&] {
        std::unique_lock lock(mutex);
        reconstruction_started = true;
        cv.notify_all();
        cv.wait(lock, [&] { return may_finish; });
        return old_value;
    });

    doc::PublishedValue reconstructed;
    std::thread reconstruction([&] { reconstructed = slot.pin(); });
    {
        std::unique_lock lock(mutex);
        cv.wait(lock, [&] { return reconstruction_started; });
    }
    std::thread publication([&] { slot.publish(new_value); });
    {
        std::lock_guard lock(mutex);
        may_finish = true;
    }
    cv.notify_all();
    reconstruction.join();
    publication.join();

    require(reconstructed &&
                std::get<std::int64_t>(reconstructed->payload()) == 1,
            "reconstruction did not return its complete admitted value");
    const auto final_value = slot.pin();
    require(final_value && std::get<std::int64_t>(final_value->payload()) == 2,
            "older reconstruction overwrote a newer publication");
}

}  // namespace

int main() {
    const std::vector<std::pair<std::string, std::function<void()>>> tests = {
        {"representation and initialization", test_representation_and_initialization},
        {"repair-admissible seed validation", test_repair_admissible_seed_validation},
        {"zero-premise definition", test_zero_premise_definition},
        {"equal source no-op and atomic rejection", test_equal_source_noop_and_atomic_rejection},
        {"locality and equality cutoff", test_locality_and_equality_cutoff},
        {"conservative always-propagate profile", test_conservative_always_propagate_profile},
        {"multiple contributors through explicit merge", test_multiple_contributors_through_explicit_merge},
        {"transitive ready frontier", test_transitive_ready_frontier},
        {"multipath activation and expansion", test_multipath_activation_and_expansion},
        {"one evaluation per epoch", test_one_evaluation_per_epoch},
        {"9,600 randomized differential epochs", test_randomized_differential_9600_epochs},
        {"random frontier-subset schedule agreement", test_random_frontier_subset_schedule_agreement},
        {"sequential/parallel agreement", test_sequential_parallel_agreement},
        {"source-epoch serialization", test_source_epoch_serialization},
        {"observation waits for committed epoch", test_observation_waits_for_committed_epoch},
        {"persistent pool and owner participation", test_persistent_pool_and_owner_participation},
        {"accepted source persists across frontier failure", test_accepted_source_persists_across_frontier_failure},
        {"private frontier failure", test_private_frontier_failure},
        {"placement generation join/drain", test_placement_generation_join_and_drain},
        {"versioned recurrence factorial and retention", test_versioned_recurrence_factorial_and_retention},
        {"recurrence historical stopping and carry authority", test_recurrence_historical_stopping_and_carry_authority},
        {"versioned recurrence multiple-state step", test_versioned_recurrence_multiple_state_step},
        {"two-counter machine recurrence conformance", test_two_counter_machine_recurrence_conformance},
        {"immutable graph versions", test_immutable_graph_versions},
        {"graph-version authority transitions and tokens", test_graph_version_authority_transitions_and_tokens},
        {"finite interaction-trace conformance", test_finite_interaction_trace_conformance},
        {"transport serialization admission and TCP", test_transport_serialization_admission_and_tcp},
        {"bounded fail-stop reconstruction", test_bounded_fail_stop_reconstruction},
        {"abrupt placement failure", test_abrupt_placement_failure},
        {"network placed runtime join/drain/fail-stop", test_network_placed_runtime_join_drain_and_fail_stop},
        {"network placed runtime respects logical frontier", test_network_placed_runtime_respects_logical_frontier},
        {"recovery serializes source changes", test_recovery_serializes_source_changes},
        {"effect journal explicit boundary", test_effect_journal_explicit_boundary},
        {"typed immutable publication and reclamation", test_typed_immutable_publication_and_reclamation},
        {"logical availability with eviction and reconstruction", test_logical_availability_with_eviction_and_reconstruction},
        {"reconstruction/publication serialization", test_reconstruction_publication_serialization},
    };

    for (const auto& [name, test] : tests) {
        try {
            test();
            std::cout << "[PASS] " << name << '\n';
        } catch (const std::exception& error) {
            std::cerr << "[FAIL] " << name << ": " << error.what() << '\n';
            return 1;
        }
    }
    std::cout << tests.size() << " named suites passed\n";
    return 0;
}
