---
emoji: "🧩"
title: "版式组件<br>速查"
subtitle: "同一套组件适配所有主题"
---

# 栅格与面板

<div class="grid grid-2">

<div class="panel-capped">
<div class="cap">panel-capped</div>
<div class="body">顶部有色标题条的面板，适合 N 个并列项。</div>
</div>

<div class="panel-capped">
<div class="cap">grid-2</div>
<div class="body">两栏。放 4 个子元素就是 2×2 宫格。</div>
</div>

<div class="panel">
**panel**

普通实色面板，内部可写 markdown。
</div>

<div class="panel-outline">
**panel-outline**

描边面板，适合深色满版主题。
</div>

</div>

---

# 圆徽与步骤流

<div class="badge-row">
<div class="badge">📥</div>
<div class="txt">
**badge-row**

圆徽 + 文字横排，圆徽里放数字或 emoji 都行。
</div>
</div>

<div class="steps">

<div class="step">
<div class="dot">1</div>
<div class="txt">**steps** 竖向步骤流，自动画连接线</div>
</div>

<div class="step">
<div class="dot">2</div>
<div class="txt">最后一步不画线</div>
</div>

<div class="step">
<div class="dot">3</div>
<div class="txt">适合有先后顺序的流程</div>
</div>

</div>

---

# 对比与数据

<div class="vs">

<div class="bad">
**旧方案**

弱化显示，半透明
</div>

<div class="mark">VS</div>

<div class="good">
**新方案**

强调色左边框
</div>

</div>

<div class="stats">
<div><span class="num">282%</span><span class="cap">偿付能力</span></div>
<div><span class="num">4年</span><span class="cap">回本</span></div>
<div><span class="num">6.5%</span><span class="cap">IRR</span></div>
</div>

<div class="highlight center">
highlight：一句话结论，一张卡最多一个
</div>

---

# 三栏与分区

<div class="grid grid-3">

<div class="panel center">
<div class="badge-sm">1</div>

**col-title**

栏标题，居中强调色
</div>

<div class="panel center">
<div class="badge-sm">2</div>

**sub-label**

小号分区标签
</div>

<div class="panel center">
<div class="badge-sm">3</div>

**divider**

虚线分隔
</div>

</div>

<p class="center muted">三栏字号自动降到 0.74em，中文要更短</p>
