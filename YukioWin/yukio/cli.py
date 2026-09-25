"""无窗口的检查与调试模式，macOS／Linux 上也能跑（用来离线自查）。

    python -m yukio --check                 加载并裁切全部素材，确认帧不越界
    python -m yukio --snapshot out.png      把实际使用的动画画在棋盘格上
    python -m yukio --bubble out.png        画几种头顶气泡样例，检查排版与位置
    python -m yukio --cards out.png         画“气泡 + 上面那摞别的聊天”，检查排版与层次
    python -m yukio --question out.png      画她身边那张问题卡（可直接回答），检查排版与命中分区
    python -m yukio --hang out.png          把被拎着的几个倾角画出来，并自查摆动方向
    python -m yukio --replay 会话.jsonl     用虚拟时钟回放一份会话记录，打印状态序列
    python -m yukio --watch 60              实时跟随，打印事件与状态切换（不打印对话内容）
    python -m yukio --chats 3               列出最近的聊天，标出此刻会跟哪条
      两者都可加 --source auto|claude|deepcode|gpt 指定跟哪一家（默认 auto，三家都跟）
    python -m yukio --chat-link <会话ID>    查这条聊天对应桌面版 Claude 的哪一条（点牌子跳哪去）
    python -m yukio --open-chat            查桌面版 Claude 此刻开着哪条聊天（那条不举牌）
    python -m yukio --selftest              跑核心测试
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import List, Optional

from .bridge import BridgeParser
from .catalog import AnimationCatalog, CatalogError, HELD_ID, assets_root
from .console import force_utf8_console
from .events import ALL_STATES, Kind, PetEvent, PetState
from .hang import HangGeometry, Tuning as HangTuning, feet_offset_at
from .l10n import tr
from .parsers_claude import ClaudeTranscriptParser
from .parsers_codex import CodexRolloutParser
from .parsers_deepcode import DeepCodeMessageParser
from .router import ActivityRouter, HeldValue, RouterConfig
from .sources import default_sources
from .sprites import SpriteError, SpriteLibrary, image_size
from .tailer import JSONObjectStream


def now_ms() -> float:
    return time.time() * 1000.0


def time_string(ms: float) -> str:
    t = time.localtime(ms / 1000.0)
    return "%02d:%02d:%02d.%03d" % (t.tm_hour, t.tm_min, t.tm_sec, int(ms) % 1000)


def load_catalog_or_exit():
    root = assets_root()
    if not root:
        sys.stderr.write("找不到素材目录 Assets（可用 YUKIO_ASSETS 指定）\n")
        raise SystemExit(1)
    try:
        return AnimationCatalog.load(root), root
    except CatalogError as exc:
        sys.stderr.write("素材加载失败：%s\n" % exc)
        raise SystemExit(1)


def load_library_or_exit():
    catalog, root = load_catalog_or_exit()
    try:
        return catalog, SpriteLibrary(catalog, root), root
    except SpriteError as exc:
        sys.stderr.write("素材加载失败：%s\n" % exc)
        raise SystemExit(1)


def describe_event(e: PetEvent) -> str:
    bits = [e.kind.value]
    if e.tool:
        bits.append(e.tool)
    if e.activity:
        bits.append("→ %s" % e.activity.value)
    elif e.kind is Kind.activity_start:
        bits.append("→ (延续上一个)")
    return " ".join(bits)


# MARK: 素材检查

def run_check() -> int:
    catalog, library, root = load_library_or_exit()
    def size(rel):
        try:
            return image_size(os.path.join(root, *rel.split("/")))
        except (OSError, ValueError):
            return library.logical_asset_size(rel)

    problems = catalog.validate(size)
    if problems:
        for p in problems:
            print("问题：%s" % p)
        return 1
    print("OK：%d 段动画，素材目录 %s" % (len(catalog.specs), root))
    print("头顶线：站姿 %.0f 像素、坐姿 %.0f 像素（各段分开量，气泡贴各自的头）"
          % (library.head_top_inset_for("idle"), library.head_top_inset_for("thinking")))
    print("被拎起来：摆长 %.0f 像素，最多坠 %.0f 像素"
          % (library.hang_length, library.hang_length * HangTuning().max_sag_ratio))
    from .bubble import font_file
    print("气泡字体：%s" % (font_file() or "（没找到中文字体，会退回西文位图字体）",))
    return 0


def _checkerboard(width: int, height: int):
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (width, height), (235, 235, 235, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, height, 16):
        for x in range(0, width, 16):
            dark = ((x // 16) + (y // 16)) % 2 == 0
            draw.rectangle((x, y, x + 15, y + 15), fill=(204, 204, 204, 255) if dark else (235, 235, 235, 255))
    return image


def _points_image(image, spec):
    """2 倍图条的帧缩回按点的尺寸（检查图按 1 倍画）。"""
    from PIL import Image
    size = (spec.frame_width, spec.frame_height)
    return image if image.size == size else image.resize(size, Image.LANCZOS)


def run_snapshot(path: str) -> int:
    """把播放器实际使用的动画画在棋盘格上（检查裁切、透明边缘、比例）。帧多的均匀抽 10 帧。"""
    from PIL import ImageDraw
    from .bubble import load_font
    catalog, library, _ = load_library_or_exit()
    specs = [catalog.spec(s) for s in ALL_STATES] + [catalog.specs[HELD_ID]]
    # 「被拎起来」那一帧比常规帧高（领口的尖在头顶上方、腿垂下来），格子按最高的那段算。
    cell_w, cell_h, label_h, max_cols = 192, max(s.frame_height for s in specs), 26, 10
    cols = min(max_cols, max(library.frame_count(s.id) for s in specs))
    width, height = cols * cell_w, len(specs) * (cell_h + label_h)
    sheet = _checkerboard(width, height)
    draw = ImageDraw.Draw(sheet)
    font = load_font(13)
    for row, spec in enumerate(specs):
        top = row * (cell_h + label_h)
        draw.rectangle((0, top, width, top + label_h), fill=(255, 255, 255, 255))
        count = library.frame_count(spec.id)
        picks = list(range(count)) if count <= max_cols else \
            [i * (count - 1) // (max_cols - 1) for i in range(max_cols)]
        title = "%s · %s · %d 帧 · %d 步 · 一轮 %d ms · %s" % (
            spec.id, spec.label, count, len(spec.sequence), int(spec.cycle_ms),
            "循环" if spec.loop else "播一次后停住")
        draw.text((6, top + 5), title, font=font, fill=(0, 0, 0, 255))
        for i, f in enumerate(picks):
            sheet.alpha_composite(_points_image(library.frame(spec.id, f).image, spec),
                                  (i * cell_w, top + label_h + cell_h - spec.frame_height))
    avatar = library.avatar_image(96)
    if avatar is not None and library.frame_count(specs[0].id) + 2 <= cols:
        sheet.alpha_composite(avatar, (6 * cell_w + 20, 30))
        sheet.alpha_composite(avatar.resize((32, 32)), (7 * cell_w + 20, 30))
    sheet.save(path)
    print("已写出 %s（%d×%d）" % (path, width, height))
    return 0


def run_bubble_snapshot(path: str) -> int:
    """把几种头顶气泡画在对应动作上方，按 2 倍分辨率输出（检查排版、截断、位置）。"""
    from .bubble import BubbleLayout
    from .router import Progress, StatusLine
    catalog, library, _ = load_library_or_exit()
    samples = [
        (PetState.write_file, StatusLine("桌宠缺失状态", "实现头顶气泡", Progress(3, 7))),
        (PetState.verify, StatusLine("修复登录页的表单校验问题并补充单元测试，顺便整理目录结构",
                                     "$ pytest -q tests/test_login.py", None)),
        (PetState.thinking, StatusLine(None, "思考中", None)),
        (PetState.failed, StatusLine("桌宠缺失状态", "出错：$ pytest -q", Progress(7, 7))),
        (PetState.question_for_user, StatusLine("Deep Code 会话", "等你批准", None)),
        (PetState.task_complete, StatusLine("桌宠缺失状态", "已完成 · 点我打开对话", Progress(7, 7))),
    ]
    px = 2
    cell_w, cell_h = 240, 208 + 64
    sheet = _checkerboard(cell_w * len(samples) * px, cell_h * px)
    for i, (state, line) in enumerate(samples):
        spec = catalog.spec(state)
        frame = library.frame(spec.id, spec.sequence[-1])
        pet_x = i * cell_w + (cell_w - 192) // 2
        pet_y = cell_h - 208
        sheet.alpha_composite(frame.image.resize((192 * px, 208 * px)), (pet_x * px, pet_y * px))
        layout = BubbleLayout(line, scale=px)
        ox, oy = BubbleLayout.origin(layout.size_pt, (pet_x, pet_y, 192, 208),
                                     library.head_top_inset_for(spec.id))
        sheet.alpha_composite(layout.render(), (int(ox * px), int(oy * px)))
    sheet.save(path)
    print("已写出 %s（%d×%d）" % (path, sheet.size[0], sheet.size[1]))
    return 0


def run_question_snapshot(path: str) -> int:
    """画她身边那张问题卡（单选、多选、没有选项、已送出四格），按 2 倍分辨率输出。

    用来核对排版、折行、截断和与雪绪的相对位置——本机没有 Windows，界面只能这样自查。
    """
    from .events import PetQuestion, QuestionOption
    from .question import QuestionCardLayout, probe_points
    catalog, library, _ = load_library_or_exit()
    long_q = PetQuestion(
        header=tr("Release scope", "发布范围"),
        text=tr("This folder still has another session's finished but uncommitted work (two new states, "
                "54 tests passing). Should the installer on GitHub include it?",
                "这个文件夹里还有另一个会话刚做完、但没提交的改动（问号卡／勾选卡两个新状态，54 个测试通过）。"
                "发到 GitHub 的安装包要包含它们吗？"),
        options=[
            QuestionOption(tr("Ship it together (recommended)", "一起发（推荐）"),
                           tr("Two commits, merge into main, release v0.1.0", "新状态和图标分两次提交，合并进 main，发 v0.1.0")),
            QuestionOption(tr("Icon only", "只发图标这版"),
                           tr("Rebuild from a clean tree without the new states", "从不含新状态的干净工作树重新构建打包")),
            QuestionOption(tr("Don't commit yet", "先别提交推送")),
        ])
    multi = PetQuestion(
        text=tr("Which checks should run before pushing?", "推之前跑哪几项检查？"),
        options=[QuestionOption("pytest"), QuestionOption(tr("Windows packaging CI", "Windows 打包 CI")),
                 QuestionOption(tr("Screenshot self-check", "离屏截图自查"))],
        multi_select=True)
    plain = PetQuestion(text=tr("What should the release notes say?", "发布说明里写什么？"))
    samples = [
        (long_q, (), None, ""),
        (multi, (0, 2), None, ""),
        (plain, (), None, tr("Say it fixes the login page", "就说修好了登录页")),
        (long_q, (), tr("Answer sent", "答案已送出"), ""),
    ]
    px = 2
    cell_w, cell_h = 500, 320
    sheet = _checkerboard(cell_w * len(samples) * px, cell_h * px)
    spec = catalog.spec(PetState.question_for_user)
    frame = library.frame(spec.id, spec.sequence[-1])
    for i, (question, picked, notice, typed) in enumerate(samples):
        pet_x = i * cell_w + 12
        pet_y = cell_h - 216
        sheet.alpha_composite(frame.image.resize((192 * px, 208 * px)), (pet_x * px, pet_y * px))
        layout = QuestionCardLayout(question, picked=picked, can_open_chat=True,
                                    sent_notice=notice, typed=typed, scale=px)
        ox, oy = QuestionCardLayout.origin(layout.size_pt, (pet_x, pet_y, 192, 208),
                                           (i * cell_w, 0, (i + 1) * cell_w, cell_h))
        sheet.alpha_composite(layout.render(), (int(ox * px), int(oy * px)))
    sheet.save(path)
    probe = QuestionCardLayout(long_q, scale=1.0)
    print("卡片 %d×%d 点；点击分区自查：" % probe.size_px)
    for name, (x, y) in probe_points(probe):
        print("  %s → %s" % (name, probe.hit(x, y)))
    print("已写出 %s（%d×%d）" % (path, sheet.size[0], sheet.size[1]))
    return 0


def run_cards_snapshot(path: str) -> int:
    """画“气泡 + 上面那摞别的聊天”：收起与展开各一格，按 2 倍分辨率输出。"""
    from .bubble import BubbleLayout
    from .cards import ActivityCard, CardStatus
    from .cardstack import CardStackLayout
    from .router import Progress, StatusLine
    catalog, library, _ = load_library_or_exit()
    # 顺序就是 router.cards() 给的那套档位：等你回答 → 出错 → 答完 → 在跑，
    # 最要紧的那张挨着气泡（也就是画在最下面）。
    cards = [
        ActivityCard("ask", "要不要换个库", "等你挑一个", CardStatus.waiting, 12000),
        ActivityCard("bad", "跑个构建", "出错：$ npm run build", CardStatus.failed, 60000),
        ActivityCard("done", "写个备份脚本", "点开看看", CardStatus.ready, 4000),
        ActivityCard("work", "改登录页", "编辑 login.py", CardStatus.running, 800),
    ]
    line = StatusLine("桌宠缺失状态", "实现头顶气泡", Progress(3, 7))
    px = 2
    cell_w, cell_h = 260, 208 + 210
    sheet = _checkerboard(cell_w * 2 * px, cell_h * px)
    spec = catalog.spec(PetState.write_file)
    for i, expanded in enumerate((False, True)):
        pet_x = i * cell_w + (cell_w - 192) // 2
        pet_y = cell_h - 208
        sheet.alpha_composite(library.frame(spec.id, spec.sequence[0]).image.resize((192 * px, 208 * px)),
                              (pet_x * px, pet_y * px))
        bubble = BubbleLayout(line, scale=px)
        bx, by = BubbleLayout.origin(bubble.size_pt, (pet_x, pet_y, 192, 208),
                                     library.head_top_inset_for(spec.id))
        sheet.alpha_composite(bubble.render(), (int(bx * px), int(by * px)))
        stack = CardStackLayout(cards, expanded=expanded, scale=px)
        sx, sy = CardStackLayout.origin(stack.size_pt, (pet_x, pet_y, 192, 208), by)
        sheet.alpha_composite(stack.render(), (int(sx * px), int(sy * px)))
    sheet.save(path)
    print("已写出 %s（%d×%d）：左边收起、右边展开" % (path, sheet.size[0], sheet.size[1]))
    return 0


def run_hang_snapshot(path: str) -> int:
    """把「被大手拎着」按几个倾角画出来，外面套上实际会用的窗口框，并自查摆动方向。

    用来核对：抓手点是不是在头发顶端上方、晃到两边会不会被窗口切掉、上边缘是否与平时那块对齐。
    """
    from PIL import Image, ImageDraw
    from .bubble import load_font
    catalog, library, _ = load_library_or_exit()
    spec = catalog.specs[HELD_ID]
    tuning = HangTuning()
    sag_room = library.hang_length * tuning.max_sag_ratio
    geo = HangGeometry.make((192, 208), (spec.frame_width, spec.frame_height),
                            spec.hang.grip, scale=1.0, sag_room=sag_room)
    angles = [-tuning.max_angle_deg, -tuning.max_angle_deg / 2, 0,
              tuning.max_angle_deg / 2, tuning.max_angle_deg]
    cell_w, cell_h, label_h = geo.panel_size[0], geo.panel_size[1], 26
    sheet = _checkerboard(cell_w * len(angles), cell_h + label_h)
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((0, 0, sheet.size[0], label_h), fill=(255, 255, 255, 255))
    title = ("held · 摆长 %d px · 一摆 %.2f 秒 · 最多坠 %d px · 窗口 %d×%d（平时 192×208）· "
             "抓手点 (%d, 上边下 %d) · 倾角 %s") % (
        library.hang_length, tuning.period_sec, sag_room, cell_w, cell_h,
        geo.pivot[0], geo.pivot[1], " ".join("%d°" % a for a in angles))
    draw.text((6, 5), title, font=load_font(13), fill=(0, 0, 0, 255))

    frame = _points_image(library.frame(spec.id, 0).image, spec)
    for i, deg in enumerate(angles):
        dx = i * cell_w
        canvas = Image.new("RGBA", geo.panel_size, (0, 0, 0, 0))
        canvas.alpha_composite(frame, (int(round(geo.sprite_rect[0])), int(round(geo.sprite_rect[1]))))
        if abs(deg) > 0.01:
            canvas = canvas.rotate(deg, resample=Image.BICUBIC, center=geo.pivot)
        sheet.alpha_composite(canvas, (dx, label_h))
        # 平时那块 192×208 的位置（蓝框）与放大后的窗口（红框）。
        nx, ny = dx - geo.offset[0], label_h - geo.offset[1]
        draw.rectangle((nx, ny, nx + 191, ny + 207), outline=(51, 128, 255, 204))
        draw.rectangle((dx, label_h, dx + cell_w - 1, label_h + cell_h - 1), outline=(255, 51, 51, 153))
        px_, py_ = dx + geo.pivot[0], label_h + geo.pivot[1]
        draw.ellipse((px_ - 3, py_ - 3, px_ + 3, py_ + 3), fill=(255, 102, 0, 255))
    sheet.save(path)
    print("已写出 %s（%d×%d）" % (path, sheet.size[0], sheet.size[1]))
    return 0 if _check_swing_direction(frame, geo) else 1


def _check_swing_direction(frame, geo: HangGeometry) -> bool:
    """摆动方向自检：正角必须让脚偏向右边。

    这件事只错过一次就够难看的——macOS 版曾经把旋转写成 -angle，屏幕上成了
    「脚朝着移动方向甩出去」，与真实的钟摆相反。所以这里两条路都量一遍：
    画到位图上量脚的位置，再直接按渲染用的换算算一次。
    """
    from PIL import Image

    def feet_offset(deg: float) -> float:
        """把图按给定角度绕抓手点画一遍，返回「下半身横向重心 − 上半身横向重心」（正数＝脚偏右）。"""
        canvas = Image.new("RGBA", geo.panel_size, (0, 0, 0, 0))
        canvas.alpha_composite(frame, (int(round(geo.sprite_rect[0])), int(round(geo.sprite_rect[1]))))
        canvas = canvas.rotate(deg, resample=Image.BICUBIC, center=geo.pivot)
        alpha = canvas.getchannel("A").point(lambda v: 255 if v > 24 else 0)
        w, h = alpha.size
        data = alpha.tobytes()
        rows = []
        for y in range(h):
            row = data[y * w:(y + 1) * w]
            total = sum(x for x in range(w) if row[x])
            count = sum(1 for x in range(w) if row[x])
            if count:
                rows.append((total, count))
        if len(rows) <= 10:
            return 0.0
        cut = max(1, len(rows) // 5)

        def centroid(part):
            s = sum(t for t, _ in part)
            c = sum(c for _, c in part)
            return s / c if c else 0.0

        # 位图第一行是画面最顶上那行，所以 rows 开头是头、结尾是脚。
        return centroid(rows[-cut:]) - centroid(rows[:cut])

    ok = True
    for deg in (-20.0, 20.0):
        drawn = feet_offset(deg)
        computed = feet_offset_at(deg)
        good = drawn * deg > 0 and computed * deg > 0
        print("  倾角 %+d°：画出来脚偏 %+.1f px、按矩阵算偏 %+.1f px %s"
              % (deg, drawn, computed, "✓" if good else "✗ 方向反了"))
        ok = ok and good
    return ok


# MARK: 回放与跟随

def _pick_parser(first_object: bytes):
    """按第一条记录判断这是哪种会话记录。"""
    try:
        obj = json.loads(first_object.decode("utf-8", "replace"))
    except ValueError:
        obj = {}
    if isinstance(obj, dict):
        if "payload" in obj or obj.get("type") in ("session_meta", "response_item", "event_msg"):
            return CodexRolloutParser(), "GPT（Codex）"
        if "role" in obj and "sessionId" in obj:
            return DeepCodeMessageParser(), "Deep Code（DeepSeek）"
        if "type" in obj and "sessionId" in obj:
            return ClaudeTranscriptParser(), "Claude Code"
        if "kind" in obj or "event" in obj:
            return BridgeParser(), "通用收件箱"
    return DeepCodeMessageParser(), "Deep Code（DeepSeek，按默认猜测）"


def run_replay(path: str, with_bubble: bool = False) -> int:
    catalog, _ = load_catalog_or_exit()
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        print("无法读取 %s（%s）" % (path, exc))
        return 1
    objects = JSONObjectStream().append(data)
    if not objects:
        print("没有可用记录")
        return 0
    parser, kind = _pick_parser(objects[0])
    session = os.path.splitext(os.path.basename(path))[0]
    events: List[PetEvent] = []
    for obj in objects:
        events += parser.events_from_line(obj, fallback_session=session, fallback_ts=0.0)
    events = [e for e in events if e.ts > 0]
    events.sort(key=lambda e: e.ts)
    if not events:
        print("识别为 %s，但没有解析出事件" % kind)
        return 0
    print("识别为 %s 的会话记录，共 %d 个事件" % (kind, len(events)))
    config = RouterConfig()
    router = ActivityRouter(now=events[0].ts, config=config)
    bubble = HeldValue(None, min_hold_ms=1200)
    counts = {}

    def tick(t: float) -> None:
        s = router.tick(t)
        if s:
            counts[s] = counts.get(s, 0) + 1
            print("%s  显示 %s（%s）" % (time_string(t), s.value, catalog.label(s)))
        if not with_bubble:
            return
        line = router.status_line(t)
        if bubble.update(line, t, immediate=(line is None) != (bubble.value is None)):
            if bubble.value:
                progress = " %d/%d" % bubble.value.progress if bubble.value.progress else ""
                print("%s  气泡 [%s] %s%s" % (time_string(t), bubble.value.title or "-",
                                             bubble.value.current, progress))
            else:
                print("%s  气泡 隐藏" % time_string(t))

    for i, e in enumerate(events):
        router.ingest(e, e.ts)
        tick(e.ts)
        next_ts = events[i + 1].ts if i + 1 < len(events) else e.ts + config.complete_arm_ms + 3000
        # 事件之间：前 20 秒逐 100 ms 推进，之后跳到失联阈值。
        t = e.ts + 100
        while t < next_ts and t < e.ts + 20000:
            tick(t)
            t += 100
        stale_at = e.ts + config.stale_no_tool_ms + 100
        if stale_at < next_ts:
            tick(stale_at)
            tick(stale_at + config.debounce_ms + 100)
    print("—— 各状态出现次数：" + " ".join("%s=%d" % (s.value, counts[s]) for s in ALL_STATES if s in counts))
    return 0


def run_chats(seconds: float, which: str = "auto") -> int:
    """列出最近的聊天（托盘菜单“跟随的聊天”里的那一份），→ 标出此刻会跟哪条。

    先跟着记录看几秒，免得只拿到启动那一瞬的样子。
    """
    sources = default_sources(which)
    start = now_ms()
    router = ActivityRouter(now=start)
    for src in sources:
        for e in src.poll(start):
            router.ingest(e, min(e.ts, start))
    router.settle(start)
    while now_ms() - start < seconds * 1000:
        now = now_ms()
        for src in sources:
            for e in src.poll(now):
                router.ingest(e, min(e.ts, now))
        router.tick(now)
        time.sleep(0.1)
    for src in sources:
        where = getattr(src, "projects_dir", None) or getattr(src, "path", "")
        print("%s：%s 存在=%s" % (src.label, where, src.available))
    chats = router.session_summaries(now_ms(), quiet_within_ms=30 * 60 * 1000.0, limit=10)
    if not chats:
        print("最近没有聊天在跑")
        return 0
    for c in chats:
        print("%s %s  %s" % ("→" if c.focused else " ", c.id, c.menu_label))
    return 0


def run_chat_link(session: str) -> int:
    """查一条转录会话对应桌面版 Claude 的哪条聊天（点举着的牌子时就是跳到那里）。"""
    from .chatlinks import ChatLinks, chat_url_for_desktop_session, default_sessions_dir
    links = ChatLinks()
    print("桌面版会话记录：%s（存在=%s）" % (links.sessions_dir, os.path.isdir(links.sessions_dir)))
    found = links.desktop_session_id(session)
    if not found:
        print("对不上桌面版的聊天：%s" % session)
        print("（在终端里跑的 Claude Code、以及 Deep Code 的会话本来就没有这种链接，点了只放下牌子。）")
        return 1
    print("%s → %s" % (session, found))
    print("点牌子会打开：%s" % chat_url_for_desktop_session(found))
    return 0


def run_open_chat() -> int:
    """查桌面版 Claude 此刻选中的是哪条聊天。

    那条聊天答完时雪绪不举牌——人已经看着它了，再举一块只是挡路。
    还要求桌面版 Claude 真在最前面才算"开在眼前"，这里一并打印出来。
    """
    from .chatlinks import ChatLinks
    links = ChatLinks()
    print("桌面版会话记录：%s（存在=%s）" % (links.sessions_dir, os.path.isdir(links.sessions_dir)))
    session = links.focused_session()
    if not session:
        print("认不出此刻开着哪条聊天：照常举牌")
        return 1
    print("此刻开着的聊天：%s" % session)
    if os.name != "nt":
        print("（这里不是 Windows，最前面那个程序查不了；Windows 上会一并判断。）")
        return 0
    from .win32 import foreground_process_name
    front = foreground_process_name() or "-"
    from .app import CLAUDE_DESKTOP_EXE
    in_sight = front.lower() == CLAUDE_DESKTOP_EXE.lower()
    print("最前面的程序：%s%s" % (front, "（算开在眼前，这条不举牌）" if in_sight else "（没在看 Claude，照常举牌）"))
    return 0


def run_watch(seconds: float, which: str = "auto") -> int:
    catalog, _ = load_catalog_or_exit()
    sources = default_sources(which)
    start = now_ms()
    router = ActivityRouter(now=start)
    for src in sources:
        for e in src.poll(start):
            router.ingest(e, min(e.ts, start))
    router.settle(start)
    for src in sources:
        where = getattr(src, "projects_dir", None) or getattr(src, "path", "")
        print("%s  %s：%s 存在=%s" % (time_string(start), src.label, where, src.available))
    print("%s  启动状态 %s（%s） 会话 %s" % (time_string(start), router.displayed.value,
                                          catalog.label(router.displayed),
                                          (router.focused_session or "-")[:8]))
    focus = router.focused_session
    while now_ms() - start < seconds * 1000:
        now = now_ms()
        for src in sources:
            for e in src.poll(now):
                router.ingest(e, min(e.ts, now))
                # 会话标题这类事件不带时间戳（ts=0），不算延迟。
                lag = "  写入延迟≈%d ms" % int(now - e.ts) if e.ts > 0 else ""
                print("%s  事件 [%s] %s%s" %
                      (time_string(now), e.session[:8], describe_event(e), lag))
        s = router.tick(now)
        if s:
            line = router.status_line(now)
            text = ("  气泡 %s" % line.current) if line else ""
            print("%s  显示 %s（%s）%s" % (time_string(now), s.value, catalog.label(s), text))
        if router.focused_session != focus:
            focus = router.focused_session
            print("%s  跟随切到 [%s]" % (time_string(now), (focus or "-")[:8]))
        time.sleep(0.1)
    return 0


def run_selftest() -> int:
    import unittest
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tests_dir = os.path.join(here, "tests")
    if not os.path.isdir(tests_dir):
        print("这是打包后的版本，里面没有带测试；要跑测试请用源码：python run.py --selftest")
        return 0
    if here not in sys.path:
        sys.path.insert(0, here)
    suite = unittest.defaultTestLoader.discover(tests_dir)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    force_utf8_console()

    def value_after(flag: str) -> Optional[str]:
        if flag in argv:
            i = argv.index(flag)
            if i + 1 < len(argv):
                return argv[i + 1]
        return None

    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    if "--check" in argv:
        return run_check()
    if value_after("--snapshot"):
        return run_snapshot(value_after("--snapshot"))
    if value_after("--bubble"):
        return run_bubble_snapshot(value_after("--bubble"))
    if value_after("--cards"):
        return run_cards_snapshot(value_after("--cards"))
    if value_after("--question"):
        return run_question_snapshot(value_after("--question"))
    if value_after("--hang"):
        return run_hang_snapshot(value_after("--hang"))
    if value_after("--replay"):
        return run_replay(value_after("--replay"), "--with-bubble" in argv)
    if "--watch" in argv:
        seconds = value_after("--watch")
        try:
            seconds = float(seconds) if seconds else 60.0
        except ValueError:
            seconds = 60.0
        return run_watch(seconds, value_after("--source") or "auto")
    if "--chats" in argv:
        seconds = value_after("--chats")
        try:
            seconds = float(seconds) if seconds else 3.0
        except ValueError:
            seconds = 3.0
        return run_chats(seconds, value_after("--source") or "auto")
    if value_after("--chat-link"):
        return run_chat_link(value_after("--chat-link"))
    if "--open-chat" in argv:
        return run_open_chat()
    if "--selftest" in argv:
        return run_selftest()

    from .app import run_app
    return run_app(argv)
