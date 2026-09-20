/* 注意：取色一律走 var(--c-accent, <字面值>) 而不是裸字面值。
   字面值保证无覆盖时行为不变；变量则让版式组件的分类配色
   （.palette 逐栏覆盖 --c-accent）能穿透到 h1 / strong / 列表标记 /
   引用条这些由主题定义的元素上。写死字面值的话，分栏换色只能换到
   组件自己的部分，主题管的部分仍是同一个颜色。 */

/* ============================================
   {label}
   由 scripts/build_theme.py 从 {slug}.json 生成 —— 不要手改这个文件，
   改 token 后重新运行 build_theme.py。
   ============================================ */

.card-inner {{
  background: {surface};
  border-radius: {radius}px;
  border: {border};
  box-shadow: {shadow};

  /* 垂直对齐。内容偏少时顶对齐会在下方留一大片空，
     content_align: center 让内容在卡片里居中。
     .card-inner 在 separator 模式下已被 min-height 撑满，所以居中在它内部生效。 */
  display: flex;
  flex-direction: column;
  justify-content: {content_align};
}}

.card-content {{
  color: {ink};
  font-family: {font_body};
  font-size: {fs_body}px;
  /* 浅色主题上 400 字重的中文笔画偏细，压在近白底上会显得"发虚"。
     这不是渲染模糊 —— 1:1 看边缘是干净的，是笔画量不够。 */
  font-weight: {weight_body};
  line-height: {line_height};
}}

/* ---- 标题 ---- */

.card-content h1 {{
  font-family: {font_title};
  font-size: {fs_h1}px;
  font-weight: {weight_title};
  color: var(--c-accent, {accent});
  margin-bottom: 40px;
  line-height: 1.3;
  {h1_decoration}
}}

.card-content h2 {{
  font-family: {font_title};
  font-size: {fs_h2}px;
  font-weight: {weight_title};
  color: {ink_strong};
  margin: 50px 0 25px 0;
  line-height: 1.4;
}}

.card-content h3 {{
  font-family: {font_title};
  font-size: {fs_h3}px;
  font-weight: 600;
  color: var(--c-accent-2, {accent_2});
  margin: 40px 0 20px 0;
  line-height: 1.4;
}}

/* ---- 正文 ---- */

.card-content p {{
  margin-bottom: 35px;
}}

.card-content strong,
.card-content b {{
  font-weight: 700;
  color: var(--c-accent, {accent});
}}

.card-content em,
.card-content i {{
  font-style: italic;
  color: var(--c-accent-2, {accent_2});
}}

.card-content a {{
  color: var(--c-accent, {accent});
  text-decoration: underline;
  text-underline-offset: 6px;
}}

/* ---- 列表 ---- */

.card-content ul,
.card-content ol {{
  margin: 0 0 35px 0;
  padding-left: 50px;
}}

.card-content li {{
  margin-bottom: 20px;
  line-height: {line_height};
}}

.card-content ul li::marker {{
  color: var(--c-accent, {accent});
}}

.card-content ol li::marker {{
  color: var(--c-accent, {accent});
  font-weight: 700;
}}

/* ---- 引用 ---- */

.card-content blockquote {{
  margin: 40px 0;
  padding: 30px 36px;
  background: {quote_bg};
  border-left: 10px solid var(--c-accent, {accent});
  border-radius: {quote_radius}px;
}}

.card-content blockquote p {{
  margin: 0;
  color: {ink_strong};
}}

/* ---- 代码 ---- */

.card-content code {{
  font-family: {font_mono};
  font-size: {fs_code}px;
  background: {code_bg};
  color: {code_ink};
  padding: 4px 12px;
  border-radius: 8px;
}}

.card-content pre {{
  margin: 35px 0;
  padding: 32px;
  background: {pre_bg};
  border-radius: {radius}px;
  overflow-x: hidden;
}}

.card-content pre code {{
  background: none;
  padding: 0;
  color: {pre_ink};
  font-size: {fs_code}px;
  line-height: 1.6;
}}

/* ---- 分隔线与表格 ---- */

.card-content hr {{
  border: none;
  border-top: 3px solid {rule_color};
  margin: 45px 0;
}}

.card-content table {{
  width: 100%;
  border-collapse: collapse;
  margin: 35px 0;
  font-size: {fs_code}px;
}}

.card-content th {{
  background: var(--c-accent, {accent});
  color: {surface_ink};
  padding: 18px;
  text-align: left;
}}

.card-content td {{
  padding: 18px;
  border-bottom: 2px solid {rule_color};
}}

/* ---- 图片与标签 ---- */

.card-content img {{
  max-width: 100%;
  border-radius: {radius}px;
}}

.tags-container {{
  margin-top: 45px;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}}

.tag {{
  font-size: {fs_tag}px;
  padding: 10px 24px;
  border-radius: 999px;
  background: {tag_bg};
  color: {tag_ink};
}}
