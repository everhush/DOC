#include "workload_generator.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>

namespace doc::bench {

namespace {

bool is_prime(std::uint64_t value) {
    if (value < 2U) return false;
    if (value % 2U == 0U) return value == 2U;
    for (std::uint64_t divisor = 3U; divisor <= value / divisor; divisor += 2U) {
        if (value % divisor == 0U) return false;
    }
    return true;
}

Value leaf_value(Value source, const ReductionConfig& config) {
    if (!config.expensive) return source;
    const auto offset = source < 0 ? static_cast<std::uint64_t>(-source) : static_cast<std::uint64_t>(source);
    return static_cast<Value>(count_primes(config.interval_start + offset, config.interval_length));
}

}  // namespace

std::uint64_t count_primes(std::uint64_t begin, std::uint64_t length) {
    std::uint64_t count = 0;
    for (std::uint64_t value = begin; value < begin + length; ++value) {
        if (is_prime(value)) ++count;
    }
    return count;
}

ReductionWorkload make_reduction(const ReductionConfig& config) {
    if (config.leaves == 0U) throw std::invalid_argument("reduction needs at least one leaf");
    GraphBuilder builder;
    std::vector<StateId> sources;
    std::vector<StateId> current;
    sources.reserve(config.leaves);
    current.reserve(config.leaves);
    for (std::size_t i = 0; i < config.leaves; ++i) {
        const auto source = builder.source("source-" + std::to_string(i), static_cast<Value>(i));
        sources.push_back(source);
        current.push_back(builder.derived("leaf-" + std::to_string(i), {source}, [config](const std::vector<Value>& v) {
            return leaf_value(v.at(0), config);
        }));
    }
    std::size_t level = 0;
    while (current.size() > 1U) {
        std::vector<StateId> next;
        next.reserve((current.size() + 1U) / 2U);
        for (std::size_t i = 0; i < current.size(); i += 2U) {
            if (i + 1U == current.size()) {
                next.push_back(current[i]);
            } else {
                next.push_back(builder.derived(
                    "sum-" + std::to_string(level) + "-" + std::to_string(i / 2U),
                    {current[i], current[i + 1U]},
                    [](const std::vector<Value>& v) { return v.at(0) + v.at(1); }));
            }
        }
        current = std::move(next);
        ++level;
    }
    const auto root = current.front();
    return ReductionWorkload{builder.build(), sources, {}, root, config};
}

Value direct_reduction(const ReductionConfig& config, const std::vector<Value>& source_values) {
    if (source_values.size() != config.leaves) throw std::invalid_argument("source count mismatch");
    std::vector<Value> current;
    current.reserve(source_values.size());
    for (const auto source : source_values) current.push_back(leaf_value(source, config));
    while (current.size() > 1U) {
        std::vector<Value> next;
        next.reserve((current.size() + 1U) / 2U);
        for (std::size_t i = 0; i < current.size(); i += 2U) {
            next.push_back(i + 1U == current.size() ? current[i] : current[i] + current[i + 1U]);
        }
        current = std::move(next);
    }
    return current.front();
}

Value financial_unit_value(Value revenue, Value material, Value payroll,
                           Value overhead, std::size_t periods) {
    // A deterministic fixed-point projection over monthly cash flows.  It is
    // deliberately ordinary integer arithmetic: the benchmark measures the
    // persistence strategy, not a specialized numerical library.
    Value cash = revenue - material - payroll - overhead;
    Value discounted_total = 0;
    Value working_revenue = revenue;
    Value working_cost = material + payroll + overhead;
    for (std::size_t month = 0; month < periods; ++month) {
        const Value season = static_cast<Value>(month % 12U) - 6;
        working_revenue += working_revenue / 400 + season * 3;
        working_cost += working_cost / 500 + static_cast<Value>(month % 5U);
        cash = working_revenue - working_cost;
        discounted_total += cash / static_cast<Value>(100U + month / 12U);
    }
    return discounted_total;
}

FinancialWorkload make_financial(const FinancialConfig& config,
                                 const std::vector<Value>& revenue,
                                 const std::vector<Value>& material,
                                 const std::vector<Value>& payroll,
                                 const std::vector<Value>& overhead) {
    if (config.units == 0U || revenue.size() != config.units || material.size() != config.units ||
        payroll.size() != config.units || overhead.size() != config.units) {
        throw std::invalid_argument("financial source count mismatch");
    }
    GraphBuilder builder;
    FinancialWorkload workload;
    workload.config = config;
    workload.revenue_sources.reserve(config.units);
    workload.material_sources.reserve(config.units);
    workload.payroll_sources.reserve(config.units);
    workload.overhead_sources.reserve(config.units);
    workload.forecasts.reserve(config.units);
    std::vector<StateId> current;
    current.reserve(config.units);
    for (std::size_t i = 0; i < config.units; ++i) {
        const auto r = builder.source("revenue-" + std::to_string(i), revenue[i]);
        const auto m = builder.source("material-" + std::to_string(i), material[i]);
        const auto p = builder.source("payroll-" + std::to_string(i), payroll[i]);
        const auto o = builder.source("overhead-" + std::to_string(i), overhead[i]);
        workload.revenue_sources.push_back(r);
        workload.material_sources.push_back(m);
        workload.payroll_sources.push_back(p);
        workload.overhead_sources.push_back(o);
        const auto forecast = builder.derived(
            "forecast-" + std::to_string(i), {r, m, p, o},
            [periods = config.periods](const std::vector<Value>& v) {
                return financial_unit_value(v.at(0), v.at(1), v.at(2), v.at(3), periods);
            });
        workload.forecasts.push_back(forecast);
        current.push_back(forecast);
    }
    std::size_t level = 0;
    while (current.size() > 1U) {
        std::vector<StateId> next;
        next.reserve((current.size() + 1U) / 2U);
        for (std::size_t i = 0; i < current.size(); i += 2U) {
            if (i + 1U == current.size()) {
                next.push_back(current[i]);
            } else {
                next.push_back(builder.derived(
                    "financial-sum-" + std::to_string(level) + "-" + std::to_string(i / 2U),
                    {current[i], current[i + 1U]},
                    [](const std::vector<Value>& v) { return v.at(0) + v.at(1); }));
            }
        }
        current = std::move(next);
        ++level;
    }
    workload.root = current.front();
    workload.graph = builder.build();
    return workload;
}

Value direct_financial(const FinancialConfig& config,
                       const std::vector<Value>& revenue,
                       const std::vector<Value>& material,
                       const std::vector<Value>& payroll,
                       const std::vector<Value>& overhead) {
    if (revenue.size() != config.units || material.size() != config.units ||
        payroll.size() != config.units || overhead.size() != config.units) {
        throw std::invalid_argument("financial source count mismatch");
    }
    Value total = 0;
    for (std::size_t i = 0; i < config.units; ++i) {
        total += financial_unit_value(revenue[i], material[i], payroll[i], overhead[i], config.periods);
    }
    return total;
}

BitonicWorkload make_bitonic(std::size_t size, const std::vector<Value>& initial_values) {
    if (size < 2U || (size & (size - 1U)) != 0U || initial_values.size() != size) {
        throw std::invalid_argument("bitonic size must be a power of two and match initial values");
    }
    GraphBuilder builder;
    std::vector<StateId> sources;
    std::vector<StateId> current;
    sources.reserve(size);
    current.reserve(size);
    for (std::size_t i = 0; i < size; ++i) {
        const auto source = builder.source("input-" + std::to_string(i), initial_values[i]);
        sources.push_back(source);
        current.push_back(source);
    }

    std::size_t comparators = 0U;
    std::size_t stage = 0U;
    for (std::size_t k = 2U; k <= size; k *= 2U) {
        for (std::size_t j = k / 2U; j > 0U; j /= 2U) {
            auto next = current;
            for (std::size_t i = 0; i < size; ++i) {
                const auto partner = i ^ j;
                if (partner <= i) continue;
                const auto low = builder.derived(
                    "cmp-" + std::to_string(stage) + "-" + std::to_string(i) + "-min",
                    {current[i], current[partner]},
                    [](const std::vector<Value>& v) { return std::min(v.at(0), v.at(1)); });
                const auto high = builder.derived(
                    "cmp-" + std::to_string(stage) + "-" + std::to_string(i) + "-max",
                    {current[i], current[partner]},
                    [](const std::vector<Value>& v) { return std::max(v.at(0), v.at(1)); });
                const bool ascending = (i & k) == 0U;
                next[i] = ascending ? low : high;
                next[partner] = ascending ? high : low;
                ++comparators;
            }
            current = std::move(next);
            ++stage;
        }
    }
    return BitonicWorkload{builder.build(), sources, current, comparators};
}

std::vector<Value> direct_bitonic(std::vector<Value> values) {
    const auto size = values.size();
    if (size < 2U || (size & (size - 1U)) != 0U) {
        throw std::invalid_argument("bitonic size must be a power of two");
    }
    for (std::size_t k = 2U; k <= size; k *= 2U) {
        for (std::size_t j = k / 2U; j > 0U; j /= 2U) {
            for (std::size_t i = 0; i < size; ++i) {
                const auto partner = i ^ j;
                if (partner <= i) continue;
                const bool ascending = (i & k) == 0U;
                if ((values[i] > values[partner]) == ascending) {
                    std::swap(values[i], values[partner]);
                }
            }
        }
    }
    return values;
}

}  // namespace doc::bench
