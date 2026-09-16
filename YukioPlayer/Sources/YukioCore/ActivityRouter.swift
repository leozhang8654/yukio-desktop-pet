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
    /// 任务结束后“递交报告”保持这么久，然后回空闲。
    public var respondLingerMs: Double = 8000
    /// 任务结束后先显示“递交报告”这么久（够播完整理文件那一下），之后换成“完成任务”的勾选卡，
    /// 直到 respondLingerMs 结束。须小于 respondLingerMs。
    public var respondHoldMs: Double = 3000
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

/// 单个会话的活动模型。
final class SessionModel {
    struct OpenCall {
        let id: String
        let state: PetState
        let at: Double
        let detail: String?
    }

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

    init(source: String, now: Double) {
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
    }

    func endTask(now: Double, ts: Double, keepAnswer: Bool) {
        taskActive = false
        taskEndedAt = now
        taskEndedTs = max(taskEndedTs, ts)
        open.removeAll()
        lastToolEndedAt = nil
        failedAt = nil
        if !keepAnswer { finalAnswerAt = nil }
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

    private var sessions: [String: SessionModel] = [:]
    private var anonymousCounter = 0

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
            s = SessionModel(source: e.source, now: now)
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

    private func isLive(_ s: SessionModel, now: Double) -> Bool {
        guard s.taskActive else { return false }
        let quiet = now - s.lastEventAt
        return quiet <= (s.open.isEmpty ? config.staleNoToolMs : config.staleOpenToolMs)
    }

    private func desired(for s: SessionModel, now: Double) -> PetState {
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
        if s.finalAnswerAt != nil, let end = s.taskEndedAt, now - end < config.respondLingerMs {
            // 先递交报告（整理文件那一下），再举勾选卡停住。
            return now - end < min(config.respondHoldMs, config.respondLingerMs) ? .respond : .task_complete
        }
        if let f = s.failedAt, now - f < config.failedLingerMs { return .failed }
        return .idle
    }

    private func updateFocus(now: Double) {
        if let f = focusedSession, let s = sessions[f], isLive(s, now: now) { return }
        let live = sessions.filter { isLive($0.value, now: now) }
        if let best = live.max(by: { $0.value.lastEventAt < $1.value.lastEventAt }) {
            focusedSession = best.key
        }
        // 没有进行中的会话时保持原焦点，让“递交报告”能停留完。
    }

    /// 不考虑防抖时，此刻“应该”显示的状态。
    public func desiredState(now: Double) -> PetState {
        updateFocus(now: now)
        guard let f = focusedSession, let s = sessions[f] else { return .idle }
        return desired(for: s, now: now)
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

    private func commit(_ state: PetState, now: Double) {
        displayed = state
        displayedSince = now
        pending = nil
    }

    public func reset(now: Double) {
        sessions.removeAll()
        focusedSession = nil
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
            current = s.failedDetail.map { "出错：\($0)" } ?? "出错了"
        case .respond:
            current = s.taskActive ? "整理回答" : "已回答"
        case .idle, .question_for_user:
            current = s.open.last?.detail ?? "等你回答"
        case .task_complete:
            current = "已完成"
        case .thinking:
            current = inProgress ?? "思考中"
        default:
            current = inProgress ?? s.lastDetail[displayed] ?? Self.fallbackText(displayed)
        }
        return StatusLine(title: s.title ?? s.prompt, current: current, progress: progress)
    }

    private static func fallbackText(_ state: PetState) -> String {
        switch state {
        case .read_file: return "阅读文件"
        case .view_image: return "查看图片"
        case .write_file: return "修改文件"
        case .verify: return "运行测试"
        case .read_web: return "浏览网页"
        case .default_work: return "处理中"
        case .thinking: return "思考中"
        case .respond: return "整理回答"
        case .failed: return "出错了"
        case .question_for_user: return "等你回答"
        case .task_complete: return "已完成"
        case .idle: return "等你回答"
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
