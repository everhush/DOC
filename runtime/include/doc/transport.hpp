#pragma once

#include "doc/runtime.hpp"

#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

namespace doc {

[[nodiscard]] std::uint64_t placement_role_key(const std::string& role) noexcept;

struct ValueEnvelope {
    StateId state = 0;
    std::uint64_t source_epoch = 0;
    std::uint64_t role_key = 0;
    std::uint64_t placement_generation = 0;
    Value value = 0;
};

[[nodiscard]] std::vector<std::uint8_t> serialize(const ValueEnvelope& envelope);
[[nodiscard]] std::optional<ValueEnvelope> deserialize(
    const std::vector<std::uint8_t>& bytes,
    std::string* error = nullptr);

enum class AdmissionResult {
    Accepted,
    Duplicate,
    Stale,
    Conflict,
    WrongRole,
    StaleGeneration,
};

class ValueInbox {
public:
    AdmissionResult admit(const ValueEnvelope& envelope,
                          std::uint64_t expected_role_key,
                          std::uint64_t current_placement_generation);
    [[nodiscard]] std::optional<Value> value(StateId state,
                                              std::uint64_t role_key) const;
    [[nodiscard]] std::optional<std::uint64_t> epoch(StateId state,
                                                      std::uint64_t role_key) const;

private:
    struct Key {
        StateId state = 0;
        std::uint64_t role_key = 0;

        friend bool operator==(const Key&, const Key&) = default;
    };
    struct KeyHash {
        std::size_t operator()(const Key& key) const noexcept;
    };
    struct Entry {
        std::uint64_t source_epoch = 0;
        Value value = 0;
    };
    std::unordered_map<Key, Entry, KeyHash> entries_;
};

// A real TCP loopback channel used as a bounded transport witness. It moves
// serialized immutable envelopes over a stream socket; it is not a production
// cluster protocol.
class LoopbackTcpChannel {
public:
    LoopbackTcpChannel();
    ~LoopbackTcpChannel();

    LoopbackTcpChannel(const LoopbackTcpChannel&) = delete;
    LoopbackTcpChannel& operator=(const LoopbackTcpChannel&) = delete;

    bool send(const ValueEnvelope& envelope, std::string* error = nullptr) const;
    [[nodiscard]] std::optional<ValueEnvelope> receive(
        std::chrono::milliseconds timeout,
        std::string* error = nullptr);
    [[nodiscard]] std::uint16_t port() const noexcept;

private:
    void accept_loop();

    int listener_ = -1;
    std::uint16_t port_ = 0;
    std::thread thread_;
    mutable std::mutex mutex_;
    std::condition_variable cv_;
    bool stopping_ = false;
    std::deque<std::vector<std::uint8_t>> queue_;
    std::string background_error_;
};

}  // namespace doc
