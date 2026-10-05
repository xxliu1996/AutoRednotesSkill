---
name: xhs-card-studio
description: 小红书图文卡片生成技能。从一份 content.md 生成 3:4（1080×1440）的封面 + 正文卡片图，全程 HTML + Chromium 渲染，不用 AI 生图。当用户需要制作小红书图文、笔记配图、多图轮播卡片时使用。支持版式组件（多栏栅格、编号圆徽、正反对比、步骤流）、渲染前内容审查、SVG 素材内联、从样板图片提取风格生成自定义主题，收录 4 套从真实小红书样图提取的主题与 4 种分页模式。
---

# 小红书图文卡片

输入一份 `content.md`，输出一组风格统一的 3:4 卡片图。

**不代写内容** —— 内容由用户在 `content.md` 里定稿，我负责审查、配风格、出图。
**不负责发布** —— 只出图片文件。

---

## 工作流

### 第一步：选模板

调用 skill 时先问用户挑哪个模板（除非用户已经在请求里指定了主题名或给了样图）：

| 模板 | 主题名 | 视觉语言 | 适合内容 |
|---|---|---|---|
| **A** | `dark-gold` | 深蓝底 + 金色标题，行标签对比矩阵 | 财经、评测、多方案对比 |
| **B** | `marker-duo` | 米橙底 + 黑橙双色大标题，放射 Hub、之字形时间轴 | 职场干货、步骤教程 |
| **C** | `kraft-marker` | 牛皮纸底 + 马克笔高光/黄色荧光笔框，贴纸标签 | 科普、知识点讲解 |
| **D** | `scrapbook-kai` | 卡其灰底 + **楷体正文** + 标题逐词换色，便签/图钉/卷轴/虚线框剪贴报 | 财经科普、书单、清单盘点 |

这个发布版本只收录这 4 套从真实样图提取的主题，没有通用内置主题——用户想要
另一种视觉语言时走第三步 A「从样板图片提取」，不是从内置列表里选。

`scrapbook-kai` 有一批自己的专属组件（便签 `.sticky`、卷轴 `.scroll-note`、
橙边正文框 `.note-panel`、虚线卡 `.dash-card`、空心方框待办 `.todo`、
逐词换色 `.w-red/.w-green/.w-amber`、免责声明条 `.disclaimer`、
巨字标语卡 `.shout` + `.shout-line`/`.shout-sub`、竖排档位标签 `.side-tag`），
定义在 `assets/themes/scrapbook-kai.custom.css`，用之前先看一眼那个文件。

同一篇笔记里**不要每张卡都用同一套骨架**。`.shout` 这种整屏巨字卡不配图也能
撑住一整张，`.side-tag` 配 `grid-side` 做图文分栏，`.dash-card` 栅格加
`palette` 还能让并列项各拿一个调色盘色——先把可用版式列出来，再给每张卡分配
一种，避免连续几张都是「h1 → 正文框 → 卷轴」。

用 `AskUserQuestion` 问，每个选项配一句适用场景。用户也可以跳过这一步直接说
"从这张样图提取风格"或"用 xxx 主题"。

### 第二步：内容审查

先读 `content.md`，跑客观体检，再输出一份 `REVIEW.md` 给用户确认。

```bash
python scripts/render_xhs.py content.md --dry-run
```

体检报告每张卡的渲染高度与溢出量、缺失素材、封面字数。**先跑它再写 REVIEW.md** —— 客观数字能佐证主观判断。

然后按 `references/content-review.md` 的清单读 md，逐卡列「现状 → 建议 → 原因」。

**报告问题、给出建议，但不擅自改写用户的文案。** 用户确认或说"按你的建议改"之后才动 md。

跳过这一步的唯一情况：用户明确说了不用审查。

### 第三步：定风格

第一步选的 A/B/C/D 四套已经是现成主题，直接用最省事。用户想要另一种视觉语言、
且不在这 4 套里时，二选一：

**A. 从样板图片提取**（用户给了样图时）

读 `references/style-extraction.md`。这是一个**循环**不是一张清单 —— 先用探针量出客观数据，我据此判断，建完再量差距，迭代到收敛：

```bash
python scripts/style_probe.py sample.png          # 量：主色占比、明暗、饱和分布
python scripts/build_theme.py --new my-style      # 我据此填 token（必填只有 5 项）
python scripts/build_theme.py assets/themes/my-style.json
python scripts/preview_theme.py my-style -o preview
python scripts/style_probe.py sample.png preview/preview-my-style-card.png   # 量差距
```

**token 表达不了的写进 `assets/themes/my-style.custom.css`** —— 自动追加在生成的 CSS 之后，可覆盖任何规则。这是逃生舱：新参考图只要有一个我没设槽位的特征（票根缺口、手写下划线、斜切色带…），token 就表达不了，而不断给 schema 加槽位永远慢参考图一步。凡是 CSS 能表达的直接写。

**看样图时同时记下它用了哪些版式组件**（几栏、有没有编号圆徽、有没有分区标签、
有没有对比结构）—— 那部分不进 token，进第三步的版式设计。样图之所以比默认输出
好看，多半赢在版式而不是配色。

自定义主题会被自动发现，`-t my-style` 即可用。

**B. 用户直接给配色要求** —— 同 A，跳过看图，直接写 token。

### 第四步：设计版式 ⭐

**这一步决定卡片好不好看，不能跳过。**

只靠主题 token 出来的卡片一定单调 —— token 管颜色字体，版式永远是「标题 → 段落 → 列表」
的单栏流。多栏并排、编号圆徽、分区面板、正反对比，都要用组件在 `content.md` 里搭出来。

**读 `references/layout-authoring.md`**，按内容的**结构**选组件：

| 内容形态 | 用什么 |
|---|---|
| N 个并列的东西 | `grid` + `panel-capped`（N=4 优先 2×2） |
| N 类人群 / 场景 | `grid-3` + `badge-sm` |
| 有先后的流程 | `steps` |
| 两个方案对照 | `vs` |
| 一堆数字 | `stats` |
| 单个结论 | `highlight` |

在 `content.md` 里直接写 HTML 和 markdown 混排，不用手写 `markdown="1"`（自动补齐）：

```markdown
<div class="grid grid-2">
<div class="panel-capped">
<div class="cap">功能名</div>
<div class="body">一句话说明，可以写 **加粗** 和列表。</div>
</div>
…
</div>
```

**改完必须重跑 `--dry-run`** —— 组件比纯文本容易溢出得多。

### 多主题防串味 ⚠️

**同一份 content.md 要给多个主题分别出图时，每个主题的 `content_cards_<theme>.md`
必须独立设计版式，不能把 A 主题写好的文件复制过去改个标题当 B 主题用。**

这是真实踩过的坑：`kraft-marker` 和 `marker-duo` 的内容一度是同一套骨架改的——
标题换成 `.marker` 高光、图标换个文件，结构照搬（同样的 2 栏 hub、同样的
"大图+一段话"卡）。两个主题各自的真实样图其实有完全不同的版式语言
（`kraft-marker` 是马克笔高光+贴纸标签；`marker-duo` 是放射状 hub 绕一圈+
之字形时间轴带描边卡片），复制来的骨架跟哪个主题的样图都对不上，用户一眼
就看出"这个版式眼熟，好像是另一个主题的"。

**规则**：

1. 不要以任何已写好的 `content_cards_<其他主题>.md` 作为起草模板去复制/
   查找替换。同一份 `content.md` 的信息要给几个主题各自重新组织一遍结构——
   哪些信息适合放进放射 hub、哪些适合时间轴、哪些该单独成卡，每个主题的
   答案可能不一样，这本身就是版式设计的一部分，不是机械转译。
2. 组件名字相同不代表效果相同——`.hub`、`.timeline` 是跨主题的通用组件，
   但"要不要用、用成什么形态"（`hub-radial` 还是默认 2 栏、`tl-box` 加框
   还是裸文字）要看**这个主题**的 custom.css 和 `layout-authoring.md`
   「主题专属组件」一节怎么记录的，不能照抄另一个主题里同名组件的用法。
3. 图源同理：一个主题验证过的配图关键词/风格（写实照片、卡通拟人、扁平
   插画……）不要顺手带进另一个主题，先看 `image-sourcing.md`。

### 第四步补充：配图（可选）

内容需要图但用户没提供时，从图库检索：

```bash
export PIXABAY_API_KEY=...   # 用户自己申请，见 references/image-sourcing.md
python scripts/fetch_images.py "tank military history" -o ./assets -n 6 --type vector --min-width 700
```

抓 6 张候选 + 拼一张**联系表**（带编号，Read 一次看全部）+ 记好出处到 MANIFEST.md。
**选哪张、放哪里、多大由我判断** —— 相关度排第一的未必配得上文案。

**深色主题优先 `--type vector`** —— 只有它返回真透明 PNG，剪影浮在满版深色底上
不用加相框。代价是最大 1280px，`--min-width` 要调到 700-900。

关键词用**具体的物**（`tank military` 而不是 `history`），抽象词返回的多是概念图标。
我负责把中文文案翻成检索词。

详见 `references/image-sourcing.md`。

**并排放的配图必须先裁成同一比例**，否则 `size=md` 只约束宽度，
每张的高度都不一样，下面的名字标签参差不齐，一眼就是"随手贴的"：

```bash
# 人像：按人脸位置对齐，统一裁成 3:4
python scripts/crop_portraits.py images/*.jpg -o images/cropped --ratio 3:4

# logo / 奖章 / 图表这类不能裁的：补边成同一比例，不切内容
python scripts/crop_portraits.py images/logo.png -o images/cropped \
    --ratio 3:4 --no-crop --bg "#DEDCCD"
```

裁完把 md 里的路径指向 `images/cropped/`。锚点取人脸中心、纵向 0.42 处，
不是几何中心——横幅照片里人往往不在正中间，几何居中会把人裁掉半张脸。

### 第五步：出图与自检

**出图前必跑自检，别等用户指出问题。**

```bash
python scripts/render_xhs.py content.md -t <theme> --dry-run
# 有样图时加 --sample sample.png，额外量与样图的客观差距
```

自动检查溢出、卡片偏空、封面孤字、缺字形字符、分类配色未用、素材缺失。
每一条都对应一次真实踩过的坑 —— 读 `references/qa-checklist.md`，
里面还有脚本量不出、需要我自己看的部分。

**用户只该为两件事介入：文案取舍、审美拍板。** 溢出怎么改、字形方块怎么换、
素材太大、要不要用分类配色 —— 这些有确定答案，自己修完在交付说明里带一句即可。

```bash
python scripts/render_xhs.py content.md -t <theme> -o out/
```

生成 `cover.png` + `card_1.png`、`card_2.png`…，默认 1080×1440 @ dpr 2（实际 2160×2880）。

有素材时加 `--materials-dir`：

```bash
python scripts/render_xhs.py content.md -t kraft-marker --materials-dir ./materials -o out/
```

---

## content.md 格式

```markdown
---
emoji: "🚀"
title: "主题<br>数字承诺"   # 可用 <br> 手动断行，字号按最长的一行算
subtitle: "封面副标题"     # ≤15 字，无自动缩放，超了会溢出
---

<div class="grid grid-2 palette-solid">
<div class="panel center">要点一</div>
<div class="panel center">要点二</div>
</div>

# 第一张卡的标题

正文，**加粗**，`行内代码`。

> 引用块

- 列表项
- 列表项

---

# 第二张卡的标题

用 `---` 手动分隔卡片。
```

结尾可以放标签：`#效率工具 #数字生产力`，会渲染成标签胶囊。

**封面正文**：frontmatter 与第一个 `# ` 之间的内容归封面，走和正文卡**完全一样**的管线 ——
组件库、素材内联、分类配色全都能用。留空就是老样子（emoji + 标题 + 副标题）。

**宫格和配图只能二选一。** 封面文字区约 780×1150，标题（两行约 340px）和副标题
已占掉大半，留给正文的只有 400px 上下。两样都塞会挤，而且丢焦点 ——
`--dry-run` 会直接报警。

**既然是二选一，就别替用户选：默认出两版让人挑。** 用 `<!-- or -->` 分隔：

```markdown
---
emoji: "📈"
title: "预测行业趋势<br>4个方法"
subtitle: "普通人也能找到投资机会"
---

<div class="grid grid-2 palette-solid">
<div class="panel center">研究历史</div>
<div class="panel center">观察富人</div>
<div class="panel center">政府规划</div>
<div class="panel center">行业报告</div>
</div>

<!-- or -->

![size=lg align=center](assets/books.png)

# 第一张卡
```

出 `cover-a.png` / `cover-b.png`（单版时仍是 `cover.png`）。交付时并排给用户挑，
挑完删掉没选的那张。

**封面标题**：字号按**最长的一行**自动适配可用宽度，放不下就缩小，不会断出孤字。
用 `<br>` 手动控制断点能把字放大 —— 小红书常见的「主题 + 数字承诺」两行式排版就靠它。

**封面副标题**：优先压成一行（缩几个 px 远比断出「会」这样的孤字好看），
长到压过下限才换行。

**生僻字形**：中文标题字体多为展示字体，字符集不全。`①②③`、`Ⅰ`、`㊙`、`🆚`
会渲染成空心方块 —— `--dry-run` 会自动报出来。标题里改用普通数字或
「（上）（下）」。emoji 一般走系统 emoji 字体不受影响，但少数（如 🆚）有文字形态
回退会被标题字体接管成单色。

---

## 素材（SVG / 图片）

原生 markdown 图片语法，指令写在 alt 文本里：

```markdown
![](materials/icon.svg)                    行内，默认 md 尺寸
![size=lg align=center](materials/flow.svg)
![hero](materials/banner.svg)              卡片顶部通栏
![size=sm recolor](materials/badge.svg)    强制跟随主题色
```

| 指令 | 取值 |
|---|---|
| `size` | `sm` 120px / `md` 220px / `lg` 380px / `xl` 560px / `hero` 通栏 |
| `align` | `left` `center` `right`（左右为浮动，正文绕排） |
| `recolor` | 默认只换填充；`recolor=stroke` 只换描边；`recolor=all` 都换 |

**SVG 会被内联**，所以 `fill="currentColor"` 的路径自动跟随主题色 —— 同一组素材换主题就换色。内联前会剔除 `<script>`、事件处理器、外链资源。

素材找不到时渲染成刺眼的红色占位块，不会静默留白。想让某个元素豁免 recolor，在 SVG 里给它加 `data-keep`。

**注意**：`recolor` 一刀切会毁掉双色图形（蓝底 + 白勾会糊成一块），所以默认只换填充。线性图形要显式写 `recolor=stroke`。

---

## 参数速查

```bash
python scripts/render_xhs.py <content.md> [选项]
```

| 参数 | 说明 | 默认 |
|---|---|---|
| `-o` | 输出目录 | 当前目录 |
| `-t` | 主题 | `dark-gold` |
| `-m` | 分页模式 | `separator` |
| `--materials-dir` | 素材目录 | md 文件所在目录 |
| `--dry-run` | 只体检不出图 | — |
| `--page-number` | 在右下角渲染 `n/N` 页码（**一般不要加**） | 不显示 |
| `--sample` | 样图路径，配合 `--dry-run` 量与样图的差距 | — |
| `-w` / `--height` | 画布尺寸 | 1080 / 1440 |
| `--dpr` | 像素比 | 2 |

**分页模式**：`separator` 按 `---` 手动分（默认）｜ `auto-split` 按渲染高度自动切（内容长短不定时用）｜ `auto-fit` 固定尺寸整体缩放 ｜ `dynamic` 按内容撑高（允许不等高卡片）

完整参数见 `references/params.md`。

---

## 首次使用

```bash
bash scripts/check_deps.sh
```

建本 skill 自己的 `.venv`，装 markdown / pyyaml / playwright + chromium。幂等，重复跑是快速 no-op。

之后每次跑脚本前先 `source .venv/bin/activate`。

---

## 文件结构

```
scripts/
  render_xhs.py       主渲染（含 --dry-run 体检）
  themes.py           主题注册表：自动发现 assets/themes/*.json 主题
  materials.py        素材内联与 SVG 清洗
  build_theme.py      风格 token → 主题 CSS
  preview_theme.py    单主题预览（封面 + 一张正文卡）
  style_probe.py      风格探针：量样图色板/明暗；给两张图则对比
  fetch_images.py     图库检索：抓候选 + 拼联系表 + 记出处（Pixabay）
  crop_portraits.py   配图统一裁剪：人像对齐人脸，不可裁的图改为补边
  check_deps.sh       依赖安装
assets/
  themes/*.css        主题样式
  themes/*.json       自定义主题的风格 token
  themes/_template.css.tpl   token → CSS 的模板
  themes/*.custom.css        手写 CSS 逃生舱（可选，覆盖生成规则）
  components.css      版式组件库（栅格/面板/圆徽/对比/步骤流）
  materials.css       素材样式
references/
  qa-checklist.md     交付前自检（脚本检查 + 人工清单）⭐
  image-sourcing.md   自动配图：检索、选图、摆放判断
  layout-authoring.md 版式组件清单与选型判断 ⭐
  content-review.md   内容审查清单 + REVIEW.md 格式
  style-extraction.md 看样图提取风格的方法
  params.md           完整参数
demos/
  content.md              基础示例
  content_materials.md    素材用法示例
  materials/              示例 SVG
```

---

## 改动记录

本 skill fork 自 [comeonzhj/Auto-Redbook-Skills](https://github.com/comeonzhj/Auto-Redbook-Skills)（MIT），在其基础上：

- **新增素材内联** —— 原版靠临时文件渲染，相对路径素材必然 404
- **新增样图风格提取** —— 原版主题身份硬编码在 5 处，新增一个主题要同时改 5 个地方
- **新增版式组件库** —— 原版只有单栏文本流，无论换什么主题都只能出「标题+段落+列表」，这是输出单调的根因
- **新增渲染前内容审查与交付自检** —— 原版无内容质量检查
- **修掉封面标题孤字** —— 原版字号只按字数查表、不校验放不放得下，6 个汉字按「极大」档
  是 151px（连起来 906px），而封面文字区只有 780px，于是断行留下孤字。
  原版 `demos/content.md` 自己就中招（「5个效率神 / 器」）。现按可用宽度反算字号，
  汉字与拉丁字母分开估宽，并留 8% 余量（`font-weight:900` 合成加粗会让字形变宽）。
- **素材按显示尺寸压缩** —— base64 内联，1.9MB 实拍图会让单页 HTML 膨胀到 4MB+。
  `size` 指令已经声明了显示宽度，据此缩放；带透明通道的保留 PNG，其余转 JPEG。
- **删除发布功能** —— 不需要，也就不必配 Cookie
- **删除 3 份冗余渲染器**（v2 与两个 JS 版）—— 同功能四份实现，改动要做四遍

**与原版的一致性**：主题收口重构本身零行为变更（8 套内置主题 × 4 种分页模式曾逐字节一致）。
封面字号修复后，封面部分**有意偏离**原版 —— 修的是上游缺陷。正文卡片部分仍与原版一致。
