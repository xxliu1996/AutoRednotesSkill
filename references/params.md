# 参数参考

## render_xhs.py — 渲染 / 体检

```bash
python scripts/render_xhs.py <content.md> [选项]
```

| 参数 | 简写 | 说明 | 默认 |
|---|---|---|---|
| `--output-dir` | `-o` | 输出目录 | 当前工作目录 |
| `--theme` | `-t` | 排版主题 | `dark-gold` |
| `--mode` | `-m` | 分页模式 | `separator` |
| `--materials-dir` | | 素材目录 | md 文件所在目录 |
| `--dry-run` | | 只体检不出图 | — |
| `--page-number` | | 在右下角渲染 `n/N` 页码。**默认不渲染，一般也不要开**：真实小红书图没有页码，带上就露出"批量生成"的痕迹 | 不显示 |
| `--sample` | | 样图路径，配合 `--dry-run` 量与样图的客观差距 | — |
| `--width` | `-w` | 图片宽度（px） | `1080` |
| `--height` | | 图片高度（`dynamic` 下为最小高度） | `1440` |
| `--max-height` | | `dynamic` 模式下的最大高度 | `4320` |
| `--dpr` | | 设备像素比（清晰度） | `2` |

`--dry-run` 检查：卡片溢出、卡片偏空、封面字数、**封面孤字**、**缺字形字符**、
**分类配色声明了却没用**、素材缺失。发现问题时退出码为 1，可用于脚本串联。

加 `--sample sample.png` 会额外渲染一张代表卡片并跑 `style_probe` 对比。
完整自检流程见 `qa-checklist.md`。

### 主题

这个发布版本只收录 4 套从真实小红书样图提取的主题，没有通用内置主题：

| 值 | 名称 |
|---|---|
| `dark-gold` | 深蓝底 + 金色标题（默认），行标签对比矩阵 |
| `marker-duo` | 米橙底 + 黑橙双色大标题，放射状 Hub、之字形时间轴 |
| `kraft-marker` | 牛皮纸底 + 马克笔高光/黄色荧光笔框，贴纸标签 |
| `scrapbook-kai` | 卡其灰底 + 楷体正文 + 标题逐词换色，便签/卷轴/虚线框剪贴报 |

主题是 `assets/themes/<slug>.json` + `.css` 自动发现的，加一套新主题不需要
改任何源码。查看当前可用主题：`python scripts/themes.py`

### 分页模式

| 值 | 说明 | 适用场景 |
|---|---|---|
| `separator` | 按 `---` 分隔符分页 | 内容已手动控量，需要精确分页 |
| `auto-fit` | 固定尺寸，自动整体缩放内容 | 封面 + 单张图，尺寸固定不溢出 |
| `auto-split` | 根据渲染后高度自动切分 | 内容长短不稳定，通用推荐 |
| `dynamic` | 根据内容动态调整图片高度 | 允许不等高卡片，字数 ≤550 |

### 示例

```bash
# 默认：dark-gold 主题 + 手动分隔
python scripts/render_xhs.py content.md

# 出图前体检
python scripts/render_xhs.py content.md --dry-run

# 自动分页 + 切主题
python scripts/render_xhs.py content.md -t marker-duo -m auto-split

# 带素材
python scripts/render_xhs.py content.md -t kraft-marker --materials-dir ./materials -o out/

# 自定义尺寸
python scripts/render_xhs.py content.md -t kraft-marker -m dynamic -w 1080 --height 1440 --dpr 2
```

---

## build_theme.py — 风格 token → 主题 CSS

```bash
python scripts/build_theme.py --new <slug>                 # 生成 token 骨架
python scripts/build_theme.py assets/themes/<slug>.json    # 生成 CSS
```

### token 字段

**必填**（5 项）

| 字段 | 说明 |
|---|---|
| `label` | 主题中文名 |
| `bg_card` | 卡片外层背景（纯色或渐变） |
| `title_gradient` | 封面大标题的文字渐变 |
| `ink` | 正文墨色 —— **决定整套主题的明暗走向**，其余默认值由它推导 |
| `accent` | 全局强调色（大标题、结论块） |

**选填**（留空则自动推导）

| 字段 | 默认来源 |
|---|---|
| `bg_cover` | 同 `bg_card` |
| `palette` | 分类配色数组（最多 6 色），给 `.grid.palette` 逐栏取用；不填则分栏用中性默认色 |
| `accent_2` | 由 `accent` 推同族深/浅变体 |
| `surface` / `cover_surface` | 由 `ink` 的明暗判断走近白还是近黑 |
| `cover_ink` | 同 `ink` |
| `material_accent` | 同 `accent` |
| `page_number_color` | `ink` 加 45% 透明度 |
| `radius` | `20` |
| `border` | `none` |
| `shadow` | `0 8px 32px rgba(0,0,0,0.1)` |
| `content_align` | `flex-start`（顶对齐）。设 `center` 让内容在卡片里垂直居中 |
| `font_title` / `font_body` | Noto Sans SC 系列 |
| `fs_body` / `fs_h1` / `fs_h2` / `fs_h3` | `42` / `72` / `56` / `48` |
| `line_height` | `1.8` |
| `font_license_note` | 无。用到需授权字体时**必须**填，生成时会打印提醒 |

### 逃生舱

`assets/themes/<slug>.custom.css` 若存在，自动追加在生成的主题 CSS 之后，
可覆盖任何规则。token schema 是固定槽位，表达不了的结构性特征（票根缺口、
手写下划线、斜切色带…）直接写 CSS，不需要先改 schema。

取色用 `var(--c-accent)` 等变量而非写死，分类配色才能穿透。

提取方法见 `style-extraction.md`。

---

## fetch_images.py — 图库检索

```bash
python scripts/fetch_images.py "关键词" -o ./assets [选项]
```

| 参数 | 说明 | 默认 |
|---|---|---|
| `-o` `--out` | 输出目录（候选落在 `<out>/candidates/`） | 当前目录 |
| `-n` `--count` | 候选数量 | `6` |
| `--type` | `all` / `photo` / `illustration` / **`vector`** | `all` |
| `--orientation` | `all` / `horizontal` / `vertical` | `all` |
| `--min-width` | 最小宽度 | `1200` |
| `--lang` | 搜索语言 | `en` |
| `--order` | `popular` / `latest` | `popular` |

产物：候选图 + **联系表 PNG**（带编号，Read 一次看全部）+ `MANIFEST.md`（出处与授权）。

**`--type vector` 是唯一返回真透明 PNG 的**，深色主题首选；代价是最大 1280px，
`--min-width` 要调到 700-900。

API key：`PIXABAY_API_KEY` 环境变量或 `<skill>/.pixabay_key`。
限流 100 次 / 60 秒。详见 `image-sourcing.md`。

---

## style_probe.py — 风格探针

```bash
python scripts/style_probe.py <样图>                 # 量单图
python scripts/style_probe.py <样图> <预览图>         # 量差距
```

| 参数 | 说明 | 默认 |
|---|---|---|
| `-k` | 提取几个主色 | `6` |

单图模式输出主色及占比、平均亮度、明暗对比、平均饱和、**高饱和色块占比**
（这个数 >30% 通常意味着分类配色）。

双图模式在此基础上给出五个维度的差值与色板距离，把"像不像"从主观争论
变成可逐轮收敛的数字。指标是信号不是判决 —— 探针量不出字形气质与版式节奏。

---

## preview_theme.py — 单主题预览

```bash
python scripts/preview_theme.py <theme> [选项]
```

| 参数 | 说明 | 默认 |
|---|---|---|
| `--content` | 预览用的 md | `assets/example.md` |
| `--card` | 预览第几张正文卡 | `1` |
| `--output-dir` `-o` | 输出目录 | `./preview` |
| `--dpr` | 像素比 | `1`（预览求快） |

出一张封面 + 一张正文卡，用于与样图并排比对。比跑完整 `content.md` 快得多。

---

## check_deps.sh — 依赖

```bash
bash scripts/check_deps.sh
```

建 `.venv` 并安装 markdown / PyYAML / playwright + chromium。幂等，重复跑是快速 no-op。

之后每次跑脚本前 `source .venv/bin/activate`。
