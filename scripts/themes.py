#!/usr/bin/env python3
"""主题注册表 —— 把散落在 render_xhs.py 里的主题硬编码收口到一处。

改造前，新增一个主题要同时改 5 个地方：主题 CSS 文件、AVAILABLE_THEMES 白名单、
generate_cover_html 里的 theme_backgrounds、generate_card_html 里**同名字典的第二份
拷贝**、以及 title_gradients。每次「样图 → 风格」提取都手改 5 处 = 必错。

收口后，一个自定义主题 = 两个文件，零源码改动：
    assets/themes/<slug>.json   风格 token（我看样图后写的）
    assets/themes/<slug>.css    由 build_theme.py 从 token 生成

这个发布版本只保留 3 套从真实样图提取的主题（dark-gold / marker-duo /
kraft-marker，见各自的 references/<theme>-source.md），原来的 8 套通用内置
主题（BUILTIN_THEMES 曾经的默认内容）和另外 2 套单图提取的主题
（sketch-cream / pastel-tier）在这个包里被移除了，不是这次要展示的内容。
BUILTIN_THEMES 留空字典，`discover_themes()` 因此只会发现 assets/themes/
下的 *.json 自定义主题。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
THEMES_DIR = ASSETS_DIR / "themes"

# 改造前 .cover-inner 的背景是写死的 #F3F3F3、副标题写死 #000000、页码写死半透明白，
# 与主题无关。内置主题沿用这些值以保持像素一致；自定义主题可以覆盖。
_COVER_SURFACE_DEFAULT = "#F3F3F3"
_COVER_INK_DEFAULT = "#000000"
_PAGE_NUMBER_COLOR_DEFAULT = "rgba(255, 255, 255, 0.8)"
_FONT_DEFAULT = (
    "'Noto Sans SC', 'Source Han Sans CN', 'PingFang SC', 'Microsoft YaHei', sans-serif"
)

#: 渲染管线真正读取的 token。build_theme.py 用的 token（ink/accent/radius…）
#: 只影响生成的 CSS，不在这里出现。
RENDER_TOKENS = (
    "bg_cover",
    "bg_card",
    "title_gradient",
    "cover_surface",
    "cover_ink",
    "page_number_color",
    "font_title",
    "font_body",
)

BUILTIN_THEMES: Dict[str, Dict[str, str]] = {}
# 原来这里有 8 套通用内置主题（default/playful-geometric/neo-brutalism/
# botanical/professional/retro/terminal/sketch）的 token，这个发布版本
# 移除了，只保留下面 assets/themes/*.json 里的 3 套真实样图提取主题。


#: 内置主题的素材强调色 —— 取自各主题 CSS 里链接/引用条的那个真正的"跳色"，
#: 而不是 h1 的颜色（default / professional / sketch 的 h1 是近黑色，不是强调色）。
#: 素材因此会跟着主题走，而不是一律染成正文色。
_BUILTIN_MATERIAL_ACCENT: Dict[str, str] = {}

#: 版式组件（assets/components.css）要用的 token，以 CSS 变量注入。
#: 内置主题的值抄自各自 CSS 里的 .card-content{color} 与 .card-inner{background}，
#: 这样组件在 8 套内置主题下也能自动配色，而不是只服务自定义主题。
_BUILTIN_COMPONENT_TOKENS: Dict[str, Dict[str, object]] = {}

#: 注入给组件用的 CSS 变量名 → token 名
COMPONENT_VARS = {
    "--c-ink": "ink",
    "--c-accent": "accent",
    "--c-accent-2": "accent_2",
    "--c-solid": "solid",
    "--c-radius": "radius_css",
    "--c-title-font": "font_title",
}


def _translucent(color: str, alpha: float) -> str:
    """#RRGGBB → rgba(...)。非 hex 输入原样返回。"""
    import re

    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", color.strip())
    if not m:
        return color
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def _is_dark(color: str) -> bool:
    import re

    m = re.fullmatch(r"#([0-9a-fA-F]{6})", color.strip())
    if not m:
        return False
    h = m.group(1)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128


def _contrast_shift(color: str, lighten: bool, ratio: float = 0.42) -> str:
    """把分类色朝白或黑推一档，得到在该主题背景上够亮/够深的文字色。

    深色主题往白推，浅色主题往黑推。非 hex 输入原样返回。
    """
    import re

    m = re.fullmatch(r"#([0-9a-fA-F]{6})", color.strip())
    if not m:
        return color
    h = m.group(1)
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    target = 255 if lighten else 0
    shifted = [round(c + (target - c) * ratio) for c in rgb]
    return "#{:02X}{:02X}{:02X}".format(*shifted)


def _panel_solid(tokens: Dict[str, str]) -> str:
    """组件面板的实色底。ink 浅 = 深色主题 → 面板要比背景亮一点，反之亦然。"""
    return "#1E2739" if not _is_dark(str(tokens.get("ink", "#000000"))) else "#FFFFFF"


def _with_component_vars(tokens: Dict[str, str]) -> Dict[str, str]:
    """把组件要用的 token 拼成一段 CSS 变量声明，供渲染时注入。"""
    radius = tokens.get("radius", 20)
    tokens["radius_css"] = f"{radius}px" if not str(radius).endswith(("px", "%")) else str(radius)
    decls = [
        f"    {var}: {tokens.get(key, 'inherit')};" for var, key in COMPONENT_VARS.items()
    ]

    # 分类配色：palette 里的第 n 个色变成 --c-pN，供 .grid.palette 逐栏取用。
    # 只有一个 accent 的主题表达不了「四栏各一色」这类版式 —— 那不是审美退让，
    # 是 schema 缺口（小红书里分类配色极常见）。
    palette = tokens.get("palette") or []
    if isinstance(palette, str):
        palette = [c.strip() for c in palette.split(",") if c.strip()]

    # 每个分类色出两份：
    #   --c-pN   原色，用作面板填充（palette-solid）
    #   --c-pNt  对比调整版，用作文字/圆徽（palette）
    # 从样图取到的通常是「色块填充色」—— 那种饱和度的砖红、深绿放在深色底上当
    # 文字会发闷、发暗。一个变量没法同时服务填充和文字，所以分两套。
    dark_theme = not _is_dark(str(tokens.get("ink", "#000000")))
    for i, color in enumerate(palette[:6], start=1):
        decls.append(f"    --c-p{i}: {color};")
        decls.append(f"    --c-p{i}t: {_contrast_shift(color, lighten=dark_theme)};")

    tokens["component_vars"] = "\n".join(decls)
    return tokens


def _defaults() -> Dict[str, str]:
    return {
        "cover_surface": _COVER_SURFACE_DEFAULT,
        "cover_ink": _COVER_INK_DEFAULT,
        "page_number_color": _PAGE_NUMBER_COLOR_DEFAULT,
        "font_title": _FONT_DEFAULT,
        "font_body": _FONT_DEFAULT,
        "material_accent": "currentColor",
    }


def custom_theme_names() -> List[str]:
    """themes 目录下所有 <slug>.json 对应的自定义主题名（按字母序）。"""
    if not THEMES_DIR.is_dir():
        return []
    names = {p.stem for p in THEMES_DIR.glob("*.json") if not p.stem.startswith("_")}
    return sorted(names - set(BUILTIN_THEMES))


def discover_themes() -> List[str]:
    """可用主题 = 8 套内置 + themes 目录下发现的自定义主题。"""
    return list(BUILTIN_THEMES) + custom_theme_names()


def load_tokens(theme: str) -> Dict[str, str]:
    """读取主题 token（不含 CSS 文本）。未知主题回退到 default。"""
    tokens = _defaults()
    if theme in BUILTIN_THEMES:
        tokens.update(BUILTIN_THEMES[theme])
        tokens["material_accent"] = _BUILTIN_MATERIAL_ACCENT[theme]
        comp = _BUILTIN_COMPONENT_TOKENS[theme]
        tokens.update({
            "ink": comp["ink"],
            "accent": _BUILTIN_MATERIAL_ACCENT[theme],
            "accent_2": comp["h1"],
            "solid": comp["solid"],
            "radius": comp["radius"],
        })
        return _with_component_vars(tokens)

    token_file = THEMES_DIR / f"{theme}.json"
    if token_file.is_file():
        try:
            written = json.loads(token_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"❌ 主题 token 解析失败 {token_file}: {exc}") from exc
        tokens.update({k: v for k, v in written.items() if v not in ("", None)})

        # 自定义主题允许只给 bg_card，封面背景与之相同即可
        tokens.setdefault("bg_cover", tokens.get("bg_card", ""))
        tokens.setdefault("bg_card", tokens.get("bg_cover", ""))

        # 素材色默认跟随主题强调色，而不是 _defaults() 里那个"跟随正文色"的
        # currentColor —— 否则自定义主题里的 SVG 会渲染成正文的墨色，
        # 白白丢掉「素材跟着主题走」这个卖点。
        if "material_accent" not in written and written.get("accent"):
            tokens["material_accent"] = written["accent"]

        # 页码浮在最外层背景上。内置主题的背景都偏深，写死半透明白没问题；
        # 自定义主题可能是浅底（奶油色、米白），白色页码会直接隐形。
        if "page_number_color" not in written and written.get("ink"):
            tokens["page_number_color"] = _translucent(written["ink"], 0.45)

        # 组件用的实色底：surface 可能是 transparent（满版主题），组件面板需要
        # 一个真实存在的底色，否则叠在深色背景上会整块消失。
        tokens.setdefault("solid", _panel_solid(tokens))
        tokens.setdefault("accent_2", tokens.get("accent", "#888888"))
        return _with_component_vars(tokens)
        missing = [k for k in ("bg_cover", "bg_card", "title_gradient") if not tokens.get(k)]
        if missing:
            raise SystemExit(f"❌ 主题 {theme} 缺少必需 token: {missing}")
        return tokens

    # 未知主题名——这个发布版本没有 BUILTIN_THEMES["default"] 可回退了，
    # 与其静默退化成一张没有背景/标题渐变的空白卡，不如直接报错列出可用主题。
    raise SystemExit(
        f"❌ 未知主题 {theme!r}，可用主题：{', '.join(discover_themes())}"
    )


def load_css(theme: str) -> str:
    """加载主题 CSS。load_tokens() 已经在这之前把未知主题名拦下来了
    （见其 SystemExit 分支），所以这里只会拿到 3 套已发布主题之一的名字，
    文件必然存在——不再回退到 default.css（这个发布版本里已经删掉了）。

    若存在 <theme>.custom.css，追加在生成的 CSS 之后 —— 这是**逃生舱**：

    token schema 是一组固定槽位（背景、墨色、强调色、圆角、边框、阴影…），
    只能表达我预先想到的风格轴。换一张参考图，只要它的风格语言里有个我没设槽位的
    东西（票根缺口、手写下划线、斜切色带、标题描边、纸纹叠加…），token 就表达不了，
    而给 schema 不断加槽位是条没有尽头的路 —— 永远慢参考图一步。

    逃生舱把这条路封死：凡是 CSS 能表达的，我都能直接写，不需要先改 schema。
    追加在后面所以能覆盖生成的规则；跟着主题名走所以不污染其他主题。
    """
    theme_file = THEMES_DIR / f"{theme}.css"
    css = theme_file.read_text(encoding="utf-8") if theme_file.is_file() else ""

    custom = THEMES_DIR / f"{theme}.custom.css"
    if custom.is_file():
        css += f"\n\n/* ---- {theme}.custom.css（手写，覆盖以上生成规则）---- */\n"
        css += custom.read_text(encoding="utf-8")
    return css


def load_theme(theme: str) -> Dict[str, str]:
    """token + css，渲染管线的唯一入口。"""
    tokens = load_tokens(theme)
    tokens["css"] = load_css(theme)
    return tokens


if __name__ == "__main__":
    for name in discover_themes():
        kind = "内置" if name in BUILTIN_THEMES else "自定义"
        print(f"{name:<20} [{kind}] {load_tokens(name).get('label', '')}")
