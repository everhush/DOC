#include "doc/runtime.hpp"

#include <iostream>

int main() {
    doc::GraphBuilder builder;
    const auto a = builder.source("a", 2);
    const auto b = builder.source("b", 3);
    const auto sum = builder.derived("sum", {a, b}, [](const std::vector<doc::Value>& input) {
        return input.at(0) + input.at(1);
    });
    const auto doubled = builder.derived("doubled", {sum}, [](const std::vector<doc::Value>& input) {
        return input.at(0) * 2;
    });

    doc::Runtime runtime(builder.build());
    std::string error;
    const auto initial = runtime.observe(doubled, &error);
    if (!initial) {
        std::cerr << error << '\n';
        return 1;
    }
    std::cout << "initial=" << *initial << '\n';

    runtime.reset_stats();
    if (!runtime.update_batch({{a, 4}, {b, 1}}, &error)) {
        std::cerr << error << '\n';
        return 1;
    }
    const auto later = runtime.value(doubled);
    const auto stats = runtime.stats();
    std::cout << "later=" << *later
              << " evaluations=" << stats.evaluations
              << " cutoffs=" << stats.equality_cutoffs << '\n';
    return 0;
}
