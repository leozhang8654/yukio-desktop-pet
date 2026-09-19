import Testing
@testable import YukioCore

private extension Harness {
    /// 指定聊天发事件，可带标题／说明。
    func to(_ session: String, _ kind: PetEvent.Kind, id: String? = nil, _ activity: PetState? = nil,
            detail: String? = nil) {
        router.ingest(PetEvent(ts: now, source: "test", session: session, kind: kind, eventID: id,
                               activity: activity, detail: detail), now: now)
    }
}

/// 多个聊天同时跑：谁优先、怎么挑一条跟。
@Suite struct ChatPickTests {
    @Test func aFinishedChatTakesOverEvenWhileAnotherChatKeepsWorking() {
        let h = Harness()
        h.to("A", .taskStart)
        h.to("A", .activityStart, id: "a1", .read_file)
        h.run(to: 2000)
        #expect(h.router.focusedSession == "A")

        h.to("B", .taskStart)
        h.run(to: 2500)
        h.to("B", .finalAnswer)
        h.to("B", .taskEnd)
        h.run(to: 3200)
        // B 答完了：哪怕 A 还在读文件，也先把 B 的完成提示显示出来。
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .respond)

        h.to("A", .activityEnd, id: "a1")
        h.to("A", .activityStart, id: "a2", .write_file)
        h.run(to: 12000)
        #expect(h.router.displayed == .task_complete)
        #expect(h.router.completedSession == "B")

        // 点掉牌子：回到仍在干活的 A。
        #expect(h.router.dismissCompletion(now: h.now))
        #expect(h.router.focusedSession == "A")
        #expect(h.router.displayed == .write_file)
    }

    @Test func aQuestionTakesOverFromAnotherChatsWork() {
        let h = Harness()
        h.to("A", .taskStart)
        h.to("A", .activityStart, id: "a1", .default_work)
        h.run(to: 2000)
        h.to("B", .taskStart)
        h.to("B", .activityStart, id: "q", .question_for_user)
        h.run(to: 4500)
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .question_for_user)

        // 回答之后 B 接着干活，焦点留在 B，A 不来抢。
        h.to("B", .activityEnd, id: "q")
        h.to("B", .activityStart, id: "b1", .write_file)
        h.run(to: 8000)
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .write_file)
    }

    @Test func theOlderCardComesBackAfterYouHandleTheNewerOne() {
        let h = Harness()
        h.to("B", .taskStart)
        h.run(to: 1000)
        h.to("B", .finalAnswer)
        h.to("B", .taskEnd)
        h.run(to: 6000)
        #expect(h.router.displayed == .task_complete)
        #expect(h.router.completedSession == "B")

        // C 随后提问：更近的先给你看，B 的牌子仍举着。
        h.to("C", .taskStart)
        h.to("C", .activityStart, id: "q", .question_for_user)
        h.run(to: 9000)
        #expect(h.router.focusedSession == "C")
        #expect(h.router.displayed == .question_for_user)

        h.to("C", .activityEnd, id: "q")
        h.to("C", .activityStart, id: "c1", .read_file)
        h.run(to: 13000)
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .task_complete)
    }

    @Test func anIgnoredCardYieldsAfterAWhileAndComesBackWhenTheOtherChatStops() {
        var config = RouterConfig()
        config.signYieldMs = 15 * 60 * 1000
        let h = Harness(config: config)
        h.to("A", .taskStart, detail: "改登录页")
        h.to("A", .activityStart, id: "a1", .read_file)
        h.run(to: 1000)
        h.to("B", .taskStart, detail: "写个脚本")
        h.run(to: 2000)
        h.to("B", .finalAnswer)
        h.to("B", .taskEnd)
        h.run(to: 12000)
        // 先举牌：A 还在读文件也抢不走。
        #expect(h.router.displayed == .task_complete)
        #expect(h.router.completedSession == "B")

        // 晾了一刻钟没人点：先让位给还在干活的 A，牌子不放下。
        h.run(to: 16 * 60_000)
        #expect(h.router.focusedSession == "A")
        #expect(h.router.displayed == .read_file)
        #expect(h.router.completedSession == nil)
        let listed = h.router.sessionSummaries(now: h.now)
        #expect(listed.first?.id == "B")        // 仍排在最前，等你处理
        #expect(listed.first?.signYielded == true)
        #expect(listed.first?.menuLabel == "写个脚本 · 举着牌子等你（先让位了）")

        // A 也停了：牌子重新举回来，点它照样跳回 B。
        h.to("A", .taskAbort)
        h.run(to: 16 * 60_000 + 5000)
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .task_complete)
        #expect(h.router.completedSession == "B")
        #expect(h.router.dismissCompletion(now: h.now))
        #expect(h.router.displayed == .idle)
    }

    @Test func aQuestionOutranksANewerFinishedChatAndAStuckChatOutranksWork() {
        let h = Harness()
        // A 在等你拿主意。
        h.to("A", .taskStart)
        h.to("A", .activityStart, id: "q", .question_for_user)
        h.run(to: 2000)
        // B 稍后才答完：虽然更近，问号卡仍排在勾选卡前面（和 GPT 那只宠物的档位一致）。
        h.to("B", .taskStart)
        h.run(to: 3000)
        h.to("B", .finalAnswer)
        h.to("B", .taskEnd)
        h.run(to: 9000)
        #expect(h.router.focusedSession == "A")
        #expect(h.router.displayed == .question_for_user)

        // C 整轮出错：排在问号卡之后、勾选卡之前，所以还是 A。
        h.to("C", .taskStart)
        h.run(to: 10000)
        h.to("C", .taskFailed)
        h.run(to: 12000)
        #expect(h.router.focusedSession == "A")

        // A 答完了问题、接着干活：这时轮到出错的 C，而不是还举着牌子的 B。
        h.to("A", .activityEnd, id: "q")
        h.to("A", .activityStart, id: "a1", .write_file)
        h.run(to: 14000)
        #expect(h.router.focusedSession == "C")
        #expect(h.router.displayed == .failed)

        // C 的沮丧停留完，才轮到 B 的勾选卡（答完时她在跟别人，牌子也没丢）。
        h.run(to: 22000)
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .task_complete)
    }

    @Test func aStuckChatIsListedAheadOfTheOnesStillWorking() {
        let h = Harness()
        h.to("work", .taskStart, detail: "改登录页")
        h.to("work", .activityStart, id: "w1", .write_file)
        h.run(to: 1000)
        h.to("bad", .taskStart, detail: "跑个构建")
        h.run(to: 2000)
        h.to("bad", .taskFailed)
        h.run(to: 4000)
        let chats = h.router.sessionSummaries(now: h.now)
        #expect(chats.map(\.id) == ["bad", "work"])
        #expect(chats[0].wantsYou && !chats[1].wantsYou)
        #expect(chats[0].menuLabel == "跑个构建 · 出错停住了")
    }

    @Test func pinnedChatIsNotStolenByOtherChats() {
        let h = Harness()
        h.to("A", .taskStart)
        h.to("A", .activityStart, id: "a1", .read_file)
        h.run(to: 1000)
        h.to("B", .taskStart)
        h.to("B", .activityStart, id: "b1", .write_file)
        h.run(to: 3000)
        #expect(h.router.displayed == .read_file)

        // 挑定 B：立刻换过去，不等防抖。
        #expect(h.router.pinSession("B", now: h.now))
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .write_file)

        // A 答完举牌也抢不走挑定的 B。
        h.to("A", .activityEnd, id: "a1")
        h.to("A", .finalAnswer)
        h.to("A", .taskEnd)
        h.run(to: 8000)
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .write_file)

        // 回到自动：A 的完成提示这时才轮到。
        #expect(h.router.pinSession(nil, now: h.now))
        #expect(h.router.pinnedSession == nil)
        #expect(h.router.focusedSession == "A")
        #expect(h.router.displayed == .task_complete)
    }

    @Test func pinnedChatStaysEvenAfterItStops() {
        let h = Harness()
        h.to("A", .taskStart)
        h.to("A", .activityStart, id: "a1", .read_file)
        h.run(to: 1000)
        h.to("B", .taskStart)
        h.to("B", .activityStart, id: "b1", .write_file)
        h.run(to: 3000)
        h.router.pinSession("B", now: h.now)
        h.to("B", .activityEnd, id: "b1")
        h.to("B", .taskAbort)
        h.run(to: 9000)
        // 挑定的那条停了就空闲等着，不会自己跑去跟 A。
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .idle)

        h.router.pinSession(nil, now: h.now)
        #expect(h.router.focusedSession == "A")
        #expect(h.router.displayed == .read_file)
    }

    @Test func chatListPutsTheOnesWaitingForYouFirst() {
        let h = Harness()
        h.to("old", .taskStart, detail: "看看昨天的报错")
        h.run(to: 1000)
        h.to("old", .taskAbort)
        h.run(to: 600_000)
        h.to("work", .taskStart, detail: "改登录页")
        h.to("work", .activityStart, id: "w1", .write_file)
        h.run(to: 605_000)
        h.to("done", .taskStart, detail: "写个脚本")
        h.to("done", .sessionTitle, detail: "写个备份脚本")
        h.run(to: 606_000)
        h.to("done", .finalAnswer)
        h.to("done", .taskEnd)
        h.run(to: 612_000)

        let chats = h.router.sessionSummaries(now: h.now)
        #expect(chats.map(\.id) == ["done", "work", "old"])
        #expect(chats[0].menuLabel == "写个备份脚本 · 举着牌子等你点")
        #expect(chats[0].raisedSign && chats[0].focused)
        #expect(chats[1].menuLabel == "改登录页 · 修改文件")
        #expect(chats[2].menuLabel == "看看昨天的报错 · 10 分钟前")

        // 安静太久的不列；等你处理的和在跑的一定留着。
        #expect(h.router.sessionSummaries(now: h.now, quietWithinMs: 60_000).map(\.id) == ["done", "work"])
        #expect(h.router.sessionSummaries(now: h.now, limit: 1).map(\.id) == ["done"])
    }

    @Test func aChatWithoutATitleIsListedByItsSessionID() {
        let h = Harness()
        h.to("c0a80650-7c4e-4a1b-9c3d-000000000000", .taskStart)
        h.run(to: 1000)
        let chats = h.router.sessionSummaries(now: h.now)
        #expect(chats.count == 1)
        #expect(chats[0].menuLabel == "会话 c0a80650… · 思考中")
    }

    @Test func aChatThatFinishesWhileSheFollowsAnotherOneKeepsItsCard() {
        let h = Harness()
        h.to("A", .taskStart)
        h.to("A", .activityStart, id: "a1", .read_file)
        h.run(to: 1000)
        h.to("B", .taskStart)
        h.run(to: 2000)
        h.to("B", .finalAnswer)
        h.to("B", .taskEnd)
        // 挑定 A：她一直跟 A，但 B 答完的牌子照样举起来存着，不会因为没轮到就丢了。
        h.router.pinSession("A", now: h.now)
        h.run(to: 20000)
        #expect(h.router.displayed == .read_file)
        let listed = h.router.sessionSummaries(now: h.now)
        #expect(listed.first(where: { $0.id == "B" })?.raisedSign == true)
        // 列聊天只看不动：看完了她还是跟着 A。
        #expect(h.router.displayed == .read_file)
        // 回到自动：B 的牌子这才露出来。
        h.router.pinSession(nil, now: h.now)
        #expect(h.router.focusedSession == "B")
        #expect(h.router.displayed == .task_complete)
        #expect(h.router.completedSession == "B")
    }

    @Test func pickingAChatThePlayerHasNeverSeenChangesNothing() {
        let h = Harness()
        h.to("A", .taskStart)
        h.run(to: 1000)
        #expect(h.router.pinSession("从没见过", now: h.now) == false)
        #expect(h.router.pinnedSession == nil)
        #expect(h.router.focusedSession == "A")
    }
}
