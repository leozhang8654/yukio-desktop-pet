#!/usr/bin/env python3
"""生成雪绪的动作图条（Resources/Assets/motion/ 与 motion.json）。

用法（在 YukioPlayer 目录）：
  python3 tools/motion/make_motion.py                  生成全部动作
  python3 tools/motion/make_motion.py --eyes out.png   眨眼检测图（检查眼睛框）
  python3 tools/motion/make_motion.py --parts 目录      每个动作的部件蒙版、补齐后的背景和几个时刻的放大局部
  python3 tools/motion/make_motion.py --sheet 目录      局部变形的放大对照图
  python3 tools/motion/make_motion.py --html out.html  新旧动作并排播放的预览页

需要 numpy、opencv-python、Pillow。每个动作只用一张已确认的底图，桌椅逐像素不动：
- 手、笔、放大镜、纸这类要明显移动的东西抠成一层单独平移、旋转（从部件内部的点漫延选取，遇描边即停），
  原位置用四周像素补齐；
- 头、眼这类只动 1–2 像素的用局部平滑变形；
- 眨眼画在底图上，眼皮跟着头动。
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from motionlib import (H, W, Frame, Part, Rotate, Shift, assemble, clean_plate, compose, detect_eye,  # noqa: E402
                       disk_mask, ease, extend_rows, flood_mask, keys, load_frame, max_step, paint_blink,
                       polygon_mask, render, save_strip, scalar, sheet_image, to_image, unpremul_rgb, vec)

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'Resources' / 'Assets'
OUT = ASSETS / 'motion'

BLINK = [(0.55, 50), (1.0, 70), (0.45, 80)]          # (闭合程度, 毫秒)：快速闭上、稍停、睁开
SLOW_BLINK = [(0.5, 70), (1.0, 110), (0.5, 110)]     # 思考、沮丧：慢一点


@dataclass
class Rig:
    handles: list = field(default_factory=list)   # 局部变形（作用在补齐后的底图上）
    parts: list = field(default_factory=list)     # 整块移动的部件（叠在最上面）
    behind: list = field(default_factory=list)    # 叠在底图与部件之间的层（后面那几张纸）
    fix: object = None                            # (底图, 补齐后的背景, 挖掉的范围) -> 修过的背景


@dataclass
class State:
    id: str
    plate: tuple                   # (相对 Assets 的路径, 帧号)
    eyes: list                     # 两只眼的搜索框 (x0, y0, x1, y1)，1 倍坐标
    period: float                  # 循环一轮的秒数（period × fps 须为整数）
    cycles: int                    # 时间轴重复几轮；各轮相同的帧只存一份
    fps: int
    blinks: list                   # 眨眼时刻（循环时间，秒）
    rig: object                    # (plate, eyes) -> Rig；时间 t < 0 表示开场（intro），t ≥ 0 是循环
    blink: list = field(default_factory=lambda: BLINK)
    intro: float = 0.0             # 开场只播一次的秒数
    intro_fps: int = 30


def irises(eyes, motion, sigma=(2.2, 2.0)):
    """眼珠（连同睫毛）小幅移动：看向别处。"""
    return [Shift(e.center, sigma, motion, e.box, feather=1.5) for e in eyes]


def scaled(motion, kx=1.0, ky=1.0):
    return lambda t: (motion(t)[0] * kx, motion(t)[1] * ky)


def head(center, region, motion, sigma=(24, 22)):
    return Shift(center, sigma, motion, region=region, feather=5)


# ---------- 各动作 ----------

def thinking(plate, eyes):
    # 托腮：头绕托着下巴的手慢慢歪一点又回来，眼睛偶尔往上看。幅度小。
    tilt = scalar([(0, 0), (1.2, 0), (2.6, 1.5), (4.4, 1.5), (5.8, 0)], 7.0)
    gaze = vec([(0, 0, 0), (1.6, 0, 0), (2.2, -0.8, -0.5), (3.8, -0.8, -0.5), (4.4, 0, 0)], 7.0)
    return Rig(handles=[Rotate((96, 88), (88, 50), (26, 24), tilt, region=(50, 14, 134, 86), feather=5),
                        *irises(eyes, gaze)])


def read_file(plate, eyes):
    # 读书：指着书的手沿一行从左划到右，读完回到行首；视线和头跟着。
    trace = keys([(0, -3.0, -0.3, 0), (1.75, 3.0, 0.3, 0)], 2.2)
    hand = Part(flood_mask(plate, [(68, 107), (74, 108), (78, 111), (65, 110)], region=[(56, 98), (86, 98), (90, 118), (56, 118)]),
                (70, 104), trace)
    return Rig(handles=[head((92, 50), (54, 14, 130, 84), lambda t: (0.3 * trace(t)[0], 0)),
                        *irises(eyes, lambda t: (0.45 * trace(t)[0], 0.2))],
               parts=[hand])


def view_image(plate, eyes):
    # 放大镜：拿镜子的手带着镜片在照片上方来回扫，微微走弧线，手腕跟着转；视线跟着镜片。
    P = 2.8

    def sweep(t):
        u = (t % P) / P
        return (-4.0 * math.cos(2 * math.pi * u), -0.7 * math.sin(2 * math.pi * u) ** 2,
                2.0 * math.sin(2 * math.pi * u))

    # 圆盘要罩住整圈镜框（镜框外缘：圆心 (89, 94.5)、半径约 12.5），手套往外长 2 像素把自己的描边带上，
    # 否则镜子扫开后原位置会留下一圈镜框的影子，手的下沿也拖着一道。
    handle = polygon_mask([(68, 96), (77, 101), (71, 109), (63, 104)])
    lens = Part(flood_mask(plate, [(62, 104), (66, 108), (70, 104), (64, 101)],
                           region=[(52, 93), (76, 93), (80, 104), (75, 117), (52, 117)], grow=2,
                           add=(disk_mask((89, 94.5), 13.0), handle)), (64, 106), sweep)
    return Rig(handles=[head((92, 50), (54, 14, 130, 80), lambda t: (0.15 * sweep(t)[0], 0)),
                        *irises(eyes, lambda t: (0.22 * sweep(t)[0], 0.15))],
               parts=[lens])


def write_file(plate, eyes):
    # 写字：握笔的手带着笔一边写笔画（笔尖只往上挑，不越过纸边）、笔杆跟着微微摆，一边往右移，写完一行回到左边。
    P, END = 2.0, 1.6

    def pen(t):
        t %= P
        if t < END:
            u = t / END
            env = math.sin(math.pi * u)
            stroke = 0.5 - 0.5 * math.cos(2 * math.pi * 3.5 * t)
            return (-1.6 + 3.2 * u, -1.0 * env * stroke, 2.0 * env * math.sin(2 * math.pi * 3.5 * t + 0.6))
        return (1.6 - 3.2 * ease((t - END) / (P - END)), 0.0, 0.0)

    # 笔杆带宽一些，笔杆的描边和金色条纹都要整条带走，否则笔移开后原位置会留下淡淡的笔影。
    shaft = polygon_mask([(59, 86), (68, 85), (79, 103), (72, 108)])
    nib = polygon_mask([(82, 115), (89, 115), (89, 123), (82, 123)])
    hand = Part(flood_mask(plate, [(66, 112), (72, 110), (78, 114), (62, 116), (74, 117)],
                           region=[(56, 101), (72, 99), (82, 101), (89, 109), (89, 123), (60, 123), (55, 112)],
                           add=(shaft, nib)), (74, 110), pen)
    return Rig(handles=[head((92, 50), (54, 14, 130, 84), lambda t: (0.3 * pen(t)[0], 0)),
                        *irises(eyes, lambda t: (0.45 * pen(t)[0], 0.2))],
               parts=[hand])


def verify(plate, eyes):
    # 对照检查：头在左右两份文件之间转来转去；正在看的那份，手指顺着往下点着核对。
    look = vec([(0, -1.4, 0), (1.3, -1.4, 0), (1.9, 1.4, 0), (3.0, 1.4, 0)], 3.6)

    def tracer(side):
        def f(t):
            w = max(0.0, side * look(t)[0] / 1.4)
            return (1.2 * w + 0.5 * w * math.sin(2 * math.pi * 2.0 * t), 1.8 * w, 0.0)
        return f

    left = Part(flood_mask(plate, [(66, 108), (72, 110), (78, 112)], region=[(55, 99), (86, 99), (88, 119), (55, 119)]),
                (70, 104), tracer(-1))
    right = Part(flood_mask(plate, [(104, 108), (110, 110), (116, 112)], region=[(96, 99), (126, 99), (126, 119), (96, 119)]),
                 (110, 104), tracer(1))
    return Rig(handles=[Shift((88, 50), (26, 24), look, region=(50, 14, 130, 86), feather=5),
                        Shift((90, 73), (14, 7), scaled(look, 0.5, 0), region=(70, 63, 110, 84), feather=3),
                        *irises(eyes, scaled(look, 0.5, 0))],
               parts=[left, right])


def read_web(plate, eyes):
    # 平板：点着屏幕的手指往上划两下（翻页），停一会儿；眼睛跟着往下扫。
    swipe = keys([(0, 0, 0, 0), (0.45, 0, 0, 0), (0.62, -1.0, -3.0, -3.0), (1.1, 0, 0, 0), (1.3, 0, 0, 0),
                  (1.47, -1.0, -3.0, -3.0), (1.95, 0, 0, 0)], 2.4)
    # 种子只点在手套上：指尖旁边就是浅色屏幕，点到屏幕会把一块屏幕跟手一起抠走。
    hand = Part(flood_mask(plate, [(70, 100), (78, 102), (66, 104), (74, 106)],
                           region=[(56, 92), (86, 92), (93, 99), (93, 111), (84, 114), (56, 114)]),
                (70, 100), swipe)
    return Rig(handles=[*irises(eyes, lambda t: (0.25 * swipe(t)[0], -0.15 * swipe(t)[1]))], parts=[hand])


def default_work(plate, eyes):
    # 敲键盘：两只手轮流抬起、敲下，一边在键位间左右挪，节奏不齐，敲一阵停一下；眼睛在屏幕上扫。
    P = 2.4
    L = [(0.00, -1.0), (0.27, 0.6), (0.55, -0.4), (0.80, 1.0), (1.07, 0.0), (1.55, -1.0)]
    R = [(0.13, 0.6), (0.41, -0.8), (0.68, 0.8), (0.93, 0.0), (1.33, 1.0), (1.47, -0.5)]

    def stroke(u):
        """一次敲键：抬起 2.2 像素、稍停、敲下略过头、回位。"""
        if u < 0.06:
            return -2.2 * ease(u / 0.06)
        if u < 0.09:
            return -2.2
        if u < 0.14:
            return -2.2 + 2.6 * ease((u - 0.09) / 0.05)
        if u < 0.22:
            return 0.4 * (1 - ease((u - 0.14) / 0.08))
        return 0.0

    def hand(strokes):
        def f(t):
            t %= P
            done = [s for s in strokes if s[0] <= t]
            if not done:
                return (0.0, 0.0, 0.0)
            s, kx = done[-1]
            prev = done[-2][1] if len(done) > 1 else 0.0
            x = prev + (kx - prev) * ease((t - s) / 0.06)
            if t > 1.9:   # 停一下：手慢慢回到正中
                x *= 1 - ease((t - 1.9) / 0.4)
            return (x, stroke(t - s), 0.0)
        return f

    scan = vec([(0, -0.3, 0), (1.2, 0.3, 0)], P)
    left = Part(flood_mask(plate, [(93, 106), (98, 104), (90, 109)], region=[(85, 99), (106, 99), (106, 116), (85, 116)]),
                (94, 101), hand(L))
    right = Part(flood_mask(plate, [(113, 107), (119, 108), (123, 110)], region=[(106, 100), (128, 100), (128, 118), (106, 118)]),
                 (115, 102), hand(R))
    return Rig(handles=[*irises(eyes, scan)], parts=[left, right])


def respond(plate, eyes):
    # 递交报告：先整理文件——后面两张没对齐的纸从两侧伸出来，拿着整叠在桌上磕两下，纸慢慢对齐；然后停住只眨眼。
    INTRO = 1.4
    lift = keys([(0, 0, 0, 0), (0.25, 0, 0, 0), (0.45, 0, -2.2, 0), (0.58, 0, 0, 0), (0.78, 0, -1.6, 0),
                 (0.9, 0, 0, 0), (1.4, 0, 0, 0)], 10.0)
    fan = scalar([(0, 1.0), (0.3, 1.0), (0.58, 0.5), (0.9, 0.12), (1.1, 0.0), (1.4, 0.0)], 10.0)

    def main(t):
        return lift(t + INTRO) if t < 0 else (0.0, 0.0, 0.0)

    def loose(dx, angle):
        def f(t):
            if t >= 0:
                return (0.0, 0.0, 0.0)
            k = fan(t + INTRO)
            return (dx * k, lift(t + INTRO)[1], angle * k)
        return f

    rgb = unpremul_rgb(plate)
    paper_px = rgb[95:110, 88:106].reshape(-1, 3)
    fill = np.median(paper_px[paper_px.mean(axis=1) > 0.8], axis=0)
    ink = np.array([0.42, 0.42, 0.50])
    # 后面那两张纸要能完全躲回整叠后面：按整叠的实心范围（x 78..107、y 85..118）往里收着画，
    # 转动的支点也放到整叠的底边上。原来画成 (79, 80, 116, 120)，比整叠还大一圈——纸对齐之后
    # 仍有一圈灰边框套在报告外面收不回去，散开时纸角还会转到桌面下边去。
    sheet = sheet_image((79, 86, 106, 116), np.append(fill, 1.0), np.append(ink, 1.0))
    ones = np.ones((H, W), np.float32)
    stack = Part(flood_mask(plate, [(97, 84), (90, 95), (104, 102), (92, 112), (100, 117), (86, 88), (110, 90),
                                    (77, 106), (80, 110), (114, 106), (117, 110)],
                            region=[(68, 79), (124, 79), (124, 121), (68, 121)]), (97, 110), main)
    return Rig(parts=[stack],
               behind=[Part(ones, (97, 117), loose(-6.0, -6.0), image=sheet),
                       Part(ones, (97, 117), loose(5.0, 5.0), image=sheet)])


def question_for_user(plate, eyes):
    # 等你回答：问号卡立在桌上，指着卡的手点两下，然后抬眼看你、停住。
    P = 4.2
    tap = keys([(0, 0, 0, 0), (0.5, 0, 0, 0), (0.70, 1.7, -1.3, 0), (0.98, 0, 0, 0), (1.18, 0, 0, 0),
                (1.38, 1.7, -1.3, 0), (1.66, 0, 0, 0), (4.2, 0, 0, 0)], P)
    # 抬头看你：头往上一点，眼珠跟着多抬一点，然后一直保持到这一轮结束。
    look = vec([(0, 0, 0), (2.0, 0, 0), (2.6, 0, -0.9), (4.2, 0, -0.9)], P)
    hand = Part(flood_mask(plate, [(74, 108), (78, 106), (72, 111), (82, 105)],
                           region=[(66, 97), (92, 97), (95, 105), (92, 118), (66, 118)]), (80, 108), tap)
    return Rig(handles=[head((94, 50), (56, 14, 132, 86), look),
                        *irises(eyes, lambda t: (0.28 * tap(t)[0], 1.5 * look(t)[1]))],
               parts=[hand])


def task_complete(plate, eyes):
    # 完成任务：双手托着勾选卡轻轻抬起来给你看一眼，再放回桌上；抬起时头微微跟一下。
    P = 5.0
    show = keys([(0, 0, 0, 0), (1.0, 0, 0, 0), (1.5, 0, -2.6, 0), (3.0, 0, -2.6, 0), (3.5, 0, 0, 0),
                 (5.0, 0, 0, 0)], P)
    card = polygon_mask([(77, 89), (112, 89), (112, 118), (77, 118)])
    unit = Part(flood_mask(plate, [(80, 107), (84, 110), (76, 110), (110, 107), (114, 111), (117, 112)],
                           region=[(66, 96), (126, 96), (126, 120), (66, 120)], add=(card,)), (94, 118), show)
    return Rig(handles=[head((94, 50), (56, 14, 132, 86), lambda t: (0.0, 0.3 * show(t)[1])),
                        *irises(eyes, lambda t: (0.0, 0.5 * show(t)[1]))],
               parts=[unit],
               fix=lambda plate, base, hole: extend_rows(plate, base, hole, 100, 124))


def idle(plate, eyes):
    # 空闲：偶尔向左、向右看一看（轮廓、五官、眼珠依次多移一点，像是转头），头跟着歪。
    look = vec([(0, 0, 0), (2.6, 0, 0), (3.3, -2.0, 0), (5.0, -2.0, 0), (5.7, 0, 0),
                (8.4, 0, 0), (9.1, 2.0, 0), (10.6, 2.0, 0), (11.3, 0, 0)], 12.0)
    return Rig(handles=[Rotate((93, 80), (93, 44), (26, 24), lambda t: 0.8 * look(t)[0], region=(54, 8, 134, 80), feather=5),
                        Shift((93, 44), (26, 24), look, region=(54, 8, 134, 80), feather=5),
                        Shift((93, 60), (14, 8), scaled(look, 0.5, 0), region=(72, 49, 114, 73), feather=3),
                        *irises(eyes, scaled(look, 0.6, 0))])


def failed(plate, eyes):
    # 沮丧：垂眼停住后，慢慢叹一口气（头往下沉再回来），慢慢眨眼。
    sigh = vec([(0, 0, 0), (1.5, 0, 0), (2.7, 0, 0.9), (4.4, 0, 0)], 5.5)
    return Rig(handles=[Shift((93, 46), (26, 24), sigh, region=(54, 8, 134, 80), feather=5)])


STATES = [
    State('thinking', ('activities/thinking.webp', 0), [(76, 63, 88, 77), (95, 63, 107, 77)],
          7.0, 1, 8, [0.9, 4.9], thinking, blink=SLOW_BLINK),
    State('read_file', ('activities/read_file.webp', 0), [(77, 64, 89, 78), (97, 64, 109, 78)],
          2.2, 2, 20, [4.25], read_file),
    State('view_image', ('activities/view_image.webp', 0), [(77, 64, 89, 78), (97, 64, 109, 78)],
          2.8, 2, 15, [1.4, 4.2], view_image),
    State('write_file', ('activities/write_file.webp', 0), [(76, 64, 88, 78), (97, 64, 109, 78)],
          2.0, 2, 30, [3.7], write_file),
    State('verify', ('activities/verify.webp', 0), [(74, 66, 87, 79), (93, 68, 108, 79)],
          3.6, 1, 15, [1.6], verify),
    State('read_web', ('activities/read_web.webp', 0), [(78, 66, 90, 77), (99, 66, 111, 77)],
          2.4, 2, 20, [3.5], read_web),
    State('respond', ('activities/respond.webp', 3), [(77, 65, 89, 79), (97, 65, 109, 79)],
          4.0, 1, 15, [1.6], respond, intro=1.4, intro_fps=30),
    State('default_work', ('activities/computer-desk.png', 0), [(92, 62, 102, 75), (110, 57, 122, 72)],
          2.4, 2, 20, [4.25], default_work),
    State('question_for_user', ('activities/question_for_user.webp', 0), [(77, 63, 90, 77), (99, 63, 112, 77)],
          4.2, 1, 20, [3.1], question_for_user),
    State('task_complete', ('activities/task_complete.webp', 0), [(76, 63, 90, 78), (99, 63, 112, 78)],
          5.0, 1, 20, [4.2], task_complete),
    State('idle', ('base/idle.webp', 0), [(78, 54, 90, 68), (97, 50, 109, 64)],
          12.0, 1, 12, [1.3, 5.2, 7.3, 10.9], idle),
    State('failed', ('base/failed.webp', 3), [(78, 56, 91, 68), (98, 52, 110, 64)],
          5.5, 1, 10, [0.9], failed, blink=SLOW_BLINK),
]

# 沮丧先垂眼一次（原图条的中立 → 过渡帧），再循环。
FAILED_INTRO = [('base/failed.webp', 0, 240), ('base/failed.webp', 2, 180)]


# ---------- 生成 ----------

def plate_and_eyes(st: State):
    plate = load_frame(str(ASSETS / st.plate[0]), st.plate[1])
    return plate, [detect_eye(plate, b) for b in st.eyes]


class Scene:
    """一个动作的底图、补齐后的背景和部件；按时间和眨眼程度出帧。"""

    def __init__(self, st: State):
        self.plate, self.eyes = plate_and_eyes(st)
        self.rig = st.rig(self.plate, self.eyes)
        self.hole = np.zeros((H, W), np.float32)
        for p in self.rig.parts:
            self.hole = np.maximum(self.hole, p.mask)
        self.base = clean_plate(self.plate, self.hole) if self.rig.parts else self.plate
        if self.rig.fix is not None:
            self.base = self.rig.fix(self.plate, self.base, self.hole)
        self._blink = {}

    def frame(self, t: float, blink: float = 0.0) -> np.ndarray:
        k = round(blink, 3)
        if k not in self._blink:
            self._blink[k] = paint_blink(self.base, self.eyes, blink)
        base = render(self._blink[k], self.rig.handles, t)
        layers = [p.layer(self.plate, t) for p in self.rig.behind] + [p.layer(self.plate, t) for p in self.rig.parts]
        return compose(base, layers) if layers else base

    def step(self, t0: float, t1: float) -> float:
        """两帧之间最大的移动（像素）：变形位移的变化，加上部件平移与转角（按 15 像素力臂折算）的变化。"""
        worst = max_step(self.rig.handles, t0, t1)
        for p in self.rig.parts + self.rig.behind:
            a, b = p.motion(t0), p.motion(t1)
            worst = max(worst, math.hypot(b[0] - a[0], b[1] - a[1]) + abs(b[2] - a[2]) * math.pi / 180 * 15)
        return worst


def build(st: State):
    scene = Scene(st)
    per = int(round(st.period * st.fps))
    assert abs(per - st.period * st.fps) < 1e-6, f'{st.id}: period × fps 须为整数'
    intro = [Frame(load_frame(str(ASSETS / p), i), ms) for p, i, ms in (FAILED_INTRO if st.id == 'failed' else [])]
    n_intro = int(round(st.intro * st.intro_fps))
    worst = 0.0
    for k in range(n_intro):
        t = -st.intro + k / st.intro_fps
        intro.append(Frame(scene.frame(t), 1000 / st.intro_fps))
        worst = max(worst, scene.step(t, t + 1 / st.intro_fps))
    loop, pending = [], sorted(st.blinks)
    for k in range(per * st.cycles):
        phase = (k % per) / st.fps
        m = k / st.fps
        while pending and pending[0] <= m + 1e-9:
            pending.pop(0)
            for a, ms in st.blink:
                loop.append(Frame(scene.frame(phase, a), ms))
        loop.append(Frame(scene.frame(phase), 1000 / st.fps))
        worst = max(worst, scene.step(phase, ((k + 1) % per) / st.fps))
    return scene, intro, loop, worst


def combine(intro, loop):
    """先播一次的帧和循环帧放进同一条图条；返回 (帧, 序列, 时长, 循环起点)。"""
    iu, iseq, idur = assemble(intro) if intro else ([], [], [])
    lu, lseq, ldur = assemble(loop)
    return iu + lu, iseq + [i + len(iu) for i in lseq], idur + ldur, len(iseq)


def generate():
    OUT.mkdir(exist_ok=True)
    entries = []
    for st in STATES:
        scene, intro, loop, worst = build(st)
        uniques, seq, dur, loop_start = combine(intro, loop)
        save_strip(uniques, str(OUT / f'{st.id}.webp'))
        # 桌腿、椅子一带（y ≥ 126）必须与底图逐像素相同：不许抽搐。
        # 只查由底图生成的帧；沮丧开场那两帧是原图条原样拷贝的站姿，不在此列。
        base = np.round(scene.plate * 255)
        copied = len(FAILED_INTRO) if st.id == 'failed' else 0
        moved = max(int((np.abs(np.round(f.image * 255) - base)[126:].max(axis=2) > 0).sum())
                    for f in intro[copied:] + loop)
        entries.append({'id': st.id, 'asset': f'{st.id}.webp', 'frameWidth': W, 'frameHeight': H,
                        'sequence': seq, 'durationsMs': dur, 'loop': True, 'loopStart': loop_start})
        cycle = sum(dur[loop_start:])
        print(f'{st.id:13s} 不重复帧 {len(uniques):3d}  步数 {len(seq):3d}  一轮 {cycle / 1000:5.2f}s  '
              f'相邻帧最大移动 {worst:.2f}px  桌腿区变化像素 {moved}')
        if moved:
            raise SystemExit(f'{st.id}: 桌腿区被改动了')
    (OUT / 'motion.json').write_text(json.dumps({
        'version': 2,
        'generator': 'tools/motion/make_motion.py',
        'note': '每个动作只用一张底图：要明显移动的手、笔、放大镜、纸抠成一层单独移动，原位置补齐；头眼用局部变形；桌椅逐像素不动。',
        'states': entries,
    }, ensure_ascii=False, indent=1) + '\n')
    print('写入', OUT / 'motion.json')


# ---------- 检查图 ----------

def eyes_sheet(path):
    """每个底图的两只眼：检测结果（红=睫毛线顶，绿=眼睛下缘）、半闭、全闭，放大 8 倍。"""
    tiles = []
    for st in STATES:
        plate, eyes = plate_and_eyes(st)
        x0 = min(b[0] for b in st.eyes) - 3
        y0 = min(b[1] for b in st.eyes) - 4
        x1 = max(b[2] for b in st.eyes) + 3
        y1 = max(b[3] for b in st.eyes) + 3
        row = []
        for a in (0.0, 0.5, 1.0):
            im = Image.new('RGBA', (W, H), (255, 255, 255, 255))
            im.alpha_composite(to_image(paint_blink(plate, eyes, a)))
            im = im.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 8, (y1 - y0) * 8), Image.NEAREST)
            if a == 0:
                d = ImageDraw.Draw(im)
                for e in eyes:
                    bx0, by0, bx1, by1 = e.box
                    d.rectangle([(bx0 - x0) * 8, (by0 - y0) * 8, (bx1 - x0) * 8 - 1, (by1 - y0) * 8 - 1], outline=(0, 120, 255))
                    for x, (top, lash, bottom) in e.columns.items():
                        d.rectangle([(x - x0) * 8 + 3, (top - y0) * 8 + 3, (x - x0) * 8 + 5, (top - y0) * 8 + 5], fill=(255, 0, 0))
                        d.rectangle([(x - x0) * 8 + 3, (bottom - 1 - y0) * 8 + 3, (x - x0) * 8 + 5, (bottom - 1 - y0) * 8 + 5], fill=(0, 200, 0))
            row.append(im)
        tiles.append((st.id, row))
    tw = max(sum(i.width for i in r) + 20 for _, r in tiles)
    th = sum(r[0].height + 18 for _, r in tiles)
    sheet = Image.new('RGBA', (tw, th), (230, 230, 230, 255))
    d = ImageDraw.Draw(sheet)
    y = 0
    for name, row in tiles:
        d.text((4, y + 2), name, fill=(0, 0, 0))
        x = 0
        for im in row:
            sheet.alpha_composite(im, (x, y + 16))
            x += im.width + 10
        y += row[0].height + 18
    sheet.save(path)


def _on_white(p: np.ndarray) -> Image.Image:
    im = Image.new('RGBA', (W, H), (255, 255, 255, 255))
    im.alpha_composite(to_image(p))
    return im


def parts_sheets(folder):
    """有部件的动作：蒙版（红）、补齐后的背景、以及几个时刻的放大局部。"""
    Path(folder).mkdir(parents=True, exist_ok=True)
    for st in STATES:
        scene = Scene(st)
        if not scene.rig.parts:
            continue
        hole = scene.hole
        ys, xs = np.nonzero(hole > 0.04)
        x0, x1 = max(xs.min() - 8, 0), min(xs.max() + 9, W)
        y0, y1 = max(ys.min() - 8, 0), min(ys.max() + 9, H)
        z = 4
        overlay = np.asarray(_on_white(scene.plate)).astype(np.float32)
        overlay[..., 0] = overlay[..., 0] * (1 - 0.5 * hole) + 255 * 0.5 * hole
        overlay[..., 1] = overlay[..., 1] * (1 - 0.5 * hole)
        overlay[..., 2] = overlay[..., 2] * (1 - 0.5 * hole)
        tiles = [('蒙版', Image.fromarray(overlay.astype(np.uint8))), ('补齐的背景', _on_white(scene.base))]
        times = ([-st.intro + st.intro * j / 3 for j in range(3)] if st.intro else []) + \
                [st.period * j / (6 if not st.intro else 3) for j in range(6 if not st.intro else 3)]
        for t in times:
            tiles.append((f't={t:.2f}s', _on_white(scene.frame(t))))
        cw, ch = (x1 - x0) * z, (y1 - y0) * z
        cols = 4
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new('RGBA', (cols * (cw + 8), rows * (ch + 18)), (230, 230, 230, 255))
        d = ImageDraw.Draw(sheet)
        for i, (label, im) in enumerate(tiles):
            X, Y = (i % cols) * (cw + 8), (i // cols) * (ch + 18)
            d.text((X + 2, Y + 2), f'{st.id} {label}', fill=(0, 0, 0))
            sheet.alpha_composite(im.crop((x0, y0, x1, y1)).resize((cw, ch), Image.NEAREST), (X, Y + 16))
        sheet.save(Path(folder) / f'{st.id}.png')


def motion_sheets(folder):
    """局部变形：六个相位的放大局部（上）与相对底图的差异（下，红色越深变化越大）。"""
    Path(folder).mkdir(parents=True, exist_ok=True)
    for st in STATES:
        scene = Scene(st)
        handles = scene.rig.handles
        if not handles:
            continue
        wsum = sum(h.w for h in handles)
        ys, xs = np.nonzero(wsum > 0)
        x0, x1 = max(xs.min() - 4, 0), min(xs.max() + 5, W)
        y0, y1 = max(ys.min() - 4, 0), min(ys.max() + 5, H)
        z = 4
        tiles = []
        for j in range(6):
            t = st.period * j / 6
            f = scene.frame(t)
            crop = _on_white(f).crop((x0, y0, x1, y1)).resize(((x1 - x0) * z, (y1 - y0) * z), Image.NEAREST)
            diff = np.abs(f - scene.plate).max(axis=2)[y0:y1, x0:x1]
            heat = np.full((y1 - y0, x1 - x0, 3), 255, np.uint8)
            k = np.clip(diff * 4, 0, 1)
            heat[..., 1] = (255 * (1 - k)).astype(np.uint8)
            heat[..., 2] = (255 * (1 - k)).astype(np.uint8)
            heat = Image.fromarray(heat).resize(((x1 - x0) * z, (y1 - y0) * z), Image.NEAREST).convert('RGBA')
            tiles.append((f't={t:.2f}s', crop, heat))
        cw, ch = tiles[0][1].size
        sheet = Image.new('RGBA', (len(tiles) * (cw + 8), 2 * ch + 30), (230, 230, 230, 255))
        d = ImageDraw.Draw(sheet)
        for i, (label, crop, heat) in enumerate(tiles):
            d.text((i * (cw + 8) + 2, 1), f'{st.id} {label}', fill=(0, 0, 0))
            sheet.alpha_composite(crop, (i * (cw + 8), 14))
            sheet.alpha_composite(heat, (i * (cw + 8), 16 + ch))
        sheet.save(Path(folder) / f'{st.id}.png')


def html_preview(path):
    """新旧动作并排播放（按图条的序列与时长，放大 2 倍，线性插值，和桌面上一样）。"""
    def data_uri(p):
        return 'data:image/webp;base64,' + base64.b64encode(Path(p).read_bytes()).decode()

    acts = {s['id']: s for s in json.loads((ASSETS / 'activities/activities.json').read_text())['states']}
    base = {a['id']: a for a in json.loads((ASSETS / 'base/base-animations.json').read_text())['animations']}
    motion = {s['id']: s for s in json.loads((OUT / 'motion.json').read_text())['states']}
    items = []
    for st in STATES:
        if st.id in acts:
            a = acts[st.id]
            old = dict(src=data_uri(ASSETS / 'activities' / a['asset']), seq=a['sequence'], dur=a['durationsMs'],
                       loop=a['loop'], loopStart=0)
        elif st.id == 'idle':
            b = base['idle']
            old = dict(src=data_uri(ASSETS / 'base' / b['asset']), seq=list(range(b['frameCount'])),
                       dur=b['nativeDurationsMs'], loop=True, loopStart=0)
        else:
            old = dict(src=data_uri(ASSETS / 'base/failed.webp'), seq=[0, 2, 3], dur=[240, 180, 1000],
                       loop=False, loopStart=0)
        m = motion[st.id]
        new = dict(src=data_uri(OUT / m['asset']), seq=m['sequence'], dur=m['durationsMs'], loop=True,
                   loopStart=m['loopStart'])
        items.append(dict(id=st.id, old=old, new=new))
    page = HTML_TEMPLATE.replace('__ITEMS__', json.dumps(items))
    Path(path).write_text(page)


HTML_TEMPLATE = """<!doctype html><meta charset="utf-8"><title>雪绪动作预览</title>
<style>
body{margin:0;padding:16px;font:14px -apple-system,system-ui,sans-serif;background:#eef1f5;color:#1f2a44}
h1{font-size:18px;margin:0 0 4px} p{margin:0 0 14px;color:#56627a}
.grid{display:flex;flex-wrap:wrap;gap:14px}
.card{background:#fff;border-radius:10px;padding:10px 12px;box-shadow:0 1px 2px rgba(0,0,0,.08)}
.card h2{font-size:13px;margin:0 0 6px}
.pair{display:flex;gap:8px}.pair div{text-align:center;font-size:11px;color:#6b7690}
canvas{width:192px;height:208px;background:repeating-conic-gradient(#f4f4f4 0 25%,#fff 0 50%) 0 0/16px 16px;border-radius:6px}
</style>
<h1>雪绪 · 新旧动作对照</h1><p>左：原来的动作；右：新的动作。按图条的真实时长播放，放大显示和桌面一致。</p>
<div class="grid" id="g"></div>
<script>
const items = __ITEMS__;
const players = [];
for (const it of items) {
  const card = document.createElement('div'); card.className = 'card';
  card.innerHTML = `<h2>${it.id}</h2><div class="pair"><div><canvas width="384" height="416"></canvas><br>原来</div><div><canvas width="384" height="416"></canvas><br>新</div></div>`;
  document.getElementById('g').appendChild(card);
  const cs = card.querySelectorAll('canvas');
  for (const [k, spec] of [[0, it.old], [1, it.new]]) {
    const img = new Image(); img.src = spec.src;
    players.push({ctx: cs[k].getContext('2d'), img, spec, step: 0, at: performance.now(), done: false});
  }
}
function frame(now) {
  for (const p of players) {
    const s = p.spec;
    while (!p.done && now - p.at >= s.dur[p.step]) {
      p.at += s.dur[p.step];
      if (p.step + 1 < s.seq.length) p.step++;
      else if (s.loop) p.step = s.loopStart;
      else p.done = true;
    }
    if (!p.img.complete) continue;
    p.ctx.imageSmoothingEnabled = true;
    p.ctx.clearRect(0, 0, 384, 416);
    p.ctx.drawImage(p.img, s.seq[p.step] * 192, 0, 192, 208, 0, 0, 384, 416);
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
</script>
"""


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--eyes')
    ap.add_argument('--parts')
    ap.add_argument('--sheet')
    ap.add_argument('--html')
    args = ap.parse_args()
    if args.eyes:
        eyes_sheet(args.eyes)
    elif args.parts:
        parts_sheets(args.parts)
    elif args.sheet:
        motion_sheets(args.sheet)
    elif args.html:
        html_preview(args.html)
    else:
        generate()
