#include "doc/effect.hpp"

#include <fcntl.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <charconv>
#include <cstring>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string_view>

namespace doc {

namespace {

std::string hex_encode(const std::string& input) {
    constexpr char digits[] = "0123456789abcdef";
    std::string output;
    output.reserve(input.size() * 2U);
    for (const char character : input) {
        const auto byte = static_cast<unsigned char>(character);
        output.push_back(digits[byte >> 4U]);
        output.push_back(digits[byte & 0x0fU]);
    }
    return output;
}

std::optional<std::string> hex_decode(const std::string& input) {
    if (input.size() % 2U != 0U) {
        return std::nullopt;
    }
    auto nibble = [](char value) -> std::optional<unsigned char> {
        if (value >= '0' && value <= '9') {
            return static_cast<unsigned char>(value - '0');
        }
        if (value >= 'a' && value <= 'f') {
            return static_cast<unsigned char>(value - 'a' + 10);
        }
        return std::nullopt;
    };
    std::string output;
    output.reserve(input.size() / 2U);
    for (std::size_t index = 0; index < input.size(); index += 2U) {
        const auto high = nibble(input[index]);
        const auto low = nibble(input[index + 1U]);
        if (!high || !low) {
            return std::nullopt;
        }
        output.push_back(static_cast<char>((*high << 4U) | *low));
    }
    return output;
}

std::uint64_t checksum(std::string_view text) {
    std::uint64_t hash = 1469598103934665603ULL;
    for (const char character : text) {
        const auto byte = static_cast<unsigned char>(character);
        hash ^= byte;
        hash *= 1099511628211ULL;
    }
    return hash;
}

bool parse_u64(std::string_view text, std::uint64_t* value) {
    const auto result = std::from_chars(text.data(), text.data() + text.size(), *value);
    return result.ec == std::errc{} && result.ptr == text.data() + text.size();
}

bool write_all(int fd, const char* data, std::size_t size) {
    std::size_t written = 0;
    while (written < size) {
        const auto result = ::write(fd, data + written, size - written);
        if (result < 0) {
            if (errno == EINTR) {
                continue;
            }
            return false;
        }
        if (result == 0) {
            return false;
        }
        written += static_cast<std::size_t>(result);
    }
    return true;
}

std::vector<std::string> split_tabs(const std::string& line) {
    std::vector<std::string> fields;
    std::size_t start = 0;
    while (true) {
        const auto tab = line.find('\t', start);
        if (tab == std::string::npos) {
            fields.push_back(line.substr(start));
            break;
        }
        fields.push_back(line.substr(start, tab - start));
        start = tab + 1U;
    }
    return fields;
}

}  // namespace

EffectJournal::EffectJournal(std::string path) : path_(std::move(path)) {
    if (path_.empty()) {
        throw std::invalid_argument("effect journal path must not be empty");
    }
    std::string error;
    if (!load(&error)) {
        throw std::runtime_error(error);
    }
}

bool EffectJournal::request(std::string id, std::string kind, std::string payload,
                            std::string* error) {
    std::lock_guard lock(mutex_);
    if (id.empty() || kind.empty()) {
        if (error) {
            *error = "effect request id and kind must be non-empty";
        }
        return false;
    }
    const auto existing = records_.find(id);
    if (existing != records_.end()) {
        const bool same = existing->second.kind == kind && existing->second.payload == payload;
        if (!same && error) {
            *error = "effect id already names a different request";
        }
        return same;
    }
    EffectSnapshot record{std::move(id), std::move(kind), std::move(payload),
                          EffectStatus::Requested, 0U, {}};
    if (!append('R', record, {}, error)) {
        return false;
    }
    records_.emplace(record.id, std::move(record));
    return true;
}

bool EffectJournal::authorize(const std::string& id, std::string* error) {
    std::lock_guard lock(mutex_);
    const auto iterator = records_.find(id);
    if (iterator == records_.end() ||
        (iterator->second.status != EffectStatus::Requested &&
         iterator->second.status != EffectStatus::Failed)) {
        if (error) {
            *error = "only requested or failed effects may be authorized";
        }
        return false;
    }
    if (!append('A', iterator->second, {}, error)) {
        return false;
    }
    iterator->second.status = EffectStatus::Authorized;
    iterator->second.note.clear();
    return true;
}

bool EffectJournal::begin(const std::string& id, std::string* error) {
    std::lock_guard lock(mutex_);
    const auto iterator = records_.find(id);
    if (iterator == records_.end() || iterator->second.status != EffectStatus::Authorized) {
        if (error) {
            *error = "only an authorized effect may begin";
        }
        return false;
    }
    if (!append('B', iterator->second, {}, error)) {
        return false;
    }
    iterator->second.status = EffectStatus::InFlight;
    ++iterator->second.attempts;
    iterator->second.note.clear();
    return true;
}

bool EffectJournal::commit(const std::string& id, std::string note,
                           std::string* error) {
    std::lock_guard lock(mutex_);
    const auto iterator = records_.find(id);
    if (iterator == records_.end() || iterator->second.status != EffectStatus::InFlight) {
        if (error) {
            *error = "only an in-flight effect may commit";
        }
        return false;
    }
    if (!append('C', iterator->second, note, error)) {
        return false;
    }
    iterator->second.status = EffectStatus::Committed;
    iterator->second.note = std::move(note);
    return true;
}

bool EffectJournal::fail(const std::string& id, std::string note,
                         std::string* error) {
    std::lock_guard lock(mutex_);
    const auto iterator = records_.find(id);
    if (iterator == records_.end() || iterator->second.status != EffectStatus::InFlight) {
        if (error) {
            *error = "only an in-flight effect may fail";
        }
        return false;
    }
    if (!append('F', iterator->second, note, error)) {
        return false;
    }
    iterator->second.status = EffectStatus::Failed;
    iterator->second.note = std::move(note);
    return true;
}

bool EffectJournal::resolve_inflight(const std::string& id, bool committed,
                                     std::string note,
                                     std::string* error) {
    return committed ? commit(id, std::move(note), error)
                     : fail(id, std::move(note), error);
}

bool EffectJournal::execute(const std::string& id,
                            const std::function<void()>& external_action,
                            std::string* error) {
    if (!external_action) {
        if (error) {
            *error = "external effect callback is empty";
        }
        return false;
    }
    if (!begin(id, error)) {
        return false;
    }
    try {
        external_action();
    } catch (const std::exception& exception) {
        std::string journal_error;
        const bool recorded = fail(id, exception.what(), &journal_error);
        if (error) {
            *error = recorded ? exception.what() : journal_error;
        }
        return false;
    } catch (...) {
        std::string journal_error;
        const bool recorded = fail(id, "non-standard exception", &journal_error);
        if (error) {
            *error = recorded ? "non-standard exception" : journal_error;
        }
        return false;
    }
    return commit(id, "external action completed", error);
}

std::optional<EffectSnapshot> EffectJournal::lookup(const std::string& id) const {
    std::lock_guard lock(mutex_);
    const auto iterator = records_.find(id);
    return iterator == records_.end() ? std::nullopt
                                      : std::optional<EffectSnapshot>{iterator->second};
}

std::vector<EffectSnapshot> EffectJournal::snapshot() const {
    std::lock_guard lock(mutex_);
    std::vector<EffectSnapshot> output;
    output.reserve(records_.size());
    for (const auto& [id, record] : records_) {
        (void)id;
        output.push_back(record);
    }
    std::sort(output.begin(), output.end(), [](const auto& left, const auto& right) {
        return left.id < right.id;
    });
    return output;
}

bool EffectJournal::load(std::string* error) {
    std::lock_guard lock(mutex_);
    std::ifstream input(path_, std::ios::binary);
    if (!input) {
        // A not-yet-created file may not expose a portable errno through
        // iostreams. Create an empty journal and let the first fsync-backed
        // append establish content.
        std::ofstream create(path_, std::ios::app | std::ios::binary);
        if (create) {
            return true;
        }
        if (error) {
            *error = "cannot open effect journal";
        }
        return false;
    }

    const std::string content((std::istreambuf_iterator<char>(input)),
                              std::istreambuf_iterator<char>());
    std::size_t start = 0;
    std::size_t line_number = 0;
    while (start < content.size()) {
        const auto newline = content.find('\n', start);
        if (newline == std::string::npos) {
            // A crash may leave only the last append fragment incomplete. A
            // completed begin record is fsynced before external execution, so
            // ignoring an uncommitted tail preserves explicit uncertainty.
            break;
        }
        ++line_number;
        const std::string line = content.substr(start, newline - start);
        start = newline + 1U;
        const auto checksum_tab = line.rfind('\t');
        if (checksum_tab == std::string::npos) {
            if (error) {
                *error = "malformed effect journal at line " +
                         std::to_string(line_number);
            }
            return false;
        }
        const std::string payload = line.substr(0U, checksum_tab);
        std::uint64_t expected_checksum = 0;
        if (!parse_u64(std::string_view(line).substr(checksum_tab + 1U),
                       &expected_checksum) ||
            checksum(payload) != expected_checksum) {
            if (error) {
                *error = "effect journal checksum mismatch at line " +
                         std::to_string(line_number);
            }
            return false;
        }

        const auto fields = split_tabs(payload);
        if (fields.size() != 5U || fields[0].size() != 1U) {
            if (error) {
                *error = "malformed effect journal at line " +
                         std::to_string(line_number);
            }
            return false;
        }
        const auto id = hex_decode(fields[1]);
        const auto kind = hex_decode(fields[2]);
        const auto decoded_payload = hex_decode(fields[3]);
        const auto note = hex_decode(fields[4]);
        if (!id || !kind || !decoded_payload || !note || id->empty()) {
            if (error) {
                *error = "invalid effect journal encoding at line " +
                         std::to_string(line_number);
            }
            return false;
        }
        const char event = fields[0][0];
        auto iterator = records_.find(*id);
        if (event == 'R') {
            if (iterator != records_.end()) {
                if (error) {
                    *error = "duplicate effect request in journal";
                }
                return false;
            }
            records_.emplace(*id, EffectSnapshot{*id, *kind, *decoded_payload,
                                                 EffectStatus::Requested, 0U, *note});
            continue;
        }
        if (iterator == records_.end() || iterator->second.kind != *kind ||
            iterator->second.payload != *decoded_payload) {
            if (error) {
                *error = "effect journal event has no matching request";
            }
            return false;
        }
        auto& record = iterator->second;
        auto invalid_transition = [&] {
            if (error) {
                *error = "invalid effect journal transition at line " +
                         std::to_string(line_number);
            }
            return false;
        };
        switch (event) {
            case 'A':
                if (record.status != EffectStatus::Requested &&
                    record.status != EffectStatus::Failed) {
                    return invalid_transition();
                }
                record.status = EffectStatus::Authorized;
                record.note.clear();
                break;
            case 'B':
                if (record.status != EffectStatus::Authorized) {
                    return invalid_transition();
                }
                record.status = EffectStatus::InFlight;
                ++record.attempts;
                record.note.clear();
                break;
            case 'C':
                if (record.status != EffectStatus::InFlight) {
                    return invalid_transition();
                }
                record.status = EffectStatus::Committed;
                record.note = *note;
                break;
            case 'F':
                if (record.status != EffectStatus::InFlight) {
                    return invalid_transition();
                }
                record.status = EffectStatus::Failed;
                record.note = *note;
                break;
            default:
                if (error) {
                    *error = "unknown effect journal event";
                }
                return false;
        }
    }
    return true;
}

bool EffectJournal::append(char event, const EffectSnapshot& record,
                           const std::string& note,
                           std::string* error) {
    const std::string payload = std::string(1U, event) + "\t" +
                                hex_encode(record.id) + "\t" +
                                hex_encode(record.kind) + "\t" +
                                hex_encode(record.payload) + "\t" +
                                hex_encode(note);
    const std::string line = payload + "\t" +
                             std::to_string(checksum(payload)) + "\n";
    const int fd = ::open(path_.c_str(), O_CREAT | O_WRONLY | O_APPEND, 0600);
    if (fd < 0) {
        if (error) {
            *error = std::string("cannot append effect journal: ") +
                     std::strerror(errno);
        }
        return false;
    }
    const bool ok = write_all(fd, line.data(), line.size()) && ::fsync(fd) == 0;
    const int saved_errno = errno;
    ::close(fd);
    if (!ok && error) {
        *error = std::string("cannot durably append effect journal: ") +
                 std::strerror(saved_errno);
    }
    return ok;
}

}  // namespace doc
