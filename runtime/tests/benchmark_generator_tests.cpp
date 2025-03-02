#include "workload_generator.hpp"

#include <algorithm>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}
}

int main() {
    try {
        for (std::uint64_t begin = 0; begin < 100; begin += 7) {
            std::uint64_t naive = 0;
            for (std::uint64_t value = begin; value < begin + 50; ++value) {
                bool prime = value >= 2;
                for (std::uint64_t d = 2; d <= value / d && prime; ++d) prime = value % d != 0;
                if (prime) ++naive;
            }
            require(doc::bench::count_primes(begin, 50) == naive, "prime counter mismatch");
        }

        doc::bench::ReductionConfig config;
        config.leaves = 64;
        config.interval_start = 1000;
        config.interval_length = 200;
        auto reduction = doc::bench::make_reduction(config);
        doc::Runtime runtime(reduction.graph);
        std::string error;
        const auto result = runtime.observe(reduction.root, &error);
        require(result.has_value(), error);
        std::vector<doc::Value> sources(config.leaves);
        for (std::size_t i = 0; i < sources.size(); ++i) sources[i] = static_cast<doc::Value>(i);
        require(*result == doc::bench::direct_reduction(config, sources), "reduction generator differs from direct path");

        doc::bench::FinancialConfig financial_config;
        financial_config.units = 32;
        financial_config.periods = 24;
        std::vector<doc::Value> revenue(financial_config.units);
        std::vector<doc::Value> material(financial_config.units);
        std::vector<doc::Value> payroll(financial_config.units);
        std::vector<doc::Value> overhead(financial_config.units);
        for (std::size_t i = 0; i < financial_config.units; ++i) {
            revenue[i] = 200000 + static_cast<doc::Value>(i * 100);
            material[i] = 50000 + static_cast<doc::Value>(i * 10);
            payroll[i] = 45000 + static_cast<doc::Value>(i * 5);
            overhead[i] = 15000 + static_cast<doc::Value>(i * 3);
        }
        auto financial = doc::bench::make_financial(
            financial_config, revenue, material, payroll, overhead);
        doc::Runtime financial_runtime(financial.graph);
        require(financial_runtime.stabilize(&error), error);
        require(*financial_runtime.value(financial.root) == doc::bench::direct_financial(
                    financial_config, revenue, material, payroll, overhead),
                "financial graph differs from direct reevaluation");
        revenue[3] += 999;
        payroll[3] += 101;
        require(financial_runtime.update_batch(
                    {{financial.revenue_sources[3], revenue[3]},
                     {financial.payroll_sources[3], payroll[3]}},
                    &error),
                error);
        require(*financial_runtime.value(financial.root) == doc::bench::direct_financial(
                    financial_config, revenue, material, payroll, overhead),
                "incremental financial graph differs from direct reevaluation");

        std::mt19937_64 random(2026U);
        std::vector<doc::Value> values(512);
        for (auto& value : values) value = static_cast<doc::Value>(random() % 100000U);
        auto bitonic = doc::bench::make_bitonic(values.size(), values);
        require(bitonic.comparators == 11520U, "unexpected comparator count");
        require(bitonic.graph.states.size() == 512U + 23040U, "unexpected bitonic graph size");
        doc::Runtime bitonic_runtime(bitonic.graph);
        require(bitonic_runtime.stabilize(&error), error);
        std::vector<doc::Value> graph_output;
        for (const auto output : bitonic.outputs) graph_output.push_back(*bitonic_runtime.value(output));
        const auto direct = doc::bench::direct_bitonic(values);
        auto sorted = values;
        std::sort(sorted.begin(), sorted.end());
        require(graph_output == direct, "graph bitonic differs from direct network");
        require(graph_output == sorted, "bitonic network differs from std::sort");

        std::uint64_t previous_evaluations = 0;
        for (const std::size_t changed : {1U, 8U, 64U, 256U, 512U}) {
            auto updated_values = values;
            auto density_workload = doc::bench::make_bitonic(updated_values.size(), updated_values);
            doc::Runtime density_runtime(density_workload.graph);
            require(density_runtime.stabilize(&error), error);

            std::vector<std::pair<doc::StateId, doc::Value>> batch;
            batch.reserve(changed);
            for (std::size_t i = 0; i < changed; ++i) {
                updated_values[i] += static_cast<doc::Value>(999999 + i * 104729);
                batch.emplace_back(density_workload.sources[i], updated_values[i]);
            }

            density_runtime.reset_stats();
            require(density_runtime.update_batch(batch, &error), error);
            graph_output.clear();
            for (const auto output : density_workload.outputs) {
                graph_output.push_back(*density_runtime.value(output));
            }
            const auto density_direct = doc::bench::direct_bitonic(updated_values);
            sorted = updated_values;
            std::sort(sorted.begin(), sorted.end());
            require(graph_output == density_direct,
                    "incremental bitonic graph differs from direct network");
            require(graph_output == sorted,
                    "incremental bitonic graph differs from std::sort");

            const auto evaluations = density_runtime.stats().evaluations;
            require(evaluations >= previous_evaluations,
                    "bitonic evaluation count decreased as update density increased");
            previous_evaluations = evaluations;
            if (changed == 1U) {
                require(evaluations < 23040U,
                        "one-input bitonic update failed to reuse graph work");
            }
            if (changed == 512U) {
                require(evaluations == 23040U,
                        "all-input bitonic update did not evaluate the complete graph");
                require(density_runtime.stats().equality_cutoffs == 0U,
                        "all-input bitonic update unexpectedly cut off a path");
            }
        }

        std::cout << "[PASS] benchmark generator, direct equivalence, and bitonic density curve\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "[FAIL] " << error.what() << '\n';
        return 1;
    }
}
