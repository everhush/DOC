#include "workload_generator.hpp"

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <random>
#include <string>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;

template <class F>
double milliseconds(F&& function) {
    const auto begin = Clock::now();
    function();
    const auto end = Clock::now();
    return std::chrono::duration<double, std::milli>(end - begin).count();
}

int run_density(std::size_t changed) {
    doc::bench::ReductionConfig config;
    config.leaves = 2048;
    config.interval_start = 100000;
    config.interval_length = 1200;
    auto workload = doc::bench::make_reduction(config);
    std::vector<doc::Value> values(config.leaves);
    for (std::size_t i = 0; i < values.size(); ++i) values[i] = static_cast<doc::Value>(i);

    doc::Runtime runtime(workload.graph);
    std::string error;
    if (!runtime.stabilize(&error)) throw std::runtime_error(error);
    std::vector<std::pair<doc::StateId, doc::Value>> batch;
    for (std::size_t i = 0; i < std::min(changed, values.size()); ++i) {
        values[i] += 5000;
        batch.emplace_back(workload.sources[i], values[i]);
    }
    runtime.reset_stats();
    doc::Value doc_value = 0;
    const auto doc_ms = milliseconds([&] {
        if (!runtime.update_batch(batch, &error)) throw std::runtime_error(error);
        doc_value = *runtime.value(workload.root);
    });
    doc::Value direct_value = 0;
    const auto direct_ms = milliseconds([&] { direct_value = doc::bench::direct_reduction(config, values); });
    if (doc_value != direct_value) throw std::runtime_error("direct/DOC mismatch");
    const auto stats = runtime.stats();
    std::cout << "scenario=density changed=" << changed
              << " direct_ms=" << direct_ms
              << " doc_ms=" << doc_ms
              << " evaluations=" << stats.evaluations
              << " cutoffs=" << stats.equality_cutoffs
              << " value=" << doc_value << '\n';
    return 0;
}

int run_cold() {
    doc::bench::ReductionConfig config;
    config.leaves = 2048;
    config.interval_length = 1200;
    auto workload = doc::bench::make_reduction(config);
    std::vector<doc::Value> values(config.leaves);
    for (std::size_t i = 0; i < values.size(); ++i) values[i] = static_cast<doc::Value>(i);
    doc::Value direct_value = 0;
    const auto direct_ms = milliseconds([&] { direct_value = doc::bench::direct_reduction(config, values); });
    doc::Runtime runtime(workload.graph);
    std::string error;
    const auto doc_ms = milliseconds([&] {
        if (!runtime.stabilize(&error)) throw std::runtime_error(error);
    });
    const auto doc_value = *runtime.value(workload.root);
    if (doc_value != direct_value) throw std::runtime_error("cold direct/DOC mismatch");
    std::cout << "scenario=cold direct_ms=" << direct_ms << " doc_ms=" << doc_ms
              << " evaluations=" << runtime.stats().evaluations
              << " participants=" << runtime.participant_capacity() << '\n';
    return 0;
}

int run_cutoff() {
    doc::GraphBuilder builder;
    const auto a = builder.source("a", 2);
    const auto b = builder.source("b", 3);
    const auto sum = builder.derived("sum", {a, b}, [](const std::vector<doc::Value>& v) { return v[0] + v[1]; });
    const auto expensive = builder.derived("expensive", {sum}, [](const std::vector<doc::Value>& v) {
        doc::Value result = v[0];
        for (int i = 0; i < 2000000; ++i) result = (result * 48271 + 1) % 2147483647;
        return result;
    });
    doc::Runtime runtime(builder.build());
    std::string error;
    if (!runtime.observe(expensive, &error)) throw std::runtime_error(error);
    runtime.reset_stats();
    const auto elapsed = milliseconds([&] {
        if (!runtime.update_batch({{a, 4}, {b, 1}}, &error)) throw std::runtime_error(error);
    });
    const auto stats = runtime.stats();
    std::cout << "scenario=cutoff elapsed_ms=" << elapsed
              << " evaluations=" << stats.evaluations
              << " cutoffs=" << stats.equality_cutoffs << '\n';
    return 0;
}

int run_parallel() {
    doc::bench::ReductionConfig config;
    config.leaves = 40;
    config.interval_start = 500000;
    config.interval_length = 25000;
    auto workload = doc::bench::make_reduction(config);
    doc::Runtime runtime(workload.graph);
    std::string error;
    const auto elapsed = milliseconds([&] {
        if (!runtime.stabilize(&error)) throw std::runtime_error(error);
    });
    const auto stats = runtime.stats();
    std::cout << "scenario=parallel elapsed_ms=" << elapsed
              << " participants=" << runtime.participant_capacity()
              << " evaluations=" << stats.evaluations
              << " owner_jobs=" << stats.owner_jobs
              << " worker_jobs=" << stats.worker_jobs << '\n';
    return 0;
}

int run_dense_cheap() {
    doc::bench::ReductionConfig config;
    config.leaves = 4096;
    config.expensive = false;
    auto workload = doc::bench::make_reduction(config);
    doc::Runtime runtime(workload.graph);
    std::string error;
    if (!runtime.stabilize(&error)) throw std::runtime_error(error);
    runtime.reset_stats();
    std::vector<doc::Value> values(config.leaves);
    double doc_ms = milliseconds([&] {
        for (int epoch = 0; epoch < 30; ++epoch) {
            std::vector<std::pair<doc::StateId, doc::Value>> batch;
            batch.reserve(config.leaves);
            for (std::size_t i = 0; i < config.leaves; ++i) {
                values[i] = static_cast<doc::Value>(i + epoch + 1);
                batch.emplace_back(workload.sources[i], values[i]);
            }
            if (!runtime.update_batch(batch, &error)) throw std::runtime_error(error);
        }
    });
    doc::Value direct_value = 0;
    double direct_ms = milliseconds([&] {
        for (int epoch = 0; epoch < 30; ++epoch) {
            for (std::size_t i = 0; i < config.leaves; ++i) {
                values[i] = static_cast<doc::Value>(i + epoch + 1);
            }
            direct_value = doc::bench::direct_reduction(config, values);
        }
    });
    if (runtime.value(workload.root) != direct_value) throw std::runtime_error("dense-cheap mismatch");
    std::cout << "scenario=dense-cheap direct_ms=" << direct_ms << " doc_ms=" << doc_ms
              << " evaluations=" << runtime.stats().evaluations << '\n';
    return 0;
}


class SumTree {
public:
    explicit SumTree(const std::vector<doc::Value>& leaves) {
        size_ = 1U;
        while (size_ < leaves.size()) size_ *= 2U;
        tree_.assign(size_ * 2U, 0);
        for (std::size_t i = 0; i < leaves.size(); ++i) tree_[size_ + i] = leaves[i];
        for (std::size_t i = size_; i-- > 1U;) tree_[i] = tree_[i * 2U] + tree_[i * 2U + 1U];
    }
    void set(std::size_t index, doc::Value value) {
        std::size_t node = size_ + index;
        tree_[node] = value;
        while (node > 1U) {
            node /= 2U;
            tree_[node] = tree_[node * 2U] + tree_[node * 2U + 1U];
        }
    }
    [[nodiscard]] doc::Value total() const { return tree_.at(1U); }
private:
    std::size_t size_ = 0U;
    std::vector<doc::Value> tree_;
};

int run_financial(std::size_t changed) {
    doc::bench::FinancialConfig config;
    std::vector<doc::Value> revenue(config.units);
    std::vector<doc::Value> material(config.units);
    std::vector<doc::Value> payroll(config.units);
    std::vector<doc::Value> overhead(config.units);
    for (std::size_t i = 0; i < config.units; ++i) {
        revenue[i] = 250000 + static_cast<doc::Value>((i * 7919U) % 90000U);
        material[i] = 70000 + static_cast<doc::Value>((i * 3571U) % 30000U);
        payroll[i] = 60000 + static_cast<doc::Value>((i * 1237U) % 25000U);
        overhead[i] = 20000 + static_cast<doc::Value>((i * 331U) % 12000U);
    }
    auto workload = doc::bench::make_financial(config, revenue, material, payroll, overhead);
    doc::Runtime runtime(workload.graph);
    std::string error;
    if (!runtime.stabilize(&error)) throw std::runtime_error(error);

    std::vector<doc::Value> cached_leaves(config.units);
    for (std::size_t i = 0; i < config.units; ++i) {
        cached_leaves[i] = doc::bench::financial_unit_value(
            revenue[i], material[i], payroll[i], overhead[i], config.periods);
    }
    SumTree cached(cached_leaves);
    if (cached.total() != *runtime.value(workload.root)) throw std::runtime_error("financial initial mismatch");

    changed = std::min(changed, config.units);
    std::vector<std::pair<doc::StateId, doc::Value>> batch;
    batch.reserve(changed * 2U);
    for (std::size_t i = 0; i < changed; ++i) {
        revenue[i] += 2500 + static_cast<doc::Value>(i % 17U);
        payroll[i] += 400 + static_cast<doc::Value>(i % 11U);
        batch.emplace_back(workload.revenue_sources[i], revenue[i]);
        batch.emplace_back(workload.payroll_sources[i], payroll[i]);
    }

    doc::Value direct_value = 0;
    const auto direct_ms = milliseconds([&] {
        direct_value = doc::bench::direct_financial(config, revenue, material, payroll, overhead);
    });
    doc::Value cached_value = 0;
    const auto cached_ms = milliseconds([&] {
        for (std::size_t i = 0; i < changed; ++i) {
            cached.set(i, doc::bench::financial_unit_value(
                revenue[i], material[i], payroll[i], overhead[i], config.periods));
        }
        cached_value = cached.total();
    });
    runtime.reset_stats();
    doc::Value doc_value = 0;
    const auto doc_ms = milliseconds([&] {
        if (!runtime.update_batch(batch, &error)) throw std::runtime_error(error);
        doc_value = *runtime.value(workload.root);
    });
    if (doc_value != direct_value || cached_value != direct_value) {
        throw std::runtime_error("financial direct/cached/DOC mismatch");
    }
    const auto stats = runtime.stats();
    std::cout << "scenario=financial changed=" << changed
              << " units=" << config.units
              << " periods=" << config.periods
              << " direct_ms=" << direct_ms
              << " cached_ms=" << cached_ms
              << " doc_ms=" << doc_ms
              << " evaluations=" << stats.evaluations
              << " cutoffs=" << stats.equality_cutoffs
              << " value=" << doc_value << '\n';
    return 0;
}

int run_bitonic(std::size_t changed) {
    std::mt19937_64 random(2026U);
    std::vector<doc::Value> values(512);
    for (auto& value : values) value = static_cast<doc::Value>(random() % 1000000U);
    auto workload = doc::bench::make_bitonic(values.size(), values);
    std::vector<doc::Value> direct_output;
    const auto direct_cold_ms = milliseconds([&] { direct_output = doc::bench::direct_bitonic(values); });
    doc::Runtime runtime(workload.graph);
    std::string error;
    const auto cold_ms = milliseconds([&] {
        if (!runtime.stabilize(&error)) throw std::runtime_error(error);
    });
    std::vector<doc::Value> graph_output;
    for (const auto state : workload.outputs) graph_output.push_back(*runtime.value(state));
    if (graph_output != direct_output) throw std::runtime_error("cold bitonic mismatch");

    changed = std::min(changed, values.size());
    std::vector<std::pair<doc::StateId, doc::Value>> batch;
    batch.reserve(changed);
    for (std::size_t i = 0; i < changed; ++i) {
        values[i] += static_cast<doc::Value>(999999 + i * 104729);
        batch.emplace_back(workload.sources[i], values[i]);
    }
    const auto direct_update_ms = milliseconds([&] { direct_output = doc::bench::direct_bitonic(values); });
    runtime.reset_stats();
    const auto update_ms = milliseconds([&] {
        if (!runtime.update_batch(batch, &error)) throw std::runtime_error(error);
    });
    graph_output.clear();
    for (const auto state : workload.outputs) graph_output.push_back(*runtime.value(state));
    auto expected = values;
    std::sort(expected.begin(), expected.end());
    if (graph_output != expected || graph_output != direct_output) throw std::runtime_error("bitonic output mismatch");
    const auto stats = runtime.stats();
    std::cout << "scenario=bitonic changed=" << changed
              << " states=" << workload.graph.states.size()
              << " comparators=" << workload.comparators
              << " direct_cold_ms=" << direct_cold_ms
              << " doc_cold_ms=" << cold_ms
              << " direct_update_ms=" << direct_update_ms
              << " doc_update_ms=" << update_ms
              << " update_evaluations=" << stats.evaluations
              << " cutoffs=" << stats.equality_cutoffs << '\n';
    return 0;
}
}

int main(int argc, char** argv) {
    try {
        std::cout << std::fixed << std::setprecision(6);
        const std::string scenario = argc > 1 ? argv[1] : "cold";
        if (scenario == "cold") return run_cold();
        if (scenario == "density") return run_density(argc > 2 ? static_cast<std::size_t>(std::stoull(argv[2])) : 1U);
        if (scenario == "cutoff") return run_cutoff();
        if (scenario == "parallel") return run_parallel();
        if (scenario == "dense-cheap") return run_dense_cheap();
        if (scenario == "financial") return run_financial(argc > 2 ? static_cast<std::size_t>(std::stoull(argv[2])) : 1U);
        if (scenario == "bitonic") return run_bitonic(argc > 2 ? static_cast<std::size_t>(std::stoull(argv[2])) : 1U);
        std::cerr << "usage: doc_benchmark cold|density N|cutoff|parallel|dense-cheap|financial N|bitonic [changed]\n";
        return 2;
    } catch (const std::exception& error) {
        std::cerr << "benchmark failed: " << error.what() << '\n';
        return 1;
    }
}
