import Foundation

/// 雪绪可显示的状态。七个活动 + 默认电脑桌 + 失败 + 空闲。
/// 拖动跑动不是状态：由窗口层临时覆盖，松手后回到当前状态。
public enum PetState: String, CaseIterable, Codable, Sendable {
    case idle
    case thinking
    case read_file
    case view_image
    case write_file
    case verify
    case read_web
    case respond
    case default_work
    /// 工具报错或本轮因错误中止：沮丧（基础图条 failed）。
    case failed
    /// AskUserQuestion：把问号卡立在桌上、指着它等你回答。
    case question_for_user
    /// 一轮任务结束：递交报告之后举起勾选卡，直到回空闲。
    case task_complete

    public var isWork: Bool { self != .idle && self != .question_for_user && self != .task_complete }
}

/// Claude 任务清单中的一条（TodoWrite，或 TaskCreate／TaskUpdate）。
public struct TodoItem: Codable, Equatable, Sendable {
    public enum Status: String, Codable, Sendable {
        case pending
        case inProgress = "in_progress"
        case completed
        /// TaskUpdate 删除条目。
        case deleted
    }

    public var id: String
    /// 条目文字；更新事件里为 nil 表示不改。
    public var subject: String?
    /// 更新事件里为 nil 表示不改；新条目缺省为 pending。
    public var status: Status?

    public init(id: String, subject: String? = nil, status: Status? = nil) {
        self.id = id
        self.subject = subject
        self.status = status
    }
}

/// 与具体来源无关的小型事件协议。
/// 适配层（Claude 转录、Claude hooks、模拟脚本）只负责把原始数据翻译成这些事件；
/// 路由、防抖和保持时间全部在 ActivityRouter 中完成。
public struct PetEvent: Codable, Equatable, Sendable {
    public enum Kind: String, Codable, Sendable {
        /// 用户发出新请求，任务开始。detail 为请求的第一行。
        case taskStart = "task_start"
        /// 任务正常结束（已给出回答）。
        case taskEnd = "task_end"
        /// 任务被中断／取消／会话关闭。
        case taskAbort = "task_abort"
        /// 本轮因错误中止（例如 API 报错）：沮丧一会儿再回空闲。
        case taskFailed = "task_failed"
        /// 工具开始执行。activity 为 nil 表示“延续上一个工具的活动”（例如轮询后台命令输出）。
        case activityStart = "activity_start"
        /// 工具执行结束：成功，或被用户拒绝／中断（这些不算失败）。
        case activityEnd = "activity_end"
        /// 工具执行失败（报错、非零退出）。同样结束该工具调用。
        case activityFailed = "activity_failed"
        /// 模型产生了思考内容或过程说明：只说明任务仍在进行。
        case thinking
        /// 最终回答已输出。
        case finalAnswer = "final_answer"
        /// 来源断开（文件消失、适配器出错）；该来源的所有会话回到空闲。
        case sourceLost = "source_lost"
        /// 会话标题（大任务），标题文字在 detail。
        case sessionTitle = "session_title"
        /// 任务清单整体替换（TodoWrite），完整清单在 todos。
        case todoList = "todo_list"
        /// 任务清单个别条目新增或更新（TaskCreate／TaskUpdate），要合并的条目在 todos。
        case todoUpdate = "todo_update"
    }

    /// 事件发生时间，毫秒（Unix 纪元）。
    public var ts: Double
    /// 来源标识，例如 "claude-transcript"、"claude-hook"、"sim"。
    public var source: String
    /// 会话 ID。多个会话同时运行时用于隔离状态。
    public var session: String
    public var kind: Kind
    /// 工具调用 ID（tool_use_id），用于配对开始／结束与去重。
    public var eventID: String?
    public var activity: PetState?
    /// 原始工具名，仅用于显示和调试。
    public var tool: String?
    /// 给人看的简短说明：工具调用是“编辑 main.swift”这类描述，任务开始是请求的第一行，会话标题是标题文字。
    public var detail: String?
    /// 任务清单事件的条目。
    public var todos: [TodoItem]?
    /// AskUserQuestion 抄下来的那道题：举牌时原样显示在她身边，选项可以直接点。
    public var question: PetQuestion?

    public init(ts: Double, source: String, session: String, kind: Kind,
                eventID: String? = nil, activity: PetState? = nil, tool: String? = nil,
                detail: String? = nil, todos: [TodoItem]? = nil, question: PetQuestion? = nil) {
        self.ts = ts
        self.source = source
        self.session = session
        self.kind = kind
        self.eventID = eventID
        self.activity = activity
        self.tool = tool
        self.detail = detail
        self.todos = todos
        self.question = question
    }
}

public extension PetEvent {
    /// 解析 ISO-8601 时间戳（带或不带小数秒），返回毫秒。
    static func parseTimestamp(_ s: String?) -> Double? {
        guard let s else { return nil }
        let withFraction = ISO8601DateFormatter()
        withFraction.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = withFraction.date(from: s) { return d.timeIntervalSince1970 * 1000 }
        let plain = ISO8601DateFormatter()
        if let d = plain.date(from: s) { return d.timeIntervalSince1970 * 1000 }
        return nil
    }
}
