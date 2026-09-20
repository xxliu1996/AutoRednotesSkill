# 版式设计

**这一层决定卡片好不好看，比配色重要得多。**

主题 token 只能换颜色、字体、圆角；版式默认永远是「标题 → 段落 → 列表」的单栏流。
只靠 token 做出来的卡片必然单调 —— 多栏并排、编号圆徽、分区面板、正反对比，
这些都要在 `content.md` 里用组件搭出来。

组件全部用 `var(--c-*)` 取色，**8 套内置主题和任何自定义主题都能直接用**，
不需要为每个主题重写。

---

## 怎么用

`content.md` 里直接写 HTML，和 markdown 混排：

```markdown
# 卡片标题

<div class="grid grid-2">

<div class="panel-capped">
<div class="cap">功能名称</div>
<div class="body">
一句话说明，这里可以写 **加粗**、列表、`代码`。
</div>
</div>

<div class="panel-capped">
<div class="cap">另一个功能</div>
<div class="body">
同上。
</div>
</div>

</div>
```

**不用手写 `markdown="1"`** —— 渲染器会按 class 名自动补（`autotag_components`）。
容器类补块级解析，单行类补 span 解析。手写了就以你写的为准。

> 这个自动补齐是必要的：python-markdown 要求 `markdown="1"` 出现在**每一层祖先**上，
> 漏掉任何一层，内部的 `**粗体**` 就会原样输出成星号。多层嵌套时这个坑必踩。

---

## 封面也能用组件

frontmatter 与第一个 `# ` 之间的内容是**封面正文**，和正文卡走同一条管线。

封面是决定点击率的一张，却最容易被做成「emoji + 标题 + 副标题」三行字加一片空。
并列要点做成彩色宫格、放一张去背剪影，都写在这里：

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

# 第一张卡
```

**空间很紧**：封面文字区约 780×1150，标题（两行约 340px）和副标题已占掉大半，
留给正文的通常只有 400px 上下。放两行宫格**或**一张图就满了。

**宫格和配图二选一，不要硬塞。** 两样都放会挤，而且封面丢了焦点就白做了 ——
`--dry-run` 检测到两者同时出现会报警。

**默认出两版让用户挑**，用 `<!-- or -->` 分隔封面正文：

```markdown
<div class="grid grid-2 palette-solid">…</div>

<!-- or -->

![size=lg align=center](assets/books.png)
```

产出 `cover-a.png` / `cover-b.png`。这类取舍是审美判断没有对错，
比起我替用户拍板，出两版给人选成本低得多。

---

## 组件清单

### 栅格 — 多栏并排

```html
<div class="grid grid-2">…</div>   两栏（也可放 4 个做 2×2 宫格）
<div class="grid grid-3">…</div>   三栏
<div class="grid grid-4">…</div>   四栏
<div class="grid grid-side">…</div> 主次不等宽（1 : 1.6）
```

栏数越多字号自动越小（2 栏 0.86em / 3 栏 0.74em / 4 栏 0.62em）。

**分类配色 —— 每栏一个色**（样图里「四栏各一色」就靠这个）：

```html
<div class="grid grid-4 palette">…</div>        每栏的强调色不同
<div class="grid grid-4 palette-solid">…</div>  整栏染色，文字翻白
```

`palette` 只换强调色（标题条、圆徽、边框、加粗、列表标记跟着变），
`palette-solid` 连面板底色一起换 —— 后者就是样图那种「白底标题 + 彩色正文区」的强对比结构。

**不限于 `.grid`** —— `steps`、`stats`，或随便包一层 `<div class="palette">` 裹住几个
`badge-row`，都能逐个分色。

**语义绑定**：不想按栏位序号分配时，直接在子元素上写
`c-blue` `c-red` `c-green` `c-amber` `c-purple` `c-teal`，覆盖序号分配。
适合「风险项固定红、推荐项固定绿」这类需要颜色带含义的场合：

```html
<div class="vs">
  <div class="bad c-red">…</div>
  <div class="mark">VS</div>
  <div class="good c-green">…</div>
</div>
```

颜色来自主题 token 的 `palette` 数组（最多 6 个），主题没定义时用一组中性默认色。
所有组件都通过 `var(--c-accent)` 取色，所以**一处覆盖整栏跟着变**。

> **每个分类色会自动生成两份**：原色用于面板填充（`palette-solid`），
> 提亮/压暗后的版本用于文字和圆徽（`palette`）。
> 从样图取到的分类色通常是**色块填充色**那种饱和度，直接拿来当深色底上的文字会发闷 ——
> 一个变量没法同时服务填充和文字。
**4 栏在 1080 宽下每栏只有约 190px，一栏最多放 6-8 个汉字一行**，超过就压字。
中文内容用 4 栏要非常克制，通常 2×2 宫格比 1×4 好读。

### 面板 — 栅格里的一栏，或独立使用

```html
<div class="panel">普通面板，实色底</div>

<div class="panel-capped">          顶部有色标题条
  <div class="cap">标题</div>
  <div class="body">正文</div>
</div>

<div class="panel-outline">描边面板，不占实色，适合深色满版主题</div>
```

### 编号圆徽

```html
<div class="badge">1</div>       76px 圆徽，块级居中
<div class="badge-sm">1</div>    52px

<div class="badge-row">           圆徽 + 文字横排
  <div class="badge">📥</div>
  <div class="txt">
  **小标题**

  说明文字
  </div>
</div>
```

`badge` 里放数字、emoji 都行。

### 栏内分区 — 样图那种「大白话解释 / 评判标准 / 举例」

```html
<div class="col-title">栏标题</div>      居中、强调色、粗体
<div class="sub-label">评判标准</div>     小号、字间距大、半透明
<hr class="divider">                     虚线分隔
```

### 正反对比

```html
<div class="vs">
  <div class="bad">**旧方案** 说明</div>
  <div class="mark">VS</div>
  <div class="good">**新方案** 说明</div>
</div>
```

### 数据条

```html
<div class="stats">
  <div><span class="num">282%</span><span class="cap">偿付能力</span></div>
  <div><span class="num">4年</span><span class="cap">回本</span></div>
  <div><span class="num">6.5%</span><span class="cap">IRR</span></div>
</div>
```

### 步骤流

```html
<div class="steps">
  <div class="step"><div class="dot">1</div><div class="txt">**第一步** 说明</div></div>
  <div class="step"><div class="dot">2</div><div class="txt">**第二步** 说明</div></div>
</div>
```

自动画连接线，最后一步不画。

### 强调块

```html
<div class="highlight">一句话结论，强调色底</div>
```

一张卡最多一个，多了就没有强调可言。

### 对比矩阵 —— 行标签 + N 列数据

从 dark-gold 样图提取。用真实 `<table>`，不用 div 网格——markdown
的 tables 扩展本来就支持，行列对齐交给浏览器表格布局：

```html
<table class="matrix palette-solid">
<thead><tr><th></th><th>方案A</th><th>方案B</th></tr></thead>
<tbody>
<tr><th>门槛</th><td>高</td><td>低</td></tr>
<tr><th>速度</th><td>慢</td><td>快</td></tr>
</tbody>
</table>
```

第一列（`<th>`）是行名，`thead` 是列头。`palette-solid` 按**列**上色（对应
`palette` 的第 1-6 色）；不加就是单色表格。适合"N 个方案在 M 个维度上对比"。

### 统计数字块 —— 大数字堆叠

配合 `panel-capped` 用，样图那种"头像/logo + 一串大数字"的统计列：

```html
<div class="panel-capped">
<div class="cap">零跑</div>
<div class="body">
<div class="stat-block"><span class="stat-num">596555</span><span class="stat-cap">交付(台)</span></div>
<div class="stat-block"><span class="stat-num">647.3亿</span><span class="stat-cap">营收</span></div>
</div>
</div>
```

配 `grid grid-N palette-solid` 用，一栏一个对象。

### 交错时间线 —— 左右错开的步骤

从 marker-duo 样图提取。中间一条实线（带端点圆点的时间轴质感），步骤标签左右交替：

```html
<div class="timeline">
<div class="tl-step tl-left"><span class="tl-badge">第一步</span><p>说明文字</p></div>
<div class="tl-step tl-right"><span class="tl-badge">第二步</span><p>说明文字</p></div>
</div>
```

`tl-left`/`tl-right` 交替写，不交替就是同一侧堆叠（也能用，只是没有交错感）。
适合 4-8 步、每步说明不长的流程。

**信息量大的步骤（多字段：小标题 + 核心逻辑 + 行动步骤），加 `tl-box`**——
marker-duo 样图的时间轴内容不是一句话，是带描边卡片的多字段堆叠：

```html
<div class="tl-step tl-left tl-box">
<span class="tl-title">方法一：研究历史</span>
<p><strong>核心逻辑：</strong>正文...<br><strong>怎么用：</strong>正文...</p>
</div>
```

`tl-box` 给这一步加描边卡片（`--c-accent` 描边 + `--c-surface` 底），
`tl-title` 是加粗小标题；字段的粗体前缀直接用 markdown `**粗体**` 写在
`<p>` 里，不需要额外组件。信息密度高的内容优先用 `tl-box`，一句话的短步骤
用不加框的默认版即可，两者可以在同一个 `.timeline` 里混用。

### 放射 Hub —— 中心图 + 环绕编号说明

默认版（不加 `hub-radial`）是居中主图 + 两栏堆叠，任何条目数都不会崩，
适合"一个核心概念 + 3-5 个要点"这种不追求精确构图的场合：

```html
<div class="hub">
<div class="hub-image">![size=lg align=center](assets/icon.png)</div>
<div class="hub-items">
<div class="hub-item"><span class="hub-num">1</span><p>说明</p></div>
<div class="hub-item"><span class="hub-num">2</span><p>说明</p></div>
<div class="hub-item span-2"><span class="hub-num">3</span><p>说明</p></div>
</div>
</div>
```

**真正绕一圈的放射版，加 `hub-radial`**——marker-duo 样图
的放射构图是要点真的沿八个方位绕中心一圈，不是两栏堆叠。加 `hub-radial`
后用八个方位类 `pos-n/pos-ne/pos-e/pos-se/pos-s/pos-sw/pos-w/pos-nw`
给每个 `hub-item` 分配位置（任选 3-8 个，不用的方位就是留白，不会因为
条目数变化而崩）：

```html
<div class="hub hub-radial">
<div class="hub-center">
<div class="hub-image">![size=sm align=center](assets/icon.png)</div>
<span class="hub-label">核心概念</span>
</div>
<div class="hub-items">
<div class="hub-item pos-ne"><span class="hub-num">1</span><p>说明</p></div>
<div class="hub-item pos-se"><span class="hub-num">2</span><p>说明</p></div>
<div class="hub-item pos-sw"><span class="hub-num">3</span><p>说明</p></div>
<div class="hub-item pos-nw"><span class="hub-num">4</span><p>说明</p></div>
</div>
</div>
```

4 项优先用四个斜角（`ne/se/sw/nw`），比四正方向（`n/e/s/w`）更紧凑，
四正方向中间会留出较大空白。6-8 项就八个方位挑着用，跟样图一样"绕一圈"。
`hub-center` 是必须的包装层（图 + 标签一起居中），不能像默认版那样图和
`hub-items` 是平级兄弟——`hub-radial` 需要把图和标签锁定在圆心。

### 十字象限图 —— 真坐标轴，不是四宫格

从 marker-duo 样图提取。**跟 `.grid.grid-2` 四宫格的区别**：
这个组件画了一条真的十字轴线穿过中间，视觉上是"一张图表"而不是"排版网格"，
适合内容本身就是两个维度交叉、四个象限各自独立的场合（比如"哪些行为会/
不会导致某个结果"），**不要为了凑密度硬套**——4 条不构成两个维度对照的
要点，用普通 `.grid.grid-2` 或 `hub-radial` 更合适：

```html
<div class="quadrant">
<div class="quad-item"><span class="q-title">学生思维</span><span class="q-sub">绊住职场晋升</span><p>说明文字</p></div>
<div class="quad-item"><span class="q-title">不会汇报</span><span class="q-sub">埋头干活难被见</span><p>说明文字</p></div>
<div class="quad-item"><span class="q-title">不会沟通</span><span class="q-sub">回避沟通成隐形人</span><p>说明文字</p></div>
<div class="quad-item"><span class="q-title">不会复盘</span><span class="q-sub">经验难沉淀</span><p>说明文字</p></div>
</div>
```

`q-title` 是象限标题（加粗强调色），`q-sub` 是小一号的副标题行，都是可选——
只写 `<p>` 也能用，只是少了样图那种"标题+副标题"的两级强调感。

### 图标格 —— 图 + 说明堆叠

配合 `grid` 用，"一排头像/图标各配一个名字"：

```html
<div class="grid grid-3">
<div class="icon-tile">![size=sm align=center](assets/a.png)<span class="cap">名字</span></div>
…
</div>
```

跨主题基础版在 `components.css`；风格化主题（如 `kraft-marker`）会在
`custom.css` 里把 `.cap` 换成贴纸胶囊之类的形态。

### 微调

`center` 居中 ｜ `muted` 半透明 ｜ `accent` 强调色 ｜ `tight` 压缩间距

### 主题专属组件

不是每个组件都跨主题——`kraft-marker` 有 `.marker`（橙色马克笔扫过，句中
关键词高光用）、`.hl-box`（黄色荧光笔实色方框，整段小标题/短语套框用，
比 `.marker` 更常用）和 `.sticker`（不规则圆角贴纸标签），定义在它自己的
`custom.css` 里，换主题不一定有对应效果。用之前看一眼那套主题的
`custom.css` 里有没有。`kraft-marker` 的图标全是扁平卡通/矢量风格，没有
一张写实照片是用来讲解概念的（写实照片只用来拍具体的产品/建筑实物），
配图时照这个规则挑图源。

**不要把这套版式判断带去下一个主题。** `marker-duo` 的放射 hub、带描边框
的时间轴是那套样图独有的构图，`kraft-marker` 的贴纸/荧光笔框在
`marker-duo` 的样图里根本不存在，反过来也一样。真实踩过的坑：两个主题的
`content_cards` 曾经是同一份骨架复制改标题，结果两边都跟各自样图对不上——
**跨主题串版式**比"没设计版式、只有单栏文本流"更隐蔽，因为卡片看起来是
"有设计的"，只是设计错了主题。给某个主题写内容前，只看那个主题自己的
`custom.css` 和这一节的记录，不要凭上一个主题刚用完的组件顺手带过来。
详见 `SKILL.md`「多主题防串味」。

---

## 选版式的判断

看内容的**结构**，不是看内容的多少：

| 内容形态 | 用什么 |
|---|---|
| N 个并列的东西（功能、指标、工具） | `grid` + `panel-capped`，N=4 优先 2×2 |
| N 类人群 / N 个场景 | `grid-3` + `badge-sm` |
| 有先后顺序的流程 | `steps` |
| 两个方案对照 | `vs` |
| 一堆数字 | `stats` |
| 单个结论 / 金句 | `highlight` |
| 一条主线 + 若干要点 | `badge-row` 连续几个 |
| 真的就是一段说明文字 | 什么都不用，纯 markdown |

**别为了用组件而用组件。** 一段完整论述硬拆成三栏，只会让每栏都读不通。

---

## 硬约束

**每次改完版式必须重跑 `--dry-run`。** 组件比纯文本更容易溢出，而且溢出量不直观：

```bash
python scripts/render_xhs.py content.md -t <theme> --dry-run
```

溢出时的处理优先级：

1. **删内容** —— 最有效。面板里的正文合成一段，比分两段省一大截（段间距 ×N）
2. **换版式** —— 1×4 改 2×2，三栏改两栏
3. **降字号** —— 主题 token 里调 `fs_body`，最后手段

组件内部的段落间距已经调紧（14px vs 正文流的 35px），不用再手动压。

---

## 踩过的坑

**面板高度不齐** —— 栅格默认 `align-items: stretch`，同一行的面板等高，但不同行之间不会。
内容长短差太多时改用 `grid-2` 分两行，或把内容配平。

**中文压字** —— 中文没有词间空格，长词不会在理想位置断。窄栏里一个 7 字的词组
可能直接溢出栏宽。栏越窄，文案越要短。

**底色用了强调色的组件，内部别再用强调色** —— `.highlight` 的底色就是 accent，
而主题给 `strong`/`em`/`a`/列表标记的也是 accent。同色压同色，整段字直接隐形，
**没有任何报错**。组件库里已对 `.highlight` 和 `.palette-solid` 做了修正；
自己写 custom.css 时要留意同一个坑。

**封面标题不能用 `text-shadow`** —— `.cover-title` 靠 `background-clip: text` +
`-webkit-text-fill-color: transparent` 做渐变裁切，**字身本身是透明的**。
text-shadow 画在透明字后面，整行只剩一团糊影，标题完全消失且无任何报错。
要投影只能用 `filter: drop-shadow()`，它作用在元素最终的渲染结果上。
（浅色主题给白字加光晕时必踩。）

**给封面标题内的 `<span>` 加背景高光，三个坑连环踩**（这是查得最辛苦的一组）：

1. 组件的 CSS 规则若写成 `.card-content .xxx`，**封面标题不在 `.card-content`
   里**（它是 `.cover-body.card-content` 的兄弟节点）——选择器压根不命中。
   涉及封面标题的组件规则不能限定这个祖先。
2. **CSS 自定义属性不跨兄弟节点**。`--c-accent` 等变量若只注入在 `.cover-body`
   上，`.cover-title` 拿不到——渲染器已把这层变量注入挂到共同祖先
   `.cover-inner` 上，但自己在主题 `custom.css` 里加新规则时仍要留意：
   `var(--c-xxx)` 在封面标题里能不能取到值，取决于它是不是真的在祖先链上。
3. **`z-index` 会逃逸层叠上下文**。给高光条用 `position:absolute; z-index:-1`
   时，父元素只有 `position:relative` 不够——没有独立层叠上下文，`-1` 会一路
   穿透到页面根，被卡片背景整个盖住。`getComputedStyle` 查出来的
   `background`/`color`/`opacity` 会全部正确，但截图里什么都看不见——
   **属性值对不代表渲染层级对**。父元素加 `isolation: isolate` 解决。

**调试方法**：改了 CSS 但截图看不出变化时，别继续猜着改——直接起 Playwright
查 `getComputedStyle(el, '::before')`，几秒钟就能分清是"选择器没命中"
"变量没取到值"还是"层级被压住"这三类完全不同的病因。

**`markdown="1"` 只在标准 HTML 块级元素上生效** —— `<div>` `<p>` `<span>` 可以，
自定义标签不行。

**emoji 在标题里可能变单色** —— 中文标题字体是展示字体，部分 emoji（如 🆚）
有文字形态回退会被它接管，渲染成单色描边。要彩色就换一个 emoji。
