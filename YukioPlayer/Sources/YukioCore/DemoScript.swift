import Foundation

/// 可重复的模拟事件脚本：用于演示和测试，不代表真实 Claude 活动。
/// 故意包含连续短调用、同类合并、快速交替、失败后修正、提问等待和结束保持等情形；
/// 前半段没有任务清单（气泡显示当前活动），7.5 秒起建立清单（气泡显示进行中的一项与进度）。
public enum DemoScript {
    public static let source = "sim"

    public struct Step: Sendable {
        public let offsetMs: Double
        public let event: PetEvent
    }

    public static func steps(session: String = "demo", start: Double = 0) -> [Step] {
        var out: [Step] = []
        var n = 0
        func add(_ t: Double, _ kind: PetEvent.Kind, id: String? = nil, _ activity: PetState? = nil, tool: String? = nil,
                 detail: String? = nil, todos: [TodoItem]? = nil) {
            out.append(Step(offsetMs: t, event: PetEvent(ts: start + t, source: source, session: session, kind: kind,
                                                         eventID: id, activity: activity, tool: tool,
                                                         detail: detail, todos: todos)))
        }
        func tool(_ t0: Double, _ t1: Double, _ activity: PetState, _ name: String, _ detail: String, fails: Bool = false) {
            n += 1
            add(t0, .activityStart, id: "sim-\(n)", activity, tool: name, detail: detail)
            add(t1, fails ? .activityFailed : .activityEnd, id: "sim-\(n)", tool: name)
        }
        func todo(_ t: Double, _ id: String, _ subject: String? = nil, status: TodoItem.Status? = nil) {
            add(t, .todoUpdate, todos: [TodoItem(id: id, subject: subject, status: status)])
        }

        add(0, .sessionTitle, detail: "演示：修复登录页")
        add(0, .taskStart, detail: "登录页的表单校验有问题，帮我修一下")          // 思考
        tool(3000, 3150, .read_file, "Read", "阅读 LoginView.swift")         // 一串短读取 → 合并成一次“桌前读书”
        tool(3300, 3400, .read_file, "Grep", "搜索 validate")
        tool(3600, 3700, .read_file, "Read", "阅读 Validator.swift")
        tool(4000, 4200, .read_file, "Glob", "查找 **/*Login*")
        tool(4500, 4600, .read_file, "Read", "阅读 LoginTests.swift")
        add(6800, .thinking)
        todo(7500, "1", "查看报错截图和文档")                                  // 建立任务清单
        todo(7500, "2", "修正表单校验")
        todo(7500, "3", "跑测试并构建")
        todo(7600, "1", status: .inProgress)
        tool(9000, 12500, .view_image, "Read", "查看 报错截图.png")            // 查看截图
        tool(14000, 18000, .read_web, "WebFetch", "浏览 developer.apple.com") // 阅读网页
        todo(18500, "1", status: .completed)
        todo(18500, "2", status: .inProgress)
        tool(19500, 19800, .write_file, "Edit", "编辑 Validator.swift")       // 连续修改
        tool(20100, 20500, .write_file, "Write", "写入 LoginRules.swift")
        tool(20800, 21200, .write_file, "Edit", "编辑 LoginView.swift")
        tool(22800, 27500, .verify, "Bash", "$ swift test", fails: true)     // 运行测试，失败 → 沮丧
        tool(30500, 30900, .write_file, "Edit", "编辑 Validator.swift")       // 修正
        todo(31500, "2", status: .completed)
        todo(31500, "3", status: .inProgress)
        tool(32000, 35500, .verify, "Bash", "$ swift test")                  // 再测一次，通过
        tool(36600, 36700, .read_file, "Read", "阅读 Package.swift")          // 快速交替：不应逐个闪现
        tool(36750, 36850, .default_work, "Bash", "$ swift package resolve")
        tool(36900, 37000, .read_file, "Read", "阅读 README.md")
        tool(39000, 43000, .default_work, "Bash", "$ swift build")           // 未识别工作 → 电脑桌
        todo(44000, "3", status: .completed)
        add(44500, .thinking)
        tool(45500, 48500, .question_for_user, "AskUserQuestion", "等你回答")  // 立问号卡，指着它等你回答
        add(49500, .finalAnswer)                                           // 先递交报告，再举勾选卡
        add(49500, .taskEnd)
        return out
    }

    /// 脚本全长（最后一个事件之后再留出递交报告与举起勾选卡的时间；牌子会一直举到演示结束）。
    public static let durationMs: Double = 49500 + 8000 + 3000
}
