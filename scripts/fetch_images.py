#!/usr/bin/env python3
"""配图检索 —— 从图库搜候选图，我来挑。

分工同风格提取：**机器负责抓，我负责判断。**

图片切不切题是判断题。搜「历史」可能返回古籍、博物馆、老照片、罗马废墟 ——
脚本按相关度排序，但排第一的未必配得上你那段文案。所以这里只负责：
把候选抓下来、拼成一张联系表、记好出处，剩下的我看图决定。

用法：
    python scripts/fetch_images.py "tank military" -o ./assets
    python scripts/fetch_images.py "bull market finance" -o ./assets --type illustration

产物：
    <out>/candidates/<slug>-1.jpg …          候选图
    <out>/candidates/<slug>-sheet.png        联系表（带编号，一张图看全部）
    <out>/candidates/MANIFEST.md             出处与授权记录

API key：环境变量 PIXABAY_API_KEY，或 skill 目录下的 .pixabay_key 文件。
免费申请：https://pixabay.com/api/docs/（登录后页面顶部显示自己的 key）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional

SKILL_DIR = Path(__file__).resolve().parent.parent
API_URL = "https://pixabay.com/api/"

#: 联系表每张缩略图的宽度
THUMB_W = 320


def load_key() -> str:
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if key:
        return key
    key_file = SKILL_DIR / ".pixabay_key"
    if key_file.is_file():
        return key_file.read_text(encoding="utf-8").strip()
    raise SystemExit(
        "❌ 缺少 Pixabay API key。\n"
        "   1. 注册 https://pixabay.com/accounts/register/\n"
        "   2. 登录后在 https://pixabay.com/api/docs/ 页面顶部复制你的 key\n"
        "   3. 二选一：\n"
        f"      echo '你的key' > {SKILL_DIR / '.pixabay_key'}\n"
        "      或 export PIXABAY_API_KEY=你的key"
    )


def slugify(text: str) -> str:
    s = re.sub(r"[^\w一-龥]+", "-", text.strip().lower())
    return s.strip("-")[:40] or "img"


def search(key: str, query: str, count: int, image_type: str,
           orientation: str, min_width: int, lang: str, order: str) -> List[dict]:
    params = {
        "key": key,
        "q": query,
        # 多要一些再筛：相关度排序前几名常有重复构图或带水印文字的
        "per_page": max(3, min(200, count * 3)),
        "image_type": image_type,
        "orientation": orientation,
        "min_width": min_width,
        "safesearch": "true",
        "order": order,
        "lang": lang,
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:200]
        raise SystemExit(f"❌ Pixabay 返回 {exc.code}: {body}")
    except Exception as exc:
        raise SystemExit(f"❌ 请求失败: {exc}")

    hits = data.get("hits", [])
    if not hits:
        raise SystemExit(f"❌ 没搜到结果: {query!r}\n   换个关键词，或把 --type 放宽到 all")

    # 同一作者的多张图往往是同一组，取前几张会得到几乎一样的构图 —— 每人限一张
    seen_users, picked = set(), []
    for h in hits:
        if h.get("user") in seen_users:
            continue
        seen_users.add(h.get("user"))
        picked.append(h)
        if len(picked) >= count:
            break
    return picked or hits[:count]


def download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "xhs-card-studio/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as exc:
        print(f"  ⚠️  下载失败 {url}: {exc}", file=sys.stderr)
        return False


def visible_luma(path: Path) -> Optional[float]:
    """素材「可见部分」的平均亮度（忽略透明像素）。

    图库的 vector 素材大量是**黑色线稿**（为浅底设计）。放在深色主题上会直接消失，
    而联系表看着"有内容"—— 挑完才发现出图是一片空。这个数让挑选前就能判断：
    深色主题要 >90，浅色主题要 <170。
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return None
    try:
        a = np.asarray(Image.open(path).convert("RGBA"))
    except Exception:
        return None
    vis = a[..., 3] > 128
    if not vis.any():
        return None
    lum = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    return float(lum[vis].mean())


def contact_sheet(paths: List[Path], out: Path, cols: int = 3) -> Optional[Path]:
    """把候选图拼成一张带编号的联系表 —— 我读一张图就能看全部，省掉 N 次 Read。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    # 联系表底色。透明图必须正确合成到这个色上 —— 直接 convert("RGB") 会把
    # 透明区变成黑色并带出条纹伪影，看不出哪些图是去背的、去得干不干净。
    BG = (24, 24, 28)

    thumbs = []
    for p in paths:
        try:
            im = Image.open(p)
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                plate = Image.new("RGBA", im.size, BG + (255,))
                plate.alpha_composite(im)
                im = plate.convert("RGB")
            else:
                im = im.convert("RGB")
            ratio = THUMB_W / im.width
            thumbs.append(im.resize((THUMB_W, max(1, round(im.height * ratio)))))
        except Exception:
            thumbs.append(Image.new("RGB", (THUMB_W, THUMB_W // 2), (60, 60, 60)))

    if not thumbs:
        return None

    rows = (len(thumbs) + cols - 1) // cols
    row_h = [max(t.height for t in thumbs[r * cols:(r + 1) * cols]) for r in range(rows)]
    pad, label_h = 12, 34
    sheet = Image.new(
        "RGB",
        (cols * THUMB_W + (cols + 1) * pad,
         sum(row_h) + rows * (label_h + pad) + pad),
        (24, 24, 28),
    )
    draw = ImageDraw.Draw(sheet)

    y = pad
    for r in range(rows):
        x = pad
        for c in range(cols):
            i = r * cols + c
            if i >= len(thumbs):
                break
            draw.text((x + 4, y + 8), f"[{i + 1}]  {paths[i].name}", fill=(255, 211, 78))
            sheet.paste(thumbs[i], (x, y + label_h))
            x += THUMB_W + pad
        y += row_h[r] + label_h + pad

    sheet.save(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="从 Pixabay 搜配图候选")
    ap.add_argument("query", help="搜索关键词（英文命中率明显更高）")
    ap.add_argument("-o", "--out", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("-n", "--count", type=int, default=6, help="候选数量（默认 6）")
    ap.add_argument("--type", default="all",
                    choices=["all", "photo", "illustration", "vector"],
                    help="图片类型。剪影/插画类用 illustration 或 vector")
    ap.add_argument("--orientation", default="all",
                    choices=["all", "horizontal", "vertical"])
    ap.add_argument("--min-width", type=int, default=1200,
                    help="最小宽度（默认 1200，够 xl 档用）")
    ap.add_argument("--lang", default="en", help="搜索语言（默认 en）")
    ap.add_argument("--order", default="popular", choices=["popular", "latest"])
    args = ap.parse_args()

    key = load_key()
    slug = slugify(args.query)
    cand_dir = Path(args.out) / "candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)

    print(f"🔎 搜索 {args.query!r}（type={args.type}, 最小宽度 {args.min_width}）")
    hits = search(key, args.query, args.count, args.type,
                  args.orientation, args.min_width, args.lang, args.order)

    saved, rows = [], []
    for i, h in enumerate(hits, 1):
        url = h.get("largeImageURL") or h.get("webformatURL")
        if not url:
            continue
        ext = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
        dest = cand_dir / f"{slug}-{i}{ext}"
        if not download(url, dest):
            continue
        saved.append(dest)
        lum = visible_luma(dest)
        rows.append({
            "n": i, "file": dest.name,
            "size": f"{h.get('imageWidth')}x{h.get('imageHeight')}",
            "user": h.get("user", "?"), "page": h.get("pageURL", ""),
            "tags": h.get("tags", ""), "luma": lum,
        })
        note = ""
        if lum is not None:
            note = f"  亮度{lum:5.1f}"
            if lum < 90:
                note += " ← 深色主题上会糊"
            elif lum > 200:
                note += " ← 浅色主题上会糊"
        print(f"  [{i}] {dest.name}  {h.get('imageWidth')}x{h.get('imageHeight')}  by {h.get('user')}{note}")

    if not saved:
        raise SystemExit("❌ 一张都没下载成功")

    manifest = cand_dir / "MANIFEST.md"
    lines = [f"# 配图候选：{args.query}", "",
             "来源 Pixabay（Content License：可免费商用，无需署名；",
             "不得原样倒卖，不得以暗示背书的方式使用可识别的人物或品牌）。", "",
             "「亮度」是可见部分的平均亮度：深色主题要 >90，浅色主题要 <170。", "",
             "| # | 文件 | 尺寸 | 亮度 | 作者 | 标签 | 出处 |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        lum = f"{r['luma']:.0f}" if r["luma"] is not None else "?"
        lines.append(f"| {r['n']} | `{r['file']}` | {r['size']} | {lum} | {r['user']} | "
                     f"{r['tags']} | {r['page']} |")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sheet = contact_sheet(saved, cand_dir / f"{slug}-sheet.png")

    print(f"\n✅ {len(saved)} 张候选 → {cand_dir}")
    print(f"   出处记录 {manifest}")
    if sheet:
        print(f"   联系表   {sheet}  ← 先看这张挑编号")
    print("\n挑好后把选中的图移到素材目录，在 content.md 里引用：")
    print(f'   ![size=xl align=center]({slug}-1.jpg)')


if __name__ == "__main__":
    main()
