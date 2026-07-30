#pragma once

#include <cstdint>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace doc {

struct PlacementToken {
    std::string role;
    std::string resource;
    std::uint64_t generation = 0;
};

class PlacementTable {
public:
    bool join(std::string resource);
    bool assign(std::string role, const std::string& resource);
    bool begin_drain(const std::string& resource);
    bool finish_drain(const std::string& resource);
    bool fail(const std::string& resource);

    [[nodiscard]] std::optional<PlacementToken> capture(const std::string& role) const;
    [[nodiscard]] bool may_publish(const PlacementToken& token) const;
    [[nodiscard]] bool contains_resource(const std::string& resource) const;
    [[nodiscard]] bool is_draining(const std::string& resource) const;
    [[nodiscard]] std::vector<std::string> unassigned_roles() const;
    [[nodiscard]] std::vector<std::string> roles_on_resource(const std::string& resource) const;
    [[nodiscard]] std::vector<std::string> resources() const;

private:
    struct Assignment {
        std::string resource;
        std::uint64_t generation = 0;
    };

    mutable std::mutex mutex_;
    std::unordered_set<std::string> resources_;
    std::unordered_set<std::string> draining_;
    std::unordered_map<std::string, Assignment> assignments_;
};

}  // namespace doc
