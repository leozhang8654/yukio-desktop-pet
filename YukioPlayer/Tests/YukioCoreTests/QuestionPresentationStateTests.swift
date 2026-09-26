import Testing
@testable import YukioCore

@Suite struct QuestionPresentationStateTests {
    private func key(_ session: String, _ call: String) -> QuestionPresentationState.Key {
        .init(.init(session: session, callID: call, question: PetQuestion(header: nil, text: "选择一个")))
    }

    @Test func closingSeveralCardsDoesNotReshowTheFirst() {
        var state = QuestionPresentationState()
        let a = key("chat-a", "call"), b = key("chat-b", "call")
        state.dismiss(a)
        #expect(!state.isDismissed(b))
        state.dismiss(b)
        #expect(state.isDismissed(a))
        #expect(!state.isDismissed(key("chat-a", "new-call")))
    }

    @Test func sendResultSurvivesFocusChangeWithoutClaimingDelivery() {
        var state = QuestionPresentationState()
        let a = key("chat-a", "call"), b = key("chat-b", "call")
        state.setNotice("Sending", for: a)
        state.setNotice("Copied, paste in chat", for: a)
        #expect(state.notice(for: a) == "Copied, paste in chat")
        #expect(!state.isDismissed(a))
        #expect(state.notice(for: b) == nil)
        state.dismiss(a)
        #expect(state.isDismissed(a))
        #expect(!state.isDismissed(b))
    }
}
