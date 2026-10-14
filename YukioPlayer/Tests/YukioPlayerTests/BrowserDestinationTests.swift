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
    @Test func sharedFullScreenTabStripIsNotCountedFourTimes() {
        let children = [0: [1, 2, 3, 4, 9], 1: [5], 2: [5], 3: [5], 4: [5], 5: [6, 7], 9: [8]]
        let roles = [0: "AXWindow", 1: "AXGroup", 2: "AXGroup", 3: "AXGroup", 4: "AXGroup",
                     5: "AXTabGroup", 6: "AXRadioButton", 7: "AXRadioButton", 9: "AXWebArea", 8: "AXTab"]
        let found = BrowserChatDestination.collectTabs(0, children: { children[$0] ?? [] },
            role: { roles[$0] ?? "" }, same: { $0 == $1 })
        #expect(found == [6, 7])
    }
}
