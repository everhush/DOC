#include "doc/typed_value.hpp"

#include <algorithm>
#include <stdexcept>

namespace doc {

TypedValue::TypedValue(bool value) : payload_(value) {}
TypedValue::TypedValue(std::int64_t value) : payload_(value) {}
TypedValue::TypedValue(Payload payload) : payload_(std::move(payload)) {}

TypedValue TypedValue::tuple(Tuple values) {
    return TypedValue(Payload{std::make_shared<const Tuple>(std::move(values))});
}

TypedValue TypedValue::tagged(std::string tag, TypedValue value) {
    auto payload = std::make_shared<const TypedValue>(std::move(value));
    return TypedValue(Payload{std::make_shared<const Tagged>(Tagged{std::move(tag), std::move(payload)})});
}

const TypedValue::Payload& TypedValue::payload() const noexcept {
    return payload_;
}

bool operator==(const TypedValue& left, const TypedValue& right) {
    if (left.payload_.index() != right.payload_.index()) {
        return false;
    }
    if (std::holds_alternative<std::monostate>(left.payload_)) {
        return true;
    }
    if (const auto* value = std::get_if<bool>(&left.payload_)) {
        return *value == std::get<bool>(right.payload_);
    }
    if (const auto* value = std::get_if<std::int64_t>(&left.payload_)) {
        return *value == std::get<std::int64_t>(right.payload_);
    }
    if (const auto* tuple = std::get_if<TypedValue::TuplePtr>(&left.payload_)) {
        return **tuple == *std::get<TypedValue::TuplePtr>(right.payload_);
    }
    const auto& left_tagged = *std::get<TypedValue::TaggedPtr>(left.payload_);
    const auto& right_tagged = *std::get<TypedValue::TaggedPtr>(right.payload_);
    return left_tagged.tag == right_tagged.tag &&
           *left_tagged.value == *right_tagged.value;
}

PublishedValue ImmutableObjectStore::construct(TypedValue value) {
    auto object = std::make_shared<const TypedValue>(std::move(value));
    std::lock_guard lock(mutex_);
    objects_.emplace(next_id_++, object);
    return object;
}

void ImmutableObjectStore::collect() {
    std::lock_guard lock(mutex_);
    std::erase_if(objects_, [](const auto& item) { return item.second.expired(); });
}

std::size_t ImmutableObjectStore::tracked_objects() const {
    std::lock_guard lock(mutex_);
    return objects_.size();
}

std::size_t ImmutableObjectStore::live_objects() const {
    std::lock_guard lock(mutex_);
    return static_cast<std::size_t>(std::count_if(
        objects_.begin(), objects_.end(), [](const auto& item) {
            return !item.second.expired();
        }));
}

void ImmutableStateSlot::publish(PublishedValue value) {
    if (!value) {
        throw std::invalid_argument("cannot publish an empty immutable object");
    }
    current_.store(std::move(value), std::memory_order_release);
}

PublishedValue ImmutableStateSlot::pin() const {
    return current_.load(std::memory_order_acquire);
}

ReconstructibleStateSlot::ReconstructibleStateSlot(Reconstructor reconstructor)
    : reconstructor_(std::move(reconstructor)) {
    if (!reconstructor_) {
        throw std::invalid_argument("reconstructible state requires an authoritative reconstructor");
    }
}

void ReconstructibleStateSlot::publish(PublishedValue value) {
    if (!value) {
        throw std::invalid_argument("cannot publish an empty immutable object");
    }
    std::lock_guard lock(reconstruction_mutex_);
    current_.store(std::move(value), std::memory_order_release);
}

void ReconstructibleStateSlot::evict() {
    std::lock_guard lock(reconstruction_mutex_);
    current_.store({}, std::memory_order_release);
}

PublishedValue ReconstructibleStateSlot::pin() const {
    auto value = current_.load(std::memory_order_acquire);
    if (value) {
        return value;
    }

    std::lock_guard lock(reconstruction_mutex_);
    value = current_.load(std::memory_order_acquire);
    if (value) {
        return value;
    }

    value = reconstructor_();
    if (!value) {
        throw std::runtime_error("authoritative reconstruction returned no value");
    }
    current_.store(value, std::memory_order_release);
    return value;
}

bool ReconstructibleStateSlot::resident() const noexcept {
    return static_cast<bool>(current_.load(std::memory_order_acquire));
}

}  // namespace doc
