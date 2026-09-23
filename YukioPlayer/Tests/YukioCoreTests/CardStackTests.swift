import Testing
@testable import YukioCore

private extension Harness {
    func to(_ session: String, _ kind: PetEvent.Kind, id: String? = nil, _ activity: PetState? = nil,
            detail: String? = nil) {
        router.ingest(PetEvent(ts: now, source: "test", session: session, kind: kind, eventID: id,
                               activity: activity, detail: detail), now: now)
    }

    var cards: [ActivityCard] { router.cards(now: now) }
}

/// 雪绪旁边那叠通知卡。
@Suite struct CardStackTests {
    init() { L10n.language = .chinese }   // 这些测试按中文文案断言
    /// 三条聊天各有话说：等你回答的排最前，然后出错的、答完的，最后还在干活的。
    private func threeChats() -> Harness {
        let h = Harness()
        h.to("work", .taskStart, detail: "改登录页")
        h.to("work", .activityStart, id: "w1", .write_file, detail: "编辑 Login.swift")
        h.run(to: 1000)
        h.to("done", .taskStart, detail: "写个脚本")
        h.run(to: 2000)
        h.to("done", .finalAnswer)
        h.to("done", .taskEnd)
        h.run(to: 3000)
        h.to("ask", .taskStart, detail: "要不要换个库")
        h.to("ask", .activityStart, id: "q", .question_for_user, detail: "等你挑一个")
        h.run(to: 6000)
        return h
    }

    @Test func cardsAreSortedByWhoNeedsYouFirstAndSkipTheOneSheIsShowing() {
        let h = threeChats()
        // 她跟着“等你回答”的那条，所以那条不在卡叠里（头顶气泡已经在讲它）。
        #expect(h.router.focusedSession == "ask")
        #expect(h.cards.map(\.session) == ["done", "work"])
        #expect(h.cards[0].status == .ready)
        #expect(h.cards[0].title == "写个脚本")
        #expect(h.cards[0].subtitle == "点开看看")
        #expect(h.cards[1].status == .running)
        #expect(h.cards[1].subtitle == "编辑 Login.swift")
        // 连她正显示的那条一起列（自查用）时，等你回答的排最前。
        #expect(h.router.cards(now: h.now, includeFocused: true).map(\.session) == ["ask", "done", "work"])
    }

    @Test func aFailedChatGetsACardAheadOfTheFinishedOne() {
        let h = threeChats()
        h.to("bad", .taskStart, detail: "跑个构建")
        h.run(to: 7000)
        h.to("bad", .taskFailed)
        h.run(to: 8000)
        #expect(h.cards.map(\.session) == ["bad", "done", "work"])
        #expect(h.cards[0].status == .failed)
        #expect(h.cards[0].subtitle == "这一轮没做完")
    }

    @Test func dismissingACardPutsTheSignDownAndKeepsItAwayUntilTheNextTurn() {
        let h = threeChats()
        #expect(h.cards.map(\.session) == ["done", "work"])
        h.router.dismissCard(session: "done", now: h.now)
        #expect(h.cards.map(\.session) == ["work"])
        // 那条聊天又开工：卡重新出现。
        h.run(to: 9000)
        h.to("done", .taskStart, detail: "接着写")
        h.to("done", .activityStart, id: "d1", .read_file, detail: "读 backup.sh")
        h.run(to: 10000)
        #expect(h.cards.contains { $0.session == "done" && $0.status == .running })
    }

    @Test func dismissingTheCardOfTheChatSheIsShowingSwitchesHerToTheNextOne() {
        let h = threeChats()
        // 她正举着别人的问号卡；直接点掉“等你回答”的那条（卡叠里看不到它，但菜单可以）。
        #expect(h.router.focusedSession == "ask")
        h.router.dismissCard(session: "ask", now: h.now)
        h.run(to: 8000)
        // 换成答完的那条（档位比“在跑”的高）。
        #expect(h.router.focusedSession == "done")
        #expect(h.cards.map(\.session) == ["work"])
    }

    @Test func mutedChatsGetNoCards() {
        let h = threeChats()
        h.router.muteCards(session: "work")
        #expect(h.router.isMuted(session: "work"))
        #expect(h.cards.map(\.session) == ["done"])
        h.router.unmuteCards(session: "work")
        #expect(h.cards.map(\.session) == ["done", "work"])
    }

    @Test func quietChatsDropOffTheStack() {
        let h = threeChats()
        // 半个多小时没动静：在跑的和等你回答的都算失联，不再出卡；
        // 只剩那条举着牌子的，她自己转过去显示它，旁边就空了。
        h.run(to: 35 * 60_000)
        #expect(h.router.focusedSession == "done")
        #expect(h.cards.isEmpty)
        #expect(h.router.cards(now: h.now, includeFocused: true).map(\.session) == ["done"])
    }
}
