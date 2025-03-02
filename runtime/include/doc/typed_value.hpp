#pragma once

#include <atomic>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>
#include <variant>
#include <vector>

namespace doc {

class TypedValue {
public:
    using Tuple = std::vector<TypedValue>;
    struct Tagged;
    using TuplePtr = std::shared_ptr<const Tuple>;
    using TaggedPtr = std::shared_ptr<const Tagged>;
    using Payload = std::variant<std::monostate, bool, std::int64_t, TuplePtr, TaggedPtr>;

    TypedValue() = default;
    explicit TypedValue(bool value);
    explicit TypedValue(std::int64_t value);

    static TypedValue tuple(Tuple values);
    static TypedValue tagged(std::string tag, TypedValue value);

    [[nodiscard]] const Payload& payload() const noexcept;
    friend bool operator==(const TypedValue& left, const TypedValue& right);

private:
    explicit TypedValue(Payload payload);
    Payload payload_;
};

struct TypedValue::Tagged {
    std::string tag;
    std::shared_ptr<const TypedValue> value;
};

using PublishedValue = std::shared_ptr<const TypedValue>;

// Tracks immutable publications without owning them. Physical reclamation is
// automatic when no slot or pin retains a shared reference.
class ImmutableObjectStore {
public:
    [[nodiscard]] PublishedValue construct(TypedValue value);
    void collect();
    [[nodiscard]] std::size_t tracked_objects() const;
    [[nodiscard]] std::size_t live_objects() const;

private:
    mutable std::mutex mutex_;
    std::uint64_t next_id_ = 1U;
    std::unordered_map<std::uint64_t, std::weak_ptr<const TypedValue>> objects_;
};

class ImmutableStateSlot {
public:
    void publish(PublishedValue value);
    [[nodiscard]] PublishedValue pin() const;

private:
    mutable std::atomic<PublishedValue> current_;
};

// A logical state may remain available even when its current physical
// materialization has been evicted. The reconstruction function represents
// authoritative retained information (for example current sources plus pure
// definitions or a durable checkpoint). Existing pins keep an evicted object
// alive until their use completes; a later pin reconstructs and republishes a
// complete immutable value.
class ReconstructibleStateSlot {
public:
    using Reconstructor = std::function<PublishedValue()>;

    explicit ReconstructibleStateSlot(Reconstructor reconstructor);

    void publish(PublishedValue value);
    void evict();
    [[nodiscard]] PublishedValue pin() const;
    [[nodiscard]] bool resident() const noexcept;

private:
    mutable std::atomic<PublishedValue> current_;
    Reconstructor reconstructor_;
    // Serializes reconstruction admission with publication and eviction so a
    // completed reconstruction cannot overwrite a newer publication.
    mutable std::mutex reconstruction_mutex_;
};

}  // namespace doc
