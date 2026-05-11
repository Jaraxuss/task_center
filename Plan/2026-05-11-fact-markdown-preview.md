# 事实详情页 Markdown 渲染预览 + 编辑切换（2026-05-11）

创建时间：2026-05-11  
负责人：南哥 / Kiro  
父 Plan：`Plan/2026-05-07-mobile-knowledge-project-facts.md`

## 目标

在移动端「知识」→「事实」详情页（`FactEditorSheet`）的「事实原文 Markdown」区域，增加 Markdown 渲染预览能力，支持预览/编辑模式切换。

当前该字段是一个纯 `<textarea>`，直接显示 markdown 源码。改造后：

- 默认进入详情页为**预览模式**，渲染 markdown 为可读格式。
- 用户点击切换按钮进入**编辑模式**，回到 textarea 编辑源码。
- 切回预览模式时立即看到渲染效果。

---

## 0. 与已有 Plan 的关系

### 0.1 仍然有效

- `Plan/2026-05-07-mobile-knowledge-project-facts.md` 中事实页的客户→项目→事实三级结构、懒加载、overview 接口继续生效。
- `Plan/2026-05-04-material-cleanup-and-mobile-knowledge.md` 中 `raw_markdown` 作为事实唯一正文的原则继续生效。
- `Plan/2026-05-10-phase-2-3-4-mobile-only.md` 中 Phase 3 拆分后的文件结构继续生效。

### 0.2 本 Plan 不改动的内容

- 后端 API 零改动。
- 事实列表页（`FactRow`）不做 markdown 渲染，保持纯文本截断。
- 不支持图片渲染（后续按需扩展）。
- 不引入富文本编辑器（保持 textarea 源码编辑）。

---

## 1. 产品决策

### 1.1 默认模式

进入事实详情页时默认为**预览模式**。理由：用户查看事实的频率远高于编辑频率。

### 1.2 切换交互

在「事实原文 Markdown」label 同行右侧放置 segmented 切换按钮：`[预览]` / `[编辑]`。

```
┌─────────────────────────────────────────┐
│ 事实原文 Markdown       [预览] [编辑]   │
├─────────────────────────────────────────┤
│                                         │
│  预览模式：渲染后的 markdown 内容        │
│  编辑模式：textarea 源码编辑            │
│                                         │
└─────────────────────────────────────────┘
```

### 1.3 预览模式行为

- 渲染 `draft.raw_markdown` 的内容为格式化 HTML。
- 支持 GFM（GitHub Flavored Markdown）：标题、列表、表格、代码块、粗体/斜体、删除线、任务列表。
- 不渲染原始 HTML 标签（安全考虑）。
- 不渲染图片（本轮不支持）。
- 内容为空时显示占位文字「暂无正文」。

### 1.4 编辑模式行为

- 与当前行为完全一致：`<textarea rows={14}>` 绑定 `draft.raw_markdown`。
- 切换到编辑模式时不丢失已有修改。

### 1.5 状态持久性

- 预览/编辑模式状态为组件本地 state，不持久化。
- 关闭详情页再打开，恢复默认预览模式。

---

## 2. 技术方案

### 2.1 新增依赖

| 包名 | 版本 | 用途 | gzip 大小 |
|---|---|---|---|
| `react-markdown` | `^9.0.0` | React 组件式 markdown 渲染 | ~8KB |
| `remark-gfm` | `^4.0.0` | GFM 扩展（表格、删除线、任务列表） | ~4KB |

选择理由：
- `react-markdown` 是 React 生态标准选择，不使用 `dangerouslySetInnerHTML`，天然防 XSS。
- `remark-gfm` 补充表格和任务列表支持，事实原文中大概率会用到。
- 总增量 ~12KB gzip，对移动端可接受。

### 2.2 不引入的依赖

- `DOMPurify`：不需要，`react-markdown` 不走 innerHTML。
- `highlight.js` / `prism`：代码高亮本轮不做，事实原文以自然语言为主。
- 任何富文本编辑器（Tiptap / Slate / ProseMirror）：保持 textarea 简单编辑。

---

## 3. 实现范围

### 3.1 修改文件清单

| 文件 | 改动 |
|---|---|
| `mobile_frontend/package.json` | 新增 `react-markdown`、`remark-gfm` 依赖 |
| `mobile_frontend/src/sheets/FactEditorSheet.tsx` | 增加预览/编辑切换逻辑和 markdown 渲染组件 |
| `mobile_frontend/src/styles.css` | 新增 `.markdown-body` 渲染样式 |

### 3.2 `FactEditorSheet.tsx` 改动详情

1. 顶部 import `react-markdown` 和 `remark-gfm`。
2. 组件内新增 `useState<'preview' | 'edit'>('preview')` 本地状态。
3. 替换原「事实原文 Markdown」section 内容：

```tsx
<section className="editor-card editor-card-soft">
  <div className="editor-field editor-field-description">
    <div className="editor-label-row">
      <span className="editor-label">事实原文 Markdown</span>
      <div className="markdown-mode-toggle">
        <button
          type="button"
          className={mdMode === 'preview' ? 'toggle-btn toggle-btn-active' : 'toggle-btn'}
          onClick={() => setMdMode('preview')}
        >
          预览
        </button>
        <button
          type="button"
          className={mdMode === 'edit' ? 'toggle-btn toggle-btn-active' : 'toggle-btn'}
          onClick={() => setMdMode('edit')}
        >
          编辑
        </button>
      </div>
    </div>
    {mdMode === 'edit' ? (
      <textarea
        rows={14}
        value={draft.raw_markdown}
        onChange={(event) => onChange({ ...draft, raw_markdown: event.target.value })}
        placeholder="保留客户原话、转写、证据截图描述。"
      />
    ) : (
      <div className="markdown-body">
        {draft.raw_markdown ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {draft.raw_markdown}
          </ReactMarkdown>
        ) : (
          <p className="markdown-empty">暂无正文</p>
        )}
      </div>
    )}
  </div>
</section>
```

### 3.3 样式新增（`styles.css`）

新增以下 class：

- `.editor-label-row`：label 和切换按钮的 flex 行布局。
- `.markdown-mode-toggle`：切换按钮容器。
- `.toggle-btn` / `.toggle-btn-active`：切换按钮样式，复用项目已有的 segmented/chip 视觉风格。
- `.markdown-body`：markdown 渲染容器，提供基础排版：
  - 标题（h1–h4）字号层级
  - 列表缩进
  - 表格边框
  - 代码块背景
  - 段落间距
  - 最大高度与滚动（与 textarea 高度对齐）

---

## 4. 验证

### 4.1 构建验证

```bash
cd mobile_frontend
npm install
npm run build
```

### 4.2 手测路径

1. 进入「知识」→「事实」，展开任意项目，点击一条事实进入详情页。
2. 确认默认为预览模式，markdown 内容渲染为格式化文本。
3. 点击「编辑」按钮，确认切换到 textarea，内容与预览一致。
4. 在 textarea 中修改内容（如加粗、加列表）。
5. 点击「预览」按钮，确认渲染结果反映修改。
6. 点击「保存」，确认数据正常保存。
7. 关闭详情页再打开，确认恢复默认预览模式。
8. 测试空内容事实，确认显示「暂无正文」占位。

### 4.3 边界情况

- 超长 markdown 内容：预览区域应有 `max-height` + `overflow-y: auto`。
- 含 HTML 标签的内容：确认不渲染为真实 HTML（安全）。
- 含图片语法 `![](url)` 的内容：显示为文本链接或 alt text，不加载图片。

---

## 5. 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| 新增依赖包体积 | 低 | ~12KB gzip，移动端可接受 |
| markdown 内容含恶意脚本 | 低 | react-markdown 默认不渲染原始 HTML |
| 渲染样式与全局样式冲突 | 低 | `.markdown-body` 容器隔离 |
| 切换模式时丢失编辑内容 | 无 | 预览/编辑共享同一个 `draft.raw_markdown` state |

---

## 6. 后续可扩展方向（不在本轮）

- 代码块语法高亮（引入 `rehype-highlight`）。
- 图片渲染支持。
- 材料详情页（`MaterialEditorSheet`）的 `raw_facts_markdown` 字段同样增加预览能力。
- 列表页 `FactRow` 的预览文本改为 strip markdown 语法后的纯文本（而非直接截断源码）。

---

## 7. 工作量

约 **0.5 天**，单次会话可完成。涉及 3 个文件改动，后端零改动。
