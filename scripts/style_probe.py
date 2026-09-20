#!/usr/bin/env python3
"""风格探针 —— 从图片里量出客观数据，供我做判断。

分工：**机器负责测量，我负责判断。**

我看图能判断"这是编辑风还是粗野主义"，但说不准背景到底是 #171F30 还是 #1A2033，
也数不清强调色占了画面的 3% 还是 11%。反过来，脚本能精确取色，但分不清
一个颜色是"背景"还是"一个分类项"。硬把判断写进代码，换一张参考图就失效。

两种用法：

  单图 —— 提取候选色板与明暗结构，作为写 token 的起点
      python scripts/style_probe.py sample.png

  双图 —— 把预览图和样图并排量，给出可迭代的差距信号
      python scripts/style_probe.py sample.png preview.png

第二种是关键：它把"像不像"从主观争论变成可以逐轮收敛的数字。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:
    print("缺少依赖，请运行: bash scripts/check_deps.sh", file=sys.stderr)
    sys.exit(1)

MAX_SIDE = 400  # 缩图再量，够准且快


def _load(path: Path) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return np.asarray(img, dtype=np.float64).reshape(-1, 3)


def _hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(int(round(c)) for c in rgb))


def _luma(rgb) -> float:
    """感知亮度 0-255（ITU-R BT.601）。"""
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def _saturation(rgb) -> np.ndarray:
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    return np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)


def kmeans(pixels: np.ndarray, k: int, iters: int = 30, seed: int = 0):
    """朴素 k-means。不引 sklearn —— 这点规模不值得多一个重依赖。"""
    rng = np.random.default_rng(seed)
    # k-means++ 式初始化：第一个随机，其余按距离平方加权挑，避免初值挤在一起
    centers = [pixels[rng.integers(len(pixels))]]
    for _ in range(k - 1):
        d2 = np.min(((pixels[:, None, :] - np.array(centers)[None, :, :]) ** 2).sum(-1), axis=1)
        total = d2.sum()
        probs = d2 / total if total > 0 else None
        centers.append(pixels[rng.choice(len(pixels), p=probs)])
    centers = np.array(centers)

    labels = np.zeros(len(pixels), dtype=int)
    for _ in range(iters):
        dist = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        new_labels = dist.argmin(axis=1)
        if (new_labels == labels).all():
            break
        labels = new_labels
        for i in range(k):
            members = pixels[labels == i]
            if len(members):
                centers[i] = members.mean(axis=0)
    counts = np.bincount(labels, minlength=k)
    return centers, counts / counts.sum()


def profile(path: Path, k: int) -> dict:
    px = _load(path)
    centers, weights = kmeans(px, k)
    order = np.argsort(-weights)
    centers, weights = centers[order], weights[order]

    lum = _luma(px)
    sat = _saturation(px)

    return {
        "path": path,
        "colors": [(_hex(c), float(w)) for c, w in zip(centers, weights)],
        "centers": centers,
        "weights": weights,
        "mean_luma": float(lum.mean()),
        "dark_ratio": float((lum < 110).mean()),
        "contrast": float(lum.std()),
        "mean_sat": float(sat.mean()),
        "vivid_ratio": float(((sat > 0.45) & (lum > 40)).mean()),
    }


def report(p: dict, title: str) -> None:
    print(f"\n=== {title}: {p['path'].name} ===")
    print("主色（按画面占比）：")
    for hexv, w in p["colors"]:
        lum = _luma(np.array([int(hexv[i:i + 2], 16) for i in (1, 3, 5)], dtype=float))
        role = "偏暗" if lum < 90 else ("偏亮" if lum > 180 else "中调")
        bar = "█" * max(1, round(w * 40))
        print(f"  {hexv}  {w*100:5.1f}%  {role:<4} {bar}")
    print(f"平均亮度 {p['mean_luma']:6.1f}/255   暗部占比 {p['dark_ratio']*100:5.1f}%")
    print(f"明暗对比 {p['contrast']:6.1f}       平均饱和 {p['mean_sat']:.3f}")
    print(f"高饱和色块占比 {p['vivid_ratio']*100:5.1f}%  ← 这个数高通常意味着分类配色")


def nearest_gap(a: dict, b: dict) -> float:
    """把 a 的每个主色映射到 b 里最近的色，按占比加权求平均色差。"""
    diffs = []
    for center, w in zip(a["centers"], a["weights"]):
        d = np.sqrt(((b["centers"] - center) ** 2).sum(axis=1)).min()
        diffs.append(d * w)
    return float(sum(diffs))


def compare(sample: dict, preview: dict) -> None:
    print("\n" + "=" * 52)
    print("差距（左=样图，右=预览）")
    print("=" * 52)

    rows = [
        ("平均亮度", sample["mean_luma"], preview["mean_luma"], 18, "整体明暗走向"),
        ("明暗对比", sample["contrast"], preview["contrast"], 15, "层次是否够"),
        ("暗部占比", sample["dark_ratio"] * 100, preview["dark_ratio"] * 100, 12, "深底还是浅底"),
        ("平均饱和", sample["mean_sat"] * 100, preview["mean_sat"] * 100, 8, "颜色浓淡"),
        ("高饱和占比", sample["vivid_ratio"] * 100, preview["vivid_ratio"] * 100, 6, "色块用量"),
    ]
    for name, a, b, tol, why in rows:
        delta = b - a
        flag = "✅" if abs(delta) <= tol else ("⚠️" if abs(delta) <= tol * 2 else "❌")
        print(f"  {name:<10} {a:7.1f} → {b:7.1f}  ({delta:+7.1f})  {flag}  {why}")

    gap = nearest_gap(sample, preview)
    flag = "✅" if gap < 30 else ("⚠️" if gap < 60 else "❌")
    print(f"  {'色板距离':<10} {gap:7.1f}                        {flag}  样图主色在预览里能否找到对应")

    print("\n怎么读这份报告：")
    print("  平均亮度差太多 → 改 bg_card / ink 的明暗走向")
    print("  明暗对比偏低   → 拉开 ink 与 surface 的差，或加大 h1 字号")
    print("  高饱和占比偏低 → 样图多半用了分类配色，检查 palette 是否填了、版式是否加了 .palette")
    print("  色板距离大     → 主色取错了，回到样图重新取")
    print("\n这些是信号不是判决。数字全绿但观感不对，以观感为准。")


def main() -> None:
    ap = argparse.ArgumentParser(description="从图片量出风格数据；给两张图则对比")
    ap.add_argument("sample", help="样图")
    ap.add_argument("preview", nargs="?", help="预览图（给了就做对比）")
    ap.add_argument("-k", type=int, default=6, help="提取几个主色（默认 6）")
    args = ap.parse_args()

    sample_path = Path(args.sample)
    if not sample_path.is_file():
        raise SystemExit(f"❌ 找不到: {sample_path}")

    s = profile(sample_path, args.k)
    report(s, "样图")

    if args.preview:
        preview_path = Path(args.preview)
        if not preview_path.is_file():
            raise SystemExit(f"❌ 找不到: {preview_path}")
        p = profile(preview_path, args.k)
        report(p, "预览")
        compare(s, p)
    else:
        print("\n下一步：把上面的主色分派到 token —— 占比最大且低饱和的通常是背景，")
        print("      与背景明暗相反的是 ink，剩下高饱和的若彼此并列就是 palette。")
        print("      填好 token 后跑 preview_theme.py，再用两张图模式量差距。")


if __name__ == "__main__":
    main()
