#!/usr/bin/env python3
"""风格 token → 主题 CSS。

分工：**视觉判断由 Claude 做，代码只做确定性转换。**

    样图.png
      │  Claude 用 Read 看图，按 references/style-extraction.md 的清单判断
      ▼
    assets/themes/<slug>.json          风格 token
      │  python scripts/build_theme.py assets/themes/<slug>.json
      ▼
    assets/themes/<slug>.css           从 _template.css.tpl 生成
      │  python scripts/preview_theme.py <slug>
      ▼
    预览图 → 与样图对比 → 不满意就改 token 重跑

token 只有 label / bg_card / title_gradient / ink / accent 是必填，
其余全部由这里从必填项推导出合理默认值 —— 让「看图写 token」这一步尽量轻。

用法:
    python scripts/build_theme.py assets/themes/my-style.json
    python scripts/build_theme.py --new my-style        # 生成一份带注释的 token 骨架
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import themes as theme_registry

THEMES_DIR = theme_registry.THEMES_DIR
TEMPLATE_PATH = THEMES_DIR / "_template.css.tpl"

REQUIRED = ("label", "bg_card", "title_gradient", "ink", "accent")

SKELETON = {
    "label": "风格中文名",
    "_note": "必填: label / bg_card / title_gradient / ink / accent；其余留空则自动推导",
    "bg_card": "linear-gradient(135deg, #FFF8F0 0%, #FFE0C2 100%)",
    "bg_cover": "",
    "title_gradient": "linear-gradient(180deg, #2B1D14 0%, #8A5A3C 100%)",
    "ink": "#2B1D14",
    "accent": "#FF6B57",
    "accent_2": "",
    "surface": "",
    "cover_surface": "",
    "cover_ink": "",
    "material_accent": "",
    "radius": 20,
    "border": "none",
    "shadow": "",
    "font_title": "",
    "font_body": "",
    "font_license_note": "",
}


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", value.strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgba(value: str, alpha: float, fallback: str) -> str:
    rgb = _hex_to_rgb(value)
    if rgb is None:
        return fallback
    return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})"


def _mix_toward(value: str, target: tuple[int, int, int], ratio: float) -> str:
    """把颜色朝 target 方向拉 ratio，用来推导「更浅/更深」的同族色。"""
    rgb = _hex_to_rgb(value)
    if rgb is None:
        return value
    mixed = tuple(round(c + (t - c) * ratio) for c, t in zip(rgb, target))
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def _is_dark(value: str) -> bool:
    rgb = _hex_to_rgb(value)
    if rgb is None:
        return False
    # 感知亮度（ITU-R BT.601），用于判断正文色是深是浅 → 决定代码块底色走向
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) < 128


def resolve(tokens: dict) -> dict:
    """补全 token：必填项之外全部推导，已给的值一律不覆盖。"""
    missing = [k for k in REQUIRED if not tokens.get(k)]
    if missing:
        raise SystemExit(f"❌ token 缺少必填项: {missing}")

    ink = tokens["ink"]
    accent = tokens["accent"]
    dark_ink = _is_dark(ink)

    d = dict(tokens)
    d.setdefault("bg_cover", d["bg_card"])
    # 卡片内面板：深色正文 → 近白底；浅色正文（深色主题）→ 近黑底
    d.setdefault("surface", "rgba(255, 255, 255, 0.95)" if dark_ink else "rgba(20, 20, 24, 0.94)")
    d.setdefault("surface_ink", "#FFFFFF" if dark_ink else "#101014")
    d.setdefault("cover_surface", "#F3F3F3" if dark_ink else "#16161A")
    d.setdefault("cover_ink", ink)
    d.setdefault("accent_2", _mix_toward(accent, (0, 0, 0) if dark_ink else (255, 255, 255), 0.25))
    d.setdefault("ink_strong", _mix_toward(ink, (0, 0, 0) if dark_ink else (255, 255, 255), 0.2))
    d.setdefault("material_accent", accent)

    d.setdefault("radius", 20)
    d.setdefault("border", "none")
    d.setdefault("shadow", "0 8px 32px rgba(0, 0, 0, 0.1)")
    d.setdefault("quote_radius", max(0, int(d["radius"]) - 8))
    d.setdefault("quote_bg", _rgba(accent, 0.08, "rgba(0,0,0,0.05)"))
    d.setdefault("rule_color", _rgba(ink, 0.15, "rgba(0,0,0,0.15)"))
    d.setdefault("code_bg", _rgba(accent, 0.12, "rgba(0,0,0,0.06)"))
    d.setdefault("code_ink", accent)
    d.setdefault("pre_bg", "#1F2430" if dark_ink else "rgba(255,255,255,0.06)")
    d.setdefault("pre_ink", "#E6E6E6")
    d.setdefault("tag_bg", _rgba(accent, 0.14, "rgba(0,0,0,0.08)"))
    d.setdefault("tag_ink", accent)

    # 字号沿用内置主题的量级（1080 画布、正文可用宽约 860px）
    d.setdefault("fs_body", 42)
    d.setdefault("fs_h1", 72)
    d.setdefault("fs_h2", 56)
    d.setdefault("fs_h3", 48)
    d.setdefault("fs_code", 34)
    d.setdefault("fs_tag", 30)
    d.setdefault("line_height", 1.8)
    d.setdefault("weight_title", 700)
    d.setdefault("weight_body", 400)
    d.setdefault("h1_decoration", "")
    # flex-start = 顶对齐（内置主题的观感）；center = 垂直居中，内容偏少时不留大片空白
    d.setdefault("content_align", "flex-start")

    default_font = (
        "'Noto Sans SC', 'Source Han Sans CN', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    )
    d.setdefault("font_title", default_font)
    d.setdefault("font_body", default_font)
    d.setdefault("font_mono", "'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace")
    return d


def build(token_path: Path) -> Path:
    tokens = json.loads(token_path.read_text(encoding="utf-8"))
    slug = token_path.stem
    resolved = resolve(tokens)
    resolved["slug"] = slug

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    try:
        css = template.format(**resolved)
    except KeyError as exc:
        raise SystemExit(f"❌ 模板需要的 token 缺失: {exc}") from exc

    out = THEMES_DIR / f"{slug}.css"
    out.write_text(css, encoding="utf-8")

    # token 文件里只保留人写的内容，推导值不回写 —— 保持「必填项少」的手感
    print(f"✅ 已生成 {out}")
    if resolved.get("font_license_note"):
        print(f"⚠️  字体授权提醒: {resolved['font_license_note']}")
    print(f"   预览: python scripts/preview_theme.py {slug}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="风格 token → 主题 CSS")
    ap.add_argument("token_file", nargs="?", help="assets/themes/<slug>.json")
    ap.add_argument("--new", metavar="SLUG", help="生成一份 token 骨架供填写")
    args = ap.parse_args()

    if args.new:
        path = THEMES_DIR / f"{args.new}.json"
        if path.exists():
            raise SystemExit(f"❌ 已存在: {path}")
        path.write_text(json.dumps(SKELETON, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✅ 已生成骨架 {path}")
        return

    if not args.token_file:
        ap.error("需要 token 文件路径，或用 --new SLUG 生成骨架")

    token_path = Path(args.token_file)
    if not token_path.is_file():
        raise SystemExit(f"❌ 找不到 token 文件: {token_path}")
    build(token_path)


if __name__ == "__main__":
    main()
