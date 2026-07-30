#pragma once

#include "doc/runtime.hpp"

#include <cstddef>
#include <cstdint>
#include <vector>

namespace doc::bench {

struct ReductionConfig {
    std::size_t leaves = 2048;
    std::uint64_t interval_start = 100000;
    std::uint64_t interval_length = 2000;
    bool expensive = true;
};

struct ReductionWorkload {
    Graph graph;
    std::vector<StateId> sources;
    std::vector<StateId> leaves;
    StateId root = 0;
    ReductionConfig config;
};


struct FinancialConfig {
    std::size_t units = 4096;
    std::size_t periods = 360;
};

struct FinancialWorkload {
    Graph graph;
    std::vector<StateId> revenue_sources;
    std::vector<StateId> material_sources;
    std::vector<StateId> payroll_sources;
    std::vector<StateId> overhead_sources;
    std::vector<StateId> forecasts;
    StateId root = 0;
    FinancialConfig config;
};

struct BitonicWorkload {
    Graph graph;
    std::vector<StateId> sources;
    std::vector<StateId> outputs;
    std::size_t comparators = 0;
};

[[nodiscard]] std::uint64_t count_primes(std::uint64_t begin, std::uint64_t length);
[[nodiscard]] ReductionWorkload make_reduction(const ReductionConfig& config);
[[nodiscard]] Value direct_reduction(const ReductionConfig& config,
                                     const std::vector<Value>& source_values);
[[nodiscard]] Value financial_unit_value(Value revenue, Value material, Value payroll,
                                          Value overhead, std::size_t periods);
[[nodiscard]] FinancialWorkload make_financial(const FinancialConfig& config,
                                               const std::vector<Value>& revenue,
                                               const std::vector<Value>& material,
                                               const std::vector<Value>& payroll,
                                               const std::vector<Value>& overhead);
[[nodiscard]] Value direct_financial(const FinancialConfig& config,
                                     const std::vector<Value>& revenue,
                                     const std::vector<Value>& material,
                                     const std::vector<Value>& payroll,
                                     const std::vector<Value>& overhead);
[[nodiscard]] BitonicWorkload make_bitonic(std::size_t size,
                                           const std::vector<Value>& initial_values);
[[nodiscard]] std::vector<Value> direct_bitonic(std::vector<Value> values);

}  // namespace doc::bench
