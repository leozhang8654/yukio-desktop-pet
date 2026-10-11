import Testing
@testable import YukioCore

@Suite struct VisibleChatTitleTests {
    @Test func officialPanelHeaderAndActivitySuffix() {
        for suffix in ["", " No chats in progress", " 1 chat in progress", " 3 chats in progress"] {
            #expect(VisibleChatTitle.session(header: "添加自动移除牌子功能" + suffix,
                candidates: [("one", "添加自动移除牌子功能"), ("two", "别的聊天")]) == "one")
        }
    }
    @Test func duplicatePartialMissingAndGenericTitlesNeverDismiss() {
        #expect(VisibleChatTitle.session(header: "相同标题", candidates: [("one", "相同标题"), ("two", "相同标题")]) == nil)
        #expect(VisibleChatTitle.session(header: "添加自动…", candidates: [("one", "添加自动移除牌子功能")]) == nil)
        #expect(VisibleChatTitle.session(header: "添加自动", candidates: [("one", "添加自动移除牌子功能")]) == nil)
        #expect(VisibleChatTitle.session(header: "New chat", candidates: [("one", "New chat")]) == nil)
        #expect(VisibleChatTitle.session(header: "No chats in progress", candidates: []) == nil)
    }
}
