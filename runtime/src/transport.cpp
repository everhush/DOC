#include "doc/transport.hpp"

#include <arpa/inet.h>
#include <cerrno>
#include <cstring>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <array>
#include <bit>
#include <limits>
#include <stdexcept>

namespace doc {

namespace {

constexpr std::uint32_t magic = 0x444f4332U;  // DOC2
constexpr std::size_t payload_size = 4U + 4U + 8U + 8U + 8U + 8U;
constexpr std::size_t wire_size = payload_size + 8U;
constexpr std::size_t maximum_frame_size = 4096U;

void append_u32(std::vector<std::uint8_t>& out, std::uint32_t value) {
    for (int shift = 24; shift >= 0; shift -= 8) {
        out.push_back(static_cast<std::uint8_t>((value >> shift) & 0xffU));
    }
}

void append_u64(std::vector<std::uint8_t>& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8) {
        out.push_back(static_cast<std::uint8_t>((value >> shift) & 0xffU));
    }
}

std::uint32_t read_u32(const std::vector<std::uint8_t>& bytes, std::size_t offset) {
    std::uint32_t value = 0;
    for (std::size_t i = 0; i < 4U; ++i) {
        value = static_cast<std::uint32_t>((value << 8U) | bytes.at(offset + i));
    }
    return value;
}

std::uint64_t read_u64(const std::vector<std::uint8_t>& bytes, std::size_t offset) {
    std::uint64_t value = 0;
    for (std::size_t i = 0; i < 8U; ++i) {
        value = (value << 8U) | bytes.at(offset + i);
    }
    return value;
}

std::uint64_t checksum(const std::vector<std::uint8_t>& bytes, std::size_t count) {
    std::uint64_t hash = 1469598103934665603ULL;
    for (std::size_t i = 0; i < count; ++i) {
        hash ^= bytes.at(i);
        hash *= 1099511628211ULL;
    }
    return hash;
}

bool write_all(int socket, const std::uint8_t* data, std::size_t size) {
    std::size_t sent = 0;
    while (sent < size) {
        const auto result = ::send(socket, data + sent, size - sent, MSG_NOSIGNAL);
        if (result < 0) {
            if (errno == EINTR) {
                continue;
            }
            return false;
        }
        if (result == 0) {
            return false;
        }
        sent += static_cast<std::size_t>(result);
    }
    return true;
}

bool read_all(int socket, std::uint8_t* data, std::size_t size) {
    std::size_t received = 0;
    while (received < size) {
        const auto result = ::recv(socket, data + received, size - received, 0);
        if (result < 0) {
            if (errno == EINTR) {
                continue;
            }
            return false;
        }
        if (result == 0) {
            return false;
        }
        received += static_cast<std::size_t>(result);
    }
    return true;
}

}  // namespace

std::uint64_t placement_role_key(const std::string& role) noexcept {
    std::uint64_t hash = 1469598103934665603ULL;
    for (const char character : role) {
        const auto byte = static_cast<unsigned char>(character);
        hash ^= byte;
        hash *= 1099511628211ULL;
    }
    return hash;
}

std::vector<std::uint8_t> serialize(const ValueEnvelope& envelope) {
    std::vector<std::uint8_t> bytes;
    bytes.reserve(wire_size);
    append_u32(bytes, magic);
    append_u32(bytes, envelope.state);
    append_u64(bytes, envelope.source_epoch);
    append_u64(bytes, envelope.role_key);
    append_u64(bytes, envelope.placement_generation);
    append_u64(bytes, std::bit_cast<std::uint64_t>(envelope.value));
    append_u64(bytes, checksum(bytes, bytes.size()));
    return bytes;
}

std::optional<ValueEnvelope> deserialize(const std::vector<std::uint8_t>& bytes,
                                         std::string* error) {
    if (bytes.size() != wire_size) {
        if (error) {
            *error = "transport envelope has an invalid length";
        }
        return std::nullopt;
    }
    if (read_u32(bytes, 0U) != magic) {
        if (error) {
            *error = "transport envelope has an invalid magic";
        }
        return std::nullopt;
    }
    const auto expected = read_u64(bytes, payload_size);
    if (checksum(bytes, payload_size) != expected) {
        if (error) {
            *error = "transport envelope checksum mismatch";
        }
        return std::nullopt;
    }
    ValueEnvelope envelope;
    envelope.state = read_u32(bytes, 4U);
    envelope.source_epoch = read_u64(bytes, 8U);
    envelope.role_key = read_u64(bytes, 16U);
    envelope.placement_generation = read_u64(bytes, 24U);
    envelope.value = std::bit_cast<Value>(read_u64(bytes, 32U));
    return envelope;
}

std::size_t ValueInbox::KeyHash::operator()(const Key& key) const noexcept {
    const auto a = static_cast<std::uint64_t>(key.state);
    const auto mixed = key.role_key ^ (a + 0x9e3779b97f4a7c15ULL +
                                       (key.role_key << 6U) + (key.role_key >> 2U));
    return static_cast<std::size_t>(mixed);
}

AdmissionResult ValueInbox::admit(const ValueEnvelope& envelope,
                                  std::uint64_t expected_role_key,
                                  std::uint64_t current_placement_generation) {
    if (envelope.role_key != expected_role_key) {
        return AdmissionResult::WrongRole;
    }
    if (envelope.placement_generation != current_placement_generation) {
        return AdmissionResult::StaleGeneration;
    }
    const Key key{envelope.state, envelope.role_key};
    const auto iterator = entries_.find(key);
    if (iterator == entries_.end()) {
        entries_.emplace(key, Entry{envelope.source_epoch, envelope.value});
        return AdmissionResult::Accepted;
    }
    if (envelope.source_epoch < iterator->second.source_epoch) {
        return AdmissionResult::Stale;
    }
    if (envelope.source_epoch == iterator->second.source_epoch) {
        return envelope.value == iterator->second.value
            ? AdmissionResult::Duplicate
            : AdmissionResult::Conflict;
    }
    iterator->second = Entry{envelope.source_epoch, envelope.value};
    return AdmissionResult::Accepted;
}

std::optional<Value> ValueInbox::value(StateId state, std::uint64_t role_key) const {
    const auto iterator = entries_.find(Key{state, role_key});
    return iterator == entries_.end() ? std::nullopt
                                      : std::optional<Value>{iterator->second.value};
}

std::optional<std::uint64_t> ValueInbox::epoch(StateId state,
                                                std::uint64_t role_key) const {
    const auto iterator = entries_.find(Key{state, role_key});
    return iterator == entries_.end()
        ? std::nullopt
        : std::optional<std::uint64_t>{iterator->second.source_epoch};
}

LoopbackTcpChannel::LoopbackTcpChannel() {
    listener_ = ::socket(AF_INET, SOCK_STREAM, 0);
    if (listener_ < 0) {
        throw std::runtime_error("failed to create loopback TCP listener");
    }
    int reuse = 1;
    (void)::setsockopt(listener_, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = 0;
    if (::bind(listener_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0 ||
        ::listen(listener_, 8) != 0) {
        const auto message = std::string("failed to bind loopback TCP listener: ") +
                             std::strerror(errno);
        ::close(listener_);
        listener_ = -1;
        throw std::runtime_error(message);
    }

    socklen_t length = sizeof(address);
    if (::getsockname(listener_, reinterpret_cast<sockaddr*>(&address), &length) != 0) {
        ::close(listener_);
        listener_ = -1;
        throw std::runtime_error("failed to inspect loopback TCP listener");
    }
    port_ = ntohs(address.sin_port);
    thread_ = std::thread([this] { accept_loop(); });
}

LoopbackTcpChannel::~LoopbackTcpChannel() {
    {
        std::lock_guard lock(mutex_);
        stopping_ = true;
    }
    // listener_ is immutable while the accept thread is running. Closing the
    // descriptor wakes accept(); the member is reset only after join so the
    // accept loop and destructor never race on the integer object itself.
    if (listener_ >= 0) {
        ::shutdown(listener_, SHUT_RDWR);
        ::close(listener_);
    }
    cv_.notify_all();
    if (thread_.joinable()) {
        thread_.join();
    }
    listener_ = -1;
}

bool LoopbackTcpChannel::send(const ValueEnvelope& envelope, std::string* error) const {
    const auto bytes = serialize(envelope);
    const int client = ::socket(AF_INET, SOCK_STREAM, 0);
    if (client < 0) {
        if (error) {
            *error = "failed to create loopback TCP client";
        }
        return false;
    }
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = htons(port_);
    if (::connect(client, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0) {
        if (error) {
            *error = std::string("loopback TCP connect failed: ") + std::strerror(errno);
        }
        ::close(client);
        return false;
    }
    std::array<std::uint8_t, 4> length{
        static_cast<std::uint8_t>((bytes.size() >> 24U) & 0xffU),
        static_cast<std::uint8_t>((bytes.size() >> 16U) & 0xffU),
        static_cast<std::uint8_t>((bytes.size() >> 8U) & 0xffU),
        static_cast<std::uint8_t>(bytes.size() & 0xffU),
    };
    const bool ok = write_all(client, length.data(), length.size()) &&
                    write_all(client, bytes.data(), bytes.size());
    if (!ok && error) {
        *error = "loopback TCP send failed";
    }
    ::shutdown(client, SHUT_RDWR);
    ::close(client);
    return ok;
}

std::optional<ValueEnvelope> LoopbackTcpChannel::receive(
    std::chrono::milliseconds timeout,
    std::string* error) {
    std::vector<std::uint8_t> bytes;
    {
        std::unique_lock lock(mutex_);
        cv_.wait_for(lock, timeout, [this] {
            return !queue_.empty() || !background_error_.empty() || stopping_;
        });
        if (!background_error_.empty()) {
            if (error) {
                *error = background_error_;
            }
            return std::nullopt;
        }
        if (queue_.empty()) {
            if (error) {
                *error = "loopback TCP receive timed out";
            }
            return std::nullopt;
        }
        bytes = std::move(queue_.front());
        queue_.pop_front();
    }
    return deserialize(bytes, error);
}

std::uint16_t LoopbackTcpChannel::port() const noexcept {
    return port_;
}

void LoopbackTcpChannel::accept_loop() {
    while (true) {
        const int client = ::accept(listener_, nullptr, nullptr);
        if (client < 0) {
            std::lock_guard lock(mutex_);
            if (stopping_) {
                return;
            }
            if (errno == EINTR) {
                continue;
            }
            background_error_ = std::string("loopback TCP accept failed: ") +
                                std::strerror(errno);
            cv_.notify_all();
            return;
        }

        std::array<std::uint8_t, 4> length_bytes{};
        bool ok = read_all(client, length_bytes.data(), length_bytes.size());
        const std::size_t length =
            (static_cast<std::size_t>(length_bytes[0]) << 24U) |
            (static_cast<std::size_t>(length_bytes[1]) << 16U) |
            (static_cast<std::size_t>(length_bytes[2]) << 8U) |
            static_cast<std::size_t>(length_bytes[3]);
        if (length > maximum_frame_size) {
            ok = false;
        }
        std::vector<std::uint8_t> bytes;
        if (ok) {
            bytes.resize(length);
            ok = read_all(client, bytes.data(), bytes.size());
        }
        ::shutdown(client, SHUT_RDWR);
        ::close(client);

        std::lock_guard lock(mutex_);
        if (!ok) {
            background_error_ = "loopback TCP received an incomplete or oversized frame";
            cv_.notify_all();
            return;
        }
        queue_.push_back(std::move(bytes));
        cv_.notify_all();
    }
}

}  // namespace doc
