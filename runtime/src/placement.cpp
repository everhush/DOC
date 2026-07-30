#include "doc/placement.hpp"

#include <algorithm>

namespace doc {

bool PlacementTable::join(std::string resource) {
    std::lock_guard lock(mutex_);
    if (resource.empty()) {
        return false;
    }
    draining_.erase(resource);
    return resources_.insert(std::move(resource)).second;
}

bool PlacementTable::assign(std::string role, const std::string& resource) {
    std::lock_guard lock(mutex_);
    if (role.empty() || !resources_.contains(resource) || draining_.contains(resource)) {
        return false;
    }
    auto& assignment = assignments_[role];
    if (assignment.resource != resource) {
        assignment.resource = resource;
        ++assignment.generation;
    }
    return true;
}

bool PlacementTable::begin_drain(const std::string& resource) {
    std::lock_guard lock(mutex_);
    if (!resources_.contains(resource)) {
        return false;
    }
    draining_.insert(resource);
    for (auto& [role, assignment] : assignments_) {
        (void)role;
        if (assignment.resource == resource) {
            ++assignment.generation;
            assignment.resource.clear();
        }
    }
    return true;
}

bool PlacementTable::fail(const std::string& resource) {
    std::lock_guard lock(mutex_);
    if (!resources_.contains(resource)) {
        return false;
    }
    for (auto& [role, assignment] : assignments_) {
        (void)role;
        if (assignment.resource == resource) {
            ++assignment.generation;
            assignment.resource.clear();
        }
    }
    draining_.erase(resource);
    resources_.erase(resource);
    return true;
}

bool PlacementTable::finish_drain(const std::string& resource) {
    std::lock_guard lock(mutex_);
    if (!draining_.contains(resource)) {
        return false;
    }
    draining_.erase(resource);
    resources_.erase(resource);
    return true;
}

std::optional<PlacementToken> PlacementTable::capture(const std::string& role) const {
    std::lock_guard lock(mutex_);
    const auto iterator = assignments_.find(role);
    if (iterator == assignments_.end() || iterator->second.resource.empty()) {
        return std::nullopt;
    }
    return PlacementToken{role, iterator->second.resource, iterator->second.generation};
}

bool PlacementTable::may_publish(const PlacementToken& token) const {
    std::lock_guard lock(mutex_);
    const auto iterator = assignments_.find(token.role);
    return iterator != assignments_.end() &&
           iterator->second.resource == token.resource &&
           iterator->second.generation == token.generation &&
           resources_.contains(token.resource) &&
           !draining_.contains(token.resource);
}

bool PlacementTable::contains_resource(const std::string& resource) const {
    std::lock_guard lock(mutex_);
    return resources_.contains(resource);
}

bool PlacementTable::is_draining(const std::string& resource) const {
    std::lock_guard lock(mutex_);
    return draining_.contains(resource);
}

std::vector<std::string> PlacementTable::unassigned_roles() const {
    std::lock_guard lock(mutex_);
    std::vector<std::string> roles;
    for (const auto& [role, assignment] : assignments_) {
        if (assignment.resource.empty()) {
            roles.push_back(role);
        }
    }
    std::sort(roles.begin(), roles.end());
    return roles;
}

std::vector<std::string> PlacementTable::roles_on_resource(const std::string& resource) const {
    std::lock_guard lock(mutex_);
    std::vector<std::string> roles;
    for (const auto& [role, assignment] : assignments_) {
        if (assignment.resource == resource) {
            roles.push_back(role);
        }
    }
    std::sort(roles.begin(), roles.end());
    return roles;
}

std::vector<std::string> PlacementTable::resources() const {
    std::lock_guard lock(mutex_);
    std::vector<std::string> output(resources_.begin(), resources_.end());
    std::sort(output.begin(), output.end());
    return output;
}

}  // namespace doc
