#pragma once

#include <cstdint>
#include <functional>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace doc {

enum class EffectStatus {
    Requested,
    Authorized,
    InFlight,
    Committed,
    Failed,
};

struct EffectSnapshot {
    std::string id;
    std::string kind;
    std::string payload;
    EffectStatus status = EffectStatus::Requested;
    std::uint64_t attempts = 0;
    std::string note;
};

// An explicit append-only effect boundary. The journal makes intent,
// authorization, attempts, and outcomes durable. It deliberately leaves an
// in-flight record after a crash between external execution and commit; the
// application or operator must resolve that uncertainty rather than receiving
// a false exactly-once guarantee.
class EffectJournal {
public:
    explicit EffectJournal(std::string path);

    bool request(std::string id, std::string kind, std::string payload,
                 std::string* error = nullptr);
    bool authorize(const std::string& id, std::string* error = nullptr);
    bool begin(const std::string& id, std::string* error = nullptr);
    bool commit(const std::string& id, std::string note = {},
                std::string* error = nullptr);
    bool fail(const std::string& id, std::string note,
              std::string* error = nullptr);
    bool resolve_inflight(const std::string& id, bool committed,
                          std::string note,
                          std::string* error = nullptr);

    bool execute(const std::string& id,
                 const std::function<void()>& external_action,
                 std::string* error = nullptr);

    [[nodiscard]] std::optional<EffectSnapshot> lookup(const std::string& id) const;
    [[nodiscard]] std::vector<EffectSnapshot> snapshot() const;

private:
    bool load(std::string* error);
    bool append(char event, const EffectSnapshot& record,
                const std::string& note,
                std::string* error);

    std::string path_;
    mutable std::mutex mutex_;
    std::unordered_map<std::string, EffectSnapshot> records_;
};

}  // namespace doc
