#!/usr/bin/env python3
"""素材内联 —— 让 md 里的 SVG / 图片真的能出现在卡片上。

为什么必须内联而不能靠相对路径：render_html_to_image 把 HTML 写进
tempfile.NamedTemporaryFile 再 page.goto('file:///var/folders/…/tmpXXXX.html')，
所以 <img src="materials/icon.svg"> 会相对那个临时目录解析 —— 必然 404。
<base href> 能救 <img>，但救不了「让 SVG 跟着主题变色」这件事。

内联换来的好处：SVG 变成页面里真实的 <svg> 元素，fill="currentColor" 的路径
自动继承主题色，同一组素材换主题就换色，不用维护多套配色的 SVG 文件。

md 侧保持原生语法，指令写在 alt 文本里：
    ![](materials/icon.svg)                   行内，跟随正文流
    ![size=lg align=right](materials/x.svg)   → .material--lg .material--right
    ![hero](materials/banner.svg)             卡片顶部通栏插图
"""
from __future__ import annotations

import base64
import mimetypes
import re
import sys
from html import escape
from pathlib import Path
from typing import Dict, List, Tuple

#: alt 文本里可用的指令。未识别的 token 会被当作普通 alt 文字保留。
SIZES = {"sm", "md", "lg", "xl", "hero"}
ALIGNS = {"left", "center", "right"}

_IMG_RE = re.compile(r"<img\b([^>]*?)/?>", re.IGNORECASE)
_ATTR_RE = re.compile(r"""(\w[\w-]*)\s*=\s*["']([^"']*)["']""")

# SVG 清洗：脚本、外链、事件处理器一律剔除。素材可能来自网上随手下载的文件，
# 内联等于把它塞进渲染页面，不清洗就是任意脚本执行。
_SVG_SCRIPT_RE = re.compile(r"<script\b.*?</script\s*>|<foreignObject\b.*?</foreignObject\s*>", re.DOTALL | re.IGNORECASE)
_SVG_ON_ATTR_RE = re.compile(r"\son\w+\s*=\s*(?:\"[^\"]*\"|'[^']*')", re.IGNORECASE)
_SVG_HREF_RE = re.compile(r"\s(?:xlink:href|href)\s*=\s*[\"'](?!#)[^\"']*[\"']", re.IGNORECASE)
_SVG_OPEN_RE = re.compile(r"<svg\b([^>]*)>", re.IGNORECASE)
_SVG_DIM_ATTR_RE = re.compile(r'\s(?:width|height)\s*=\s*(?:"[^"]*"|\'[^\']*\')', re.IGNORECASE)

RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}


class MaterialReport:
    """收集内联过程中的问题，供 --dry-run 与渲染时的警告使用。"""

    def __init__(self) -> None:
        self.resolved: List[str] = []
        self.missing: List[str] = []
        self.errors: List[Tuple[str, str]] = []

    @property
    def ok(self) -> bool:
        return not self.missing and not self.errors

    def merge(self, other: "MaterialReport") -> None:
        self.resolved.extend(other.resolved)
        self.missing.extend(other.missing)
        self.errors.extend(other.errors)


def parse_directives(alt: str) -> Tuple[List[str], str]:
    """从 alt 文本中拆出样式指令，返回 (class 列表, 剩余 alt 文字)。"""
    classes: List[str] = []
    leftover: List[str] = []
    for token in alt.split():
        key, _, value = token.partition("=")
        key, value = key.lower(), value.lower()
        if key == "size" and value in SIZES:
            classes.append(f"material--{value}")
        elif key == "align" and value in ALIGNS:
            classes.append(f"material--{value}")
        elif key in SIZES:
            classes.append(f"material--{key}")
        elif key in ALIGNS:
            classes.append(f"material--{key}")
        elif key == "recolor":
            # recolor / recolor=fill → 只换填充；recolor=stroke → 只换描边；
            # recolor=all → 两者都换。见 assets/materials.css 里为何要分档。
            variant = value if value in ("fill", "stroke", "all") else "fill"
            classes.append("material--recolor" if variant == "fill" else f"material--recolor-{variant}")
        else:
            leftover.append(token)
    if not any(c.startswith("material--") and c.split("--")[1] in SIZES for c in classes):
        classes.append("material--md")
    return classes, " ".join(leftover)


def sanitize_svg(svg_text: str) -> str:
    """把任意 SVG 文件收拾成可安全内联、且尺寸由 CSS 控制的 <svg> 片段。"""
    svg = _SVG_SCRIPT_RE.sub("", svg_text)
    svg = _SVG_ON_ATTR_RE.sub("", svg)
    svg = _SVG_HREF_RE.sub("", svg)

    match = _SVG_OPEN_RE.search(svg)
    if not match:
        raise ValueError("文件里找不到 <svg> 根元素")

    attrs = match.group(1)
    has_viewbox = "viewbox" in attrs.lower()
    if not has_viewbox:
        # 没有 viewBox 就无法等比缩放，用原始 width/height 补一个
        dims = dict((k.lower(), v) for k, v in _ATTR_RE.findall(attrs))
        w, h = dims.get("width", ""), dims.get("height", "")
        num = re.compile(r"^([\d.]+)")
        mw, mh = num.match(w or ""), num.match(h or "")
        if mw and mh:
            attrs += f' viewBox="0 0 {mw.group(1)} {mh.group(1)}"'

    # 去掉写死的 width/height，改由 .material CSS 控制尺寸
    attrs = _SVG_DIM_ATTR_RE.sub("", attrs)
    if "preserveaspectratio" not in attrs.lower():
        attrs += ' preserveAspectRatio="xMidYMid meet"'
    attrs += ' focusable="false" aria-hidden="true"'

    # 丢弃 <svg> 之前的一切 —— xml 声明、DOCTYPE、注释都在这里，逐一枚举它们
    # 容易漏（曾漏掉「xml 声明 + DOCTYPE」同时存在的情况）。SVG 文件里根元素之前
    # 不可能有需要保留的内容。
    return f"<svg{attrs}>" + svg[match.end():]


#: 各尺寸档位对应的 CSS 显示宽度（px），与 assets/materials.css 里的值保持一致。
#: hero 取正文可用宽度（1080 画布减去内外边距）。
DISPLAY_WIDTH = {
    "sm": 120, "md": 220, "lg": 380, "xl": 560, "hero": 1000,
}

#: 素材实际需要的像素 = 显示宽度 × dpr。dpr 默认 2，留一点余量取 2.2。
DPR_HEADROOM = 2.2

#: 兜底上限：拿不到尺寸信息时按满宽算
MAX_RASTER_PX = 2000

#: 超过这个体积才值得重新编码（小图重编码可能反而变大）
RECODE_THRESHOLD_BYTES = 200 * 1024


def _target_px(classes: List[str]) -> int:
    """从 size 指令推出这张素材实际需要多少像素宽。

    相机直出图常有 1920px+，而卡片里可能只占 380px 宽 —— 按显示尺寸压缩能省掉
    大部分体积，且完全看不出差别。尺寸信息就在 alt 指令里，不用额外配置。
    """
    for cls in classes:
        key = cls.replace("material--", "")
        if key in DISPLAY_WIDTH:
            return min(MAX_RASTER_PX, round(DISPLAY_WIDTH[key] * DPR_HEADROOM))
    return MAX_RASTER_PX


def _data_uri(path: Path, target_px: int = MAX_RASTER_PX) -> str:
    """位图 → data URI。大图先缩放、必要时转 JPEG 再编码。

    相机直出的实拍图常有 1920px+、数 MB，而卡片里往往只占几百像素宽。
    base64 会再放大约 33%，几张图就能把单页 HTML 顶到 4MB 以上。
    """
    raw = path.read_bytes()
    mime, _ = mimetypes.guess_type(path.name)

    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and len(raw) > RECODE_THRESHOLD_BYTES:
        try:
            from io import BytesIO

            from PIL import Image
        except ImportError:
            pass  # 没装 Pillow 就原样内联，功能不受影响
        else:
            try:
                img = Image.open(BytesIO(raw))
                if img.width > target_px:
                    ratio = target_px / img.width
                    img = img.resize(
                        (target_px, max(1, round(img.height * ratio))), Image.LANCZOS
                    )

                buf = BytesIO()
                has_alpha = img.mode in ("RGBA", "LA") or "transparency" in img.info
                if has_alpha:
                    # 有透明通道就必须留 PNG，转 JPEG 会把透明区变成黑块
                    img.save(buf, format="PNG", optimize=True)
                    new_mime = "image/png"
                else:
                    img.convert("RGB").save(buf, format="JPEG", quality=88, optimize=True)
                    new_mime = "image/jpeg"

                if buf.tell() < len(raw):
                    raw, mime = buf.getvalue(), new_mime
            except Exception:
                pass  # 解码失败就用原始字节，不因为优化而丢素材

    payload = base64.b64encode(raw).decode("ascii")
    return f"data:{mime or 'application/octet-stream'};base64,{payload}"


def _resolve(src: str, base_dir: Path, md_dir: Path) -> Path | None:
    """素材路径解析顺序：--materials-dir → md 文件所在目录 → 原样路径。"""
    if re.match(r"^(?:https?:|data:)", src, re.IGNORECASE):
        return None
    candidate = Path(src)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    for root in (base_dir, md_dir):
        probe = (root / candidate).resolve()
        if probe.is_file():
            return probe
    return None


def _placeholder(src: str) -> str:
    """素材缺失时渲染成可见的红框，而不是静默留白 —— 出图前就能一眼看到。"""
    return (
        '<span class="material material--missing" '
        f'title="素材缺失: {escape(src, quote=True)}">素材缺失<br>{escape(src)}</span>'
    )


def inline_materials(
    html: str,
    base_dir: Path,
    md_dir: Path,
    report: MaterialReport | None = None,
) -> str:
    """把 HTML 里指向本地文件的 <img> 换成内联 SVG 或 data URI。"""
    report = report if report is not None else MaterialReport()

    def replace(match: re.Match) -> str:
        attrs: Dict[str, str] = {k.lower(): v for k, v in _ATTR_RE.findall(match.group(1))}
        src = attrs.get("src", "").strip()
        if not src:
            return match.group(0)

        path = _resolve(src, base_dir, md_dir)
        if path is None:
            # 远程 URL 原样放行（networkidle 会等它），本地路径找不到才算缺失
            if re.match(r"^(?:https?:|data:)", src, re.IGNORECASE):
                return match.group(0)
            report.missing.append(src)
            return _placeholder(src)

        classes, alt_text = parse_directives(attrs.get("alt", ""))
        class_attr = " ".join(["material"] + classes)

        try:
            if path.suffix.lower() == ".svg":
                inner = sanitize_svg(path.read_text(encoding="utf-8"))
                report.resolved.append(str(path))
                label = f'<span class="material-caption">{escape(alt_text)}</span>' if alt_text else ""
                return f'<span class="{class_attr} material--svg">{inner}</span>{label}'

            if path.suffix.lower() in RASTER_SUFFIXES:
                report.resolved.append(str(path))
                return (
                    f'<span class="{class_attr} material--raster">'
                    f'<img src="{_data_uri(path, _target_px(classes))}" '
                    f'alt="{escape(alt_text, quote=True)}"></span>'
                )
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            report.errors.append((src, str(exc)))
            return _placeholder(src)

        report.errors.append((src, f"不支持的素材格式 {path.suffix}"))
        return _placeholder(src)

    return _IMG_RE.sub(replace, html)


def warn(report: MaterialReport) -> None:
    for src in report.missing:
        print(f"  ⚠️  素材找不到: {src}", file=sys.stderr)
    for src, reason in report.errors:
        print(f"  ⚠️  素材处理失败: {src} —— {reason}", file=sys.stderr)
