import Testing
@testable import YukioCore

/// 用虚拟时钟驱动路由器，记录每次显示切换。
final class Harness {
    let router: ActivityRouter
    var now: Double = 0
    var transitions: [(t: Double, state: PetState)] = []
    let session: String

    init(config: RouterConfig = RouterConfig(), session: String = "s1") {
        router = ActivityRouter(config: config, now: 0)
        self.session = session
    }

    func send(_ kind: PetEvent.Kind, id: String? = nil, _ activity: PetState? = nil, session: String? = nil, source: String = "test") {
        router.ingest(PetEvent(ts: now, source: source, session: session ?? self.session, kind: kind,
                               eventID: id, activity: activity), now: now)
    }

    /// 以 25 ms 步长推进到 t。
    func run(to t: Double) {
        if let s = router.tick(now: now) { transitions.append((now, s)) }
        while now < t {
            now = min(t, now + 25)
            if let s = router.tick(now: now) { transitions.append((now, s)) }
        }
    }

    var states: [PetState] { transitions.map(\.state) }
}

@Suite struct RouterTests {
    @Test func firstSwitchOnlyWaitsForDebounce() {
        let h = Harness()
        h.send(.taskStart)
        h.run(to: 1000)
        #expect(h.states == [.thinking])
        #expect(h.transitions[0].t == 400)
    }

    @Test func burstOfShortReadsMergesIntoOneReadingPose() {
        let h = Harness()
        h.send(.taskStart)
        h.run(to: 3000)
        for (i, t) in [3000.0, 3300, 3600, 3900, 4200].enumerated() {
            h.run(to: t); h.send(.activityStart, id: "r\(i)", .read_file)
            h.run(to: t + 100); h.send(.activityEnd, id: "r\(i)")
        }
        h.run(to: 10000)
        #expect(h.states == [.thinking, .read_file, .thinking])
    }

    @Test func rapidAlternationShorterThanDebounceNeverFlashes() {
        let h = Harness()
        h.send(.taskStart)
        h.send(.activityStart, id: "a", .read_file)
        h.run(to: 3000)
        // 读取仍在进行时，插入 100 ms 的另一类工具。
        h.send(.activityStart, id: "b", .write_file)
        h.run(to: 3100); h.send(.activityEnd, id: "b")
        // 写入结束后的合并窗口里立即又开始读取。
        h.send(.activityStart, id: "c", .read_file)
        h.run(to: 6000)
        #expect(h.states == [.read_file])
    }

    @Test func eachDisplayedStateIsHeldForMinimumTime() {
        let h = Harness()
        h.send(.taskStart)
        h.send(.activityStart, id: "a", .read_file)
        h.run(to: 500)                 // read_file 于 400 ms 显示
        h.send(.activityEnd, id: "a")
        h.send(.activityStart, id: "b", .verify)
        h.run(to: 5000)
        #expect(h.states == [.read_file, .verify])
        #expect(h.transitions[1].t >= h.transitions[0].t + 1500)
    }

    @Test func sameActivityDoesNotRestart() {
        let h = Harness()
        h.send(.taskStart)
        for i in 0..<10 {
            h.send(.activityStart, id: "w\(i)", .write_file)
            h.run(to: h.now + 300)
            h.send(.activityEnd, id: "w\(i)")
            h.run(to: h.now + 300)
        }
        h.run(to: h.now + 100)
        #expect(h.states == [.write_file])
    }

    @Test func respondThenTaskCompleteAfterTaskEndThenReturnsToIdle() {
        var config = RouterConfig()
        config.respondLingerMs = 8000
        config.respondHoldMs = 3000
        let h = Harness(config: config)
        h.send(.taskStart)
        h.run(to: 3000)
        h.send(.finalAnswer); h.send(.taskEnd)
        h.run(to: 20000)
        // 先递交报告，够播完整理文件那一下，再举勾选卡停到停留结束。
        #expect(h.states == [.thinking, .respond, .task_complete, .idle])
        let respondAt = h.transitions[1].t, cardAt = h.transitions[2].t, idleAt = h.transitions[3].t
        #expect(cardAt - respondAt >= 2900 && cardAt - respondAt <= 3600)
        #expect(idleAt - respondAt >= 7500)
    }

    @Test func respondHoldLongerThanLingerNeverShowsTheCard() {
        var config = RouterConfig()
        config.respondLingerMs = 3000
        config.respondHoldMs = 8000
        let h = Harness(config: config)
        h.send(.taskStart)
        h.run(to: 3000)
        h.send(.finalAnswer); h.send(.taskEnd)
        h.run(to: 20000)
        #expect(h.states == [.thinking, .respond, .idle])
    }

    @Test func askUserQuestionShowsTheQuestionCardWhileTheTaskStaysOpen() {
        let h = Harness()
        h.send(.taskStart)
        h.send(.activityStart, id: "q", .question_for_user)
        h.run(to: 4000)
        #expect(h.states == [.question_for_user])
        #expect(h.router.statusLine(now: h.now)?.current == "等你回答")
        h.send(.activityEnd, id: "q")
        h.send(.thinking)
        h.run(to: 8000)
        #expect(h.states == [.question_for_user, .thinking])
    }

    @Test func abortGoesToIdleWithoutReport() {
        let h = Harness()
        h.send(.taskStart)
        h.send(.activityStart, id: "a", .verify)
        h.run(to: 3000)
        h.send(.taskAbort)
        h.run(to: 6000)
        #expect(h.states == [.verify, .idle])
    }

    @Test func endBeforeStartIsIgnored() {
        let h = Harness()
        h.send(.taskStart)
        h.send(.activityEnd, id: "x")
        h.send(.activityStart, id: "x", .read_web)
        h.run(to: 3000)
        #expect(h.states == [.thinking])
    }

    @Test func lateToolEventAfterTaskEndCannotRevive() {
        let h = Harness()
        h.send(.taskStart)
        h.run(to: 2000)
        h.send(.taskAbort)
        h.run(to: 4000)
        let late = PetEvent(ts: 1000, source: "test", session: "s1", kind: .activityStart, eventID: "old", activity: .verify)
        h.router.ingest(late, now: h.now)
        h.run(to: 8000)
        #expect(h.states == [.thinking, .idle])
    }

    @Test func duplicateEventsFromTwoAdaptersAreIdempotent() {
        let h = Harness()
        h.send(.taskStart, source: "claude-transcript")
        h.send(.taskStart, source: "claude-hook")
        h.send(.activityStart, id: "t1", .verify, source: "claude-transcript")
        h.send(.activityStart, id: "t1", .verify, source: "claude-hook")
        h.run(to: 2000)
        h.send(.activityEnd, id: "t1", source: "claude-hook")
        h.send(.activityEnd, id: "t1", source: "claude-transcript")
        h.run(to: 6000)
        #expect(h.states == [.verify, .thinking])
        #expect(h.router.snapshot().openTools == 0)
    }

    @Test func continuePreviousReusesLastToolActivity() {
        let h = Harness()
        h.send(.taskStart)
        h.send(.activityStart, id: "b", .verify)
        h.run(to: 2000)
        h.send(.activityEnd, id: "b")
        h.send(.activityStart, id: "poll", nil)   // 例如 TaskOutput
        h.run(to: 6000)
        #expect(h.states == [.verify])
    }

    @Test func otherSessionDoesNotCrossTalkWhileFocusedSessionIsWorking() {
        let h = Harness()
        h.send(.taskStart, session: "A")
        h.send(.activityStart, id: "a1", .read_file, session: "A")
        h.run(to: 1000)
        h.send(.taskStart, session: "B")
        h.send(.activityStart, id: "b1", .write_file, session: "B")
        h.run(to: 5000)
        #expect(h.states == [.read_file])
        #expect(h.router.focusedSession == "A")
        // A 被中断后，焦点移到仍在工作的 B。
        h.send(.taskAbort, session: "A")
        h.run(to: 9000)
        #expect(h.states == [.read_file, .write_file])
        #expect(h.router.focusedSession == "B")
    }

    @Test func staleSessionFallsBackToIdle() {
        var config = RouterConfig()
        config.staleNoToolMs = 60_000
        let h = Harness(config: config)
        h.send(.taskStart)
        h.run(to: 70_000)
        #expect(h.states == [.thinking, .idle])
    }

    @Test func longRunningToolUsesLongerStaleLimit() {
        var config = RouterConfig()
        config.staleNoToolMs = 60_000
        config.staleOpenToolMs = 300_000
        let h = Harness(config: config)
        h.send(.taskStart)
        h.send(.activityStart, id: "build", .default_work)
        h.run(to: 200_000)
        #expect(h.states == [.default_work])
        h.run(to: 320_000)
        #expect(h.states == [.default_work, .idle])
    }

    @Test func sourceLostReturnsToIdle() {
        let h = Harness()
        h.send(.taskStart, source: "claude-transcript")
        h.send(.activityStart, id: "a", .read_web, source: "claude-transcript")
        h.run(to: 3000)
        h.router.ingest(PetEvent(ts: h.now, source: "claude-transcript", session: "*", kind: .sourceLost), now: h.now)
        h.run(to: 6000)
        #expect(h.states == [.read_web, .idle])
    }

    @Test func settleAfterReplayShowsCurrentStateImmediately() {
        let router = ActivityRouter(now: 0)
        let events: [PetEvent] = [
            .init(ts: 1000, source: "t", session: "s", kind: .taskStart),
            .init(ts: 2000, source: "t", session: "s", kind: .activityStart, eventID: "1", activity: .read_file),
            .init(ts: 2100, source: "t", session: "s", kind: .activityEnd, eventID: "1"),
            .init(ts: 5000, source: "t", session: "s", kind: .activityStart, eventID: "2", activity: .verify),
        ]
        for e in events { router.ingest(e, now: e.ts) }
        router.settle(now: 5200)
        #expect(router.displayed == .verify)
    }

    @Test func toolFailureShowsDejectedUntilNextActivity() {
        let h = Harness()
        h.send(.taskStart)
        h.send(.activityStart, id: "t", .verify)
        h.run(to: 3000)
        h.send(.activityFailed, id: "t")
        h.run(to: 5500)
        h.send(.activityStart, id: "fix", .write_file)
        h.run(to: 9000)
        #expect(h.states == [.verify, .failed, .write_file])
    }

    @Test func dejectedEndsInThinkingNotInTheFailedTool() {
        let h = Harness()
        h.send(.taskStart)
        h.send(.activityStart, id: "t", .verify)
        h.run(to: 3000)
        h.send(.activityFailed, id: "t")
        h.run(to: 12000)
        // 失败的工具没有合并窗口：沮丧结束后回思考，不会又回到“对照检查”。
        #expect(h.states == [.verify, .failed, .thinking])
        #expect(h.transitions[2].t - h.transitions[1].t >= 3500)
    }

    @Test func taskFailureShowsDejectedThenIdle() {
        let h = Harness()
        h.send(.taskStart)
        h.run(to: 3000)
        h.send(.taskFailed)
        h.run(to: 20000)
        #expect(h.states == [.thinking, .failed, .idle])
        #expect(h.transitions[2].t - h.transitions[1].t >= 7500)
    }

    @Test func newPromptEndsDejectedEarly() {
        let h = Harness()
        h.send(.taskStart)
        h.run(to: 3000)
        h.send(.taskFailed)
        h.run(to: 6000)
        h.send(.taskStart)
        h.run(to: 9000)
        #expect(h.states == [.thinking, .failed, .thinking])
    }

    @Test func interruptRightAfterFailureGoesStraightToIdle() {
        let h = Harness()
        h.send(.taskStart)
        h.send(.activityStart, id: "t", .verify)
        h.run(to: 3000)
        h.send(.activityFailed, id: "t")
        h.run(to: 3100)
        h.send(.taskAbort)
        h.run(to: 8000)
        #expect(h.states == [.verify, .idle])
    }

    @Test func demoScriptShowsEveryStateAndRespectsHoldTimes() {
        let h = Harness(session: "demo")
        let steps = DemoScript.steps(session: "demo", start: 0)
        for step in steps {
            h.run(to: step.offsetMs)
            h.router.ingest(step.event, now: h.now)
        }
        h.run(to: DemoScript.durationMs)
        let shown = Set(h.states)
        for s in PetState.allCases where s != .idle { #expect(shown.contains(s), "演示中没有出现 \(s)") }
        #expect(h.states.last == .idle)
        #expect(h.states.dropLast().last == .task_complete)
        #expect(h.states.dropLast(2).last == .respond)
        for (a, b) in zip(h.transitions, h.transitions.dropFirst()) {
            #expect(b.t - a.t >= 1500, "\(a.state) 只显示了 \(b.t - a.t) ms")
        }
        // 连续短读取只出现一次读书动作。
        let readsBeforeImage = h.transitions.filter { $0.t < 9000 && $0.state == .read_file }
        #expect(readsBeforeImage.count == 1)
    }
}
