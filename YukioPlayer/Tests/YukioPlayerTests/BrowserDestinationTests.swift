import Testing
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
}
