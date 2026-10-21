import AppKit
import Combine
import YukioCore

/// One shared store for the app and reminder panel. Closing a window does not stop it.
final class ReminderStore: ObservableObject {
    @Published private(set) var book = ReminderBook()
    @Published var error: String?
    @Published private(set) var available = true
    private let repository: ReminderRepository
    private var timer: Timer?
    var onRing: (() -> Void)?

    var scheduled: [Reminder] { book.items.filter { $0.status == .scheduled }.sorted { $0.dueAt < $1.dueAt } }
    var ringing: [Reminder] { book.items.filter { $0.status == .ringing }.sorted { $0.dueAt < $1.dueAt } }
    var completed: [Reminder] { book.items.filter { $0.status == .completed }.sorted { $0.dueAt > $1.dueAt } }

    init(url: URL? = nil) {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        repository = ReminderRepository(url: url ?? base.appendingPathComponent("Yukio/reminders.json"))
        do { book = try repository.load() }
        catch {
            available = false
            self.error = "无法读取提醒，原文件已保留。\(error.localizedDescription)"
        }
    }

    func start() {
        guard timer == nil else { return }
        if !ringing.isEmpty { onRing?() }
        tick()
        let timer = Timer(timeInterval: 1, repeats: true) { [weak self] _ in self?.tick() }
        timer.tolerance = 0.2
        RunLoop.main.add(timer, forMode: .common)
        self.timer = timer
    }

    deinit { timer?.invalidate() }

    @discardableResult private func commit(_ change: (inout ReminderBook) throws -> Void) -> Bool {
        guard available else { return false }
        do {
            var next = book
            try change(&next)
            try repository.write(next)
            book = next
            error = nil
            return true
        } catch {
            self.error = "提醒未保存：\(error.localizedDescription)"
            return false
        }
    }

    @discardableResult func save(id: UUID? = nil, title: String, dueAt: Date) -> Bool {
        commit { try $0.save(id: id, title: title, dueAt: dueAt) }
    }
    func complete(_ id: UUID) { commit { $0.complete(id) } }
    func snooze(_ id: UUID) { commit { $0.snooze(id, now: Date()) } }
    func remove(_ id: UUID) { commit { $0.remove(id) } }

    private func tick() {
        guard available, scheduled.first.map({ $0.dueAt <= Date() }) == true else { return }
        if commit({ $0.advance(now: Date()) }) {
            if UserDefaults.standard.object(forKey: "assistantReminderSound") as? Bool ?? true {
                NSSound(named: "Glass")?.play()
            }
            onRing?()
        }
    }
}
