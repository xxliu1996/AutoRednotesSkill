#!/usr/bin/env python3
"""把一组尺寸杂乱的配图裁成统一比例，人像按人脸位置对齐。

卡片里并排放三张人物照时，源图长宽比从 0.66 到 2.0 不等，
`size=md` 只约束宽度，于是每张的高度都不一样，名字标签参差不齐——
肉眼一看就是"随手贴的"。这个脚本把它们统一裁成同一个比例。

裁剪锚点不是几何中心：
- 检测到人脸 → 以人脸中心为锚，并向上留出头顶空间（人脸在画面偏上更像肖像）
- 没检测到（logo、奖章、示意图）→ 退回中心裁剪，并对竖图做轻微上偏

用法：
    python scripts/crop_portraits.py images/*.jpg -o images/cropped
    python scripts/crop_portraits.py images/a.jpg --ratio 1:1
    python scripts/crop_portraits.py images/logo.png --no-crop   # 只补白边成比例

`--no-crop` 适合不能裁的图（logo、图表、奖章）：不切内容，而是补透明/底色边
把画幅撑成目标比例，这样它跟被裁过的人像在栅格里仍然等高。
"""

import argparse
import os
import sys

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None

from PIL import Image

#: 人脸在成品里的理想纵向位置（0 = 顶边，1 = 底边）。
#: 0.42 比 0.5 更像人像摄影的构图，头顶留白少一点、下巴以下多一点。
FACE_ANCHOR_Y = 0.42

#: 裁剪框高度 ÷ 人脸高度。太小会把脸怼满画幅，太大等于没裁。
FACE_ZOOM = 3.4


def parse_ratio(text):
    if ':' in text:
        w, h = text.split(':', 1)
        return float(w) / float(h)
    return float(text)


def detect_face(path):
    """返回 (cx, cy, face_h) 像素坐标，检测不到返回 None。"""
    if cv2 is None:
        return None
    img = cv2.imread(path)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade_path = os.path.join(cv2.data.haarcascades,
                                'haarcascade_frontalface_default.xml')
    cascade = cv2.CascadeClassifier(cascade_path)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5,
                                     minSize=(40, 40))
    if len(faces) == 0:
        return None
    # 多张脸（合影）时取最大的那张，通常是主体
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return (x + w / 2.0, y + h / 2.0, float(h))


def crop_one(path, out_path, target_ratio, pad_mode=False, bg=None):
    im = Image.open(path)
    im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
    W, H = im.size

    if pad_mode:
        # 不裁内容，补边到目标比例
        if W / H > target_ratio:
            nw, nh = W, int(round(W / target_ratio))
        else:
            nw, nh = int(round(H * target_ratio)), H
        fill = bg or (0, 0, 0, 0)
        canvas = Image.new('RGBA', (nw, nh), fill)
        canvas.paste(im.convert('RGBA'), ((nw - W) // 2, (nh - H) // 2))
        out = canvas if (bg is None) else canvas.convert('RGB')
        out.save(out_path)
        return 'pad'

    face = detect_face(path)

    if face is not None:
        cx, cy, fh = face
        # 以人脸高度反推裁剪框，再夹回图像范围内
        box_h = min(H, fh * FACE_ZOOM)
        box_w = box_h * target_ratio
        if box_w > W:
            box_w = W
            box_h = box_w / target_ratio
        top = cy - box_h * FACE_ANCHOR_Y
        left = cx - box_w / 2.0
        how = 'face'
    else:
        # 没有脸：取能放进原图的最大目标比例框
        if W / H > target_ratio:
            box_h, box_w = H, H * target_ratio
        else:
            box_w, box_h = W, W / target_ratio
        left = (W - box_w) / 2.0
        # 竖图轻微上偏，避免把人/主体的头切掉；横图保持居中
        top = (H - box_h) * (0.35 if H > W else 0.5)
        how = 'center'

    left = max(0, min(left, W - box_w))
    top = max(0, min(top, H - box_h))
    im.crop((int(left), int(top), int(left + box_w), int(top + box_h))).save(out_path)
    return how


def main():
    ap = argparse.ArgumentParser(description='把配图统一裁成同一比例（人像对齐人脸）')
    ap.add_argument('images', nargs='+')
    ap.add_argument('-o', '--out', default=None,
                    help='输出目录，默认原地覆盖前先写到 <dir>/cropped')
    ap.add_argument('--ratio', default='3:4', help='目标宽高比，默认 3:4')
    ap.add_argument('--no-crop', action='store_true',
                    help='不裁内容，改为补边到目标比例（logo / 图表 / 奖章用）')
    ap.add_argument('--bg', default=None,
                    help='补边颜色，如 "#DEDCCD"；不给就补透明')
    args = ap.parse_args()

    ratio = parse_ratio(args.ratio)
    bg = None
    if args.bg:
        h = args.bg.lstrip('#')
        bg = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)

    if cv2 is None and not args.no_crop:
        print('⚠️  没装 opencv-python-headless，人脸检测不可用，全部退回中心裁剪')

    out_dir = args.out or os.path.join(os.path.dirname(args.images[0]) or '.', 'cropped')
    os.makedirs(out_dir, exist_ok=True)

    for path in args.images:
        name = os.path.basename(path)
        out_path = os.path.join(out_dir, name)
        try:
            how = crop_one(path, out_path, ratio, args.no_crop, bg)
        except Exception as exc:                       # noqa: BLE001
            print(f'  ❌ {name}: {exc}')
            continue
        w, h = Image.open(out_path).size
        tag = {'face': '🙂 对齐人脸', 'center': '◻️ 居中裁剪', 'pad': '⬜ 补边'}[how]
        print(f'  ✅ {name:28s} → {w}x{h}  {tag}')

    print(f'\n✨ 完成，输出在 {out_dir}')


if __name__ == '__main__':
    sys.exit(main())
