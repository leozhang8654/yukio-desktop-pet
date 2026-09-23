import Foundation

/// 雪绪旁边那叠通知卡里的一张：一条聊天一张。
///
/// 取自 ChatGPT 桌面版那只宠物的做法：多个聊天同时跑时不逼你二选一，
/// 谁在等你、谁出错、谁答完了各挂一张卡，点哪张去哪条聊天。
/// 她自己显示的那条不在这叠里——头顶气泡已经在讲它。
public struct ActivityCard: Equatable, Sendable {
    /// 卡的状态，也是排序的档位：等你回答 → 出错停住 → 答完了 → 还在干活。
    public enum Status: String, Equatable, Sendable, CaseIterable {
        case waiting
        case failed
        case ready
        case running

        /// 越小越先看。
        public var rank: Int {
            switch self {
            case .waiting: return 0
            case .failed: return 1
            case .ready: return 2
            case .running: return 3
            }
        }

        /// 卡右上角的短标签。
        public var label: String {
            switch self {
            case .waiting: return tr("Waiting", "等你回答")
            case .failed: return tr("Error", "出错")
            case .ready: return tr("Ready", "答完了")
            case .running: return tr("Running", "在跑")
            }
        }
    }

    /// 转录会话 ID：点这张卡就用它去找对应的聊天。
    public let session: String
    /// 聊天名：会话标题或请求第一行，都没有时用会话 ID 前 8 位。
    public let title: String
    /// 第二行：正在做什么，或在等什么。
    public let subtitle: String
    public let status: Status
    /// 距最近一次事件多久（毫秒）。
    public let quietMs: Double

    public init(session: String, title: String, subtitle: String, status: Status, quietMs: Double) {
        self.session = session
        self.title = title
        self.subtitle = subtitle
        self.status = status
        self.quietMs = quietMs
    }
}

public extension ActivityRouter {
    /// 旁边那叠卡：除了她正跟着的那条，其余有话要跟你说的聊天。
    ///
    /// 排序和焦点用的是同一套档位（等你回答 → 出错 → 答完 → 在跑），同档里最近的在前。
    /// 消掉的、静音的、安静太久的不列。
    ///
    /// - includeFocused: 传 true 连她正显示的那条也列出来（`--cards` 自查用）。
    func cards(now: Double, limit: Int = 6, includeFocused: Bool = false) -> [ActivityCard] {
        updateFocus(now: now)
        var rows: [(rank: Int, quiet: Double, card: ActivityCard)] = []
        for (id, s) in sessions {
            guard includeFocused || id != focusedSession else { continue }
            guard !mutedSessions.contains(id) else { continue }
            guard let status = cardStatus(s, now: now) else { continue }
            guard !isCardDismissed(id: id, s) else { continue }
            let quiet = max(0, now - s.lastEventAt)
            rows.append((status.rank, quiet, ActivityCard(
                session: id, title: SessionSummary.displayName(title: s.title ?? s.prompt, id: id),
                subtitle: cardSubtitle(s, status: status, now: now), status: status, quietMs: quiet)))
        }
        return rows.sorted {
            if $0.rank != $1.rank { return $0.rank < $1.rank }
            if $0.quiet != $1.quiet { return $0.quiet < $1.quiet }
            return $0.card.session < $1.card.session
        }.prefix(limit).map(\.card)
    }

    /// 点掉一张卡（打开那条聊天之后，或按卡上的 ✕）。
    /// 举着的勾选卡就此放下；其余的卡这一轮不再出现，那条聊天下一轮有动静时会再来。
    func dismissCard(session: String, now: Double) {
        guard let s = sessions[session] else { return }
        if s.sign == .raised { s.sign = .dismissed }
        dismissedCards[session] = cardTurnKey(s)
        if session == focusedSession { commit(desiredState(now: now), now: now) }
    }

    /// 这条聊天不再出卡（本次运行内有效）。
    func muteCards(session: String) {
        mutedSessions.insert(session)
    }

    func unmuteCards(session: String) {
        mutedSessions.remove(session)
    }

    func isMuted(session: String) -> Bool { mutedSessions.contains(session) }
}

extension ActivityRouter {
    /// 这条聊天该出什么卡；没话要说时 nil。
    func cardStatus(_ s: SessionModel, now: Double) -> ActivityCard.Status? {
        if waitingForUser(s, now: now) { return .waiting }
        if failedPending(s, now: now) { return .failed }
        if completionPending(s, now: now) { return .ready }
        if isLive(s, now: now) { return .running }
        return nil
    }

    func cardSubtitle(_ s: SessionModel, status: ActivityCard.Status, now: Double) -> String {
        switch status {
        case .waiting:
            return s.open.last?.detail ?? tr("Needs your decision", "等你拿主意")
        case .failed:
            return s.failedDetail.map { tr("Error: \($0)", "出错：\($0)") } ?? tr("Didn't finish this turn", "这一轮没做完")
        case .ready:
            return tr("Take a look", "点开看看")
        case .running:
            let state = desired(for: s, now: now, arming: false)
            let inProgress = s.todos.first(where: { $0.status == .inProgress })?.subject
            return inProgress?.isEmpty == false ? inProgress!
                : (s.lastDetail[state] ?? ActivityRouter.stateText(state))
        }
    }

    /// 这张卡这一轮被点掉过吗。
    func isCardDismissed(id: String, _ s: SessionModel) -> Bool {
        dismissedCards[id] == cardTurnKey(s)
    }

    /// 卡片按“这一轮”记消掉：那条聊天下一轮开始（taskStartedTs 变了）时会重新出现。
    func cardTurnKey(_ s: SessionModel) -> String {
        // 没开始／没结束时是 -infinity，不能直接转整数。
        func stamp(_ v: Double) -> String { v.isFinite ? String(Int(v)) : "-" }
        return "\(stamp(s.taskStartedTs))-\(stamp(s.taskEndedTs))"
    }
}
