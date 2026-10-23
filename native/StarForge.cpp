// BWAPI 4.4.0 Win32 prototype. Real-game acceptance is required before training.
#include <winsock2.h>
#include <ws2tcpip.h>
#include <BWAPI.h>
#include <array>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int kDecisionFrames = 24;
constexpr unsigned short kPort = 8765;

// Escape bytes as ASCII JSON, avoiding invalid UTF-8 from legacy map-name encodings.
std::string jsonString(const std::string& value) {
    std::ostringstream out;
    out << '"';
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') out << '\\' << c;
        else if (c < 32 || c >= 127)
            out << "\\u00" << std::hex << std::setw(2) << std::setfill('0') << int(c);
        else out << c;
    }
    out << '"';
    return out.str();
}

struct Candidate {
    BWAPI::Unit unit = nullptr;
    BWAPI::TilePosition tile = BWAPI::TilePositions::None;
};

class StarForge final : public BWAPI::AIModule {
    SOCKET socket_ = INVALID_SOCKET;
    bool winsock_ = false;
    bool stopped_ = false;
    int sequence_ = 0;
    int lastFrame_ = -1;
    int failures_ = 0;
    std::string map_;
    std::ofstream log_;
    std::array<Candidate, 6> candidates_{};
    std::vector<BWAPI::Position> starts_;
    size_t scoutIndex_ = 0;

    void closeSocket() {
        if (socket_ != INVALID_SOCKET) {
            closesocket(socket_);
            socket_ = INVALID_SOCKET;
        }
        if (winsock_) { WSACleanup(); winsock_ = false; }
    }

    void fail(const std::string& reason) {
        stopped_ = true;
        log_ << "bridge error: " << reason << " WSA=" << WSAGetLastError() << std::endl;
        BWAPI::Broodwar->printf("StarForge bridge stopped: %s", reason.c_str());
        closeSocket(); // Server records unfinished connection as error, never loss.
        BWAPI::Broodwar->leaveGame();
    }

    void connectPolicy() {
        WSADATA data{};
        if (WSAStartup(MAKEWORD(2, 2), &data) != 0) throw std::runtime_error("WSAStartup failed");
        winsock_ = true;
        socket_ = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (socket_ == INVALID_SOCKET) throw std::runtime_error("socket failed");
        DWORD timeout = 5000;
        int noDelay = 1;
        setsockopt(socket_, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
        setsockopt(socket_, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
        setsockopt(socket_, IPPROTO_TCP, TCP_NODELAY, reinterpret_cast<const char*>(&noDelay), sizeof(noDelay));
        sockaddr_in address{};
        address.sin_family = AF_INET;
        address.sin_port = htons(kPort);
        inet_pton(AF_INET, "127.0.0.1", &address.sin_addr);
        if (connect(socket_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == SOCKET_ERROR)
            throw std::runtime_error("start python -m starforge serve before launching the game");
    }

    void sendLine(const std::string& message) {
        size_t offset = 0;
        while (offset < message.size()) {
            int sent = send(socket_, message.data() + offset, static_cast<int>(message.size() - offset), 0);
            if (sent <= 0) throw std::runtime_error("observation send failed");
            offset += sent;
        }
    }

    int receiveAction() {
        std::string line;
        for (int i = 0; i < 128; ++i) {
            char c = 0;
            if (recv(socket_, &c, 1, 0) != 1) throw std::runtime_error("policy timeout/disconnect");
            if (c == '\n') {
                std::istringstream input(line);
                std::string prefix, extra;
                int sequence = -1, action = -2;
                if (!(input >> prefix >> sequence >> action) || prefix != "ACT" || sequence != sequence_
                    || action < -1 || action > 5 || (input >> extra))
                    throw std::runtime_error("invalid policy response");
                return action;
            }
            line += c;
        }
        throw std::runtime_error("oversized policy response");
    }

    void mineIdleWorkers() {
        for (auto unit : BWAPI::Broodwar->self()->getUnits()) {
            if (!unit->exists() || !unit->isCompleted() || !unit->getType().isWorker() || !unit->isIdle()) continue;
            if (unit->isCarryingMinerals() || unit->isCarryingGas()) { unit->returnCargo(); continue; }
            BWAPI::Unit closest = nullptr;
            int distance = 1000000;
            for (auto mineral : BWAPI::Broodwar->getMinerals()) {
                if (!mineral->exists() || !mineral->isVisible() || mineral->getResources() <= 0) continue;
                int d = unit->getDistance(mineral);
                if (d < distance) { distance = d; closest = mineral; }
            }
            if (closest) unit->gather(closest);
        }
    }

    std::array<bool, 6> prepareActions() {
        using namespace BWAPI;
        candidates_ = {};
        std::array<bool, 6> legal{true, false, false, false, false, false};
        auto self = Broodwar->self();
        for (auto unit : self->getUnits()) {
            if (!unit->exists() || !unit->isCompleted()) continue;
            if (unit->getType() == UnitTypes::Terran_Command_Center && unit->isIdle() && unit->canTrain(UnitTypes::Terran_SCV)) {
                legal[1] = true; candidates_[1].unit = unit;
            }
            if (unit->getType() == UnitTypes::Terran_Barracks && unit->isIdle() && unit->canTrain(UnitTypes::Terran_Marine)) {
                legal[4] = true; candidates_[4].unit = unit;
            }
            if (unit->getType() == UnitTypes::Terran_Marine) legal[5] = true;
            if (!unit->getType().isWorker() || unit->isConstructing() || unit->isCarryingMinerals()
                || unit->isCarryingGas() || (!unit->isIdle() && !unit->isGatheringMinerals())) continue;
            for (int action : {2, 3}) {
                if (legal[action]) continue;
                auto type = action == 2 ? UnitTypes::Terran_Supply_Depot : UnitTypes::Terran_Barracks;
                // Prevent redundant buildings already under construction.
                bool pending = false;
                for (auto owned : self->getUnits())
                    if (owned->getType() == type && !owned->isCompleted()) pending = true;
                if (pending || self->minerals() < type.mineralPrice()) continue;
                auto tile = Broodwar->getBuildLocation(type, self->getStartLocation(), 32);
                if (tile.isValid() && unit->canBuild(type, tile)) {
                    legal[action] = true; candidates_[action] = {unit, tile};
                }
            }
        }
        return legal;
    }

    bool execute(int action) {
        using namespace BWAPI;
        const auto candidate = candidates_[action];
        if (action == 0) return true;
        if (action == 1) return candidate.unit && candidate.unit->train(UnitTypes::Terran_SCV);
        if (action == 4) return candidate.unit && candidate.unit->train(UnitTypes::Terran_Marine);
        if (action == 2 || action == 3)
            return candidate.unit && candidate.unit->build(action == 2 ? UnitTypes::Terran_Supply_Depot : UnitTypes::Terran_Barracks, candidate.tile);
        Position target = Positions::None;
        for (auto unit : Broodwar->getAllUnits()) {
            if (unit->exists() && unit->isVisible() && unit->getPlayer()->isEnemy(Broodwar->self())) {
                target = unit->getPosition(); break;
            }
        }
        // Public map start locations, not the opponent's actual spawn. Cycle to scout them.
        if (!target.isValid() && !starts_.empty()) {
            target = starts_[scoutIndex_ % starts_.size()];
            for (auto unit : Broodwar->self()->getUnits()) {
                if (unit->getType() == UnitTypes::Terran_Marine && unit->getDistance(target) < 160) {
                    ++scoutIndex_; target = starts_[scoutIndex_ % starts_.size()]; break;
                }
            }
        }
        bool issued = false;
        if (target.isValid()) for (auto unit : Broodwar->self()->getUnits()) {
            if (unit->exists() && unit->isCompleted() && unit->getType() == UnitTypes::Terran_Marine)
                issued = unit->attack(target) || issued;
        }
        return issued;
    }

    void exchange(const char* outcome = nullptr) {
        using namespace BWAPI;
        const bool terminal = outcome != nullptr;
        auto self = Broodwar->self();
        const auto legal = terminal ? std::array<bool, 6>{} : prepareActions();
        int workers = 0, marines = 0, barracks = 0, bases = 0, enemies = 0;
        for (auto unit : self->getUnits()) {
            if (!unit->exists()) continue;
            workers += unit->getType().isWorker();
            marines += unit->getType() == UnitTypes::Terran_Marine;
            barracks += unit->getType() == UnitTypes::Terran_Barracks;
            bases += unit->getType().isResourceDepot();
        }
        for (auto unit : Broodwar->getAllUnits())
            if (unit->exists() && unit->isVisible() && unit->getPlayer()->isEnemy(self)) ++enemies;
        std::ostringstream out;
        out << "{\"protocol\":1,\"seq\":" << sequence_ << ",\"frame\":" << Broodwar->getFrameCount()
            << ",\"minerals\":" << self->minerals() << ",\"gas\":" << self->gas()
            << ",\"supply_used\":" << self->supplyUsed() << ",\"supply_total\":" << self->supplyTotal()
            << ",\"workers\":" << workers << ",\"marines\":" << marines << ",\"barracks\":" << barracks
            << ",\"bases\":" << bases << ",\"enemy_visible\":" << enemies << ",\"legal_actions\":[";
        bool first = true;
        for (int i = 0; i < 6; ++i) if (legal[i]) { if (!first) out << ','; out << i; first = false; }
        out << "],\"terminal\":" << (terminal ? "true" : "false")
            << ",\"outcome\":" << (terminal ? jsonString(outcome) : "null")
            << ",\"map_name\":" << jsonString(map_) << ",\"backend\":\"broodwar\"}\n";
        sendLine(out.str());
        int action = receiveAction();
        if (!terminal && action == -1) {
            stopped_ = true; closeSocket(); Broodwar->leaveGame(); return;
        }
        if (!terminal) {
            if (action < 0 || !legal[action]) throw std::runtime_error("policy selected masked action");
            if (!execute(action)) ++failures_;
            log_ << "frame=" << Broodwar->getFrameCount() << " seq=" << sequence_ << " action=" << action
                 << " cumulative_execution_failures=" << failures_ << std::endl;
        }
        ++sequence_;
        lastFrame_ = Broodwar->getFrameCount();
    }

public:
    ~StarForge() override { closeSocket(); }
    void onStart() override {
        using namespace BWAPI;
        closeSocket(); stopped_ = false; sequence_ = 0; lastFrame_ = -1; failures_ = 0; scoutIndex_ = 0;
        starts_.clear();
        log_.open("bwapi-data/write/starforge-bridge.log", std::ios::app);
        if (Broodwar->isReplay() || !Broodwar->self() || Broodwar->self()->getRace() != Races::Terran) {
            fail("this bridge supports Terran live games only"); return;
        }
        map_ = Broodwar->mapFileName();
        for (auto tile : Broodwar->getStartLocations())
            if (tile != Broodwar->self()->getStartLocation()) starts_.push_back(Position(tile) + Position(64, 48));
        try { connectPolicy(); exchange(); }
        catch (const std::exception& error) { fail(error.what()); }
    }
    void onFrame() override {
        if (stopped_ || socket_ == INVALID_SOCKET || BWAPI::Broodwar->isPaused()) return;
        int frame = BWAPI::Broodwar->getFrameCount();
        if (frame <= lastFrame_ || frame % kDecisionFrames != 0) return;
        try { mineIdleWorkers(); exchange(); }
        catch (const std::exception& error) { fail(error.what()); }
    }
    void onEnd(bool isWinner) override {
        if (!stopped_ && socket_ != INVALID_SOCKET) {
            // BWAPI onEnd(false) may be an aborted game. Only isDefeated certifies a loss.
            const char* result = isWinner ? "win" :
                (BWAPI::Broodwar->self() && BWAPI::Broodwar->self()->isDefeated() ? "loss" : "truncated");
            try { exchange(result); }
            catch (const std::exception& error) { log_ << "end: " << error.what() << std::endl; }
        }
        closeSocket(); log_.close();
    }
};
} // namespace

extern "C" __declspec(dllexport) void gameInit(BWAPI::Game* game) { BWAPI::BroodwarPtr = game; }
extern "C" __declspec(dllexport) BWAPI::AIModule* newAIModule() { return new StarForge(); }
