import Foundation

/// 路由与调度参数。数值是待调起点，不是用户指定的精确值。
public struct RouterConfig: Sendable {
    /// 候选状态需稳定这么久才生效（建议 300–600 ms）。
    public var debounceMs: Double = 400
    /// 每个显示状态至少保持这么久（建议 1–2 s）。
    public var minHoldMs: Double = 1500
    /// 工具结束后仍按该工具的活动计算这么久：合并同类连续短调用，避免“读—想—读”来回切。
    /// 真实转录中连续调用之间通常隔 2–4 秒模型生成时间，1.2 秒时会读书／思考交替。
    public var toolGraceMs: Double = 3500
    /// 任务结束后先显示“递交报告”这么久（够播完整理文件那一下），之后换成“完成任务”的勾选卡。
    public var respondHoldMs: Double = 3000
    /// 勾选卡举起来就不自己放下：一直举到用户点击（点击后跳到对应的聊天）。
    /// 这个值只决定“多久之内结束的任务才举牌”：播放器启动时回放到的旧记录不会举一块过期的牌。
    /// 须大于 respondHoldMs，否则勾选卡永远不出现。
    public var completeArmMs: Double = 8000
    /// 举着的牌子被晾这么久还没点，就先让位给还在干活的聊天；牌子不放下，
    /// 等那条聊天也停下来时再举回来。
    public var signYieldMs: Double = 15 * 60 * 1000
    /// 工具失败后沮丧最多显示这么久；期间开始新工具会立即接替，之后回到思考。
    public var failedHoldMs: Double = 4000
    /// 本轮因错误中止后沮丧停留这么久，然后回空闲。
    public var failedLingerMs: Double = 8000
    /// 任务进行中、没有未结束工具、且这么久没有任何事件：视为失联，回空闲。
    public var staleNoToolMs: Double = 10 * 60 * 1000
    /// 有未结束工具（例如长时间构建）时的失联上限。
    public var staleOpenToolMs: Double = 30 * 60 * 1000
    /// 两个适配器同时报告同一任务开始时，这个窗口内的重复开始被忽略。
    public var duplicateTaskStartMs: Double = 3000

    public init() {}
}

/// 头顶气泡的内容：大任务标题 + 当前任务（没有任务清单时是正在进行的活动）+ 进度。
public struct StatusLine: Equatable, Sendable {
    public struct Progress: Equatable, Sendable {
        public let done: Int
        public let total: Int

        public init(done: Int, total: Int) {
            self.done = done
            self.total = total
        }
    }

    /// 大任务：会话标题；没有标题时用这一轮请求的第一行。
    public let title: String?
    /// 当前任务：任务清单里进行中的一项；没有清单时是正在进行的活动，例如“编辑 main.swift”。
    public let current: String
    /// 任务清单进度；没有清单时为 nil。
    public let progress: Progress?

    public init(title: String?, current: String, progress: Progress?) {
        self.title = title
        self.current = current
        self.progress = progress
    }
}

/// 一条聊天（会话）的概要：多个聊天同时跑时，菜单里按这个列出来挑一条跟。
public struct SessionSummary: Equatable, Sendable {
    /// 转录会话 ID，也是点击举牌时用来找聊天的那个 ID。
    public let id: String
    /// 会话标题；没有标题时是这一轮请求的第一行；都没有时 nil。
    public let title: String?
    /// 这条聊天此刻会让雪绪显示什么（不经防抖，也不会顺手把勾选卡举起来）。
    public let state: PetState
    /// 任务进行中且没有失联。
    public let live: Bool
    /// 轮到你了：在等你回答、出错停住、或举着勾选卡。
    public let wantsYou: Bool
    /// 已经举起勾选卡，等人点（被别的聊天挤掉焦点时仍然举着）。
    public let raisedSign: Bool
    /// 牌子举太久没人点，已经先让位给还在干活的聊天（牌子仍举着）。
    public let signYielded: Bool
    /// 距最近一次事件多久（毫秒）。
    public let quietMs: Double
    /// 雪绪当前跟的就是这条。
    public let focused: Bool
    /// 用户在菜单里挑定了这条。
    public let pinned: Bool

    public init(id: String, title: String?, state: PetState, live: Bool, wantsYou: Bool = false,
                raisedSign: Bool, signYielded: Bool = false, quietMs: Double,
                focused: Bool, pinned: Bool) {
        self.id = id
        self.title = title
        self.state = state
        self.live = live
        self.wantsYou = wantsYou
        self.raisedSign = raisedSign
        self.signYielded = signYielded
        self.quietMs = quietMs
        self.focused = focused
        self.pinned = pinned
    }

    /// 菜单里的一行：聊天名 + 它此刻在干什么。
    public var menuLabel: String { "\(name) · \(statusText)" }

    /// 聊天名：会话标题或请求第一行；都没有时用会话 ID 前 8 位。
    public var name: String { Self.displayName(title: title, id: id) }

    /// 同一套聊天名算法，旁边那叠通知卡也用它。
    public static func displayName(title: String?, id: String, max: Int = 32) -> String {
        guard let t = title?.trimmingCharacters(in: .whitespacesAndNewlines), !t.isEmpty else {
            return tr("Session \(id.prefix(8))…", "会话 \(id.prefix(8))…")
        }
        return t.count > max ? t.prefix(max) + "…" : t
    }

    /// 正在做什么：在跑的显示动作，等你处理的说在等什么，其余显示多久没动静。
    public var statusText: String {
        if signYielded { return tr("Holding the sign for you (stepped aside)", "举着牌子等你（先让位了）") }
        if raisedSign || state == .task_complete { return tr("Holding the sign, click her", "举着牌子等你点") }
        if live { return ActivityRouter.stateText(state) }
        switch state {
        case .respond: return tr("Just answered", "刚答完")
        case .failed: return tr("Stopped on an error", "出错停住了")
        default: return Self.agoText(quietMs)
        }
    }

    static func agoText(_ ms: Double) -> String {
        let seconds = Int(max(0, ms) / 1000)
        if seconds < 60 { return tr("just now", "刚刚") }
        if seconds < 3600 { return tr("\(seconds / 60) min ago", "\(seconds / 60) 分钟前") }
        return tr("\(seconds / 3600) h ago", "\(seconds / 3600) 小时前")
    }
}

/// 单个会话的活动模型。
final class SessionModel {
    /// 勾选卡的三种情形：没举、举着、用户点过了（这一轮不再举）。
    enum Sign {
        case none
        case raised
        case dismissed
    }

    struct OpenCall {
        let id: String
        let state: PetState
        let at: Double
        let detail: String?
    }

    /// 这条聊天的转录会话 ID，也就是 sessions 字典里的键。判断"这条是不是正开在眼前"要用。
    let id: String
    let source: String
    var taskActive = false
    var taskStartedAt: Double = -.infinity
    var taskStartedTs: Double = -.infinity
    var taskEndedAt: Double?
    var taskEndedTs: Double = -.infinity
    var lastEventAt: Double
    var open: [OpenCall] = []
    var lastToolState: PetState?
    var lastToolEndedAt: Double?
    var finalAnswerAt: Double?
    /// 勾选卡：任务刚结束时举起，举到用户点击为止（见 ActivityRouter.dismissCompletion）。
    var sign: Sign = .none
    /// 牌子举起来的时刻：晾太久（signYieldMs）就先让位给还在干活的聊天。
    var signRaisedAt: Double?
    /// 最近一次失败（工具报错或本轮因错误中止）的时间。
    var failedAt: Double?
    /// 失败的那次工具调用的说明；API 报错时为 nil。
    var failedDetail: String?
    /// 各动作最近一次工具调用的说明，让气泡文字和显示的动作对得上。
    var lastDetail: [PetState: String] = [:]
    /// 会话标题与这一轮请求的第一行（大任务）。
    var title: String?
    var prompt: String?
    /// 任务清单。跨轮保留：用户说“继续”时进度接着算。
    var todos: [TodoItem] = []
    /// 已结束的调用 ID（处理“结束先于开始”的乱序和重复事件）。有上限。
    private var endedIDs: [String] = []
    private var endedSet: Set<String> = []

    init(id: String, source: String, now: Double) {
        self.id = id
        self.source = source
        self.lastEventAt = now
    }

    func beginTask(now: Double, ts: Double) {
        taskActive = true
        taskStartedAt = now
        taskStartedTs = ts
        taskEndedAt = nil
        open.removeAll()
        lastToolState = nil
        lastToolEndedAt = nil
        finalAnswerAt = nil
        failedAt = nil
        failedDetail = nil
        lastDetail.removeAll()
        sign = .none
        signRaisedAt = nil
    }

    func endTask(now: Double, ts: Double, keepAnswer: Bool) {
        taskActive = false
        taskEndedAt = now
        taskEndedTs = max(taskEndedTs, ts)
        open.removeAll()
        lastToolEndedAt = nil
        failedAt = nil
        if !keepAnswer {
            finalAnswerAt = nil
            sign = .none
            signRaisedAt = nil
        }
    }

    func upsertTodo(_ item: TodoItem) {
        if let i = todos.firstIndex(where: { $0.id == item.id }) {
            if item.status == .deleted {
                todos.remove(at: i)
                return
            }
            if let subject = item.subject { todos[i].subject = subject }
            if let status = item.status { todos[i].status = status }
            return
        }
        guard item.status != .deleted else { return }
        // 上一批全部完成后又新建任务：视为新的一批，进度从头算。
        if item.status == nil, !todos.isEmpty, todos.allSatisfy({ $0.status == .completed }) {
            todos.removeAll()
        }
        var new = item
        if new.status == nil { new.status = .pending }
        todos.append(new)
    }

    func markEnded(_ id: String) {
        guard !endedSet.contains(id) else { return }
        endedIDs.append(id)
        endedSet.insert(id)
        if endedIDs.count > 512 {
            endedSet.remove(endedIDs.removeFirst())
        }
    }

    func wasEnded(_ id: String) -> Bool { endedSet.contains(id) }
}

/// 把事件流变成“当前该显示什么”，并施加防抖与最短保持。
///
/// 时间全部由调用方传入（毫秒），因此可以用虚拟时钟完整测试。
/// 实时模式传入墙钟；回放历史转录时传入事件自身的时间戳。
public final class ActivityRouter {
    public let config: RouterConfig
    public private(set) var displayed: PetState = .idle
    public private(set) var displayedSince: Double
    public private(set) var pending: PetState?
    public private(set) var pendingSince: Double = 0
    /// 当前跟随的会话。多个会话同时工作时，只跟随一个，避免交叉串状态。
    public private(set) var focusedSession: String?
    /// 用户在菜单里挑定的聊天：不为 nil 时只跟这条，别的聊天再忙也抢不走。
    /// 只在本次运行内有效，重启回到自动——和“举着的牌子”一样，是此刻的选择。
    public private(set) var pinnedSession: String?

    /// 此刻正开在眼前的那条聊天（转录会话 ID）。由播放器每隔一会儿填：桌面版 Claude 在最前面、
    /// 且选中的就是这条时才有值，否则 nil。
    ///
    /// 举牌是为了"这条答完了、点我跳过去看"。要是那条聊天本来就开在眼前，人自己已经看见了，
    /// 再举一块牌只是挡路——所以这条聊天不举牌；已经举着的，等你切过去也就放下。
    public var openChatSession: String?

    var sessions: [String: SessionModel] = [:]
    private var anonymousCounter = 0
    /// 被点掉／划掉的卡：会话 → 那一轮的 key，下一轮会重新出现（见 ActivityCards.swift）。
    var dismissedCards: [String: String] = [:]
    /// 不再出卡的聊天（本次运行内）。
    var mutedSessions: Set<String> = []

    public init(config: RouterConfig = RouterConfig(), now: Double) {
        self.config = config
        // 启动时的空闲不占用最短保持时间，第一次切换只受防抖约束。
        self.displayedSince = -.infinity
    }

    // MARK: 事件输入

    public func ingest(_ e: PetEvent, now: Double) {
        if e.kind == .sourceLost {
            for s in sessions.values where s.source == e.source && s.taskActive {
                s.endTask(now: now, ts: e.ts, keepAnswer: false)
            }
            return
        }

        let s: SessionModel
        if let existing = sessions[e.session] {
            s = existing
        } else {
            s = SessionModel(id: e.session, source: e.source, now: now)
            sessions[e.session] = s
        }
        s.lastEventAt = max(s.lastEventAt, now)

        switch e.kind {
        case .taskStart:
            if let prompt = e.detail { s.prompt = prompt }
            if s.taskActive && now - s.taskStartedAt < config.duplicateTaskStartMs { return }
            s.beginTask(now: now, ts: e.ts)

        case .taskEnd:
            guard s.taskActive, e.ts >= s.taskStartedTs else { return }
            s.endTask(now: now, ts: e.ts, keepAnswer: true)

        case .taskAbort:
            guard s.taskActive || s.finalAnswerAt != nil else { return }
            s.endTask(now: now, ts: e.ts, keepAnswer: false)
            s.taskEndedAt = nil

        case .taskFailed:
            guard s.taskActive, e.ts >= s.taskStartedTs else { return }
            s.endTask(now: now, ts: e.ts, keepAnswer: false)
            s.failedAt = now
            s.failedDetail = nil

        case .activityStart:
            // 早于当前任务或已结束任务的迟到事件不能复活旧活动。
            if e.ts < s.taskStartedTs || e.ts < s.taskEndedTs { return }
            if let id = e.eventID, s.wasEnded(id) || s.open.contains(where: { $0.id == id }) { return }
            ensureActive(s, now: now, ts: e.ts)
            let state = e.activity ?? s.lastToolState ?? .default_work
            let id = e.eventID ?? nextAnonymousID()
            s.open.append(.init(id: id, state: state, at: now, detail: e.detail))
            if let detail = e.detail { s.lastDetail[state] = detail }
            s.finalAnswerAt = nil
            s.failedAt = nil

        case .activityEnd, .activityFailed:
            let failed = e.kind == .activityFailed
            let call: SessionModel.OpenCall?
            if let id = e.eventID {
                call = s.open.firstIndex(where: { $0.id == id }).map { s.open.remove(at: $0) }
                s.markEnded(id)
            } else {
                call = s.open.popLast()
            }
            // 重复的结束（两个适配器都报告）找不到未结束调用，不会再次触发沮丧。
            guard let call, s.taskActive else { break }
            s.lastToolState = call.state
            // 失败的工具没有合并窗口：沮丧之后直接回思考，不再显示原来的动作。
            s.lastToolEndedAt = failed ? nil : now
            if failed {
                s.failedAt = now
                s.failedDetail = call.detail
            }

        case .thinking:
            if e.ts < s.taskEndedTs { return }
            ensureActive(s, now: now, ts: e.ts)

        case .finalAnswer:
            if e.ts < s.taskEndedTs { return }
            ensureActive(s, now: now, ts: e.ts)
            s.finalAnswerAt = now

        case .sessionTitle:
            if let title = e.detail?.trimmingCharacters(in: .whitespacesAndNewlines), !title.isEmpty {
                s.title = title
            }

        case .todoList:
            s.todos = (e.todos ?? []).filter { $0.status != .deleted }.map {
                var item = $0
                if item.status == nil { item.status = .pending }
                return item
            }

        case .todoUpdate:
            for item in e.todos ?? [] { s.upsertTodo(item) }

        case .sourceLost:
            break
        }
    }

    /// 在任务中途才开始跟随（或开始事件丢失）时，由其他事件隐式开启任务。
    private func ensureActive(_ s: SessionModel, now: Double, ts: Double) {
        if !s.taskActive { s.beginTask(now: now, ts: ts) }
    }

    private func nextAnonymousID() -> String {
        anonymousCounter += 1
        return "anon-\(anonymousCounter)"
    }

    // MARK: 状态计算

    func isLive(_ s: SessionModel, now: Double) -> Bool {
        guard s.taskActive else { return false }
        let quiet = now - s.lastEventAt
        return quiet <= (s.open.isEmpty ? config.staleNoToolMs : config.staleOpenToolMs)
    }

    /// arming=false：只看不动，不会把勾选卡举起来（列聊天时用）。
    func desired(for s: SessionModel, now: Double, arming: Bool = true) -> PetState {
        if s.taskActive {
            guard isLive(s, now: now) else { return .idle }
            if let last = s.open.last { return last.state }
            if s.finalAnswerAt != nil { return .respond }
            if let f = s.failedAt, now - f < config.failedHoldMs { return .failed }
            if let st = s.lastToolState, let end = s.lastToolEndedAt, now - end < config.toolGraceMs {
                return st
            }
            return .thinking
        }
        if s.finalAnswerAt != nil, let end = s.taskEndedAt {
            let age = now - end
            // 先递交报告（整理文件那一下），再举勾选卡。
            if age < min(config.respondHoldMs, config.completeArmMs) { return .respond }
            // 举起来就不放下：等用户点击（点击后 dismissCompletion 把它记成 .dismissed）。
            // 举牌只发生在任务刚结束时，所以启动时回放到的旧记录不会举牌。
            // 那条聊天正开在眼前：答完的结果他自己看得见，不举牌；已经举着的也就此放下。
            let inSight = openChatSession != nil && openChatSession == s.id
            if s.sign == .raised {
                if inSight {
                    if arming { s.sign = .dismissed }
                } else {
                    return .task_complete
                }
            } else if s.sign == .none && age < config.completeArmMs {
                if inSight {
                    if arming { s.sign = .dismissed }
                } else {
                    if arming {
                        s.sign = .raised
                        s.signRaisedAt = now
                    }
                    return .task_complete
                }
            }
        }
        if let f = s.failedAt, now - f < config.failedLingerMs { return .failed }
        return .idle
    }

    /// 这条聊天刚答完、正等着举牌或已经举着牌：答完的提示要让人看见。
    func completionPending(_ s: SessionModel, now: Double) -> Bool {
        if s.sign == .raised { return true }
        guard s.sign == .none, s.finalAnswerAt != nil, let end = s.taskEndedAt else { return false }
        return now - end < config.completeArmMs
    }

    /// 这条聊天在等你拿主意（AskUserQuestion 还没结束）。
    func waitingForUser(_ s: SessionModel, now: Double) -> Bool {
        isLive(s, now: now) && s.open.last?.state == .question_for_user
    }

    /// 整轮出错停在那儿（工具出错时任务还在跑，不算）。
    func failedPending(_ s: SessionModel, now: Double) -> Bool {
        guard !s.taskActive, let f = s.failedAt else { return false }
        return now - f < config.failedLingerMs
    }

    /// 轮到你了：举着牌子、刚答完、整轮出错、或在等你回答。这类聊天比“还在干活”的优先。
    private func needsUser(_ s: SessionModel, now: Double) -> Bool {
        completionPending(s, now: now) || waitingForUser(s, now: now) || failedPending(s, now: now)
    }

    /// 等你处理的分档，越小越先看。和 ChatGPT 桌面版那只宠物的排法一致：
    /// 等你回答 → 出错 → 答完举牌 → （下面才是还在干活的）。牌子晾过头的降到干活之后。
    /// 同一档里给最近的那条。
    private func attentionRank(_ s: SessionModel, now: Double) -> Int? {
        if waitingForUser(s, now: now) { return 0 }
        if failedPending(s, now: now) { return 1 }
        if completionPending(s, now: now) && !signOverdue(s, now: now) { return 2 }
        return nil
    }

    /// 牌子举了这么久都没人点：先让位给还在干活的聊天。牌子不放下，那条也停了就举回来。
    private func signOverdue(_ s: SessionModel, now: Double) -> Bool {
        guard s.sign == .raised, let at = s.signRaisedAt else { return false }
        return now - at >= config.signYieldMs
    }

    /// 任何刚答完的聊天都先把牌子举起来，哪怕这会儿她在跟别的聊天。
    /// 不然别处一忙，这条的牌子过了 completeArmMs 就再也举不起来，那一轮的完成提示就丢了。
    /// 仍受 completeArmMs 约束：播放器启动时回放到的旧记录不会举一块过期的牌。
    private func armPendingSigns(now: Double) {
        for s in sessions.values where s.sign == .none {
            guard s.finalAnswerAt != nil, let end = s.taskEndedAt else { continue }
            let age = now - end
            guard age >= config.respondHoldMs, age < config.completeArmMs else { continue }
            // 那条聊天正开在眼前：人已经看见了，这一轮就不举牌（也不进身侧那叠卡）。
            if openChatSession == s.id {
                s.sign = .dismissed
                continue
            }
            s.sign = .raised
            s.signRaisedAt = now
        }
    }

    func updateFocus(now: Double) {
        armPendingSigns(now: now)
        // 用户在菜单里挑定了一条：只跟这条，完成与提问也不抢。
        if let p = pinnedSession {
            if sessions[p] != nil { focusedSession = p; return }
            // 挑定的那条已经不在了（reset 之后）：回到自动。
            pinnedSession = nil
        }
        // 等你处理的优先：别的聊天还在干活也要先让你看见。
        // 先按档（等你回答 → 出错 → 答完举牌），同档里给最近的那条；处理掉一条再露出下一条。
        let waiting = sessions.compactMap { id, s -> (id: String, rank: Int, at: Double)? in
            // 卡被点掉／划掉的那一轮：知道了，先别再抢。
            guard !isCardDismissed(id: id, s) else { return nil }
            return attentionRank(s, now: now).map { (id, $0, s.lastEventAt) }
        }
        if let best = waiting.min(by: { $0.rank != $1.rank ? $0.rank < $1.rank : $0.at > $1.at }) {
            focusedSession = best.id
            return
        }
        if let f = focusedSession, let s = sessions[f], isLive(s, now: now) { return }
        let live = sessions.filter { isLive($0.value, now: now) }
        if let best = live.max(by: { $0.value.lastEventAt < $1.value.lastEventAt }) {
            focusedSession = best.key
            return
        }
        // 没人在干活了：晾久让位的牌子重新举回来。
        // 当前这条还有东西要显示（沮丧、没停完的递交报告）时先不换。
        if let f = focusedSession, let s = sessions[f],
           desired(for: s, now: now, arming: false) != .idle { return }
        let overdue = sessions.filter { needsUser($0.value, now: now) && !isCardDismissed(id: $0.key, $0.value) }
        if let best = overdue.max(by: { $0.value.lastEventAt < $1.value.lastEventAt }) {
            focusedSession = best.key
        }
        // 都没有时保持原焦点，让“递交报告”能停留完。
    }

    // MARK: 多个聊天同时跑时挑一条

    /// 最近的聊天，按“先看谁”排：等你处理的在最前，然后是在跑的，再按安静时间。
    ///
    /// - quietWithinMs: 多久没动静的聊天就不列了（等你处理的、在跑的、挑定的、正跟着的一定保留）。
    /// - limit: 最多列几条。
    public func sessionSummaries(now: Double, quietWithinMs: Double = .infinity,
                                 limit: Int = .max) -> [SessionSummary] {
        updateFocus(now: now)
        var rows: [(rank: Int, quiet: Double, summary: SessionSummary)] = []
        for (id, s) in sessions {
            let live = isLive(s, now: now)
            let wants = needsUser(s, now: now) && !isCardDismissed(id: id, s)
            let focused = id == focusedSession
            let pinned = id == pinnedSession
            let quiet = max(0, now - s.lastEventAt)
            guard wants || live || focused || pinned || quiet <= quietWithinMs else { continue }
            // 等你处理的按档排在最前（0–2），然后是在干活的，再是挑定／正跟着的，最后其余。
            let rank = (wants ? attentionRank(s, now: now) : nil)
                ?? (wants ? 3 : (live ? 4 : ((pinned || focused) ? 5 : 6)))
            rows.append((rank, quiet, SessionSummary(
                id: id, title: s.title ?? s.prompt, state: desired(for: s, now: now, arming: false),
                live: live, wantsYou: wants, raisedSign: s.sign == .raised,
                signYielded: signOverdue(s, now: now),
                quietMs: quiet, focused: focused, pinned: pinned)))
        }
        return rows.sorted {
            if $0.rank != $1.rank { return $0.rank < $1.rank }
            if $0.quiet != $1.quiet { return $0.quiet < $1.quiet }
            return $0.summary.id < $1.summary.id          // 同样新旧时给个稳定顺序
        }.prefix(limit).map(\.summary)
    }

    /// 在菜单里挑一条聊天跟：传 nil 回到自动（完成与提问优先）。挑中立刻生效，不等防抖。
    /// 返回 false 表示播放器没见过这条聊天（菜单只会给出见过的）。
    @discardableResult
    /// 这条聊天是哪一家的（`PetEvent.source`）。点举牌要按家分路：只有 Claude 和 Codex 能跳回聊天。
    public func sourceOfSession(_ id: String) -> String? { sessions[id]?.source }

    public func pinSession(_ id: String?, now: Double) -> Bool {
        if let id {
            guard sessions[id] != nil else { return false }
            pinnedSession = id
            focusedSession = id
        } else {
            pinnedSession = nil
        }
        commit(desiredState(now: now), now: now)
        return true
    }

    /// 不考虑防抖时，此刻“应该”显示的状态。
    public func desiredState(now: Double) -> PetState {
        updateFocus(now: now)
        guard let f = focusedSession, let s = sessions[f] else { return .idle }
        return desired(for: s, now: now)
    }

    /// 正举着勾选卡的会话 ID：点击雪绪时跳到这条聊天。没举牌时为 nil。
    public var completedSession: String? {
        guard displayed == .task_complete, let f = focusedSession, sessions[f]?.sign == .raised else { return nil }
        return f
    }

    /// 正立着问号卡的会话 ID：点击雪绪时跳到这条聊天去回答。没在问时为 nil。
    /// 和勾选卡不同，点了不收卡：问题还等着你答，卡片等 AskUserQuestion 结束自己收。
    public var askingSession: String? {
        guard displayed == .question_for_user, let f = focusedSession, sessions[f] != nil else { return nil }
        return f
    }

    /// 用户点了举着的牌子：放下，立刻回到此刻该显示的状态（不等防抖）。返回是否真的放下了。
    @discardableResult
    public func dismissCompletion(now: Double) -> Bool {
        guard let f = focusedSession, let s = sessions[f], s.sign == .raised else { return false }
        s.sign = .dismissed
        commit(desiredState(now: now), now: now)
        return true
    }

    /// 推进调度。返回新的显示状态（若发生切换）。
    @discardableResult
    public func tick(now: Double) -> PetState? {
        let want = desiredState(now: now)
        if want == displayed {
            pending = nil
            return nil
        }
        if pending != want {
            pending = want
            pendingSince = now
        }
        if now - pendingSince >= config.debounceMs && now - displayedSince >= config.minHoldMs {
            commit(want, now: now)
            return want
        }
        return nil
    }

    /// 立即显示当前应显示的状态（启动时回放完历史后使用，不做防抖）。
    public func settle(now: Double) {
        commit(desiredState(now: now), now: now)
    }

    func commit(_ state: PetState, now: Double) {
        displayed = state
        displayedSince = now
        pending = nil
    }

    public func reset(now: Double) {
        sessions.removeAll()
        focusedSession = nil
        pinnedSession = nil
        dismissedCards.removeAll()
        mutedSessions.removeAll()
        commit(.idle, now: now)
    }

    // MARK: 头顶气泡

    /// 气泡内容，跟随当前显示的动作（已防抖）。没有任务时返回 nil（隐藏气泡）。
    public func statusLine(now: Double) -> StatusLine? {
        guard let f = focusedSession, let s = sessions[f] else { return nil }
        // AskUserQuestion 等“等你回答”的调用显示空闲动作，但任务仍在进行。
        let waitingForUser = s.taskActive && s.open.last?.state == .question_for_user
        if displayed == .idle && !waitingForUser { return nil }

        let progress = s.todos.isEmpty ? nil : StatusLine.Progress(
            done: s.todos.filter { $0.status == .completed }.count, total: s.todos.count)
        let inProgress = s.todos.first(where: { $0.status == .inProgress })?.subject.flatMap { $0.isEmpty ? nil : $0 }
        let current: String
        switch displayed {
        case .failed:
            current = s.failedDetail.map { tr("Error: \($0)", "出错：\($0)") } ?? tr("Something went wrong", "出错了")
        case .respond:
            current = s.taskActive ? tr("Writing the answer", "整理回答") : tr("Answered", "已回答")
        case .idle, .question_for_user:
            // 问号卡也能点（跳到这条聊天去回答），和勾选卡一样在气泡里说一声，不然没人知道能点。
            current = tr("Your turn · click to open", "\(s.open.last?.detail ?? "等你回答") · 点她跳过去")
        case .task_complete:
            current = tr("Done · click to open", "已完成 · 点她跳过去")
        case .thinking:
            current = inProgress ?? tr("Thinking", "思考中")
        default:
            current = inProgress ?? s.lastDetail[displayed] ?? Self.stateText(displayed)
        }
        return StatusLine(title: s.title ?? s.prompt, current: current, progress: progress)
    }

    /// 状态的说法（按界面语言）：气泡没有更具体的文字时用它，聊天列表里也用它。
    public static func stateText(_ state: PetState) -> String {
        switch state {
        case .read_file: return tr("Reading a file", "阅读文件")
        case .view_image: return tr("Viewing an image", "查看图片")
        case .write_file: return tr("Editing a file", "修改文件")
        case .verify: return tr("Running tests", "运行测试")
        case .read_web: return tr("Browsing the web", "浏览网页")
        case .default_work: return tr("Working", "处理中")
        case .thinking: return tr("Thinking", "思考中")
        case .respond: return tr("Writing the answer", "整理回答")
        case .failed: return tr("Something went wrong", "出错了")
        case .question_for_user: return tr("Waiting for your answer", "等你回答")
        case .task_complete: return tr("Done · click to open", "已完成 · 点她跳过去")
        case .idle: return tr("Waiting for your answer", "等你回答")
        }
    }

    // MARK: 调试信息

    public struct Snapshot: Equatable, Sendable {
        public let focusedSession: String?
        public let taskActive: Bool
        public let openTools: Int
        public let sessionCount: Int
    }

    public func snapshot() -> Snapshot {
        let s = focusedSession.flatMap { sessions[$0] }
        return Snapshot(focusedSession: focusedSession, taskActive: s?.taskActive ?? false,
                        openTools: s?.open.count ?? 0, sessionCount: sessions.count)
    }
}
