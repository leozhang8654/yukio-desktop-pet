"""动画索引与帧时间线：从 activities.json / base-animations.json / motion/motion.json 读取。

素材与 macOS 版完全共用（YukioPlayer/Resources/Assets）：每段动画是一张横向图条，
按 sequence 取帧、每步停留 durationsMs。motion/ 里的小幅动作覆盖同名动画。

移植自 YukioPlayer/Sources/YukioCore/Catalog.swift 与 SpriteTimeline.swift。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Callable, Dict, List, Optional, Tuple

from .events import ALL_STATES, PetState

#: 拖动时显示的动作：被一只看不见的大手拎着。
HELD_ID = "held"


class CatalogError(Exception):
    pass


class HangAnchors:
    """被大手拎住时要用的两个锚点，单位是帧内像素、左上角为原点。"""

    __slots__ = ("grip_x", "grip_y", "head_top")

    def __init__(self, grip_x: float, grip_y: float, head_top: float):
        #: 抓住的那一点：领口被捏起来的那个尖。摆动绕它转。
        self.grip_x = float(grip_x)
        self.grip_y = float(grip_y)
        #: 头发顶端所在行。这一帧比常规帧高，按上边缘对齐摆放，所以画的时候
        #: 要让这条线与站立图一致。
        self.head_top = float(head_top)

    @property
    def grip(self):
        return (self.grip_x, self.grip_y)


class AnimationSpec:
    __slots__ = ("id", "label", "asset_path", "frame_width", "frame_height",
                 "sequence", "durations_ms", "loop", "hold_last_frame", "loop_start", "hang", "pixel_scale")

    def __init__(self, id, label, asset_path, frame_width, frame_height,
                 sequence, durations_ms, loop, hold_last_frame, loop_start=0, hang=None, pixel_scale=1):
        self.id = id
        self.label = label
        #: 相对资源根目录的路径，例如 "activities/thinking.webp"。
        self.asset_path = asset_path
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.sequence = sequence
        self.durations_ms = durations_ms
        self.loop = loop
        self.hold_last_frame = hold_last_frame
        #: 循环时回到的步序号：前面的步只播一次（例如先递出报告，再循环眨眼）。
        self.loop_start = loop_start
        #: 只有「被拎起来」这一段有：抓手点与头顶线。
        self.hang = hang
        #: 图条里一个点对应几个像素：2 表示 2 倍分辨率的图条（一格 (frame_width×2)×(frame_height×2) 像素，
        #: 摆放时仍按 frame_width×frame_height 个点；太长的图条会折成几行），缺省 1。
        self.pixel_scale = pixel_scale

    @property
    def max_frame_index(self) -> int:
        return max(self.sequence) if self.sequence else 0

    @property
    def cycle_ms(self) -> float:
        return float(sum(self.durations_ms))


#: 基础图条中播放器实际使用的动画（其余是旧原生槽位与视线方向，不加载）。
#: failed 原生图条是 中立 #0–1 → 过渡 #2 → 垂眼 #3–5 → 过渡 #6 → 中立 #7，140 ms 一帧循环，
#: 等于每 1.2 秒低落又恢复一次；这里只垂眼一次并停住。
_USED_BASE = {
    "idle": ("空闲", None),
    HELD_ID: ("被大手拎着", None),
    "failed": ("失败／沮丧", ([0, 2, 3], [240.0, 180.0, 1000.0])),
}


class AnimationCatalog:
    def __init__(self, specs: Dict[str, AnimationSpec]):
        self.specs = specs

    @staticmethod
    def load(assets_root: str) -> "AnimationCatalog":
        specs: Dict[str, AnimationSpec] = {}

        activities_path = os.path.join(assets_root, "activities", "activities.json")
        try:
            with open(activities_path, "r", encoding="utf-8-sig") as fh:
                activities = json.load(fh)
        except (OSError, ValueError) as exc:
            raise CatalogError("缺少资源：%s（%s）" % (activities_path, exc))
        for s in activities.get("states", []):
            if len(s["sequence"]) != len(s["durationsMs"]) or not s["sequence"]:
                raise CatalogError("%s：sequence 与 durationsMs 长度不一致" % s["id"])
            specs[s["id"]] = AnimationSpec(
                s["id"], s["label"], "activities/" + s["asset"],
                s["frameWidth"], s["frameHeight"], list(s["sequence"]),
                [float(d) for d in s["durationsMs"]], bool(s["loop"]), bool(s["holdLastFrame"]))

        base_path = os.path.join(assets_root, "base", "base-animations.json")
        try:
            with open(base_path, "r", encoding="utf-8-sig") as fh:
                base = json.load(fh)
        except (OSError, ValueError) as exc:
            raise CatalogError("缺少资源：%s（%s）" % (base_path, exc))
        for a in base.get("animations", []):
            use = _USED_BASE.get(a["id"])
            if not use:
                continue
            label, once = use
            grip = a.get("grip")
            hang = HangAnchors(grip["x"], grip["y"], grip["headTop"]) if grip else None
            if once:
                sequence, durations = once
                specs[a["id"]] = AnimationSpec(a["id"], label, "base/" + a["asset"],
                                               a["frameWidth"], a["frameHeight"],
                                               list(sequence), list(durations), False, True, hang=hang,
                                               pixel_scale=int(a.get("pixelScale") or 1))
                continue
            durations = a.get("nativeDurationsMs")
            if not durations or len(durations) != a["frameCount"]:
                raise CatalogError("%s：缺少逐帧时序" % a["id"])
            specs[a["id"]] = AnimationSpec(a["id"], label, "base/" + a["asset"],
                                           a["frameWidth"], a["frameHeight"],
                                           list(range(a["frameCount"])), [float(d) for d in durations],
                                           True, False, hang=hang, pixel_scale=int(a.get("pixelScale") or 1))

        # 小幅动作覆盖同名动画；没有这个文件时按原图条播放。
        motion_path = os.path.join(assets_root, "motion", "motion.json")
        if os.path.exists(motion_path):
            try:
                with open(motion_path, "r", encoding="utf-8-sig") as fh:
                    motion = json.load(fh)
            except (OSError, ValueError) as exc:
                raise CatalogError("动作文件读不出来：%s（%s）" % (motion_path, exc))
            for m in motion.get("states", []):
                if len(m["sequence"]) != len(m["durationsMs"]) or not m["sequence"]:
                    raise CatalogError("motion %s：sequence 与 durationsMs 长度不一致" % m["id"])
                loop_start = m.get("loopStart") or 0
                if not 0 <= loop_start < len(m["sequence"]):
                    raise CatalogError("motion %s：loopStart 越界" % m["id"])
                previous = specs.get(m["id"])
                specs[m["id"]] = AnimationSpec(
                    m["id"], previous.label if previous else m["id"], "motion/" + m["asset"],
                    m["frameWidth"], m["frameHeight"], list(m["sequence"]),
                    [float(d) for d in m["durationsMs"]], bool(m["loop"]), not bool(m["loop"]), loop_start,
                    hang=previous.hang if previous else None, pixel_scale=int(m.get("pixelScale") or 1))

        catalog = AnimationCatalog(specs)
        for state in ALL_STATES:
            if state.value not in specs:
                raise CatalogError("状态 %s 没有对应动画" % state.value)
        held = specs.get(HELD_ID)
        if held is None:
            raise CatalogError("基础动画 %s" % HELD_ID)
        if held.hang is None:
            raise CatalogError("%s：缺少 grip（抓手点与头顶线）" % HELD_ID)
        return catalog

    def spec(self, state: PetState) -> AnimationSpec:
        return self.specs.get(state.value) or self.specs[PetState.default_work.value]

    def label(self, state: PetState) -> str:
        return self.spec(state).label

    def validate(self, image_size: Callable[[str], Optional[Tuple[int, int]]]) -> List[str]:
        """检查每段动画的帧索引不越过图条、帧尺寸一致。一格是点尺寸 × pixel_scale 像素，图条可以排成几行。"""
        problems: List[str] = []
        for spec in sorted(self.specs.values(), key=lambda s: s.id):
            size = image_size(spec.asset_path)
            if not size:
                problems.append("%s：无法读取 %s" % (spec.id, spec.asset_path))
                continue
            width, height = size
            k = max(spec.pixel_scale, 1)
            cell_w, cell_h = spec.frame_width * k, spec.frame_height * k
            if height % cell_h != 0:
                problems.append("%s：图高 %d 不是帧高 %d 的整数倍" % (spec.id, height, cell_h))
            if width % cell_w != 0:
                problems.append("%s：图宽 %d 不是帧宽 %d 的整数倍" % (spec.id, width, cell_w))
            frames = (width // cell_w) * (height // cell_h)
            if spec.max_frame_index >= frames:
                problems.append("%s：帧索引 %d 越界（共 %d 帧）" % (spec.id, spec.max_frame_index, frames))
        return problems


class SpriteTimeline:
    """纯逻辑的帧时间线：给定当前时间，决定该显示哪一帧。与绘制无关。"""

    __slots__ = ("spec", "step", "step_started_at", "finished")

    def __init__(self, spec: AnimationSpec, now: float):
        self.spec = spec
        self.step = 0
        self.step_started_at = now
        #: 非循环动画播完后停在最后一帧（递交报告：递出一次后保持）。
        self.finished = len(spec.sequence) <= 1 and not spec.loop

    @property
    def frame(self) -> int:
        return self.spec.sequence[self.step]

    @property
    def next_change_at(self) -> Optional[float]:
        return None if self.finished else self.step_started_at + self.spec.durations_ms[self.step]

    def advance(self, now: float) -> bool:
        """推进到 now。返回显示帧是否改变。"""
        before = self.frame
        spec = self.spec
        cycle = spec.cycle_ms
        # 长时间挂起（休眠、窗口被遮挡）后不补播，直接从当前时刻重新计时。
        if spec.loop and cycle > 0 and now - self.step_started_at > cycle * 2:
            self.step_started_at = now
        while True:
            due = self.next_change_at
            if due is None or now < due:
                break
            if self.step + 1 < len(spec.sequence):
                self.step += 1
                self.step_started_at = due
            elif spec.loop:
                # loop_start 之前的步只播一次（先递出报告，再循环眨眼）。
                self.step = min(spec.loop_start, len(spec.sequence) - 1)
                self.step_started_at = due
            else:
                self.finished = True
        return self.frame != before


def assets_root() -> Optional[str]:
    """资源位置：环境变量 → 打包进 exe 的副本 → 仓库里的 macOS 版素材 → 顶层 assets/。"""
    def valid(path: str) -> bool:
        return bool(path) and os.path.isfile(os.path.join(path, "activities", "activities.json"))

    env = os.environ.get("YUKIO_ASSETS")
    if env and valid(env):
        return env
    bundled = getattr(sys, "_MEIPASS", None)  # PyInstaller 单文件运行时解包的目录
    if bundled:
        for name in ("Assets", "assets"):
            candidate = os.path.join(bundled, name)
            if valid(candidate):
                return candidate
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # YukioWin/
    repo = os.path.dirname(here)
    for candidate in (os.path.join(here, "Assets"),
                      os.path.join(repo, "YukioPlayer", "Resources", "Assets"),
                      os.path.join(repo, "assets")):
        if valid(candidate):
            return candidate
    return None
