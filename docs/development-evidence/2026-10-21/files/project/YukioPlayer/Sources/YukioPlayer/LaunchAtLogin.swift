import ServiceManagement

/// The system is the source of truth, including changes made in System Settings.
/// Do not save a separate Boolean or register automatically when the app starts.
enum LaunchAtLoginStatus: Equatable {
    case disabled, enabled, requiresApproval, unavailable

    var isRegistered: Bool { self == .enabled || self == .requiresApproval }
}

final class LaunchAtLogin {
    private let readStatus: () -> LaunchAtLoginStatus
    private let register: () throws -> Void
    private let unregister: () throws -> Void

    init(readStatus: @escaping () -> LaunchAtLoginStatus = {
        switch SMAppService.mainApp.status {
        case .notRegistered: return .disabled
        case .enabled: return .enabled
        case .requiresApproval: return .requiresApproval
        case .notFound: return .unavailable
        @unknown default: return .unavailable
        }
    }, register: @escaping () throws -> Void = { try SMAppService.mainApp.register() },
       unregister: @escaping () throws -> Void = { try SMAppService.mainApp.unregister() }) {
        self.readStatus = readStatus
        self.register = register
        self.unregister = unregister
    }

    var status: LaunchAtLoginStatus { readStatus() }

    func setEnabled(_ enabled: Bool) throws {
        if enabled {
            if !status.isRegistered { try register() }
        } else if status.isRegistered {
            try unregister()
        }
    }

    static func openSystemSettings() {
        SMAppService.openSystemSettingsLoginItems()
    }
}
