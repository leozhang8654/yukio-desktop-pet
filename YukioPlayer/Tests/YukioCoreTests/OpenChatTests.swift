import Foundation
import Testing
@testable import YukioCore

/// 举牌是为了"这条答完了，点我跳过去看"。那条聊天要是本来就开在眼前，人已经看见了，
/// 再举一块牌只是挡路。这组测试盯住这个取舍。
@Suite struct OpenChatTests {
    /// 答完时那条聊天正开在眼前：不举牌，直接回空闲。
    @Test func noCardWhenThatChatIsAlreadyInSight() {
        var config = RouterConfig()
        config.completeArmMs = 8000
        config.respondHoldMs = 3000
        let h = Harness(config: config)
        h.router.openChatSession = h.session
        h.send(.taskStart)
        h.run(to: 3000)
        h.send(.finalAnswer); h.send(.taskEnd)
        h.run(to: 60000)
        #expect(!h.states.contains(.task_complete))
        #expect(h.router.completedSession == nil)
    }

    /// 对照：同样的时序，人没开着那条聊天时照常举牌。
    @Test func cardStillGoesUpWhenNotInSight() {
        var config = RouterConfig()
        config.completeArmMs = 8000
        config.respondHoldMs = 3000
        let h = Harness(config: config)
        h.send(.taskStart)
        h.run(to: 3000)
        h.send(.finalAnswer); h.send(.taskEnd)
        h.run(to: 60000)
        #expect(h.states.contains(.task_complete))
        #expect(h.router.completedSession == h.session)
    }

    /// 开着的是另一条聊天：这条还是要举牌。
    @Test func anotherChatInSightDoesNotSuppressThisOne() {
        var config = RouterConfig()
        config.completeArmMs = 8000
        config.respondHoldMs = 3000
        let h = Harness(config: config)
        h.router.openChatSession = "别的聊天"
        h.send(.taskStart)
        h.run(to: 3000)
        h.send(.finalAnswer); h.send(.taskEnd)
        h.run(to: 60000)
        #expect(h.states.contains(.task_complete))
        #expect(h.router.completedSession == h.session)
    }

    /// 牌子已经举着，人自己切到那条聊天：牌子就此放下，不用再点她一下。
    @Test func raisedCardGoesDownWhenYouOpenThatChatYourself() {
        var config = RouterConfig()
        config.completeArmMs = 8000
        config.respondHoldMs = 3000
        let h = Harness(config: config)
        h.send(.taskStart)
        h.run(to: 3000)
        h.send(.finalAnswer); h.send(.taskEnd)
        h.run(to: 20000)
        #expect(h.router.displayed == .task_complete)

        h.router.openChatSession = h.session
        h.run(to: h.now + 2000)
        #expect(h.router.displayed == .idle)
        #expect(h.router.completedSession == nil)
        // 切走也不会自己举回来：这一轮已经算看过了。
        h.router.openChatSession = nil
        h.run(to: h.now + 20000)
        #expect(h.router.displayed == .idle)
    }

    /// lastFocusedAt 是裸数字，不是带引号的值：字符串版取不到，数字版取得到。
    @Test func numberFieldIsReadFromRecordHead() {
        let head = Data(#"{"sessionId":"local_a","cliSessionId":"c0a8","lastFocusedAt":1758342937123,"#.utf8)
        #expect(ClaudeSessionLinks.number(of: "lastFocusedAt", in: head) == 1758342937123)
        #expect(ClaudeSessionLinks.value(of: "lastFocusedAt", in: head) == nil)
        #expect(ClaudeSessionLinks.value(of: "cliSessionId", in: head) == "c0a8")
    }
}

/// 举牌有两条路：当前跟着的那条走 desired(for:)，别的聊天走 armPendingSigns。
/// 开在眼前的那条两条路都不该举牌——否则它会从身侧那叠卡里冒出来。
@Suite struct OpenChatArmingTests {
    @Test func aChatInSightIsNotArmedEvenWhileSheFollowsAnother() {
        var config = RouterConfig()
        config.completeArmMs = 8000
        config.respondHoldMs = 3000
        let h = Harness(config: config)
        // 她正跟着 s1（一直在干活），s2 在背后答完了，而 s2 正开在眼前。
        h.router.openChatSession = "s2"
        h.send(.taskStart, session: "s1")
        h.send(.taskStart, session: "s2")
        h.run(to: 1000)
        h.send(.finalAnswer, session: "s2"); h.send(.taskEnd, session: "s2")
        h.run(to: 20000)
        #expect(h.router.completedSession == nil)
        #expect(!h.router.sessionSummaries(now: h.now).contains { $0.id == "s2" && $0.raisedSign })
    }

    /// 对照：同样的时序，s2 没开在眼前时照常举牌，会进那叠卡。
    @Test func aChatOutOfSightIsStillArmed() {
        var config = RouterConfig()
        config.completeArmMs = 8000
        config.respondHoldMs = 3000
        let h = Harness(config: config)
        h.send(.taskStart, session: "s1")
        h.send(.taskStart, session: "s2")
        h.run(to: 1000)
        h.send(.finalAnswer, session: "s2"); h.send(.taskEnd, session: "s2")
        h.run(to: 20000)
        #expect(h.router.sessionSummaries(now: h.now).contains { $0.id == "s2" && $0.raisedSign })
    }
}
