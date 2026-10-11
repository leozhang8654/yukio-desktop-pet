import Foundation
import Testing
@testable import YukioCore

@Suite struct ChatWindowVisibilityTests {
    let mac = CGRect(x: 0, y: 0, width: 1512, height: 982)
    let chat = CGRect(x: 200, y: 100, width: 900, height: 700)

    @Test(arguments: [
        CGRect(x: 1512, y: 0, width: 1920, height: 1080),
        CGRect(x: -1920, y: 0, width: 1920, height: 1080),
        CGRect(x: 0, y: -1080, width: 1920, height: 1080),
        CGRect(x: 0, y: 982, width: 1920, height: 1080),
    ]) func anotherDisplayWorksInEveryDirection(external: CGRect) {
        let externalChat = CGRect(x: external.minX + 100, y: external.minY + 100, width: 800, height: 600)
        #expect(ChatWindowVisibility.canRead(externalChat, screens: [mac, external], covers: [mac]))
        #expect(!ChatWindowVisibility.canRead(externalChat, screens: [mac], covers: []))
    }

    @Test func coveredMinimizedOffscreenAndTitleOnlyCannotAcknowledge() {
        #expect(ChatWindowVisibility.canRead(chat, screens: [mac], covers: []))
        #expect(!ChatWindowVisibility.canRead(chat, screens: [mac], covers: [chat]))
        let left = CGRect(x: chat.minX, y: chat.minY, width: 450, height: 700)
        let right = CGRect(x: chat.minX + 450, y: chat.minY, width: 450, height: 700)
        #expect(!ChatWindowVisibility.canRead(chat, screens: [mac], covers: [left, right]))
        #expect(!ChatWindowVisibility.canRead(chat, screens: [], covers: []))
        #expect(!ChatWindowVisibility.canRead(chat, screens: [mac], covers: [CGRect(x: 200, y: 130, width: 900, height: 670)]))
        #expect(ChatWindowVisibility.canRead(chat, screens: [mac], covers: [left]))
    }

    @Test func windowStraddlingDisplaysAndIndependentChats() {
        let external = CGRect(x: 1512, y: -200, width: 1920, height: 1080)
        #expect(ChatWindowVisibility.canRead(CGRect(x: 1400, y: 100, width: 900, height: 600), screens: [mac, external], covers: [mac]))
        #expect(!ChatWindowVisibility.canRead(chat, screens: [mac, external], covers: [mac]))
    }
}
