import Testing
import Foundation
@testable import YukioPlayer

@Suite struct BrowserDestinationTests {
    @Test func tabLabelsIgnoreOnlyChangingMemorySuffix() {
        #expect(BrowserChatDestination.normalizedTitle("Lesson - 内存用量 - 227 MB") == "Lesson")
        #expect(BrowserChatDestination.normalizedTitle("Lesson - Memory usage - 1 GB") == "Lesson")
        #expect(BrowserChatDestination.normalizedTitle("Lesson - Part II") == "Lesson - Part II")
    }
    @Test func unseenPluginDoesNotHaveADesktopFallback() {
        #expect(!BrowserChatDestination.contains("never-observed-session"))
        #expect(!BrowserChatDestination.open(session: "never-observed-session"))
    }
    @Test func fullScreenStripMustBelongToTheSameContentWindow() {
        let content = CGRect(x: -88, y: -993, width: 1920, height: 993)
        #expect(BrowserChatDestination.isAttachedTabStrip(CGRect(x: -88, y: -1080, width: 1920, height: 41), content: content))
        #expect(!BrowserChatDestination.isAttachedTabStrip(CGRect(x: 0, y: 0, width: 1920, height: 41), content: content))
        #expect(!BrowserChatDestination.isAttachedTabStrip(CGRect(x: -88, y: -1080, width: 900, height: 41), content: content))
        #expect(!BrowserChatDestination.isAttachedTabStrip(CGRect(x: -88, y: -1300, width: 1920, height: 41), content: content))
        #expect(!BrowserChatDestination.isAttachedTabStrip(CGRect(x: -88, y: -1080, width: 1920, height: 1080), content: content))
    }
}
