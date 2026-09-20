#!/usr/bin/env python3
"""主题预览 —— 出一张封面 + 一张正文卡，用来跟样图并排比对。

风格提取是个来回调的过程：看样图 → 写 token → 出预览 → 对比 → 改 token。
完整跑一遍 content.md 要出 6 张图、几十秒，太慢；这里只出 2 张，秒级反馈。

用法:
    python scripts/preview_theme.py my-style
    python scripts/preview_theme.py my-style --content demos/content.md --card 2
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import themes as theme_registry
from render_xhs import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    configure_materials,
    generate_card_html,
    generate_cover_html,
    parse_markdown_file,
    render_html_to_image,
    split_content_by_separator,
)

ASSETS_DIR = theme_registry.ASSETS_DIR


async def preview(theme: str, content: Path, card_index: int, out_dir: Path, dpr: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    configure_materials(str(content), None)

    data = parse_markdown_file(str(content))
    cards = split_content_by_separator(data["body"])
    if not cards:
        raise SystemExit(f"❌ {content} 里没有正文卡片")
    idx = min(max(card_index, 1), len(cards)) - 1

    cover_html = generate_cover_html(data["metadata"], theme, DEFAULT_WIDTH, DEFAULT_HEIGHT)
    await render_html_to_image(
        cover_html, str(out_dir / f"preview-{theme}-cover.png"),
        DEFAULT_WIDTH, DEFAULT_HEIGHT, "separator", DEFAULT_HEIGHT, dpr,
    )

    card_html = generate_card_html(
        cards[idx], theme, idx + 1, len(cards), DEFAULT_WIDTH, DEFAULT_HEIGHT, "separator"
    )
    await render_html_to_image(
        card_html, str(out_dir / f"preview-{theme}-card.png"),
        DEFAULT_WIDTH, DEFAULT_HEIGHT, "separator", DEFAULT_HEIGHT, dpr,
    )

    print(f"\n✨ 预览已生成，与样图并排比对: {out_dir}")


def main() -> None:
    ap = argparse.ArgumentParser(description="渲染单个主题的封面 + 正文卡预览")
    ap.add_argument("theme", help="主题名")
    ap.add_argument("--content", default=str(ASSETS_DIR / "example.md"), help="用于预览的 md")
    ap.add_argument("--card", type=int, default=1, help="预览第几张正文卡（默认 1）")
    ap.add_argument("--output-dir", "-o", default="preview", help="输出目录（默认 ./preview）")
    ap.add_argument("--dpr", type=int, default=1, help="设备像素比（预览默认 1，出图快）")
    args = ap.parse_args()

    available = theme_registry.discover_themes()
    if args.theme not in available:
        raise SystemExit(f"❌ 未知主题 {args.theme}\n   可用: {', '.join(available)}")

    asyncio.run(preview(args.theme, Path(args.content), args.card, Path(args.output_dir), args.dpr))


if __name__ == "__main__":
    main()
