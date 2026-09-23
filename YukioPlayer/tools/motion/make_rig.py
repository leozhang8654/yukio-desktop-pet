#!/usr/bin/env python3
"""生成雪绪的动作图条（骨骼分层版）：直接在 2 倍图上出帧，写进 Resources/Assets/motion/ 与 motion.json。

用法（在 YukioPlayer 目录）：
  python3 tools/motion/make_rig.py                         生成全部动作
  python3 tools/motion/make_rig.py --only write_file       只重生成某一段（可写多次），motion.json 里只换这一条
  python3 tools/motion/make_rig.py --layers 目录            每段的分层蒙版、补好的底图和几个时刻的放大局部（调多边形看这个）
  python3 tools/motion/make_rig.py --grid write_file 118 160 200 250 out.png [--zoom 7]
                                                          底图局部放大加坐标网格（标多边形用）
  python3 tools/motion/make_rig.py --eyes out.png          眨眼检测图
  python3 tools/motion/make_rig.py --html out.html         全部动作循环播放的预览页（按真实时长，显示大小和桌面一致）
  python3 tools/motion/make_rig.py --gif 目录               每段导出 GIF（看动起来的样子）
  python3 tools/motion/make_rig.py --outline 0             不加轮廓描边（默认 0.5 点）

底图：2 倍图（384×416）由 sources/ 的源图按 tools/plates/rekey_plates.py 里同一套配准放大两倍抠出
（缓存在 build/plates-2x/）；问号卡、勾选卡用 sources/*-hold-2x.png；没有高清源图的三张（敲键盘、待机、沮丧）
由 Real-ESRGAN 从 1 倍底图超分（需要 torch 的环境，见 upscale_motion.py；缓存后系统 python 就能跑）。

做法见 riglib.py 开头：整条手臂（袖子 + 手套 + 道具）抠成一层挂在骨骼上，肩膀不动、袖口跟着手走，
道具刚性地跟着手；洞按最近像素补，再按需打补丁。旧的 make_motion.py / upscale_motion.py 保留作参考，不再用。
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import riglib as R  # noqa: E402
from riglib import (Bone, Layer, Rig, Scene, Frame, W, H, cut, disk, gauss, keys, once, polygon, ramp, scalar,  # noqa: E402
                    union, vec, opaque_within, feather, stroke)

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
ASSETS = ROOT / 'Resources' / 'Assets'
PLATES = ROOT / 'build' / 'plates-2x'
OUT = ASSETS / 'motion'
OUTLINE_PT = 0.5            # 轮廓外描边（点）；2 倍图上 1 像素
SCALE = 2
LEGS_TOP = 126 * SCALE      # 桌腿、椅子一带从这一行往下必须逐帧不变

BLINK = [(0.55, 50), (1.0, 70), (0.45, 80)]
SLOW_BLINK = [(0.5, 70), (1.0, 110), (0.5, 110)]


# ---------- 底图（2 倍） ----------

# id → 来源：('source', 源图状态, 帧号) 按 rekey_plates 的配准放大两倍；('hold', 文件) 直接用；('upscale', 相对 Assets 的 1 倍图, 帧号) 超分。
PLATE_SOURCES = {
    'thinking': ('source', 'thinking', 0),
    'read_file': ('source', 'read_file', 0),
    'view_image': ('source', 'view_image', 0),
    'write_file': ('source', 'write_file', 0),
    'verify': ('source', 'verify', 0),
    'read_web': ('source', 'read_web', 0),
    'respond': ('source', 'respond', 3),
    'question_for_user': ('hold', REPO / 'sources' / 'question_for_user-hold-2x.png'),
    'task_complete': ('hold', REPO / 'sources' / 'task_complete-hold-2x.png'),
    'default_work': ('upscale', 'activities/computer-desk.png', 0),
    'idle': ('upscale', 'base/idle.webp', 0),
    'failed': ('upscale', 'base/failed.webp', 3),
    'failed_f0': ('upscale', 'base/failed.webp', 0),
    'failed_f2': ('upscale', 'base/failed.webp', 2),
}


def plate_path(pid: str) -> Path:
    PLATES.mkdir(parents=True, exist_ok=True)
    path = PLATES / f'{pid}.png'
    if path.exists():
        return path
    kind, *args = PLATE_SOURCES[pid]
    if kind == 'source':
        sys.path.insert(0, str(ROOT / 'tools' / 'plates'))
        import rekey_plates as rk
        state, idx = args
        fr, bg = rk.source_frames(state)[idx]
        F, a = rk.key_source(fr, bg)
        prem = np.concatenate([F * a[..., None], a[..., None] * 255], axis=2)
        s, tx, ty = rk.REGISTRATION[state][idx]
        K = 2
        M = np.array([[s * SCALE * K, 0, tx * SCALE * K], [0, s * SCALE * K, ty * SCALE * K]], np.float32)
        big = cv2.warpAffine(prem, M, (W * K, H * K), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(0, 0, 0, 0))
        out = rk.to_straight(np.clip(cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA), 0, 255))
        Image.fromarray(out).save(path)
    elif kind == 'hold':
        im = Image.open(args[0]).convert('RGBA')
        if im.size != (W, H):
            raise SystemExit(f'{args[0]} 应是 {W}×{H}')
        im.save(path)
    else:
        import upscale_motion as um
        rel, idx = args
        im = Image.open(ASSETS / rel).convert('RGBA').crop((idx * W // SCALE, 0, (idx + 1) * W // SCALE, H // SCALE))
        big = um.upscale_rgba(um.Upscaler(), np.asarray(im).copy(), SCALE)
        Image.fromarray(big).save(path)
    print('底图', path)
    return path


def load_plate(pid: str) -> np.ndarray:
    return R.load_rgba(str(plate_path(pid)))


# ---------- 状态定义 ----------

@dataclass
class State:
    id: str
    plate: str                     # PLATE_SOURCES 里的 id
    eyes: list                     # 两只眼的搜索框 (x0, y0, x1, y1)，2 倍坐标
    period: float                  # 循环一轮的秒数（period × fps 须为整数）
    cycles: int                    # 时间轴重复几轮；各轮相同的帧只存一份
    fps: int
    blinks: list                   # 眨眼时刻（循环时间，秒）
    rig: object                    # (plate, eyes) -> Rig；t < 0 是开场（intro），t ≥ 0 是循环
    blink: list = field(default_factory=lambda: BLINK)
    intro: float = 0.0             # 开场只播一次的秒数
    intro_fps: int = 30
    pre: list = field(default_factory=list)   # 开场前原样拷贝的帧 [(底图 id, 毫秒)]（沮丧：先垂眼一次）


def E(box1x, pad=3):
    """1 倍坐标的眼睛框换成 2 倍；左右各放宽 pad 像素，眼角最边上那一列眼白、眼珠也归进来（闭眼时才不会剩一道蓝）。"""
    x0, y0, x1, y1 = (v * SCALE for v in box1x)
    return (x0 - pad, y0, x1 + pad, y1)


def irises(eyes, motion, sigma=(4.4, 4.0)):
    """眼珠（连同睫毛）小幅移动：看向别处。motion 返回 2 倍像素。"""
    return [Bone(f'iris{i}', e.center, gauss(e.center, sigma, e.box, fea=3.0), shift=motion) for i, e in enumerate(eyes)]


def head_bone(center, region, shift=None, angle=None, pivot=None, sigma=(48, 44)):
    b = Bone('head', pivot or center, gauss(center, sigma, region, fea=10))
    if shift is not None:
        b.shift = shift
    if angle is not None:
        b.angle = angle
    return b


def scaled(motion, kx=1.0, ky=1.0):
    return lambda t: (motion(t)[0] * kx, motion(t)[1] * ky)


def patch_clone(pts, dx, dy):
    """补丁：洞里落在多边形内的像素，改成底图上 (x+dx, y+dy) 处的像素。"""
    return lambda base, plate, hole: R.clone(base, plate, np.minimum(polygon(pts), hole), dx, dy)


def patch_rows(pts):
    """补丁：洞里落在多边形内的像素，按同一行左右两侧的完好像素横向补齐（纸、桌面、屏幕）。"""
    return lambda base, plate, hole: R.extend_rows(base, plate, polygon(pts), hole)


def patch_stroke(pts, width, at):
    """补丁：洞里沿折线画一道描线，颜色取底图 at 点。"""
    return lambda base, plate, hole: R.flat(base, plate, np.minimum(stroke(pts, width), hole), at)


def patch_flat(pts, at):
    """补丁：洞里落在多边形内的像素，平涂成底图 at 点的颜色。"""
    return lambda base, plate, hole: R.flat(base, plate, np.minimum(polygon(pts), hole), at)


def patch_paint(pts, rgba, everywhere=False):
    """补丁：多边形内平涂成给定颜色（0–1，含 alpha）；everywhere=True 时不限于洞里（画描线用）。"""
    return lambda base, plate, hole: R.paint(base, polygon(pts) if everywhere else np.minimum(polygon(pts), hole), rgba)


def arm_layers(plate, name, outline_pts, pivot, ramp_from, ramp_to, wrist, wrist_from, wrist_to,
               shift, angle=None, wrist_angle=None, props=(), z=2, parent=None, fixes=None):
    """一条手臂：袖子 + 手套（+ 刚性跟着手的道具）挂在肘骨、腕骨上。
    outline_pts：手臂层的多边形；pivot：肘；ramp_from→ramp_to：肘骨权重从 0 到 1 的方向（肩→袖口）；
    wrist：腕骨支点；wrist_from→wrist_to：腕骨权重的过渡（袖口→手背）；props：[(名字, 多边形)]，抠成刚性层。
    返回 (层列表, 肘骨, 腕骨)。"""
    elbow = Bone(f'{name}_elbow', pivot, ramp(ramp_from, ramp_to), parent=parent, shift=shift)
    if angle is not None:
        elbow.angle = angle
    hand = Bone(f'{name}_wrist', wrist, ramp(wrist_from, wrist_to), parent=elbow)
    if wrist_angle is not None:
        hand.angle = wrist_angle
    layers = []
    for i, (pname, pts) in enumerate(props):
        m = opaque_within(plate, pts if isinstance(pts, np.ndarray) else polygon(pts))
        layers.append(Layer(f'{name}_{pname}', None, [elbow, hand], mask=m, z=z + 1 + i, rigid=True,
                            fix=(fixes or {}).get(pname)))
    arm = opaque_within(plate, polygon(outline_pts))
    layers.append(Layer(name, None, [elbow, hand], mask=arm, z=z))
    return layers, elbow, hand


# ---------- 各动作 ----------

def write_file(plate, eyes):
    # 写字：右臂（画面左侧）从肩膀起是一层，袖口带着手套和笔沿着一行往右写，笔尖只往上挑不越过纸边；
    # 写完一行回到左边。头跟着微微转，眼睛盯着笔尖。笔是刚性的一层，压在手臂之上。
    P, END = 2.0, 1.6

    def pen(t):
        t %= P
        if t < END:
            u = t / END
            env = math.sin(math.pi * u)
            stroke_ = 0.5 - 0.5 * math.cos(2 * math.pi * 3.5 * t)
            return (-3.6 + 7.2 * u, -2.2 * env * stroke_, 3.0 * env * math.sin(2 * math.pi * 3.5 * t + 0.6))
        return (3.6 - 7.2 * R.ease((t - END) / (P - END)), 0.0, 0.0)

    pen_poly = [(137, 172), (150, 170), (166, 199), (187, 234), (185, 245), (171, 244), (150, 209), (133, 183)]
    arm_poly = [(138, 167), (153, 167), (161, 177), (166, 192), (169, 205), (175, 212), (181, 222), (181, 234),
                (178, 246), (164, 249), (140, 249), (126, 243), (118, 228), (120, 208), (126, 190), (131, 176)]
    layers, elbow, hand = arm_layers(
        plate, 'arm', arm_poly, pivot=(140, 198), ramp_from=(146, 176), ramp_to=(146, 208),
        wrist=(150, 208), wrist_from=(150, 203), wrist_to=(150, 217),
        shift=lambda t: pen(t)[:2], wrist_angle=lambda t: pen(t)[2], props=[('pen', pen_poly)])
    return Rig(layers=layers,
               base_bones=[head_bone((184, 100), (108, 28, 260, 168), shift=lambda t: (0.25 * pen(t)[0], 0)),
                           *irises(eyes, lambda t: (0.4 * pen(t)[0], 0.4))],
               # 手套压着的那截纸：从纸的右半边横着克隆过来（补洞按最近像素会把桌沿的灰带上去）。
               patches=[patch_rows([(100, 229), (200, 229), (200, 250), (100, 250)])])


def opaque_lens(center, r_glass, dark_lum=0.62):
    """放大镜的镜片涂成不透明：镜片里透出来的藏青（原画把外套画进了镜片）换成玻璃自己的浅色，高光留着。
    这样镜片扫过照片时里面不会带着一块冻住的外套走。"""
    cx, cy = center

    def fix(img):
        out = img.copy()
        rgb = np.clip(R.unpremul_rgb(img), 0, 1)
        lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
        inside = (R._XX - cx) ** 2 + (R._YY - cy) ** 2 <= r_glass ** 2
        glass_px = rgb[inside & (lum > dark_lum) & (lum < 0.93) & (img[..., 3] > 0.9)]
        glass = np.median(glass_px, axis=0) if len(glass_px) else np.array([0.80, 0.86, 0.92], np.float32)
        # 深色部分连同它抗锯齿的过渡一起换：亮度越低换得越彻底。
        k = np.clip((dark_lum + 0.12 - lum) / 0.12, 0, 1) * inside * (img[..., 3] > 0.5)
        for c in range(3):
            out[..., c] = np.where(k > 0, (rgb[..., c] * (1 - k) + glass[c] * k) * img[..., 3], out[..., c])
        return out
    return fix


def view_image(plate, eyes):
    # 放大镜：整条右臂带着镜子在照片上方来回扫、微微走弧线，手腕跟着转；镜片不透明；视线跟着镜片。
    P = 2.8

    def sweep(t):
        u = (t % P) / P
        return (-8.0 * math.cos(2 * math.pi * u), -1.4 * math.sin(2 * math.pi * u) ** 2,
                2.5 * math.sin(2 * math.pi * u))

    # 镜框圆盘；下缘压着照片的那几个像素不算（天蓝色的），免得镜子扫动时带着一小块天空走。
    rgb = np.clip(R.unpremul_rgb(plate), 0, 1)
    sky = ((rgb[..., 2] - rgb[..., 0] > 0.2) & (rgb[..., 2] > 0.6)).astype(np.float32)
    lens = np.minimum(disk((176.5, 187.5), 27.0), 1 - R.grow(sky, 1))
    arm_poly = [(124, 162), (160, 162), (166, 176), (168, 196), (170, 212), (168, 228), (160, 238), (140, 240),
                (122, 240), (110, 238), (104, 230), (108, 222), (114, 208), (116, 190), (120, 174)]
    layers, elbow, hand = arm_layers(
        plate, 'arm', arm_poly, pivot=(138, 198), ramp_from=(140, 172), ramp_to=(142, 200),
        wrist=(145, 205), wrist_from=(145, 200), wrist_to=(145, 214),
        shift=lambda t: sweep(t)[:2], wrist_angle=lambda t: sweep(t)[2], props=[('lens', lens)],
        fixes={'lens': opaque_lens((176.5, 187.5), 19.5)})
    return Rig(layers=layers,
               base_bones=[head_bone((184, 100), (108, 28, 260, 160), shift=lambda t: (0.15 * sweep(t)[0], 0)),
                           *irises(eyes, lambda t: (0.22 * sweep(t)[0], 0.3))],
               # 手套压着的照片左上角：从照片右边同一行克隆过来；袖子底下那截桌沿描线从左边接着克隆过来。
               patches=[patch_clone([(148, 203), (178, 203), (178, 250), (148, 250)], 36, 0),
                        patch_clone([(104, 224), (118, 224), (118, 236), (104, 236)], -8, 0)])


def question_for_user(plate, eyes):
    # 等你回答：问号卡立在桌上，整条右臂带着指着卡的手点两下（肘微微抬），然后抬眼看你、停住。
    P = 4.2
    tap = keys([(0, 0, 0, 0), (0.5, 0, 0, 0), (0.70, 3.4, -2.6, -1.5), (0.98, 0, 0, 0), (1.18, 0, 0, 0),
                (1.38, 3.4, -2.6, -1.5), (1.66, 0, 0, 0), (4.2, 0, 0, 0)], P)
    look = vec([(0, 0, 0), (2.0, 0, 0), (2.6, 0, -1.8), (4.2, 0, -1.8)], P)
    arm_poly = [(126, 160), (164, 160), (170, 172), (174, 190), (180, 200), (192, 206), (194, 216), (190, 228),
                (178, 238), (150, 242), (126, 242), (114, 228), (112, 205), (116, 182), (120, 168)]
    layers, elbow, hand = arm_layers(
        plate, 'arm', arm_poly, pivot=(136, 200), ramp_from=(146, 170), ramp_to=(152, 204),
        wrist=(160, 208), wrist_from=(160, 202), wrist_to=(160, 216),
        shift=lambda t: tap(t)[:2], angle=lambda t: tap(t)[2])
    return Rig(layers=layers,
               base_bones=[head_bone((188, 100), (112, 28, 264, 172), shift=look),
                           *irises(eyes, lambda t: (0.28 * tap(t)[0], 1.5 * look(t)[1]))],
               patches=[patch_rows([(100, 228), (200, 228), (200, 248), (100, 248)])])


def read_file(plate, eyes):
    # 读书：整条右臂带着指着书的手沿一行从左划到右，读完回到行首；视线和头跟着。
    trace = keys([(0, -6.0, -0.6, 0), (1.75, 6.0, 0.6, 0)], 2.2)
    arm_poly = [(124, 160), (162, 160), (168, 172), (172, 190), (178, 204), (182, 222), (178, 236), (162, 242),
                (140, 242), (126, 236), (118, 222), (115, 202), (118, 182), (121, 168)]
    layers, elbow, hand = arm_layers(
        plate, 'arm', arm_poly, pivot=(136, 200), ramp_from=(144, 172), ramp_to=(150, 204),
        wrist=(152, 208), wrist_from=(152, 202), wrist_to=(152, 216),
        shift=lambda t: trace(t)[:2])
    return Rig(layers=layers,
               base_bones=[head_bone((184, 100), (108, 28, 260, 168), shift=lambda t: (0.3 * trace(t)[0], 0)),
                           *irises(eyes, lambda t: (0.45 * trace(t)[0], 0.4))],
               patches=[patch_rows([(105, 222), (200, 222), (200, 250), (105, 250)])])


def read_web(plate, eyes):
    # 平板：整条右臂带着点着屏幕的手指往上划两下（翻页），停一会儿；眼睛跟着往下扫。
    swipe = keys([(0, 0, 0, 0), (0.45, 0, 0, 0), (0.62, -2.0, -6.0, -3.0), (1.1, 0, 0, 0), (1.3, 0, 0, 0),
                  (1.47, -2.0, -6.0, -3.0), (1.95, 0, 0, 0)], 2.4)
    arm_poly = [(122, 148), (162, 148), (168, 160), (172, 176), (178, 188), (186, 198), (190, 210), (188, 222),
                (174, 228), (150, 230), (126, 230), (110, 222), (104, 205), (105, 182), (112, 162)]
    layers, elbow, hand = arm_layers(
        plate, 'arm', arm_poly, pivot=(134, 190), ramp_from=(144, 160), ramp_to=(150, 192),
        wrist=(152, 196), wrist_from=(152, 190), wrist_to=(152, 204),
        shift=lambda t: swipe(t)[:2], wrist_angle=lambda t: swipe(t)[2])
    return Rig(layers=layers,
               base_bones=[*irises(eyes, lambda t: (0.25 * swipe(t)[0], -0.15 * swipe(t)[1]))],
               # 手压着的那块屏幕：从右边同一行克隆；被手掌盖住的平板左上角边框，按边框的颜色平涂一条。
               patches=[patch_clone([(150, 198), (192, 198), (192, 232), (150, 232)], 46, 0),
                        patch_flat([(139, 203), (150, 203), (150, 232), (139, 232)], (144, 236))])


def task_complete(plate, eyes):
    # 完成任务：双手托着勾选卡轻轻抬起来给你看一眼，再放回桌上；两条袖子从肩膀起顺着弯，头微微跟一下。
    P = 5.0
    show = vec([(0, 0, 0), (1.0, 0, 0), (1.5, 0, -5.2), (3.0, 0, -5.2), (3.5, 0, 0), (5.0, 0, 0)], P)
    card = polygon([(146, 174), (228, 174), (228, 240), (146, 240)])
    weight = union(ramp((145, 172), (150, 206)), ramp((250, 172), (242, 206)), card)
    lift = Bone('lift', (187, 210), weight, shift=show)
    unit_poly = [(114, 164), (172, 164), (150, 176), (222, 176), (226, 164), (284, 164), (284, 234), (270, 242),
                 (140, 242), (116, 238), (110, 210), (112, 180)]
    unit = Layer('unit', None, [lift], mask=opaque_within(plate, polygon(unit_poly)), z=2)
    return Rig(layers=[unit],
               base_bones=[head_bone((188, 100), (112, 28, 264, 172), shift=lambda t: (0.0, 0.3 * show(t)[1])),
                           *irises(eyes, lambda t: (0.0, 0.5 * show(t)[1]))],
               patches=[patch_rows([(120, 226), (260, 226), (260, 246), (120, 246)])])


def default_work(plate, eyes):
    # 敲键盘：左手在键位间敲、节奏不齐，敲一阵停一下；右手扶着鼠标偶尔挪一下；眼睛在屏幕上扫。袖口都跟着手走。
    P = 2.4
    L = [(0.00, -2.0), (0.27, 1.2), (0.55, -0.8), (0.80, 2.0), (1.07, 0.0), (1.55, -2.0)]

    def stroke_(u):
        if u < 0.06:
            return -4.4 * R.ease(u / 0.06)
        if u < 0.09:
            return -4.4
        if u < 0.14:
            return -4.4 + 5.2 * R.ease((u - 0.09) / 0.05)
        if u < 0.22:
            return 0.8 * (1 - R.ease((u - 0.14) / 0.08))
        return 0.0

    def typing(t):
        t %= P
        done = [s for s in L if s[0] <= t]
        if not done:
            return (0.0, 0.0)
        s, kx = done[-1]
        prev = done[-2][1] if len(done) > 1 else 0.0
        x = prev + (kx - prev) * R.ease((t - s) / 0.06)
        if t > 1.9:
            x *= 1 - R.ease((t - 1.9) / 0.4)
        return (x, stroke_(t - s))

    mouse = vec([(0, 0, 0), (0.7, 0, 0), (1.0, 2.0, 0.4), (1.5, 2.0, 0.4), (1.8, -1.2, -0.2), (2.3, 0, 0)], P)
    scan = vec([(0, -0.6, 0), (1.2, 0.6, 0)], P)
    left_poly = [(150, 168), (196, 168), (202, 180), (206, 196), (210, 212), (206, 228), (190, 232), (170, 232),
                 (152, 226), (140, 212), (138, 190), (141, 176)]
    right_poly = [(232, 166), (280, 166), (286, 180), (290, 200), (292, 222), (288, 236), (268, 240), (240, 238),
                  (216, 234), (208, 222), (212, 208), (222, 200), (228, 186)]
    left, _, _ = arm_layers(plate, 'left', left_poly, pivot=(160, 200), ramp_from=(172, 178), ramp_to=(180, 204),
                            wrist=(185, 206), wrist_from=(185, 200), wrist_to=(185, 214), shift=typing)
    right, _, _ = arm_layers(plate, 'right', right_poly, pivot=(262, 200), ramp_from=(262, 178), ramp_to=(252, 206),
                             wrist=(248, 212), wrist_from=(255, 208), wrist_to=(240, 214), shift=mouse)
    return Rig(layers=left + right, base_bones=[*irises(eyes, scan)],
               patches=[patch_rows([(146, 224), (300, 224), (300, 246), (146, 246)])])


def respond(plate, eyes):
    # 递交报告：先整理文件——后面两张没对齐的纸从两侧伸出来，双手拿着整叠在桌上磕两下、纸慢慢对齐；然后停住只眨眼。
    # 整叠（报告 + 两只手 + 两条袖子）挂在一根「抬」骨上：报告与手整体动，袖子从肩膀起顺着弯。
    INTRO = 1.4
    lift = keys([(0, 0, 0, 0), (0.25, 0, 0, 0), (0.45, 0, -4.4, 0), (0.58, 0, 0, 0), (0.78, 0, -3.2, 0),
                 (0.9, 0, 0, 0), (1.4, 0, 0, 0)], 10.0)
    fan = scalar([(0, 1.0), (0.3, 1.0), (0.58, 0.5), (0.9, 0.12), (1.1, 0.0), (1.4, 0.0)], 10.0)

    def main(t):
        return lift(t + INTRO)[:2] if t < 0 else (0.0, 0.0)

    def loose(dx, angle):
        def shift(t):
            if t >= 0:
                return (0.0, 0.0)
            k = fan(t + INTRO)
            return (dx * k, lift(t + INTRO)[1])

        def ang(t):
            return angle * fan(t + INTRO) if t < 0 else 0.0
        return shift, ang

    paper = polygon([(148, 170), (224, 170), (224, 244), (148, 244)])
    weight = union(ramp((140, 170), (148, 196)), ramp((262, 170), (232, 196)), paper)
    hold = Bone('hold', (186, 236), weight, shift=main)
    unit_poly = [(118, 160), (166, 160), (152, 170), (220, 170), (206, 160), (284, 160), (284, 234), (268, 242),
                 (130, 242), (116, 234), (110, 205), (112, 178)]
    unit = Layer('unit', None, [hold], mask=opaque_within(plate, polygon(unit_poly)), z=3)
    rgb = R.unpremul_rgb(plate)
    paper_px = rgb[190:220, 176:212].reshape(-1, 3)
    fill = np.median(paper_px[paper_px.mean(axis=1) > 0.8], axis=0)
    ink = np.array([0.42, 0.42, 0.50])
    # 后面那两张纸要能完全躲回整叠后面：按报告的实心范围往里收着画，转动的支点放在整叠底边。
    sheet = R.sheet_image((158, 172, 212, 232), np.append(fill, 1.0), np.append(ink, 1.0))
    behind = []
    for i, (dx, angle) in enumerate([(-12.0, -6.0), (10.0, 5.0)]):
        shift, ang = loose(dx, angle)
        b = Bone(f'loose{i}', (194, 234), R.full(), shift=shift, angle=ang)
        behind.append(Layer(f'sheet{i}', sheet, [b], mask=None, z=1 + i, rigid=True))
    return Rig(layers=[unit] + behind,
               patches=[patch_rows([(120, 228), (260, 228), (260, 248), (120, 248)])])


def verify(plate, eyes):
    # 对照检查：头在左右两份文件之间转来转去，眼珠跟着；手不动。
    look = vec([(0, -2.8, 0), (1.3, -2.8, 0), (1.9, 2.8, 0), (3.0, 2.8, 0)], 3.6)
    return Rig(base_bones=[Bone('head', (176, 100), gauss((176, 100), (52, 48), (100, 28, 260, 172), fea=10), shift=look),
                           Bone('face', (180, 146), gauss((180, 146), (28, 14), (140, 126, 220, 168), fea=6),
                                shift=scaled(look, 0.5, 0)),
                           *irises(eyes, scaled(look, 0.5, 0))])


def thinking(plate, eyes):
    # 托腮：头绕托着下巴的手慢慢歪一点又回来，眼睛偶尔往上看。幅度小。
    tilt = scalar([(0, 0), (1.2, 0), (2.6, 1.5), (4.4, 1.5), (5.8, 0)], 7.0)
    gaze = vec([(0, 0, 0), (1.6, 0, 0), (2.2, -1.6, -1.0), (3.8, -1.6, -1.0), (4.4, 0, 0)], 7.0)
    return Rig(base_bones=[Bone('head', (192, 176), gauss((176, 100), (52, 48), (100, 28, 268, 172), fea=10), angle=tilt),
                           *irises(eyes, gaze)])


def idle(plate, eyes):
    # 空闲：偶尔向左、向右看一看（轮廓、五官、眼珠依次多移一点，像是转头），头跟着歪。
    look = vec([(0, 0, 0), (2.6, 0, 0), (3.3, -4.0, 0), (5.0, -4.0, 0), (5.7, 0, 0),
                (8.4, 0, 0), (9.1, 4.0, 0), (10.6, 4.0, 0), (11.3, 0, 0)], 12.0)
    region = (108, 0, 268, 132)
    return Rig(base_bones=[Bone('tilt', (186, 132), gauss((186, 60), (52, 48), region, fea=10), angle=lambda t: 0.8 * look(t)[0] / 2),
                           Bone('head', (186, 60), gauss((186, 60), (52, 48), region, fea=10), shift=look),
                           Bone('face', (186, 92), gauss((186, 92), (28, 16), (144, 70, 228, 118), fea=6),
                                shift=scaled(look, 0.5, 0)),
                           *irises(eyes, scaled(look, 0.6, 0))])


def failed(plate, eyes):
    # 沮丧：垂眼停住后，慢慢叹一口气（头往下沉再回来），慢慢眨眼。
    sigh = vec([(0, 0, 0), (1.5, 0, 0), (2.7, 0, 1.8), (4.4, 0, 0)], 5.5)
    return Rig(base_bones=[Bone('head', (186, 64), gauss((186, 64), (52, 48), (108, 0, 268, 132), fea=10), shift=sigh)])


STATES = [
    State('thinking', 'thinking', [E((76, 63, 88, 77)), E((95, 63, 107, 77))], 7.0, 1, 8, [0.9, 4.9], thinking,
          blink=SLOW_BLINK),
    State('read_file', 'read_file', [E((77, 64, 89, 78)), E((97, 64, 109, 78))], 2.2, 2, 20, [4.25], read_file),
    State('view_image', 'view_image', [E((77, 64, 89, 78)), E((97, 64, 109, 78))], 2.8, 2, 15, [1.4, 4.2], view_image),
    State('write_file', 'write_file', [E((76, 64, 88, 78)), E((97, 64, 109, 78))], 2.0, 2, 30, [3.7], write_file),
    State('verify', 'verify', [E((74, 66, 87, 79)), E((93, 68, 108, 79))], 3.6, 1, 15, [1.6], verify),
    State('read_web', 'read_web', [E((78, 66, 90, 77)), E((99, 66, 111, 77))], 2.4, 2, 20, [3.5], read_web),
    State('respond', 'respond', [E((77, 65, 89, 79)), E((97, 65, 109, 79))], 4.0, 1, 15, [1.6], respond,
          intro=1.4, intro_fps=30),
    State('default_work', 'default_work', [E((92, 62, 102, 75)), E((110, 57, 122, 72))], 2.4, 2, 20, [4.25], default_work),
    State('question_for_user', 'question_for_user', [E((77, 63, 90, 77)), E((99, 63, 112, 77))], 4.2, 1, 20, [3.1],
          question_for_user),
    State('task_complete', 'task_complete', [E((76, 63, 90, 78)), E((99, 63, 112, 78))], 5.0, 1, 20, [4.2], task_complete),
    State('idle', 'idle', [E((78, 40, 90, 54)), E((97, 36, 109, 50))], 12.0, 1, 12, [1.3, 5.2, 7.3, 10.9], idle),
    State('failed', 'failed', [E((78, 42, 91, 54)), E((98, 38, 110, 50))], 5.5, 1, 10, [0.9], failed, blink=SLOW_BLINK,
          pre=[('failed_f0', 240), ('failed_f2', 180)]),
]


# ---------- 生成 ----------

def plate_and_eyes(st: State):
    plate = load_plate(st.plate)
    return plate, [R.detect_eye(plate, b) for b in st.eyes]


def build_scene(st: State) -> Scene:
    plate, eyes = plate_and_eyes(st)
    rig = st.rig(plate, eyes)
    # 分层：从最上面一层起依次抠出、把它的洞补上，下一层从补过的图上抠——道具压着的袖子、手压着的纸都能补出来。
    current = plate
    for L in sorted(rig.layers, key=lambda L: -L.z):
        if L.mask is not None and L.image is None:
            L.image = cut(current, L.mask)
            if L.fix is not None:
                L.image = L.fix(L.image)
            current = R.nearest_fill(current, L.mask)
    rig.base_image = current if rig.layers else plate
    for p in rig.patches:
        rig.base_image = p(rig.base_image, plate, union(*[L.mask for L in rig.layers if L.mask is not None]))
    return Scene(plate, eyes, rig)


def build(st: State):
    scene = build_scene(st)
    per = int(round(st.period * st.fps))
    assert abs(per - st.period * st.fps) < 1e-6, f'{st.id}: period × fps 须为整数'
    frames_pre = [Frame(load_plate(pid), ms) for pid, ms in st.pre]
    n_intro = int(round(st.intro * st.intro_fps))
    worst = 0.0
    intro = list(frames_pre)
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
    return scene, intro, loop, worst, len(frames_pre)


def combine(intro, loop):
    iu, iseq, idur = R.assemble(intro) if intro else ([], [], [])
    lu, lseq, ldur = R.assemble(loop)
    return iu + lu, iseq + [i + len(iu) for i in lseq], idur + ldur, len(iseq)


def finish_frame(p: np.ndarray, outline: float) -> np.ndarray:
    return R.add_outline(R.to_uint8(p), outline * SCALE)


def generate(only=None, outline=OUTLINE_PT):
    OUT.mkdir(parents=True, exist_ok=True)
    entries = []
    for st in STATES:
        if only is not None and st.id not in only:
            continue
        t0 = time.time()
        scene, intro, loop, worst, copied = build(st)
        uniques, seq, dur, loop_start = combine(intro, loop)
        # 桌腿、椅子一带必须与底图逐像素相同（开场原样拷贝的站姿帧除外）。
        base = np.round(scene.plate * 255)
        moved = max(int((np.abs(np.round(f.image * 255) - base)[LEGS_TOP:].max(axis=2) > 0).sum())
                    for f in intro[copied:] + loop)
        big = [finish_frame(u, outline) for u in uniques]
        sheet = R.pack(big)
        R.save_webp(sheet, OUT / f'{st.id}.webp')
        entries.append({'id': st.id, 'asset': f'{st.id}.webp', 'frameWidth': W // SCALE, 'frameHeight': H // SCALE,
                        'sequence': seq, 'durationsMs': dur, 'loop': True, 'loopStart': loop_start, 'pixelScale': SCALE})
        cycle = sum(dur[loop_start:])
        print(f'{st.id:18s} 不重复帧 {len(uniques):3d}  步数 {len(seq):3d}  一轮 {cycle / 1000:5.2f}s  '
              f'相邻帧最大移动 {worst / SCALE:.2f} 点  桌腿区变化像素 {moved}  图条 {sheet.width}×{sheet.height}  '
              f'{time.time() - t0:.0f}s')
        if moved:
            raise SystemExit(f'{st.id}: 桌腿区被改动了')
    write_motion_json(entries, merge=only is not None, outline=outline)


def write_motion_json(entries, merge: bool, outline: float):
    path = OUT / 'motion.json'
    if merge and path.exists():
        current = json.loads(path.read_text(encoding='utf-8'))
        by_id = {s['id']: s for s in current['states']}
        for e in entries:
            by_id[e['id']] = e
        states = list(by_id.values())
    else:
        states = entries
    note = ('每个动作只用一张底图，拆成几层挂在骨骼上：整条手臂（袖子、手套、道具）是一层，肩膀不动、袖口带着手走；'
            '头眼用局部变形；桌椅逐像素不动。图条是 2 倍分辨率（pixelScale=2），直接在 2 倍底图上生成，太长的折成几行。')
    if outline > 0:
        note += f' 轮廓外垫了一圈 {outline:g} 点的深色描边。'
    path.write_text(json.dumps({
        'version': 4,
        'generator': 'tools/motion/make_rig.py',
        'note': note,
        'states': states,
    }, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('写入', path)


# ---------- 检查图 ----------

def _font(size=11):
    try:
        return ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', size)
    except Exception:
        return ImageFont.load_default()


def grid_image(plate: np.ndarray, box: tuple, zoom: int = 6, step: int = 5, overlay=None) -> Image.Image:
    x0, y0, x1, y1 = box
    bg = R.on_white(plate)
    if overlay is not None:
        bg.alpha_composite(overlay)
    crop = bg.crop((x0, y0, x1, y1)).resize(((x1 - x0) * zoom, (y1 - y0) * zoom), Image.NEAREST)
    M = 28
    canvas = Image.new('RGB', (crop.width + M, crop.height + M), (240, 240, 240))
    canvas.paste(crop.convert('RGB'), (M, M))
    d = ImageDraw.Draw(canvas)
    font = _font(10)
    for x in range((x0 // step) * step, x1 + 1, step):
        if x < x0:
            continue
        X = M + (x - x0) * zoom
        d.line([(X, M), (X, canvas.height)], fill=(255, 60, 60) if x % (step * 5) == 0 else (90, 170, 255), width=1)
        d.text((X - 8, 2), str(x), fill=(0, 0, 0), font=font)
    for y in range((y0 // step) * step, y1 + 1, step):
        if y < y0:
            continue
        Y = M + (y - y0) * zoom
        d.line([(M, Y), (canvas.width, Y)], fill=(255, 60, 60) if y % (step * 5) == 0 else (90, 170, 255), width=1)
        d.text((1, Y - 5), str(y), fill=(0, 0, 0), font=font)
    return canvas


def layers_sheets(folder, only=None, zoom=3):
    """每段：各层蒙版（着色叠在底图上）、各层单独、补好的底图、几个时刻的帧——都裁到会动的范围放大。"""
    Path(folder).mkdir(parents=True, exist_ok=True)
    colors = [(255, 0, 0), (0, 160, 0), (0, 90, 255), (230, 120, 0), (160, 0, 200)]
    for st in STATES:
        if only is not None and st.id not in only:
            continue
        scene = build_scene(st)
        rig = scene.rig
        tiles = []
        if rig.layers:
            ys, xs = np.nonzero(scene.hole > 0.04)
            x0, x1 = max(xs.min() - 14, 0), min(xs.max() + 15, W)
            y0, y1 = max(ys.min() - 14, 0), min(ys.max() + 15, H)
        else:
            x0, y0, x1, y1 = 0, 0, W, H
            zoom = 1
        over = np.asarray(R.on_white(scene.plate)).astype(np.float32)
        for i, L in enumerate(sorted(rig.layers, key=lambda L: L.z)):
            c = np.array(colors[i % len(colors)], np.float32)
            m = (L.mask if L.mask is not None else L.image[..., 3])[..., None] * 0.55
            over[..., :3] = over[..., :3] * (1 - m) + c * m
        tiles.append(('蒙版', Image.fromarray(over.astype(np.uint8))))
        for L in sorted(rig.layers, key=lambda L: L.z):
            tiles.append((f'层 {L.name}', R.on_white(L.image)))
        tiles.append(('补好的底图', R.on_white(scene.base)))
        times = ([-st.intro + st.intro * j / 3 for j in range(3)] if st.intro else []) + \
                [st.period * j / 6 for j in range(6)]
        for t in times:
            tiles.append((f't={t:.2f}s', R.on_white(scene.frame(t))))
        cw, ch = (x1 - x0) * zoom, (y1 - y0) * zoom
        cols = 4
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * (cw + 8), rows * (ch + 18)), (225, 225, 225))
        d = ImageDraw.Draw(sheet)
        for i, (label, im) in enumerate(tiles):
            X, Y = (i % cols) * (cw + 8), (i // cols) * (ch + 18)
            d.text((X + 2, Y + 2), f'{st.id} {label}', fill=(0, 0, 0), font=_font(11))
            sheet.paste(im.crop((x0, y0, x1, y1)).resize((cw, ch), Image.NEAREST).convert('RGB'), (X, Y + 16))
        sheet.save(Path(folder) / f'{st.id}.png')
        print('写入', Path(folder) / f'{st.id}.png')


def eyes_sheet(path):
    tiles = []
    for st in STATES:
        plate, eyes = plate_and_eyes(st)
        x0 = min(b[0] for b in st.eyes) - 6
        y0 = min(b[1] for b in st.eyes) - 8
        x1 = max(b[2] for b in st.eyes) + 6
        y1 = max(b[3] for b in st.eyes) + 6
        row = []
        for a in (0.0, 0.5, 1.0):
            im = R.on_white(R.paint_blink(plate, eyes, a)).crop((x0, y0, x1, y1)).resize(((x1 - x0) * 4, (y1 - y0) * 4), Image.NEAREST)
            if a == 0:
                d = ImageDraw.Draw(im)
                for e in eyes:
                    bx0, by0, bx1, by1 = e.box
                    d.rectangle([(bx0 - x0) * 4, (by0 - y0) * 4, (bx1 - x0) * 4 - 1, (by1 - y0) * 4 - 1], outline=(0, 120, 255))
            row.append(im)
        tiles.append((st.id, row))
    tw = max(sum(i.width for i in r) + 20 for _, r in tiles)
    th = sum(r[0].height + 18 for _, r in tiles)
    sheet = Image.new('RGBA', (tw, th), (230, 230, 230, 255))
    d = ImageDraw.Draw(sheet)
    y = 0
    for name, row in tiles:
        d.text((4, y + 2), name, fill=(0, 0, 0), font=_font())
        x = 0
        for im in row:
            sheet.alpha_composite(im, (x, y + 16))
            x += im.width + 10
        y += row[0].height + 18
    sheet.save(path)


def gifs(folder, only=None):
    Path(folder).mkdir(parents=True, exist_ok=True)
    for st in STATES:
        if only is not None and st.id not in only:
            continue
        scene, intro, loop, worst, copied = build(st)
        ims, durs = [], []
        for f in intro + loop:
            ims.append(R.on_white(f.image).convert('P', palette=Image.ADAPTIVE))
            durs.append(int(f.duration_ms))
        ims[0].save(Path(folder) / f'{st.id}.gif', save_all=True, append_images=ims[1:], duration=durs, loop=0)
        print('写入', Path(folder) / f'{st.id}.gif')


def html_preview(path):
    def data_uri(p):
        return 'data:image/webp;base64,' + base64.b64encode(Path(p).read_bytes()).decode()
    motion = json.loads((OUT / 'motion.json').read_text(encoding='utf-8'))
    items = []
    for s in motion['states']:
        items.append(dict(id=s['id'], src=data_uri(OUT / s['asset']), seq=s['sequence'], dur=s['durationsMs'],
                          loopStart=s.get('loopStart', 0), k=s.get('pixelScale', 1), fw=s['frameWidth'], fh=s['frameHeight']))
    Path(path).write_text(HTML_TEMPLATE.replace('__ITEMS__', json.dumps(items)), encoding='utf-8')
    print('写入', path)


HTML_TEMPLATE = """<!doctype html><meta charset="utf-8"><title>雪绪动作预览</title>
<style>
body{margin:0;padding:16px;font:14px -apple-system,system-ui,sans-serif;background:#eef1f5;color:#1f2a44}
h1{font-size:18px;margin:0 0 4px} p{margin:0 0 14px;color:#56627a}
.grid{display:flex;flex-wrap:wrap;gap:14px}
.card{background:#fff;border-radius:10px;padding:10px 12px;box-shadow:0 1px 2px rgba(0,0,0,.08);text-align:center}
.card h2{font-size:13px;margin:0 0 6px}
canvas{width:288px;height:312px;background:repeating-conic-gradient(#f4f4f4 0 25%,#fff 0 50%) 0 0/16px 16px;border-radius:6px}
</style>
<h1>雪绪 · 动作预览</h1><p>按图条的真实时长播放，显示为 150%。</p>
<div class="grid" id="g"></div>
<script>
const items = __ITEMS__;
const players = [];
for (const it of items) {
  const card = document.createElement('div'); card.className = 'card';
  card.innerHTML = `<h2>${it.id}</h2><canvas width="${it.fw*it.k}" height="${it.fh*it.k}"></canvas>`;
  document.getElementById('g').appendChild(card);
  const img = new Image(); img.src = it.src;
  players.push({ctx: card.querySelector('canvas').getContext('2d'), img, it, step: 0, at: performance.now()});
}
function frame(now) {
  for (const p of players) {
    const s = p.it;
    while (now - p.at >= s.dur[p.step]) {
      p.at += s.dur[p.step];
      p.step = p.step + 1 < s.seq.length ? p.step + 1 : s.loopStart;
    }
    if (!p.img.complete || !p.img.naturalWidth) continue;
    const cw = s.fw * s.k, ch = s.fh * s.k, per = Math.floor(p.img.naturalWidth / cw), i = s.seq[p.step];
    p.ctx.clearRect(0, 0, cw, ch);
    p.ctx.drawImage(p.img, (i % per) * cw, Math.floor(i / per) * ch, cw, ch, 0, 0, cw, ch);
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
</script>
"""


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append', help='只处理这些动作 id')
    ap.add_argument('--layers', help='分层检查图目录')
    ap.add_argument('--grid', nargs=6, metavar=('ID', 'X0', 'Y0', 'X1', 'Y1', 'OUT'), help='底图局部放大加网格')
    ap.add_argument('--zoom', type=int, default=6)
    ap.add_argument('--step', type=int, default=5)
    ap.add_argument('--eyes')
    ap.add_argument('--html')
    ap.add_argument('--gif')
    ap.add_argument('--outline', type=float, default=OUTLINE_PT)
    args = ap.parse_args()
    only = set(args.only) if args.only else None
    if args.grid:
        pid, x0, y0, x1, y1, out = args.grid
        grid_image(load_plate(pid), (int(x0), int(y0), int(x1), int(y1)), args.zoom, args.step).save(out)
        print('写入', out)
    elif args.layers:
        layers_sheets(args.layers, only)
    elif args.eyes:
        eyes_sheet(args.eyes)
    elif args.html:
        html_preview(args.html)
    elif args.gif:
        gifs(args.gif, only)
    else:
        generate(only, args.outline)
