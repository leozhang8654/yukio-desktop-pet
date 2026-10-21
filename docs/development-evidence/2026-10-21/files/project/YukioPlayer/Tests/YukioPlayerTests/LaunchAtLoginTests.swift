import Testing
@testable import YukioPlayer

struct LaunchAtLoginTests {
    private enum Failure: Error { case denied }

    @Test func openingSettingsDoesNotRegisterAndExternalChangesAreReflected() {
        var systemStatus = LaunchAtLoginStatus.disabled
        var calls = 0
        let setting = LaunchAtLogin(readStatus: { systemStatus }, register: { calls += 1 }, unregister: { calls += 1 })
        #expect(setting.status == .disabled)
        #expect(calls == 0)
        systemStatus = .enabled
        #expect(setting.status.isRegistered)
        systemStatus = .disabled
        #expect(!setting.status.isRegistered)
    }

    @Test func canEnableAndDisableWithoutDuplicateRegistration() throws {
        var systemStatus = LaunchAtLoginStatus.disabled
        var registrations = 0
        var removals = 0
        let setting = LaunchAtLogin(readStatus: { systemStatus }, register: {
            registrations += 1
            systemStatus = .enabled
        }, unregister: {
            removals += 1
            systemStatus = .disabled
        })
        try setting.setEnabled(true)
        try setting.setEnabled(true)
        #expect(setting.status == .enabled)
        #expect(registrations == 1)
        try setting.setEnabled(false)
        try setting.setEnabled(false)
        #expect(setting.status == .disabled)
        #expect(removals == 1)
    }

    @Test func pendingApprovalCanBeCancelled() throws {
        var systemStatus = LaunchAtLoginStatus.disabled
        let setting = LaunchAtLogin(readStatus: { systemStatus }, register: {
            systemStatus = .requiresApproval
        }, unregister: {
            systemStatus = .disabled
        })
        try setting.setEnabled(true)
        #expect(setting.status == .requiresApproval)
        #expect(setting.status.isRegistered)
        try setting.setEnabled(false)
        #expect(setting.status == .disabled)
    }

    @Test func failuresNeverInventASuccessfulState() {
        var systemStatus = LaunchAtLoginStatus.disabled
        let setting = LaunchAtLogin(readStatus: { systemStatus }, register: { throw Failure.denied },
                                    unregister: { throw Failure.denied })
        #expect(throws: Failure.self) { try setting.setEnabled(true) }
        #expect(setting.status == .disabled)
        systemStatus = .enabled
        #expect(throws: Failure.self) { try setting.setEnabled(false) }
        #expect(setting.status == .enabled)
    }
}
