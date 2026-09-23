#!/usr/bin/env python3
"""从一张底图上自动找出整条手臂（袖子 + 手套）的轮廓，给 make_rig.py 里的 arm_poly 打底稿。

流程：原图 → 人体检测 → 姿态点（肩／肘／腕）→ 围出手臂的大致范围 → SAM 2 精确分割 → 蒙版修整 → 手臂轮廓
  1. 人体检测：YOLO11-pose 找人框；有透明通道的底图再和不透明区域取交，白底的普通图片把「和图边相连的白」当背景。
  2. 姿态点：同一个 YOLO11-pose 出 COCO 17 点，取肩、肘、腕。Q 版人物头大臂短，它给的肩偏向领口、肘偏向袖口，
     只当大概位置用，不当骨骼支点。
  3. 大致范围：肩肘腕的外接框，四周各留出臂长的三到五成。
  4. SAM 2：按这个框加上「上臂中点、前臂中点、腕」三个正点、领口下前襟一个负点分割（三种松紧 × 两版点位），
     六张蒙版先打分（碎、出界、被框截断的不要），剩下的逐像素投票取多数。手套常被 SAM 当成另一个东西，
     再只用腕点分一遍，圈出来的挨着袖子、不算大就并进来。
  5. 修整：只留人物不透明的像素；只留经过肘、腕的那块；沿描线（黑帽运算找的细深线）把蒙版切开，挨着前襟点的块扔掉
     （袖子和前襟一个颜色只隔一道缝线，SAM 常连着圈）；贴着袖子的描线再吸回来（袖子的轮廓线、缝线要跟着袖子走）；
     补洞；3×3 开、闭运算抹平锯齿；肩膀附近的凹口按凸包填平（这一带骨骼权重是 0，多包一点也不会动）；再补一次洞。
  6. 轮廓：外扩一像素后取外轮廓，按容差简化成多边形。坐标就是这张图的像素（底图 id 即 2 倍图坐标），直接贴进 make_rig.py。

用法（在 YukioPlayer 目录；要在装了 torch 的环境里跑，环境见 upscale_motion.py）：
  ~/.cache/yukio-sr/bin/pip install ultralytics                              第一次装
  ~/.cache/yukio-sr/bin/python tools/motion/find_arm.py read_web             底图 id → build/plates-2x/read_web.png
  ~/.cache/yukio-sr/bin/python tools/motion/find_arm.py 图.png --side both    任意图片；--side left / right / both，
                                                                           是画面的左右（同 make_rig.py）；默认 left
  ... --out 目录     每条手臂写 <名>_<side>.json（多边形、肩肘腕）、<名>_<side>.png（预览）、<名>_<side>_mask.png；默认 build/arms/
  ... --eps 1.2      多边形简化容差（像素）
  ... --line 12      描线的强度（比周围暗多少才算线；2 倍底图 12 合适，0 = 不按描线切、不吸描线）
  ... --compare "[(x, y), ...]"   预览图里再画一条手标的多边形（品红）作对照
权重 yolo11m-pose.pt（40 MB）、sam2.1_b.pt（154 MB）第一次运行自动下载到 tools/motion/models/（已在 .gitignore）。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
PLATES = ROOT / 'build' / 'plates-2x'
MODELS = Path(__file__).resolve().parent / 'models'
POSE_WEIGHTS = MODELS / 'yolo11m-pose.pt'
SAM_WEIGHTS = MODELS / 'sam2.1_b.pt'

# COCO 17 点里用到的下标。左右按画面算（和 make_rig.py 里 left_poly / right_poly 一致）：画面左边那条是人物的右臂。
NOSE, L_SHO, R_SHO, L_ELB, R_ELB, L_WRI, R_WRI, L_HIP, R_HIP = 0, 5, 6, 7, 8, 9, 10, 11, 12
SIDES = {'left': (R_SHO, R_ELB, R_WRI), 'right': (L_SHO, L_ELB, L_WRI)}
PADS = (0.3, 0.4, 0.5)          # 大致范围：四周留出臂长的几成，三种松紧各分割一次
K3 = np.ones((3, 3), np.uint8)


# ---------- 1. 读图、人体检测 ----------

def load_image(path: Path):
    """→ (白底 RGB uint8, 人物蒙版 bool)。有透明通道用透明通道；没有就把和图边相连的「接近白」当背景。"""
    rgba = np.asarray(Image.open(path).convert('RGBA'))
    alpha = rgba[..., 3]
    if alpha.min() < 255:
        person = alpha > 5
    else:
        white = (rgba[..., :3].min(-1) > 240).astype(np.uint8)
        _, cc = cv2.connectedComponents(white, connectivity=4)
        edge = np.unique(np.concatenate([cc[0], cc[-1], cc[:, 0], cc[:, -1]]))
        person = ~np.isin(cc, edge[edge > 0])
    a = alpha[..., None].astype(np.float32) / 255
    rgb = np.round(rgba[..., :3] * a + 255 * (1 - a)).astype(np.uint8)
    return rgb, person


def detect_person(pose_model, rgb: np.ndarray, person: np.ndarray):
    """YOLO11-pose：人框 + 17 个关键点。有几个框时取「和人物蒙版重叠 × 置信度」最大的。→ (框, 点 xy, 点置信度, 框置信度)"""
    r = pose_model.predict(rgb[..., ::-1].copy(), imgsz=640, conf=0.05, verbose=False)[0]   # ultralytics 吃 BGR
    if len(r.boxes) == 0:
        raise SystemExit('人体检测：没找到人')
    best, best_score = 0, -1.0
    for i in range(len(r.boxes)):
        x0, y0, x1, y1 = [max(0, int(round(v))) for v in r.boxes.xyxy[i].tolist()]
        score = float(person[y0:y1, x0:x1].sum()) * float(r.boxes.conf[i])
        if score > best_score:
            best, best_score = i, score
    box = [float(v) for v in r.boxes.xyxy[best].tolist()]
    kxy = r.keypoints.xy[best].cpu().numpy()
    kcf = r.keypoints.conf[best].cpu().numpy() if r.keypoints.conf is not None else np.ones(17, np.float32)
    return box, kxy, kcf, float(r.boxes.conf[best])


# ---------- 2–4. 手臂的大致范围、SAM 2 ----------

def arm_length(k: np.ndarray, side: str) -> float:
    s, e, w = (k[i] for i in SIDES[side])
    return float(np.linalg.norm(e - s) + np.linalg.norm(w - e))


def chest_point(k: np.ndarray, side: str) -> np.ndarray:
    """同侧领口下面的前襟：肩点往另一边肩膀挪四分之一、再往下 0.15 臂长。"""
    s = k[SIDES[side][0]]
    other = k[SIDES['left' if side == 'right' else 'right'][0]]
    return s + 0.25 * (other - s) + np.array([0.0, 0.15 * arm_length(k, side)])


def arm_box(k: np.ndarray, side: str, pad: float, shape) -> list:
    """肩肘腕的外接框，四周各留 pad × 臂长，裁到图内。"""
    pts = np.array([k[i] for i in SIDES[side]])
    L = arm_length(k, side)
    x0, y0 = pts.min(0) - pad * L
    x1, y1 = pts.max(0) + pad * L
    h, w = shape
    return [float(max(0, x0)), float(max(0, y0)), float(min(w - 1, x1)), float(min(h - 1, y1))]


def first_mask(result, shape) -> np.ndarray:
    """ultralytics 的结果里取第一张蒙版；SAM 什么都没圈到时 masks 是空的（或 None）。"""
    if result.masks is None or len(result.masks.data) == 0:
        return np.zeros(shape, bool)
    return result.masks.data[0].cpu().numpy().astype(bool)


def sam_vote(sam, rgb: np.ndarray, person: np.ndarray, k: np.ndarray, side: str):
    """几种提示各分割一次，逐像素投票。→ (多数蒙版 bool, 各次蒙版, 说明)

    只用「框 + 正点」的提示：光给框，框一松 SAM 2 就给出一片碎斑（试过 0.5 倍臂长的框，蒙版像撒了点）；
    正点是前臂中点、腕，再加一版带上臂中点的。分割完给每次打分——碎（3×3 开运算掉的比例）、出界（不在人物上的比例）、
    贴框（蒙版沿着框边被截断的比例）——太碎、出界太多、被框截断的不参加投票。"""
    bgr = rgb[..., ::-1].copy()
    s, e, w = (k[i] for i in SIDES[side])
    # 正点：上臂中点、前臂中点、腕（腕在手套上，袖子和手套才会一起出来；Q 版的肘常和腕挤在袖口，光靠肘腕两点
    # 只会圈出手套）。两版正点位置略有不同（一版偏向肩膀），让投票有点差异。
    # 负点：同侧领口下面的前襟。袖子和前襟一个颜色，只隔一道缝，不给这个点 SAM 更爱把前襟连着一起圈进来；
    # 前襟顺着「肩→袖口」方向往下延伸，骨骼权重不是 0，会跟着手撕开。
    negatives = [chest_point(k, side).tolist()]
    h, wd = rgb.shape[:2]
    scored = []
    for pad in PADS:
        box = arm_box(k, side, pad, (h, wd))
        for shift, tag in ((0.5, 'mid'), (0.35, 'up')):
            points = [(s + shift * (e - s)).tolist(), (e + shift * (w - e)).tolist(), w.tolist()]
            labels = [1] * len(points) + [0] * len(negatives)
            r = sam.predict(bgr, bboxes=[box], points=[points + negatives], labels=[labels], verbose=False)[0]
            m = first_mask(r, (h, wd))
            area = int(m.sum())
            if area == 0:
                scored.append((f'pad{pad}+{tag}', m, 1.0, 1.0, 1.0))
                continue
            opened = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, K3).astype(bool)
            noise = 1 - opened.sum() / area
            outside = (m & ~person).sum() / area
            edge = m & ~cv2.erode(m.astype(np.uint8), K3).astype(bool)
            x0, y0, x1, y1 = [int(round(v)) for v in box]
            frame = np.zeros_like(m)
            frame[y0:y1 + 1, [x0, x1]] = True
            frame[[y0, y1], x0:x1 + 1] = True
            clipped = (edge & frame).sum() / max(edge.sum(), 1)
            scored.append((f'pad{pad}+{tag}', m, noise, outside, clipped))
    good = [m for _, m, noise, outside, clipped in scored if noise < 0.08 and outside < 0.15 and clipped < 0.15]
    note = '、'.join(f'{name} 碎{noise:.2f} 出界{outside:.2f} 贴框{clipped:.2f}' for name, _, noise, outside, clipped in scored)
    if len(good) < 2:
        good = [min(scored, key=lambda t: t[2] + t[3] + t[4])[1]]
    votes = np.sum(good, axis=0)
    return votes >= len(good) / 2, [m for _, m, *_ in scored], f'{len(scored)} 次分割，{len(good)} 次参加投票（{note}）'


def hand_pass(sam, rgb: np.ndarray, person: np.ndarray, sleeve: np.ndarray, w: np.ndarray, L: float):
    """手套单独再分一遍：SAM 常把白手套当成袖子之外的另一个东西，袖子那一遍时有时无。
    只给点、不给框——腕点一个，再加一版「腕再往袖子外面伸一小截」的点。圈出来的东西比袖子还大（圈到整个人）、太碎、
    或者不挨着袖子的都不要；剩下的合并。→ (手套蒙版 或 None, 说明)"""
    bgr = rgb[..., ::-1].copy()
    ys, xs = np.nonzero(sleeve)
    if len(xs) == 0:
        return None, '袖子是空的，没找手套'
    away = w - np.array([xs.mean(), ys.mean()])
    n = float(np.linalg.norm(away))
    guess = w + away / n * 0.2 * L if n > 1e-6 else w
    keep, notes = [], []
    for pts, tag in (([w.tolist()], '腕'), ([w.tolist(), guess.tolist()], '腕+外伸')):
        r = sam.predict(bgr, points=[pts], labels=[[1] * len(pts)], verbose=False)[0]
        m = first_mask(r, sleeve.shape) & person
        area = int(m.sum())
        if area == 0 or area > sleeve.sum():
            notes.append(f'{tag} 太大/为空({area})')
            continue
        noise = 1 - cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, K3).sum() / area
        if noise > 0.1:
            notes.append(f'{tag} 太碎({noise:.2f})')
            continue
        if not (cv2.dilate(sleeve.astype(np.uint8), K3).astype(bool) & m).any():
            notes.append(f'{tag} 不挨着袖子')
            continue
        keep.append(m)
        notes.append(f'{tag} {area}px')
    if not keep:
        return None, '手套：' + '、'.join(notes)
    return np.logical_or.reduce(keep), '手套：' + '、'.join(notes)


# ---------- 5. 修整 ----------

def fill_holes(m: np.ndarray) -> np.ndarray:
    inv = (~m).astype(np.uint8)
    _, cc = cv2.connectedComponents(inv, connectivity=4)
    edge = np.unique(np.concatenate([cc[0], cc[-1], cc[:, 0], cc[:, -1]]))
    return m | ~np.isin(cc, edge)


def anchored_labels(cc: np.ndarray, n: int, anchors, hand) -> set:
    """连通块编号里「经过锚点（锚点 2 像素圆内）」或「一半以上落在手套蒙版里」的那些。"""
    keep = set()
    for x, y in anchors:
        disc = cv2.circle(np.zeros(cc.shape, np.uint8), (int(round(x)), int(round(y))), 2, 1, -1).astype(bool)
        keep |= set(int(v) for v in np.unique(cc[disc]) if v > 0)
    if hand is not None:
        for lab in range(1, n):
            comp = cc == lab
            if (comp & hand).sum() >= 0.5 * comp.sum():
                keep.add(lab)
    return keep


def keep_through(m: np.ndarray, anchors, hand=None) -> np.ndarray:
    """只留经过锚点（或者就是手套）的连通块；一个都不经过就留最大的。"""
    n, cc = cv2.connectedComponents(m.astype(np.uint8), connectivity=8)
    keep = anchored_labels(cc, n, anchors, hand)
    if not keep:
        sizes = np.bincount(cc.ravel())
        sizes[0] = 0
        keep = {int(sizes.argmax())}
    return np.isin(cc, list(keep))


def line_map(rgb: np.ndarray, person: np.ndarray, strength: float, size: int = 7) -> np.ndarray:
    """描线：黑帽运算（闭运算减原图）找出比周围暗一截的细结构。衣服的大片阴影和描线明度差不多，按明度阈值分不开，
    黑帽只认「细」的。"""
    lum = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    return (cv2.morphologyEx(lum, cv2.MORPH_BLACKHAT, k) > strength) & person


def split_by_lines(m: np.ndarray, lines: np.ndarray, anchors, hand, chest, arm_len: float):
    """沿描线把蒙版切开，扔掉前襟：袖子和前襟一个颜色只隔一道缝线，SAM 常把前襟一起圈进来。
    切开后，经过锚点的块、手套的块留下；其余的块只有挨着「前襟点」（0.12 臂长以内）的才算前襟扔掉，
    别的（被袖子上的褶线隔开的小块）留着。→ (留下的, 扔掉的)"""
    # 线加粗一像素，缝线上的小断口才封得住（加粗到两像素试过：没封住更多断口，2.png 的边反而更碎）
    parts = m & ~cv2.dilate(lines.astype(np.uint8), K3).astype(bool)
    n, cc = cv2.connectedComponents(parts.astype(np.uint8), connectivity=4)
    dropped = np.zeros(m.shape, bool)
    if n <= 2:
        return m, dropped
    keep = anchored_labels(cc, n, anchors, hand)
    total = m.sum()
    for lab in range(1, n):
        if lab in keep:
            continue
        comp = cc == lab
        ys, xs = np.nonzero(comp)
        near = np.sqrt((xs - chest[0]) ** 2 + (ys - chest[1]) ** 2).min() < 0.12 * arm_len
        # 前襟是条窄带；挨着前襟点的块要是占了蒙版一大半，那是缝线没切开、袖子和前襟连成一块了，不能整块扔
        if near and comp.sum() < 0.4 * total:
            dropped |= comp
    return m & ~dropped, dropped


def fill_shoulder(m: np.ndarray, person: np.ndarray, shoulder, radius: float) -> np.ndarray:
    """肩膀附近的凹口填平：取蒙版在肩点周围一个圆里的凸包并进来。SAM 在袖子顶端和领口交界处常拿不准，
    留下锯齿或缺口；这一带骨骼权重是 0，多包一点也不会动。"""
    yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    near = (xx - shoulder[0]) ** 2 + (yy - shoulder[1]) ** 2 < radius ** 2
    ys, xs = np.nonzero(m & near)
    if len(xs) < 10:
        return m
    hull = cv2.convexHull(np.column_stack([xs, ys]).astype(np.int32))
    filled = np.zeros(m.shape, np.uint8)
    cv2.fillConvexPoly(filled, hull, 1)
    return m | (filled.astype(bool) & near & person)


def refine(mask: np.ndarray, person: np.ndarray, rgb: np.ndarray, anchors, hand, shoulder, chest, arm_len: float,
           line_strength: float) -> np.ndarray:
    m = keep_through(mask & person, anchors, hand)
    dropped = np.zeros(m.shape, bool)
    if line_strength > 0:
        lines = line_map(rgb, person, line_strength)
        m, dropped = split_by_lines(m, lines, anchors, hand, chest, arm_len)
        # 先把描线全去掉，再把贴着蒙版的吸回来（最多 3 像素）：袖子的轮廓线、缝线、褶线跟着袖子走，
        # 前襟那边的翻领线离袖子远，吸不回来，就此丢掉。被褶线隔开的袖子块不用锚点筛，吸回褶线后自然连成一块。
        m = m & ~lines
        for _ in range(3):
            ring = cv2.dilate(m.astype(np.uint8), K3).astype(bool) & ~m & lines
            if not ring.any():
                break
            m = m | ring
    m = fill_holes(m)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, K3)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, K3).astype(bool)
    m = keep_through(m, anchors, hand)
    m = fill_shoulder(m, person & ~dropped, shoulder, 0.3 * arm_len)
    return fill_holes(m)


# ---------- 6. 轮廓 ----------

def to_polygon(mask: np.ndarray, eps: float) -> list:
    """外扩一像素再取外轮廓（riglib.polygon 填出来才能把蒙版整个盖住），按容差简化。"""
    grown = cv2.dilate(mask.astype(np.uint8), K3)
    cnts, _ = cv2.findContours(grown, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        raise SystemExit('分割结果是空的')
    c = max(cnts, key=cv2.contourArea)
    ap = cv2.approxPolyDP(c, eps, True)
    return [(int(p[0][0]), int(p[0][1])) for p in ap]


def fmt_poly(poly: list) -> str:
    items = [f'({x}, {y})' for x, y in poly]
    lines, cur = [], '    arm_poly = ['
    for i, it in enumerate(items):
        piece = it + (', ' if i < len(items) - 1 else ']')
        if len(cur) + len(piece) > 112:
            lines.append(cur.rstrip())
            cur = '                ' + piece
        else:
            cur += piece
    lines.append(cur)
    return '\n'.join(lines)


# ---------- 预览 ----------

def _font(size: int):
    for p in ('/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/Hiragino Sans GB.ttc',
              '/Library/Fonts/Arial Unicode.ttf', 'C:/Windows/Fonts/msyh.ttc'):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def preview(rgb, k, kcf, side, box, raw, final, poly, compare=None, zoom=3):
    """手臂一带放大：橙色 = SAM 投票原始蒙版，绿线 = 最终多边形，品红 = 对照的手标多边形，红点 = 肩肘腕，青框 = 大致范围。"""
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = box
    margin = 0.15 * max(x1 - x0, y1 - y0) + 12
    cx0, cy0 = int(max(0, x0 - margin)), int(max(0, y0 - margin))
    cx1, cy1 = int(min(w, x1 + margin)), int(min(h, y1 + margin))
    img = Image.fromarray(rgb[cy0:cy1, cx0:cx1]).resize(((cx1 - cx0) * zoom, (cy1 - cy0) * zoom), Image.NEAREST).convert('RGBA')
    Z = lambda x, y: ((x - cx0 + 0.5) * zoom, (y - cy0 + 0.5) * zoom)
    over = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    raw_c = raw[cy0:cy1, cx0:cx1]
    ys, xs = np.nonzero(raw_c & ~final[cy0:cy1, cx0:cx1])
    for x, y in zip(xs, ys):
        d.rectangle([x * zoom, y * zoom, (x + 1) * zoom - 1, (y + 1) * zoom - 1], fill=(255, 140, 0, 110))
    ys, xs = np.nonzero(raw_c & final[cy0:cy1, cx0:cx1])
    for x, y in zip(xs, ys):
        d.rectangle([x * zoom, y * zoom, (x + 1) * zoom - 1, (y + 1) * zoom - 1], fill=(0, 200, 90, 60))
    img.alpha_composite(over)
    d = ImageDraw.Draw(img)
    d.rectangle([Z(x0, y0), Z(x1, y1)], outline=(0, 190, 210), width=1)
    if compare:
        d.polygon([Z(x, y) for x, y in compare], outline=(230, 0, 200), width=2)
    d.polygon([Z(x, y) for x, y in poly], outline=(0, 170, 40), width=2)
    for x, y in poly:
        px, py = Z(x, y)
        d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(0, 120, 20))
    font = _font(5 * zoom)
    for name, idx in zip(('肩', '肘', '腕'), SIDES[side]):
        px, py = Z(*k[idx])
        d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(230, 30, 30), outline='white')
        d.text((px + 6, py - 8), f'{name} {kcf[idx]:.2f}', fill=(200, 0, 0), font=font)
    return img.convert('RGB')


# ---------- 主流程 ----------

def resolve_image(arg: str) -> Path:
    p = Path(arg)
    if p.exists():
        return p
    plate = PLATES / f'{arg}.png'
    if plate.exists():
        return plate
    raise SystemExit(f'找不到 {arg}：既不是文件，build/plates-2x/ 里也没有这个 id（先跑 make_rig.py 生成底图）')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('image', help='底图 id（build/plates-2x/<id>.png）或图片路径')
    ap.add_argument('--side', default='left', choices=['left', 'right', 'both'],
                    help='画面的左右（和 make_rig.py 的 left_poly / right_poly 一致）；默认 left')
    ap.add_argument('--out', default=str(ROOT / 'build' / 'arms'), help='输出目录')
    ap.add_argument('--eps', type=float, default=1.2, help='多边形简化容差（像素）')
    ap.add_argument('--line', type=float, default=12, help='描线的强度（比周围暗多少才算线），0 = 不按描线切、不吸描线')
    ap.add_argument('--compare', default=None, help='对照的手标多边形，Python 字面量 "[(x, y), ...]"')
    args = ap.parse_args()

    path = resolve_image(args.image)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    compare = ast.literal_eval(args.compare) if args.compare else None

    t0 = time.time()
    from ultralytics import SAM, YOLO
    MODELS.mkdir(exist_ok=True)
    pose_model = YOLO(str(POSE_WEIGHTS))
    sam = SAM(str(SAM_WEIGHTS))
    print(f'模型加载 {time.time() - t0:.1f}s', file=sys.stderr)

    rgb, person = load_image(path)
    pbox, k, kcf, pconf = detect_person(pose_model, rgb, person)
    print(f'人体检测：框 {[round(v) for v in pbox]} 置信度 {pconf:.2f}', file=sys.stderr)

    sides = ['left', 'right'] if args.side == 'both' else [args.side]
    for side in sides:
        t1 = time.time()
        s, e, w = (k[i] for i in SIDES[side])
        names = dict(zip(SIDES[side], ('肩', '肘', '腕')))
        low = [f'{names[i]} {kcf[i]:.2f}' for i in SIDES[side] if kcf[i] < 0.5]
        if low:
            print(f'{side}：姿态点置信度低（{", ".join(low)}），结果要多看一眼', file=sys.stderr)
        raw, _, note = sam_vote(sam, rgb, person, k, side)
        print(f'{side}：{note}', file=sys.stderr)
        hand, note = hand_pass(sam, rgb, person, raw & person, w, arm_length(k, side))
        print(f'{side}：{note}', file=sys.stderr)
        if hand is not None:
            raw = raw | hand
        anchors = [tuple(e), tuple(w), tuple((e + w) / 2)]
        final = refine(raw, person, rgb, anchors, hand, s, chest_point(k, side), arm_length(k, side), args.line)
        poly = to_polygon(final, args.eps)
        box = arm_box(k, side, PADS[1], rgb.shape[:2])
        stem = f'{path.stem}_{side}'
        Image.fromarray((final * 255).astype(np.uint8)).save(out / f'{stem}_mask.png')
        preview(rgb, k, kcf, side, box, raw, final, poly, compare).save(out / f'{stem}.png')
        rec = dict(image=str(path), side=side, size=[rgb.shape[1], rgb.shape[0]], poly=[list(p) for p in poly],
                   shoulder=[round(float(v), 1) for v in s], elbow=[round(float(v), 1) for v in e],
                   wrist=[round(float(v), 1) for v in w], keypoint_conf=[round(float(kcf[i]), 2) for i in SIDES[side]],
                   box=[round(v, 1) for v in box], area=int(final.sum()))
        (out / f'{stem}.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'\n# {path.name} {side}：{len(poly)} 个顶点，{int(final.sum())} 像素，{time.time() - t1:.1f}s；预览 {out / (stem + ".png")}')
        print(fmt_poly(poly))
        print(f'    # 姿态点（大概位置）：肩 ({s[0]:.0f}, {s[1]:.0f})  肘 ({e[0]:.0f}, {e[1]:.0f})  腕 ({w[0]:.0f}, {w[1]:.0f})')


if __name__ == '__main__':
    main()
