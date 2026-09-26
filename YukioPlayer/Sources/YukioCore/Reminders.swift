import Foundation

/// Reminder data is independent of the pet, windows, and future AI providers.
public struct Reminder: Identifiable, Codable, Equatable {
    public enum Status: String, Codable { case scheduled, ringing, completed }
    public let id: UUID
    public var title: String
    public var dueAt: Date
    public var status: Status

    public init(id: UUID = UUID(), title: String, dueAt: Date, status: Status = .scheduled) {
        self.id = id
        self.title = title
        self.dueAt = dueAt
        self.status = status
    }
}

public enum ReminderError: LocalizedError {
    case emptyTitle, pastDate, unsupportedVersion
    public var errorDescription: String? {
        switch self {
        case .emptyTitle: return "给这条提醒起个名字吧。"
        case .pastDate: return "请选择一个还没到的时间。"
        case .unsupportedVersion: return "提醒文件来自更新的版本，请升级后再打开。"
        }
    }
}

public struct ReminderBook: Codable, Equatable {
    public private(set) var version = 1
    public private(set) var items: [Reminder] = []
    public init() {}

    public mutating func save(id: UUID? = nil, title: String, dueAt: Date, now: Date = Date()) throws {
        let clean = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { throw ReminderError.emptyTitle }
        guard dueAt > now else { throw ReminderError.pastDate }
        if let id, let index = items.firstIndex(where: { $0.id == id }) {
            items[index].title = clean
            items[index].dueAt = dueAt
            items[index].status = .scheduled
        } else {
            items.append(Reminder(title: clean, dueAt: dueAt))
        }
    }

    /// Late reminders (including after wake/relaunch) become ringing exactly once.
    @discardableResult public mutating func advance(now: Date) -> [UUID] {
        var fired: [UUID] = []
        for index in items.indices where items[index].status == .scheduled && items[index].dueAt <= now {
            items[index].status = .ringing
            fired.append(items[index].id)
        }
        return fired
    }

    public mutating func complete(_ id: UUID) {
        guard let index = items.firstIndex(where: { $0.id == id }) else { return }
        items[index].status = .completed
    }

    public mutating func snooze(_ id: UUID, now: Date) {
        guard let index = items.firstIndex(where: { $0.id == id }), items[index].status == .ringing else { return }
        items[index].dueAt = now.addingTimeInterval(5 * 60)
        items[index].status = .scheduled
    }

    public mutating func remove(_ id: UUID) { items.removeAll { $0.id == id } }
}

public struct ReminderRepository {
    public let url: URL
    public init(url: URL) { self.url = url }

    public func load() throws -> ReminderBook {
        guard FileManager.default.fileExists(atPath: url.path) else { return ReminderBook() }
        let book = try JSONDecoder().decode(ReminderBook.self, from: Data(contentsOf: url))
        guard book.version == 1 else { throw ReminderError.unsupportedVersion }
        return book
    }

    public func write(_ book: ReminderBook) throws {
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        try encoder.encode(book).write(to: url, options: .atomic)
    }
}
