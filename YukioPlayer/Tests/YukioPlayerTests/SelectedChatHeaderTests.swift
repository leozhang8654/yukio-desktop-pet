import Testing
@testable import YukioPlayer

@Suite struct SelectedChatHeaderTests {
    struct Node {
        var role = "AXGroup"
        var label = ""
        var children: [Node] = []
    }
    func button(_ label: String) -> Node { Node(role: "AXButton", label: label) }
    func read(_ root: Node) -> String? {
        BrowserOpenChat.selectedHeader(root, children: { $0.children }, role: { $0.role }, label: { $0.label })
    }
    @Test func deepChromiumWrappersStillReachSelectedHeader() {
        var tree = Node(children: [button("New chat"), button("目标聊天 No chats in progress"), button("More actions")])
        for _ in 0..<9 { tree = Node(children: [tree]) }
        #expect(read(tree) == "目标聊天 No chats in progress")
    }
    @Test func loadingAndMenusDoNotBorrowMessageOrHistoryTitles() {
        let header = Node(children: [button("New chat"), button("旧聊天"), button("More actions")])
        #expect(read(Node(children: [Node(), header])) == nil)
        #expect(read(Node(children: [button("Loading"), header])) == nil)
        #expect(read(Node(children: [button("New chat"), button("旧聊天")])) == nil)
        #expect(read(Node(children: [button("Other"), button("旧聊天"), button("More actions")])) == nil)
    }
    @Test func malformedNestingIsBounded() {
        var tree = Node(children: [button("New chat"), button("目标聊天"), button("More actions")])
        for _ in 0..<20 { tree = Node(children: [tree]) }
        #expect(read(tree) == nil)
    }
}
