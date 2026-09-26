import Foundation
import Testing
@testable import YukioCore

@Suite struct ReminderTests {
    let now = Date(timeIntervalSince1970: 1_800_000_000)

    @Test func validatesInputWithoutChangingBook() throws {
        var book = ReminderBook()
        #expect(throws: ReminderError.self) { try book.save(title: " \n ", dueAt: now.addingTimeInterval(60), now: now) }
        #expect(throws: ReminderError.self) { try book.save(title: "喝水", dueAt: now, now: now) }
        #expect(book.items.isEmpty)
    }

    @Test func firesOnceAndCatchesUpAfterSleep() throws {
        var book = ReminderBook()
        try book.save(title: " 喝水 ", dueAt: now.addingTimeInterval(60), now: now)
        try book.save(title: "出门", dueAt: now.addingTimeInterval(120), now: now)
        #expect(book.items[0].title == "喝水")
        #expect(book.advance(now: now).isEmpty)
        #expect(book.advance(now: now.addingTimeInterval(3600)).count == 2)
        #expect(book.advance(now: now.addingTimeInterval(3601)).isEmpty)
        #expect(book.items.allSatisfy { $0.status == .ringing })
    }

    @Test func snoozeAndCompletionDoNotRefireOldAlarm() throws {
        var book = ReminderBook()
        try book.save(title: "休息", dueAt: now.addingTimeInterval(60), now: now)
        let id = book.items[0].id
        book.advance(now: now.addingTimeInterval(60))
        book.snooze(id, now: now.addingTimeInterval(90))
        #expect(book.items[0].dueAt == now.addingTimeInterval(390))
        #expect(book.advance(now: now.addingTimeInterval(389)).isEmpty)
        #expect(book.advance(now: now.addingTimeInterval(390)) == [id])
        book.complete(id)
        #expect(book.advance(now: now.addingTimeInterval(900)).isEmpty)
        book.snooze(id, now: now)
        #expect(book.items[0].status == .completed)
    }

    @Test func editingReschedulesAndDeletingCancels() throws {
        var book = ReminderBook()
        try book.save(title: "原提醒", dueAt: now.addingTimeInterval(60), now: now)
        let id = book.items[0].id
        try book.save(id: id, title: "新提醒", dueAt: now.addingTimeInterval(120), now: now)
        #expect(book.items.count == 1)
        #expect(book.items[0].title == "新提醒")
        #expect(book.advance(now: now.addingTimeInterval(60)).isEmpty)
        book.remove(id)
        #expect(book.advance(now: now.addingTimeInterval(120)).isEmpty)
    }

    @Test func persistsRingingStateAndRejectsCorruptFiles() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let repository = ReminderRepository(url: directory.appendingPathComponent("reminders.json"))
        #expect(try repository.load().items.isEmpty)
        var book = ReminderBook()
        try book.save(title: "重启后还在", dueAt: now.addingTimeInterval(60), now: now)
        book.advance(now: now.addingTimeInterval(60))
        try repository.write(book)
        #expect(try repository.load() == book)
        let corrupt = Data("not json".utf8)
        try corrupt.write(to: repository.url)
        #expect(throws: (any Error).self) { try repository.load() }
        #expect(try Data(contentsOf: repository.url) == corrupt)
        try Data("{\"version\":2,\"items\":[]}".utf8).write(to: repository.url)
        #expect(throws: ReminderError.self) { try repository.load() }
    }
}
