"""无窗口的检查与调试模式，macOS／Linux 上也能跑（用来离线自查）。

    python -m yukio --check                 加载并裁切全部素材，确认帧不越界
    python -m yukio --snapshot out.png      把实际使用的动画画在棋盘格上
    python -m yukio --bubble out.png        画几种头顶气泡样例，检查排版与位置
    python -m yukio --replay 会话.jsonl     用虚拟时钟回放一份会话记录，打印状态序列
    python -m yukio --watch 60              实时跟随，打印事件与状态切换（不打印对话内容）
    python -m yukio --selftest              跑核心测试
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import List, Optional

from .bridge import BridgeParser
from .catalog import AnimationCatalog, CatalogError, assets_root
from .console import force_utf8_console
from .events import ALL_STATES, Kind, PetEvent, PetState
from .parsers_claude import ClaudeTranscriptParser
from .parsers_deepcode import DeepCodeMessageParser
from .router import ActivityRouter, HeldValue, RouterConfig
from .sources import default_sources
from .sprites import SpriteError, SpriteLibrary
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
    from PIL import Image

    def size(rel):
        try:
            with Image.open(os.path.join(root, *rel.split("/"))) as im:
                return im.size
        except OSError:
            return None

    problems = catalog.validate(size)
    if problems:
        for p in problems:
            print("问题：%s" % p)
        return 1
    print("OK：%d 段动画，素材目录 %s" % (len(catalog.specs), root))
    print("头顶线 %.0f 像素，跑动时 %.0f 像素" % (library.head_top_inset, library.running_top_inset))
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


def run_snapshot(path: str) -> int:
    """把播放器实际使用的动画画在棋盘格上（检查裁切、透明边缘、比例）。帧多的均匀抽 10 帧。"""
    from PIL import ImageDraw
    from .bubble import load_font
    catalog, library, _ = load_library_or_exit()
    specs = [catalog.spec(s) for s in ALL_STATES]
    specs += [catalog.specs["running-left"], catalog.specs["running-right"]]
    cell_w, cell_h, label_h, max_cols = 192, 208, 26, 10
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
            sheet.alpha_composite(library.frame(spec.id, f).image, (i * cell_w, top + label_h))
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
        (PetState.task_complete, StatusLine("桌宠缺失状态", "已完成", Progress(7, 7))),
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
        ox, oy = BubbleLayout.origin(layout.size_pt, (pet_x, pet_y, 192, 208), library.head_top_inset)
        sheet.alpha_composite(layout.render(), (int(ox * px), int(oy * px)))
    sheet.save(path)
    print("已写出 %s（%d×%d）" % (path, sheet.size[0], sheet.size[1]))
    return 0


# MARK: 回放与跟随

def _pick_parser(first_object: bytes):
    """按第一条记录判断这是哪种会话记录。"""
    try:
        obj = json.loads(first_object.decode("utf-8", "replace"))
    except ValueError:
        obj = {}
    if isinstance(obj, dict):
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
        next_ts = events[i + 1].ts if i + 1 < len(events) else e.ts + config.respond_linger_ms + 3000
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
    while now_ms() - start < seconds * 1000:
        now = now_ms()
        for src in sources:
            for e in src.poll(now):
                router.ingest(e, min(e.ts, now))
                print("%s  事件 [%s] %s  写入延迟≈%d ms" %
                      (time_string(now), e.session[:8], describe_event(e), int(now - e.ts)))
        s = router.tick(now)
        if s:
            line = router.status_line(now)
            text = ("  气泡 %s" % line.current) if line else ""
            print("%s  显示 %s（%s）%s" % (time_string(now), s.value, catalog.label(s), text))
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
    if value_after("--replay"):
        return run_replay(value_after("--replay"), "--with-bubble" in argv)
    if "--watch" in argv:
        seconds = value_after("--watch")
        try:
            seconds = float(seconds) if seconds else 60.0
        except ValueError:
            seconds = 60.0
        return run_watch(seconds, value_after("--source") or "auto")
    if "--selftest" in argv:
        return run_selftest()

    from .app import run_app
    return run_app(argv)
