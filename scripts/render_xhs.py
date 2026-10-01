#!/usr/bin/env python3
"""
小红书卡片渲染脚本 - 增强版
支持多种排版样式和智能分页策略

使用方法:
    python render_xhs.py <markdown_file> [options]

选项:
    --output-dir, -o     输出目录（默认为当前工作目录）
    --theme, -t          排版主题：dark-gold, marker-duo, kraft-marker, scrapbook-kai
    --mode, -m           分页模式：
                         - separator  : 按 --- 分隔符手动分页（默认）
                         - auto-fit   : 自动缩放文字以填满固定尺寸
                         - auto-split : 根据内容高度自动切分
                         - dynamic    : 根据内容动态调整图片高度
    --width, -w          图片宽度（默认 1080）
    --height, -h         图片高度（默认 1440，dynamic 模式下为最小高度）
    --max-height         dynamic 模式下的最大高度（默认 4320
    --dpr                设备像素比（默认 2）

依赖安装:
    pip install markdown pyyaml playwright
    playwright install chromium
"""

import argparse
import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import markdown
    import yaml
    from playwright.async_api import async_playwright
except ImportError as e:
    print(f"缺少依赖: {e}")
    print("请运行: bash scripts/check_deps.sh")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import themes as theme_registry
from materials import MaterialReport, inline_materials, warn as warn_materials


# 获取脚本所在目录
SCRIPT_DIR = Path(__file__).parent.parent
ASSETS_DIR = SCRIPT_DIR / "assets"
THEMES_DIR = ASSETS_DIR / "themes"

# 默认卡片尺寸配置 (3:4 比例)
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1440
MAX_HEIGHT = 4320  # dynamic 模式最大高度

# 可用主题 = assets/themes/*.json 里发现的主题（见 themes.py）
AVAILABLE_THEMES = theme_registry.discover_themes()

# 分页模式
PAGING_MODES = ['separator', 'auto-fit', 'auto-split', 'dynamic']

#: 小红书信息流里，App 会在封面下缘压上笔记标题和作者名，约遮住底部 150px。
#: 核心信息必须避开这条带子 —— 见 references/cover-design.md。
UI_SAFE_BOTTOM = 150

#: 是否在卡片右下角渲染 "n/N" 页码。由 --no-page-number 关闭。
SHOW_PAGE_NUMBER = True

#: 素材解析的上下文。由 configure_materials() 在入口设置一次，
#: 因为 convert_markdown_to_html 被 auto_split_content 深层调用，逐层传参会污染
#: 五个函数签名，而这两个值在单次运行内是常量。
_MATERIALS_DIR: Path = Path.cwd()
_MD_DIR: Path = Path.cwd()
_MATERIAL_REPORT = MaterialReport()


def configure_materials(md_file: str, materials_dir: Optional[str]) -> None:
    global _MATERIALS_DIR, _MD_DIR, _MATERIAL_REPORT
    _MD_DIR = Path(md_file).resolve().parent
    _MATERIALS_DIR = Path(materials_dir).resolve() if materials_dir else _MD_DIR
    _MATERIAL_REPORT = MaterialReport()


def material_report() -> MaterialReport:
    return _MATERIAL_REPORT


def parse_markdown_file(file_path: str) -> dict:
    """解析 Markdown 文件，提取 YAML 头部和正文内容"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析 YAML 头部
    yaml_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    yaml_match = re.match(yaml_pattern, content, re.DOTALL)
    
    metadata = {}
    body = content
    
    if yaml_match:
        try:
            metadata = yaml.safe_load(yaml_match.group(1)) or {}
        except yaml.YAMLError:
            metadata = {}
        body = content[yaml_match.end():]
    
    return {
        'metadata': metadata,
        'body': body.strip()
    }


def split_content_by_separator(body: str) -> List[str]:
    """按照 --- 分隔符拆分正文为多张卡片内容"""
    parts = re.split(r'\n---+\n', body)
    return [part.strip() for part in parts if part.strip()]


#: 版式组件里「装内容」的容器 —— 内部按块级 markdown 解析（段落、列表都能用）
_BLOCK_COMPONENTS = {
    'grid', 'grid-2', 'grid-3', 'grid-4', 'grid-side',
    'panel', 'panel-capped', 'panel-outline', 'body',
    'badge-row', 'txt', 'vs', 'good', 'bad',
    'steps', 'step', 'highlight', 'stats', 'tight',
    'timeline', 'tl-step', 'hub', 'hub-image', 'hub-items', 'hub-item',
    'hub-radial', 'hub-center',
    'icon-tile', 'stat-block', 'quadrant', 'quad-item',
    'sticky', 'scroll-note', 'note-panel', 'dash-card', 'todo', 'disclaimer',
}

#: 只放一行字的组件 —— 按行内 markdown 解析，避免被包进 <p> 破坏居中/内边距
_SPAN_COMPONENTS = {'cap', 'col-title', 'sub-label', 'badge', 'badge-sm', 'dot', 'mark', 'num', 'hub-label', 'q-title', 'q-sub', 'tl-title',
                     'sticky-title', 'dash-cap', 'dash-note',
                     'w-red', 'w-green', 'w-amber', 'w-ink'}

# ul/ol/li 也要能被匹配：.todo 这类组件的容器是 <ul>，只匹配 div/p/span 的话
# markdown="1" 永远加不到它身上，列表项里的 **加粗** 会原样输出成星号。
_DIV_OPEN_RE = re.compile(r'<(div|p|span|ul|ol|li)\b([^>]*)>', re.IGNORECASE)
_CLASS_RE = re.compile(r'\bclass\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)


def autotag_components(md_content: str) -> str:
    """给版式组件自动补 markdown 属性。

    python-markdown 的 md_in_html 要求 markdown="1" 写在**每一层祖先**上，漏掉
    任何一层，内部的 **粗体** 就会原样输出。手写多层嵌套版式时这个坑必踩
    （已经踩过一次：外层 <div class="grid"> 忘了写，整张卡的加粗全失效）。

    这里按 class 名自动补：容器补 markdown="1"，单行组件补 markdown="span"
    （span 模式不会把内容包进 <p>，否则 .cap 的居中和内边距会被 p 的默认边距破坏）。
    已经手写了 markdown 属性的元素不动。
    """
    def fix(match: re.Match) -> str:
        tag, attrs = match.group(1), match.group(2)
        if re.search(r'\bmarkdown\s*=', attrs, re.IGNORECASE):
            return match.group(0)
        class_match = _CLASS_RE.search(attrs)
        if not class_match:
            return match.group(0)
        classes = set(class_match.group(1).split())
        if classes & _BLOCK_COMPONENTS:
            return f'<{tag}{attrs} markdown="1">'
        if classes & _SPAN_COMPONENTS:
            return f'<{tag}{attrs} markdown="span">'
        return match.group(0)

    return _DIV_OPEN_RE.sub(fix, md_content)


def convert_markdown_to_html(md_content: str) -> str:
    """将 Markdown 转换为 HTML"""
    # 处理 tags（以 # 开头的标签）
    tags_pattern = r'((?:#[\w\u4e00-\u9fa5]+\s*)+)$'
    tags_match = re.search(tags_pattern, md_content, re.MULTILINE)
    tags_html = ""
    
    if tags_match:
        tags_str = tags_match.group(1)
        md_content = md_content[:tags_match.start()].strip()
        tags = re.findall(r'#([\w\u4e00-\u9fa5]+)', tags_str)
        if tags:
            tags_html = '<div class="tags-container">'
            for tag in tags:
                tags_html += f'<span class="tag">#{tag}</span>'
            tags_html += '</div>'
    
    # 转换 Markdown 为 HTML
    # md_in_html 必须显式启用（markdown 3.x 的 extra 不再自动包含它）。
    # 没有它，版式组件里的 markdown="1" 不生效，组件内部就只能写裸 HTML，
    # 无法混用 markdown —— 那会让手写版式卡片的成本高一个量级。
    html = markdown.markdown(
        autotag_components(md_content),
        extensions=['extra', 'md_in_html', 'codehilite', 'tables', 'nl2br']
    )

    # 素材内联必须发生在这里 —— auto_split_content 靠试渲染量高度决定切分点，
    # 若素材此时还没进 DOM，分页会按「没有图」的高度切，实际出图必然溢出。
    html = inline_materials(html, _MATERIALS_DIR, _MD_DIR, _MATERIAL_REPORT)

    return html + tags_html


def load_theme_css(theme: str) -> str:
    """加载主题 CSS 样式（保留此函数名，实现收口到 themes.py）"""
    return theme_registry.load_css(theme)


def split_cover_body(body: str) -> tuple:
    """把 frontmatter 与第一个 `# ` 标题之间的内容切出来当封面正文。

    封面是决定点击率的一张，却曾经是能力最弱的一张 —— 结构写死在 Python 里，
    用不了组件库、素材、分类配色，只能是「emoji + 标题 + 副标题」，中间一大片空。

    给 schema 加 cover_image / cover_badges 之类的槽位是条没有尽头的路（跟风格
    token 一样的教训）。所以改成：**封面正文就是普通 markdown**，走和正文卡完全
    一样的管线，组件、素材、配色全都能用。

    frontmatter 之后、第一个 `# ` 之前的内容归封面。老文件那里是空的，行为不变。
    """
    m = re.search(r'^#\s+', body, re.MULTILINE)
    if not m:
        return "", body
    return body[:m.start()].strip(), body[m.start():]


#: 封面变体分隔符。写在封面正文里，把它切成几版备选。
COVER_VARIANT_RE = re.compile(r'^\s*<!--\s*or\s*-->\s*$', re.MULTILINE | re.IGNORECASE)


def split_cover_variants(cover_body: str) -> List[str]:
    """把封面正文按 `<!-- or -->` 切成多版备选。

    封面文字区只有约 780×1150，标题和副标题已占掉大半 —— 宫格和配图**只能二选一**，
    硬塞两样反而丢焦点。既然是二选一，就别替用户选：出两版让人挑。
    """
    if not cover_body.strip():
        return [""]
    parts = [p.strip() for p in COVER_VARIANT_RE.split(cover_body)]
    return [p for p in parts if p] or [""]


def cover_crowding_warning(variant: str) -> Optional[str]:
    """封面同时用了栅格和配图 —— 空间放不下，必然挤。"""
    has_grid = 'class="grid' in variant or "class='grid" in variant
    has_image = bool(re.search(r'!\[[^\]]*\]\([^)]+\)', variant))
    if has_grid and has_image:
        return "封面同时有栅格和配图 —— 文字区约 780×1150，标题副标题已占大半，二选一"
    return None


def generate_cover_html(metadata: dict, theme: str, width: int, height: int,
                        cover_body: str = "") -> str:
    """生成封面 HTML"""
    emoji = metadata.get('emoji', '📝')
    title = metadata.get('title', '标题')
    subtitle = metadata.get('subtitle', '')
    
    
    # 动态调整标题字体大小。
    # 按「最长的一行」而不是总字数来算 —— 标题里可以写 <br> 手动控制断点
    # （封面常见的「主题 / 数字承诺」两行式排版），此时总字数会误导字号计算，
    # 把本可以放大的标题压小。同时剔除标记，避免 <br> 本身被计入长度。
    title_lines = [re.sub(r'<[^>]+>', '', seg) for seg in re.split(r'<br\s*/?>', title)]
    title_len = max((len(line) for line in title_lines), default=0)
    # 小红书封面主标题的通行量级是 80-120pt Bold（1080×1440 画布），
    # 爆款封面往往更大 —— 3 秒法则要求视觉冲击力优先于信息量。
    # 原来的上限 0.14（151px）对 4-6 字的短标题偏保守，抬到 0.20。
    if title_len <= 4:
        title_size = int(width * 0.20)  # 超大：4 字以内，封面主视觉
    elif title_len <= 6:
        title_size = int(width * 0.17)
    elif title_len <= 10:
        title_size = int(width * 0.13)
    elif title_len <= 18:
        title_size = int(width * 0.095)
    elif title_len <= 30:
        title_size = int(width * 0.07)
    else:
        title_size = int(width * 0.055)

    # 查表定的字号只看字数，不看放不放得下 —— 6 个汉字按「极大」档是 151px，
    # 连起来 906px，而封面文字区只有约 780px 宽，于是断行、留下孤字。
    # 这里按实际可用宽度再压一次：汉字约占 1 个字宽，拉丁字母/数字窄得多，
    # 分开估算，否则纯英文标题会被无谓地缩小。
    # 封面文字区宽度。原来是 0.88 宽的面板 + 0.079 的左右内边距 = 只剩 780px，
    # 把标题硬压小了一档。放宽到 0.94 / 0.055 后有 895px，标题能大一圈。
    avail = int(width * 0.94) - 2 * int(width * 0.055)

    def _em_units(line: str) -> float:
        cjk = sum(1 for ch in line if '⺀' <= ch <= '鿿' or '　' <= ch <= '〿'
                  or '＀' <= ch <= '￯')
        return cjk + (len(line) - cjk) * 0.55

    # 留 8% 余量：字宽是估的不是量的，而且 font-weight:900 在没有 900 字重的字体上
    # 会触发合成加粗，字形比标称更宽。曾经算出 777px / 可用 780px 判定"放得下"，
    # 实际仍然断行。
    widest = max((_em_units(l) for l in title_lines), default=1) or 1
    title_size = max(int(width * 0.045), min(title_size, int(avail * 0.92 / widest)))

    # 副标题同理。原本写死 width*0.067（72px），780px 可用宽只放得下 10.8 个汉字，
    # 11 个字就断行留下「会」这样的孤字 —— 跟标题是同一个 bug，之前只修了标题那一半。
    #
    # 策略是**优先压成一行**：副标题本来就短，缩几个 px 远比断出孤字好看。
    # 只有长到压过下限（width*0.042）才让它换行，那时字数已经多到两行也算均衡。
    sub_size = int(width * 0.067)
    sub_units = _em_units(subtitle)
    if sub_units:
        sub_size = max(int(width * 0.042), min(sub_size, int(avail * 0.92 / sub_units)))

    # 主题 token（背景 / 标题渐变 / 封面内panel 底色 / 字体）统一由 themes.py 提供
    tokens = theme_registry.load_theme(theme)
    bg = tokens['bg_cover']
    title_bg = tokens['title_gradient']
    cover_surface = tokens['cover_surface']
    cover_ink = tokens['cover_ink']
    font_title = tokens['font_title']
    font_body = tokens['font_body']

    # 封面正文走和正文卡完全一样的管线 —— 组件库、素材内联、分类配色全部可用
    body_html = convert_markdown_to_html(cover_body) if cover_body.strip() else ""

    theme_css = tokens['css'] if body_html else ""
    component_vars = tokens.get('component_vars', '')
    components_css = materials_css = ""
    if body_html:
        cf = ASSETS_DIR / "components.css"
        components_css = cf.read_text(encoding='utf-8') if cf.is_file() else ""
        mf = ASSETS_DIR / "materials.css"
        materials_css = mf.read_text(encoding='utf-8') if mf.is_file() else ""
        materials_css = materials_css.replace('__MATERIAL_ACCENT__', tokens['material_accent'])

    # 标题永远按内容自然高度排布，不能 flex:1 撑满剩余空间——
    # 硬切两色标题（title_gradient 是多段 stop 的渐变，如黑/橙硬切）靠
    # background-clip:text 按标题盒子的高度百分比上色，盒子被 flex:1 撑到
    # 远大于两行文字的实际高度时，橙色那段落在文字下方的空白区域里，
    # 两行字全部落在黑色区间——标题看着"整段纯黑"，不是主题配色错，
    # 是盒子比文字高太多。副标题用 margin-top:auto 吸收剩余空间，
    # 标题固定成内容高度不影响整体上下留白的分布。
    title_flex = "0 0 auto"

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width={width}, height={height}">
    <title>小红书封面</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: {font_body};
            width: {width}px;
            height: {height}px;
            overflow: hidden;
        }}
        
        .cover-container {{
            width: {width}px;
            height: {height}px;
            background: {bg};
            position: relative;
            overflow: hidden;
        }}
        
        .cover-inner {{
            position: absolute;
            width: {int(width * 0.94)}px;
            height: {int(height * 0.955)}px;
            left: {int(width * 0.03)}px;
            top: {int(height * 0.022)}px;
            background: {cover_surface};
            border-radius: 25px;
            display: flex;
            flex-direction: column;
            /* 底部多留 UI_SAFE_BOTTOM：信息流里 App 会在封面下缘压上笔记标题和
               作者名，约占 150px。副标题原本贴着底走 margin-top:auto，正好落在
               这条带子里 —— 出图看着没问题，实际刷到的人根本看不见。 */
            padding: {int(height * 0.045)}px {int(width * 0.055)}px {int(height * 0.045) + UI_SAFE_BOTTOM}px;
            /* 组件取色变量必须挂在这一层，不能只挂在 .cover-body 上。
               .cover-title 和 .cover-body 是兄弟节点，CSS 自定义属性不会在
               兄弟间流动——只挂在 body 上时，标题里的 <span class="hl-box">
               或 <span class="marker">（引用 --c-accent-fill）在标题里完全
               拿不到值，background 直接失效、不报错、也不是错误的颜色，
               是彻底没有背景。挂在共同祖先 .cover-inner 上两边都能继承。 */
{component_vars}
        }}
        
        .cover-emoji {{
            /* 从 0.167（180px）收到 0.10（108px）。
               封面上最大的东西必须是标题 —— 一个 180px 的 emoji 会跟它抢焦点，
               还吃掉 230px 的纵向空间，把正文挤没。emoji 是点缀不是主角。 */
            font-size: {int(width * 0.10)}px;
            line-height: 1.1;
            margin-bottom: {int(height * 0.018)}px;
        }}
        
        .cover-title {{
            font-family: {font_title};
            font-weight: 900;
            font-size: {title_size}px;
            /* 大字标题要用紧行距。1.4 在 183px 字号下每行要占 256px，
               两行就吃掉 512px；1.12 省下近 100px 给正文，观感也更"重"。 */
            line-height: 1.12;
            background: {title_bg};
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            flex: {title_flex};
            /* 必须是 block 不能是 flex：flex 容器会把 <br> 忽略、把行内 <span>
               当成 flex item 横向排开 —— 关键词色块会跑到右边跨两行。
               标题就是普通的行内文字流，block 才对。 */
            display: block;
            word-break: break-all;
        }}

        /* 封面正文区。用 .card-content 这个类名是为了让组件库和主题 CSS
           原样生效 —— 它们的选择器都挂在 .card-content 下。 */
        .cover-body.card-content {{
            flex: 1;
            min-height: 0;
            overflow: hidden;
            margin-top: {int(height * 0.028)}px;
            line-height: 1.6;
        }}

        .cover-body > *:first-child {{ margin-top: 0; }}
        .cover-body > *:last-child  {{ margin-bottom: 0; }}

        {theme_css}

        {components_css}

        {materials_css}
        
        /* ---- 标题里的关键词高亮 ----
           小红书封面的核心手法：把最关键的那个词用对比色或色块抠出来，
           扫一眼先看到它。

           实现上有个坑：.cover-title 用 background-clip:text +
           -webkit-text-fill-color:transparent 做渐变裁切，**子元素会继承那份透明**。
           所以高亮元素必须显式把 fill-color 写回来，否则整段消失。 */
        .cover-title .hl {{
            -webkit-text-fill-color: {tokens['accent']};
            color: {tokens['accent']};
            background: none;
        }}

        .cover-title .hl-box {{
            -webkit-text-fill-color: {tokens.get('surface_ink', '#FFFFFF')};
            color: {tokens.get('surface_ink', '#FFFFFF')};
            background: {tokens['accent']};
            background-clip: border-box;
            -webkit-background-clip: border-box;
            padding: 0.02em 0.14em;
            border-radius: 0.1em;
            box-decoration-break: clone;
            -webkit-box-decoration-break: clone;
        }}

        /* 副标题里的次要文字 */
        .cover-subtitle .hl {{
            color: {tokens['accent']};
            font-weight: 700;
        }}

        .cover-subtitle {{
            font-weight: 350;
            font-size: {sub_size}px;
            line-height: 1.4;
            color: {cover_ink};
            margin-top: auto;
        }}
    </style>
</head>
<body>
    <div class="cover-container">
        <div class="cover-inner">
            <div class="cover-emoji">{emoji}</div>
            <div class="cover-title">{title}</div>
            {f'<div class="cover-body card-content">{body_html}</div>' if body_html else ''}
            <div class="cover-subtitle">{subtitle}</div>
        </div>
    </div>
</body>
</html>'''
    return html


def generate_card_html(content: str, theme: str, page_number: int = 1, 
                       total_pages: int = 1, width: int = DEFAULT_WIDTH, 
                       height: int = DEFAULT_HEIGHT, mode: str = 'separator') -> str:
    """生成正文卡片 HTML"""
    
    html_content = convert_markdown_to_html(content)

    tokens = theme_registry.load_theme(theme)
    theme_css = tokens['css']
    bg = tokens['bg_card']
    font_body = tokens['font_body']
    material_accent = tokens['material_accent']
    page_number_color = tokens['page_number_color']

    page_text = f"{page_number}/{total_pages}" if (SHOW_PAGE_NUMBER and total_pages > 1) else ""

    materials_css_file = ASSETS_DIR / "materials.css"
    materials_css = materials_css_file.read_text(encoding='utf-8') if materials_css_file.is_file() else ""
    materials_css = materials_css.replace('__MATERIAL_ACCENT__', material_accent)

    components_css_file = ASSETS_DIR / "components.css"
    components_css = components_css_file.read_text(encoding='utf-8') if components_css_file.is_file() else ""
    component_vars = tokens.get('component_vars', '')

    # 根据模式设置不同的容器样式
    if mode == 'auto-fit':
        container_style = f'''
            width: {width}px;
            height: {height}px;
            background: {bg};
            position: relative;
            padding: 50px;
            overflow: hidden;
        '''
        inner_style = f'''
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 60px;
            height: calc({height}px - 100px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        '''
        content_style = '''
            flex: 1;
            overflow: hidden;
        '''
    elif mode == 'dynamic':
        container_style = f'''
            width: {width}px;
            min-height: {height}px;
            background: {bg};
            position: relative;
            padding: 50px;
        '''
        inner_style = '''
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 60px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        '''
        content_style = ''
    else:  # separator 和 auto-split
        container_style = f'''
            width: {width}px;
            min-height: {height}px;
            background: {bg};
            position: relative;
            padding: 50px;
            overflow: hidden;
        '''
        inner_style = f'''
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 60px;
            min-height: calc({height}px - 100px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        '''
        content_style = ''
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width={width}">
    <title>小红书卡片</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: {font_body};
            width: {width}px;
            overflow: hidden;
            background: transparent;
        }}
        
        .card-container {{
            {container_style}
        }}
        
        .card-inner {{
            {inner_style}
        }}
        
        .card-content {{
            line-height: 1.7;
            {content_style}
        }}

        /* auto-fit 用：对整个内容块做 transform 缩放 */
        .card-content-scale {{
            transform-origin: top left;
            will-change: transform;
        }}
        
        {theme_css}

        /* 版式组件的取色变量，从主题 token 注入 */
        .card-content {{
{component_vars}
        }}

        /* 组件与素材样式放在主题 CSS 之后 —— 主题会写 .card-content img
           和各种元素规则，必须让组件的布局规则赢过它 */
        {components_css}

        {materials_css}

        .card-content :not(pre) > code {{
            overflow-wrap: anywhere;
            word-break: break-word;
        }}

        .page-number {{
            position: absolute;
            bottom: 80px;
            right: 80px;
            font-size: 36px;
            color: {page_number_color};
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="card-container">
        <div class="card-inner">
            <div class="card-content">
                <div class="card-content-scale">{html_content}</div>
            </div>
        </div>
        <div class="page-number">{page_text}</div>
    </div>
</body>
</html>'''
    return html


async def render_html_to_image(html_content: str, output_path: str, 
                               width: int = DEFAULT_WIDTH, 
                               height: int = DEFAULT_HEIGHT,
                               mode: str = 'separator',
                               max_height: int = MAX_HEIGHT,
                               dpr: int = 2):
    """使用 Playwright 将 HTML 渲染为图片"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        # 设置视口大小
        viewport_height = height if mode != 'dynamic' else max_height
        page = await browser.new_page(
            viewport={'width': width, 'height': viewport_height},
            device_scale_factor=dpr
        )
        
        # 创建临时 HTML 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html_path = f.name
        
        try:
            await page.goto(f'file://{temp_html_path}')
            await page.wait_for_load_state('networkidle')
            
            # 等待字体加载
            await page.wait_for_timeout(500)
            
            if mode == 'auto-fit':
                # 自动缩放模式：对整个内容块做 transform 缩放（标题/代码块等固定 px 也会一起缩放）
                await page.evaluate('''() => {
                    const viewportContent = document.querySelector('.card-content');
                    const scaleEl = document.querySelector('.card-content-scale');
                    if (!viewportContent || !scaleEl) return;

                    // 先重置，测量原始尺寸
                    scaleEl.style.transform = 'none';
                    scaleEl.style.width = '';
                    scaleEl.style.height = '';

                    const availableWidth = viewportContent.clientWidth;
                    const availableHeight = viewportContent.clientHeight;

                    // scrollWidth/scrollHeight 反映内容的自然尺寸
                    const contentWidth = Math.max(scaleEl.scrollWidth, scaleEl.getBoundingClientRect().width);
                    const contentHeight = Math.max(scaleEl.scrollHeight, scaleEl.getBoundingClientRect().height);

                    if (!contentWidth || !contentHeight || !availableWidth || !availableHeight) return;

                    // 只缩小不放大，避免“撑太大”
                    const scale = Math.min(1, availableWidth / contentWidth, availableHeight / contentHeight);

                    // 为避免 transform 后布局尺寸不匹配导致裁切，扩大布局盒子
                    scaleEl.style.width = (availableWidth / scale) + 'px';

                    // 顶部对齐更稳；如需居中可计算 offset
                    const offsetX = 0;
                    const offsetY = 0;

                    scaleEl.style.transformOrigin = 'top left';
                    scaleEl.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;
                }''')
                await page.wait_for_timeout(100)
                actual_height = height
                
            elif mode == 'dynamic':
                # 动态高度模式：根据内容调整图片高度
                content_height = await page.evaluate('''() => {
                    const container = document.querySelector('.card-container');
                    return container ? container.scrollHeight : document.body.scrollHeight;
                }''')
                # 确保高度在合理范围内
                actual_height = max(height, min(content_height, max_height))
                
            else:  # separator 和 auto-split
                # 获取实际内容高度
                content_height = await page.evaluate('''() => {
                    const container = document.querySelector('.card-container');
                    return container ? container.scrollHeight : document.body.scrollHeight;
                }''')
                actual_height = max(height, content_height)
            
            # 截图
            await page.screenshot(
                path=output_path,
                clip={'x': 0, 'y': 0, 'width': width, 'height': actual_height},
                type='png'
            )
            
            print(f"  ✅ 已生成: {output_path} ({width}x{actual_height})")
            return actual_height
            
        finally:
            os.unlink(temp_html_path)
            await browser.close()


async def auto_split_content(body: str, theme: str, width: int, height: int, 
                             dpr: int = 2) -> List[str]:
    """自动切分内容：根据渲染后的高度自动分页"""
    
    # 将内容按段落分割
    paragraphs = re.split(r'\n\n+', body)
    
    cards = []
    current_content = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={'width': width, 'height': height * 2},
            device_scale_factor=dpr
        )
        
        try:
            for para in paragraphs:
                # 尝试将当前段落加入
                test_content = current_content + [para]
                test_md = '\n\n'.join(test_content)
                
                html = generate_card_html(test_md, theme, 1, 1, width, height, 'auto-split')
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                    f.write(html)
                    temp_path = f.name
                
                await page.goto(f'file://{temp_path}')
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(200)
                
                content_height = await page.evaluate('''() => {
                    const content = document.querySelector('.card-content');
                    return content ? content.scrollHeight : 0;
                }''')
                
                os.unlink(temp_path)
                
                # 内容区域的可用高度（去除 padding 等）
                available_height = height - 220  # 50*2 padding + 60*2 inner padding

                if content_height > available_height and current_content:
                    # 当前卡片已满，保存并开始新卡片
                    cards.append('\n\n'.join(current_content))
                    current_content = [para]
                else:
                    current_content = test_content
            
            # 保存最后一张卡片
            if current_content:
                cards.append('\n\n'.join(current_content))
                
        finally:
            await browser.close()
    
    return cards


#: 中文展示字体（字魂系列等）普遍缺字形的码位区间。出现在标题里会渲染成空心方块。
#: 这是靠肉眼发现过两次的问题 —— 记进代码就不必再靠肉眼。
RISKY_GLYPH_RANGES = [
    (0x2460, 0x24FF, "带圈数字/字母 ①②③"),
    (0x2150, 0x218F, "罗马数字 ⅠⅡⅢ"),
    (0x3220, 0x32FF, "带圈汉字/㊙㊗"),
    (0x1F150, 0x1F19F, "方框字母 🆎🆚"),
    (0x2100, 0x214F, "字母式符号 ℃№™"),
]


def check_risky_glyphs(text: str) -> List[str]:
    """挑出标题里可能没有字形的字符。"""
    hits = []
    for ch in text:
        cp = ord(ch)
        for lo, hi, label in RISKY_GLYPH_RANGES:
            if lo <= cp <= hi:
                hits.append(f"{ch}（{label}）")
                break
    return list(dict.fromkeys(hits))


async def _cover_line_report(page, html: str, width: int, height: int) -> Optional[str]:
    """渲染封面并检查大标题的断行 —— 末行只剩 1-2 个字就是孤字。

    上游模板的字号只按字数查表、不校验放不放得下，6 个汉字按「极大」档会撑破
    封面文字区。已按可用宽度反算修掉，但内容一变仍可能触发，所以留一道检查。
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html)
        tmp = f.name
    try:
        await page.goto(f'file://{tmp}')
        await page.wait_for_load_state('networkidle')
        await page.wait_for_timeout(300)
        return await page.evaluate('''() => {
            const issues = [];

            // 封面正文溢出：.cover-body 是 flex:1 + overflow:hidden，内容超了会被
            // 悄悄裁掉，而副标题（margin-top:auto）会压在被裁的内容上。
            // 出图看着"最后一条被压住了"，但没有任何报错 —— 必须量出来。
            const body = document.querySelector('.cover-body');
            if (body && body.scrollHeight > body.clientHeight + 4) {
                issues.push(`封面正文溢出 ${Math.round(body.scrollHeight - body.clientHeight)}px`
                            + `（内容 ${body.scrollHeight} / 可用 ${body.clientHeight}）`
                            + ' —— 末尾会被裁掉并被副标题压住');
            }

            // 大标题孤字
            const el = document.querySelector('.cover-title');
            if (el) {
                const r = document.createRange();
                r.selectNodeContents(el);
                const rects = Array.from(r.getClientRects()).filter(x => x.width > 1);
                if (rects.length >= 2) {
                    const ratio = rects[rects.length - 1].width / rects[0].width;
                    if (ratio < 0.25) {
                        issues.push(`标题断成 ${rects.length} 行，`
                                    + `末行仅占 ${Math.round(ratio * 100)}% 宽 —— 孤字`);
                    }
                }
            }
            return issues.length ? issues.join('；') : null;
        }''')
    finally:
        os.unlink(tmp)


async def measure_only(md_file: str, theme: str, mode: str,
                       width: int, height: int, max_height: int, dpr: int,
                       sample: Optional[str] = None) -> bool:
    """--dry-run：走完整渲染管线但不落 PNG，只报客观数字。

    复用与出图相同的高度测量逻辑，所以这里报的溢出就是真实溢出。
    返回 True 表示无问题。
    """
    data = parse_markdown_file(md_file)
    metadata, body = data['metadata'], data['body']
    cover_body, body = split_cover_body(body)

    print(f"\n🔍 体检: {md_file}")
    print(f"  主题 {theme} / 模式 {mode} / 画布 {width}x{height}")

    problems = 0

    title = str(metadata.get('title', ''))
    subtitle = str(metadata.get('subtitle', ''))
    if metadata.get('emoji') or title:
        # 与 generate_cover_html 用同一套度量：按最长的一行算，剔除 <br> 等标记。
        # 否则手动断行的标题会被误报「偏长」——两者不一致比报错更糟。
        lines = [re.sub(r'<[^>]+>', '', seg) for seg in re.split(r'<br\s*/?>', title)]
        t_len = max((len(x) for x in lines), default=0)
        wrapped = f"（{len(lines)} 行）" if len(lines) > 1 else ""
        t_flag = "✅" if t_len <= 15 else ("⚠️ 偏长" if t_len <= 30 else "❌ 过长")
        s_flag = "✅" if len(subtitle) <= 15 else "⚠️ 偏长"
        print(f"  封面    标题最长行 {t_len}字{wrapped} {t_flag}   副标题 {len(subtitle)}字 {s_flag}")
        problems += t_flag.startswith("❌")

    # 静态检查：缺字形的字符（标题与各卡一级标题）
    headings = [title] + re.findall(r'^#\s+(.+)$', body, re.MULTILINE)
    risky = check_risky_glyphs(" ".join(headings))
    if risky:
        print(f"  字形    ❌ 标题含展示字体可能缺失的字符: {'、'.join(risky)}")
        print(f"          → 会渲染成空心方块，改用普通数字或「（上）（下）」")
        problems += 1

    # 主题声明了分类配色，内容却没用 —— 这是「图很单调」最常见的原因
    tokens = theme_registry.load_tokens(theme)
    if tokens.get("palette") and "palette" not in body:
        print(f"  配色    ⚠️ 主题 {theme} 定义了 {len(tokens['palette'])} 色分类配色，但版式里没用")
        print(f"          → 并列内容加 class=\"grid grid-N palette\" 或 palette-solid")

    if mode == 'auto-split':
        card_contents = await auto_split_content(body, theme, width, height, dpr)
    else:
        card_contents = split_content_by_separator(body)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={'width': width, 'height': height if mode != 'dynamic' else max_height},
            device_scale_factor=dpr,
        )
        try:
            if metadata.get('emoji') or title:
                variants = split_cover_variants(cover_body)
                for vi, variant in enumerate(variants):
                    tag = "封面" if len(variants) == 1 else f"封面{chr(97 + vi).upper()}"
                    crowd = cover_crowding_warning(variant)
                    if crowd:
                        print(f"  {tag}    ⚠️ {crowd}")
                    cover_html = generate_cover_html(metadata, theme, width, height, variant)
                    issue = await _cover_line_report(page, cover_html, width, height)
                    if issue:
                        print(f"  {tag}    ❌ {issue}")
                        print(f"          → 用 <br> 手动断行，或缩短标题")
                        problems += 1
                if len(variants) > 1:
                    print(f"  封面    {len(variants)} 版备选")

            for i, content in enumerate(card_contents, 1):
                html = generate_card_html(content, theme, i, len(card_contents), width, height, mode)
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                    f.write(html)
                    tmp = f.name
                try:
                    await page.goto(f'file://{tmp}')
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_timeout(200)
                    actual = await page.evaluate('''() => {
                        const c = document.querySelector('.card-container');
                        return c ? c.scrollHeight : document.body.scrollHeight;
                    }''')
                finally:
                    os.unlink(tmp)

                # 内容底部到画布底的空白比例 —— 偏大说明这张卡该加内容或合并
                fill = await page.evaluate('''(h) => {
                    const c = document.querySelector('.card-content');
                    if (!c) return null;
                    const kids = Array.from(c.querySelectorAll(':scope > * > *, :scope > *'));
                    const bottoms = kids.map(k => k.getBoundingClientRect().bottom).filter(b => b > 0);
                    if (!bottoms.length) return null;
                    return Math.max(...bottoms) / h;
                }''', height)

                if mode in ('dynamic', 'auto-fit') or actual <= height:
                    hint = ""
                    if fill is not None and fill < 0.62 and mode == 'separator':
                        hint = f"  ⚠️ 内容仅占 {fill*100:.0f}% 高度，偏空"
                    print(f"  卡片 {i}  渲染高度 {actual}px / {height}px  ✅{hint}")
                else:
                    print(f"  卡片 {i}  渲染高度 {actual}px / {height}px  ❌ 溢出 {actual - height}px")
                    problems += 1
        finally:
            await browser.close()

    report = material_report()
    if report.resolved:
        print(f"  素材    已解析 {len(report.resolved)} 个")
    for src in dict.fromkeys(report.missing):
        print(f"  素材    {src}  ❌ 文件不存在")
        problems += 1
    for src, reason in report.errors:
        print(f"  素材    {src}  ❌ {reason}")
        problems += 1

    if sample:
        # 与样图的客观差距。放在最后是因为它给的是"像不像"的信号，
        # 而上面那些是"对不对"的硬错误 —— 硬错误没修完看差距没意义。
        import subprocess
        with tempfile.TemporaryDirectory() as tmpd:
            probe_card = os.path.join(tmpd, 'probe.png')
            idx = min(1, len(card_contents) - 1)
            html = generate_card_html(card_contents[idx], theme, idx + 1,
                                      len(card_contents), width, height, mode)
            await render_html_to_image(html, probe_card, width, height, mode, max_height, 1)
            probe = Path(__file__).resolve().parent / 'style_probe.py'
            print()
            subprocess.run([sys.executable, str(probe), sample, probe_card])

    print(f"\n{'✨ 未发现问题，可以出图' if not problems else f'⚠️  发现 {problems} 处问题'}")
    return problems == 0


async def render_markdown_to_cards(md_file: str, output_dir: str,
                                   theme: str = 'dark-gold',
                                   mode: str = 'separator',
                                   width: int = DEFAULT_WIDTH,
                                   height: int = DEFAULT_HEIGHT,
                                   max_height: int = MAX_HEIGHT,
                                   dpr: int = 2):
    """主渲染函数：将 Markdown 文件渲染为多张卡片图片"""
    print(f"\n🎨 开始渲染: {md_file}")
    print(f"  📐 主题: {theme}")
    print(f"  📏 模式: {mode}")
    print(f"  📐 尺寸: {width}x{height}")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 解析 Markdown 文件
    data = parse_markdown_file(md_file)
    metadata = data['metadata']
    body = data['body']
    cover_body, body = split_cover_body(body)

    # 根据模式处理内容分割
    if mode == 'auto-split':
        print("  ⏳ 自动分析内容并切分...")
        card_contents = await auto_split_content(body, theme, width, height, dpr)
    else:
        card_contents = split_content_by_separator(body)
    
    total_cards = len(card_contents)
    print(f"  📄 检测到 {total_cards} 张正文卡片")
    
    # 生成封面
    if metadata.get('emoji') or metadata.get('title'):
        print("  📷 生成封面...")
        variants = split_cover_variants(cover_body)
        # 单版沿用 cover.png；多版用 cover-a/b/c 对称命名，方便并排挑选
        for vi, variant in enumerate(variants):
            name = 'cover.png' if len(variants) == 1 else f'cover-{chr(97 + vi)}.png'
            cover_html = generate_cover_html(metadata, theme, width, height, variant)
            await render_html_to_image(cover_html, os.path.join(output_dir, name),
                                       width, height, 'separator', max_height, dpr)
        if len(variants) > 1:
            print(f"  ↑ 封面 {len(variants)} 版备选，挑一版留下")
    
    # 生成正文卡片
    for i, content in enumerate(card_contents, 1):
        print(f"  📷 生成卡片 {i}/{total_cards}...")
        card_html = generate_card_html(content, theme, i, total_cards, width, height, mode)
        card_path = os.path.join(output_dir, f'card_{i}.png')
        await render_html_to_image(card_html, card_path, width, height, mode, max_height, dpr)

    warn_materials(material_report())
    print(f"\n✨ 渲染完成！图片已保存到: {output_dir}")
    return total_cards


def main():
    parser = argparse.ArgumentParser(
        description='将 Markdown 文件渲染为小红书风格的图片卡片（支持多种样式和分页模式）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''可用主题:
''' + ''.join(
            f"  {n:<20}- {theme_registry.load_tokens(n).get('label', '')}"
            f"{'' if n in theme_registry.BUILTIN_THEMES else '（自定义）'}\n"
            for n in AVAILABLE_THEMES
        ) + '''
分页模式:
  separator   - 按 --- 分隔符手动分页（默认）
  auto-fit    - 自动缩放文字以填满固定尺寸
  auto-split  - 根据内容高度自动切分
  dynamic     - 根据内容动态调整图片高度
'''
    )
    parser.add_argument(
        'markdown_file',
        help='Markdown 文件路径'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default=os.getcwd(),
        help='输出目录（默认为当前工作目录）'
    )
    parser.add_argument(
        '--theme', '-t',
        choices=AVAILABLE_THEMES,
        default='dark-gold',
        help='排版主题（默认: dark-gold）'
    )
    parser.add_argument(
        '--mode', '-m',
        choices=PAGING_MODES,
        default='separator',
        help='分页模式（默认: separator）'
    )
    parser.add_argument(
        '--width', '-w',
        type=int,
        default=DEFAULT_WIDTH,
        help=f'图片宽度（默认: {DEFAULT_WIDTH}）'
    )
    parser.add_argument(
        '--height',
        type=int,
        default=DEFAULT_HEIGHT,
        help=f'图片高度（默认: {DEFAULT_HEIGHT}）'
    )
    parser.add_argument(
        '--max-height',
        type=int,
        default=MAX_HEIGHT,
        help=f'dynamic 模式下的最大高度（默认: {MAX_HEIGHT}）'
    )
    parser.add_argument(
        '--dpr',
        type=int,
        default=2,
        help='设备像素比（默认: 2）'
    )
    parser.add_argument(
        '--materials-dir',
        default=None,
        help='素材（SVG/图片）所在目录（默认: markdown 文件所在目录）'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='只体检不出图：报告每张卡的渲染高度、溢出、缺失素材、封面字数'
    )
    parser.add_argument(
        '--no-page-number',
        action='store_true',
        help='不渲染右下角的 n/N 页码'
    )
    parser.add_argument(
        '--sample',
        default=None,
        help='样图路径。配合 --dry-run 时，出图后自动跑 style_probe 量与样图的差距'
    )

    args = parser.parse_args()

    global SHOW_PAGE_NUMBER
    SHOW_PAGE_NUMBER = not args.no_page_number

    if not os.path.exists(args.markdown_file):
        print(f"❌ 错误: 文件不存在 - {args.markdown_file}")
        sys.exit(1)

    configure_materials(args.markdown_file, args.materials_dir)

    if args.dry_run:
        ok = asyncio.run(measure_only(
            args.markdown_file,
            theme=args.theme,
            mode=args.mode,
            width=args.width,
            height=args.height,
            max_height=args.max_height,
            dpr=args.dpr,
            sample=args.sample,
        ))
        sys.exit(0 if ok else 1)

    asyncio.run(render_markdown_to_cards(
        args.markdown_file,
        args.output_dir,
        theme=args.theme,
        mode=args.mode,
        width=args.width,
        height=args.height,
        max_height=args.max_height,
        dpr=args.dpr
    ))


if __name__ == '__main__':
    main()
