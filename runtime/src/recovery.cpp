#include "doc/recovery.hpp"

#include <cerrno>
#include <charconv>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string_view>
#include <sys/stat.h>
#include <unistd.h>
#include <unordered_set>

namespace doc {

namespace {

std::uint64_t checksum(std::string_view text) {
    std::uint64_t hash = 1469598103934665603ULL;
    for (const char character : text) {
        const auto byte = static_cast<unsigned char>(character);
        hash ^= byte;
        hash *= 1099511628211ULL;
    }
    return hash;
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

bool parse_u64(std::string_view text, std::uint64_t* value) {
    const auto result = std::from_chars(text.data(), text.data() + text.size(), *value);
    return result.ec == std::errc{} && result.ptr == text.data() + text.size();
}

bool parse_value(std::string_view text, Value* value) {
    const auto result = std::from_chars(text.data(), text.data() + text.size(), *value);
    return result.ec == std::errc{} && result.ptr == text.data() + text.size();
}

std::vector<StateId> source_ids(const Graph& graph) {
    std::vector<StateId> ids;
    for (StateId state = 0; state < graph.states.size(); ++state) {
        if (graph.is_source(state)) {
            ids.push_back(state);
        }
    }
    return ids;
}

}  // namespace

RecoverableRuntime::RecoverableRuntime(Graph graph, CutoffPolicy cutoff_policy)
    : graph_(std::move(graph)),
      cutoff_policy_(cutoff_policy),
      durable_sources_(graph_.states.size()),
      runtime_(std::make_unique<Runtime>(graph_, cutoff_policy_)) {
    for (StateId state = 0; state < graph_.states.size(); ++state) {
        if (graph_.is_source(state)) {
            durable_sources_[state] = graph_.states[state].initial_value;
        }
    }
}

RecoverableRuntime::RecoverableRuntime(Graph graph, std::string source_journal_path,
                                       CutoffPolicy cutoff_policy)
    : graph_(std::move(graph)),
      cutoff_policy_(cutoff_policy),
      durable_sources_(graph_.states.size()),
      source_journal_path_(std::move(source_journal_path)) {
    if (!source_journal_path_ || source_journal_path_->empty()) {
        throw std::invalid_argument("source journal path must be non-empty");
    }
    for (StateId state = 0; state < graph_.states.size(); ++state) {
        if (graph_.is_source(state)) {
            durable_sources_[state] = graph_.states[state].initial_value;
        }
    }
    std::string error;
    if (!initialize_journal(&error)) {
        throw std::runtime_error(error);
    }
    runtime_ = std::make_unique<Runtime>(graph_, source_seed(), cutoff_policy_);
}

bool RecoverableRuntime::stabilize(std::string* error) {
    std::lock_guard lock(mutex_);
    return runtime_->stabilize(error);
}

bool RecoverableRuntime::commit_sources(
    const std::vector<std::pair<StateId, Value>>& assignments,
    std::string* error) {
    std::lock_guard lock(mutex_);
    std::unordered_set<StateId> seen;
    for (const auto& [state, value] : assignments) {
        (void)value;
        if (state >= graph_.states.size() || !graph_.is_source(state) ||
            !seen.insert(state).second) {
            if (error) {
                *error = "authoritative source batch is invalid";
            }
            return false;
        }
    }

    auto next_sources = durable_sources_;
    for (const auto& [state, value] : assignments) {
        next_sources[state] = value;
    }
    if (source_journal_path_) {
        if (source_journal_epoch_ == std::numeric_limits<std::uint64_t>::max()) {
            if (error) {
                *error = "source journal epoch overflow";
            }
            return false;
        }
        if (!append_source_snapshot(next_sources, source_journal_epoch_ + 1U, error)) {
            return false;
        }
        ++source_journal_epoch_;
    }

    // Source facts become authoritative before derived stabilization. A later
    // callback failure does not roll them back.
    durable_sources_ = std::move(next_sources);
    return runtime_->update_batch(assignments, error);
}

std::optional<Value> RecoverableRuntime::observe(StateId state, std::string* error) {
    std::lock_guard lock(mutex_);
    return runtime_->observe(state, error);
}

bool RecoverableRuntime::fail_stop_and_reconstruct(std::string* error) {
    std::lock_guard lock(mutex_);
    if (generation_ == std::numeric_limits<std::uint64_t>::max()) {
        if (error) {
            *error = "recovery generation overflow";
        }
        return false;
    }
    try {
        auto replacement = std::make_unique<Runtime>(graph_, source_seed(), cutoff_policy_);
        if (!replacement->stabilize(error)) {
            return false;
        }
        runtime_ = std::move(replacement);
        ++generation_;
        return true;
    } catch (const std::exception& exception) {
        if (error) {
            *error = std::string("fail-stop reconstruction failed: ") + exception.what();
        }
        return false;
    }
}

std::uint64_t RecoverableRuntime::generation() const {
    std::lock_guard lock(mutex_);
    return generation_;
}

bool RecoverableRuntime::may_publish(std::uint64_t generation) const {
    std::lock_guard lock(mutex_);
    return generation == generation_;
}

std::vector<StateSnapshot> RecoverableRuntime::snapshot() const {
    std::lock_guard lock(mutex_);
    return runtime_->snapshot();
}

bool RecoverableRuntime::file_backed() const noexcept {
    return source_journal_path_.has_value();
}

RuntimeSeed RecoverableRuntime::source_seed() const {
    RuntimeSeed seed;
    seed.values.resize(graph_.states.size());
    seed.active.assign(graph_.states.size(), 0U);
    for (StateId state = 0; state < graph_.states.size(); ++state) {
        if (graph_.is_source(state)) {
            if (!durable_sources_[state]) {
                throw std::logic_error("authoritative source store is incomplete");
            }
            seed.values[state] = durable_sources_[state];
        } else {
            seed.active[state] = 1U;
        }
    }
    return seed;
}

bool RecoverableRuntime::initialize_journal(std::string* error) {
    struct stat status {};
    errno = 0;
    const int result = ::stat(source_journal_path_->c_str(), &status);
    if (result == 0 && status.st_size > 0) {
        return load_journal(error);
    }
    if (result != 0 && errno != ENOENT) {
        if (error) {
            *error = "cannot inspect source journal";
        }
        return false;
    }
    return append_source_snapshot(durable_sources_, 0U, error);
}

bool RecoverableRuntime::load_journal(std::string* error) {
    const int fd = ::open(source_journal_path_->c_str(), O_RDONLY);
    if (fd < 0) {
        if (error) {
            *error = "cannot open source journal";
        }
        return false;
    }
    std::string content;
    char buffer[4096];
    while (true) {
        const auto count = ::read(fd, buffer, sizeof(buffer));
        if (count < 0) {
            if (errno == EINTR) {
                continue;
            }
            ::close(fd);
            if (error) {
                *error = "cannot read source journal";
            }
            return false;
        }
        if (count == 0) {
            break;
        }
        content.append(buffer, static_cast<std::size_t>(count));
    }
    ::close(fd);

    const auto ids = source_ids(graph_);
    std::size_t start = 0;
    bool found = false;
    while (start < content.size()) {
        const auto newline = content.find('\n', start);
        if (newline == std::string::npos) {
            // A crash may leave only the final append fragment incomplete.
            break;
        }
        const std::string_view line(content.data() + start, newline - start);
        start = newline + 1U;
        const auto first = line.find('|');
        const auto second = first == std::string_view::npos
            ? std::string_view::npos
            : line.find('|', first + 1U);
        if (first == std::string_view::npos || second == std::string_view::npos) {
            if (error) {
                *error = "malformed source journal record";
            }
            return false;
        }
        const auto payload = line.substr(0U, second);
        std::uint64_t expected_checksum = 0;
        if (!parse_u64(line.substr(second + 1U), &expected_checksum) ||
            checksum(payload) != expected_checksum) {
            if (error) {
                *error = "source journal checksum mismatch";
            }
            return false;
        }
        std::uint64_t epoch = 0;
        if (!parse_u64(line.substr(0U, first), &epoch) || (found && epoch <= source_journal_epoch_)) {
            if (error) {
                *error = "source journal epochs are not strictly increasing";
            }
            return false;
        }
        std::vector<std::optional<Value>> next(graph_.states.size());
        std::size_t value_start = first + 1U;
        for (std::size_t index = 0; index < ids.size(); ++index) {
            const auto comma = line.find(',', value_start);
            const auto end = index + 1U == ids.size() ? second : comma;
            if (end == std::string_view::npos || end > second ||
                (index + 1U < ids.size() && comma == std::string_view::npos)) {
                if (error) {
                    *error = "source journal has the wrong source count";
                }
                return false;
            }
            Value value = 0;
            if (!parse_value(line.substr(value_start, end - value_start), &value)) {
                if (error) {
                    *error = "source journal contains an invalid value";
                }
                return false;
            }
            next[ids[index]] = value;
            value_start = end + 1U;
        }
        const auto expected_end = ids.empty() ? second : second + 1U;
        if (value_start != expected_end) {
            if (error) {
                *error = "source journal has extra source values";
            }
            return false;
        }
        durable_sources_ = std::move(next);
        source_journal_epoch_ = epoch;
        found = true;
    }
    if (!found) {
        if (error) {
            *error = "source journal has no complete snapshot";
        }
        return false;
    }
    return true;
}

bool RecoverableRuntime::append_source_snapshot(
    const std::vector<std::optional<Value>>& sources,
    std::uint64_t epoch,
    std::string* error) const {
    const auto ids = source_ids(graph_);
    std::ostringstream payload;
    payload << epoch << '|';
    for (std::size_t index = 0; index < ids.size(); ++index) {
        if (!sources.at(ids[index])) {
            if (error) {
                *error = "cannot persist an incomplete source snapshot";
            }
            return false;
        }
        if (index != 0U) {
            payload << ',';
        }
        payload << *sources.at(ids[index]);
    }
    const auto payload_text = payload.str();
    const auto line = payload_text + '|' + std::to_string(checksum(payload_text)) + '\n';
    const int fd = ::open(source_journal_path_->c_str(), O_CREAT | O_WRONLY | O_APPEND, 0600);
    if (fd < 0) {
        if (error) {
            *error = "cannot append source journal";
        }
        return false;
    }
    const bool ok = write_all(fd, line.data(), line.size()) && ::fsync(fd) == 0;
    const int saved_errno = errno;
    ::close(fd);
    if (!ok && error) {
        *error = std::string("cannot durably append source journal: ") +
                 std::strerror(saved_errno);
    }
    return ok;
}

}  // namespace doc
