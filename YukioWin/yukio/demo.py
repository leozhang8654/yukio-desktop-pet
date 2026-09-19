"""可重复的模拟事件脚本：用于演示和测试，不代表真实的 DeepSeek／Claude 活动。

故意包含连续短调用、同类合并、快速交替、失败后修正、提问等待和结束保持等情形；
前半段没有任务清单（气泡显示当前活动），7.5 秒起建立清单（气泡显示进行中的一项与进度）。
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional

from .events import Kind, PetEvent, PetState, TodoItem, TodoStatus

SOURCE = "sim"
#: 脚本全长（最后一个事件之后再留出递交报告与举起勾选卡的时间；牌子会一直举到演示结束）。
DEMO_DURATION_MS = 49500 + 8000 + 3000


class Step(NamedTuple):
    offset_ms: float
    event: PetEvent


def demo_steps(session: str = "demo", start: float = 0.0) -> List[Step]:
    out: List[Step] = []
    counter = [0]

    def add(t, kind, id=None, activity=None, tool=None, detail=None, todos=None):
        out.append(Step(t, PetEvent(start + t, SOURCE, session, kind, event_id=id, activity=activity,
                                    tool=tool, detail=detail, todos=todos)))

    def call(t0, t1, activity, name, detail, fails=False):
        counter[0] += 1
        cid = "sim-%d" % counter[0]
        add(t0, Kind.activity_start, id=cid, activity=activity, tool=name, detail=detail)
        add(t1, Kind.activity_failed if fails else Kind.activity_end, id=cid, tool=name)

    def todo(t, id, subject=None, status: Optional[TodoStatus] = None):
        add(t, Kind.todo_update, todos=[TodoItem(id, subject, status)])

    add(0, Kind.session_title, detail="演示：修复登录页")
    add(0, Kind.task_start, detail="登录页的表单校验有问题，帮我修一下")            # 思考
    call(3000, 3150, PetState.read_file, "read", "阅读 login_view.py")           # 一串短读取 → 合并成一次“桌前读书”
    call(3300, 3400, PetState.read_file, "bash", "$ rg validate")
    call(3600, 3700, PetState.read_file, "read", "阅读 validator.py")
    call(4000, 4200, PetState.read_file, "bash", "$ ls src/login")
    call(4500, 4600, PetState.read_file, "read", "阅读 test_login.py")
    add(6800, Kind.thinking)
    todo(7500, "1", "查看报错截图和文档")                                          # 建立任务清单
    todo(7500, "2", "修正表单校验")
    todo(7500, "3", "跑测试并构建")
    todo(7600, "1", status=TodoStatus.in_progress)
    call(9000, 12500, PetState.view_image, "ReadImage", "查看 报错截图.png")        # 查看截图
    call(14000, 18000, PetState.read_web, "WebSearch", "搜索网页 表单校验 最佳实践")  # 阅读网页
    todo(18500, "1", status=TodoStatus.completed)
    todo(18500, "2", status=TodoStatus.in_progress)
    call(19500, 19800, PetState.write_file, "edit", "编辑 validator.py")          # 连续修改
    call(20100, 20500, PetState.write_file, "write", "写入 login_rules.py")
    call(20800, 21200, PetState.write_file, "edit", "编辑 login_view.py")
    call(22800, 27500, PetState.verify, "bash", "$ pytest -q", fails=True)       # 运行测试，失败 → 沮丧
    call(30500, 30900, PetState.write_file, "edit", "编辑 validator.py")          # 修正
    todo(31500, "2", status=TodoStatus.completed)
    todo(31500, "3", status=TodoStatus.in_progress)
    call(32000, 35500, PetState.verify, "bash", "$ pytest -q")                   # 再测一次，通过
    call(36600, 36700, PetState.read_file, "read", "阅读 pyproject.toml")         # 快速交替：不应逐个闪现
    call(36750, 36850, PetState.default_work, "bash", "$ pip install -e .")
    call(36900, 37000, PetState.read_file, "read", "阅读 README.md")
    call(39000, 43000, PetState.default_work, "bash", "$ python -m build")       # 未识别工作 → 电脑桌
    todo(44000, "3", status=TodoStatus.completed)
    add(44500, Kind.thinking)
    call(45500, 48500, PetState.question_for_user, "AskUserQuestion", "等你回答")  # 立问号卡，指着它等你回答
    add(49500, Kind.final_answer)                                                # 先递交报告，再举勾选卡
    add(49500, Kind.task_end)
    out.sort(key=lambda s: s.offset_ms)
    return out
