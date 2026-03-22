# 轻量任务中心前端

本目录是任务中心 MVP 的前端实现，使用 **React + TypeScript + Vite**。

## 已实现内容

- 今日视图：按时间顺序查看当天任务
- 看板视图：按状态分组查看任务
- 历史视图：支持按关键词 / 状态 / 日期筛选历史任务
- 任务详情操作：
  - 标记完成
  - 改时间
  - 延期
  - 取消
  - 添加提醒
- 任务提醒列表与最近事件日志展示
- 所有数据通过 API client 获取，不在组件中写死业务数据

## 启动方式

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

默认开发地址：`http://localhost:5173`

## 构建

```bash
npm run build
npm run preview
```

## 环境变量

创建 `.env` / `.env.local`（可直接复制 `.env.example`）。

### 开发环境：推荐走 Vite dev server proxy

开发环境默认不需要给浏览器配置完整后端 URL。当前实现里：

- 浏览器侧请求相对路径：`/api/...`
- Vite dev server 把 `/api` 代理到真实后端
- 后端本身已经使用 `/api` 前缀，因此 **不需要 rewrite**

开发时只要配置代理目标即可：

```bash
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

如果你要把后端切到局域网机器 `192.168.31.169`，开发环境改成：

```bash
VITE_API_PROXY_TARGET=http://192.168.31.169:8000
```

这样前端依然从 `http://192.168.31.169:5173` 或 `http://localhost:5173` 发起同源请求 `/api/...`，再由 Vite 代理到真实后端，浏览器不会直接跨到 `8000`，因此不会撞上这类开发期 CORS 问题。

### 非开发环境：如需显式指定 API 基地址

如果不是通过 Vite dev server 运行，仍然可以显式设置：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

当前权衡是：

- **dev 默认优先相对路径 + proxy**，解决联调时的跨域问题
- **保留 `VITE_API_BASE_URL`**，用于 preview / 部署环境或你明确想走绝对地址的场景
- Vite proxy target 也支持环境变量，避免把真实后端地址硬编码进 `vite.config.ts`

如果 `VITE_API_BASE_URL` 未配置且不是 dev 环境，前端仍会按当前页面 hostname 自动推断 `http://<hostname>:8000`。

## API Base URL 约定

前端通过 `src/api.ts` 访问后端，当前按 brief 中的 REST 草案封装，默认请求这些接口：

- `GET /api/health`
- `GET /api/dashboard/today`
- `GET /api/dashboard/board`
- `GET /api/dashboard/history`
- `GET /api/tasks/:id`
- `PATCH /api/tasks/:id`
- `POST /api/tasks/:id/complete`
- `POST /api/tasks/:id/defer`
- `POST /api/tasks/:id/cancel`
- `POST /api/tasks/:id/reminders`

## 联调说明

- 如果后端还没完全就绪，前端结构已按真实 REST API 组织，可直接对接。
- `TaskDetail` 组件假定任务详情接口会返回：
  - `reminders`
  - `events`
- `今日视图 / 看板视图 / 历史视图` 当前也能直接消费 dashboard 聚合接口。
- 若后端返回字段名有微调，优先在 `src/api.ts` 或单独加 adapter 层做映射，不建议把转换逻辑散落到 UI 组件里。

## 目录结构

```text
frontend/
├─ src/
│  ├─ api.ts          # API client
│  ├─ App.tsx         # 页面总入口
│  ├─ components.tsx  # 视图与详情组件
│  ├─ hooks.ts        # 通用异步加载 hook
│  ├─ styles.css      # MVP 样式
│  ├─ types.ts        # 领域模型类型定义
│  └─ utils.ts        # 时间/状态等辅助函数
├─ .env.example
├─ index.html
├─ package.json
├─ tsconfig*.json
└─ vite.config.ts
```

## 后续建议

1. 接入 React Router，给三种视图独立 URL。
2. 加 React Query / SWR，统一缓存与 mutation 刷新。
3. 把任务详情操作做成 toast + optimistic update，体感会更顺。
4. 后端稳定后补充创建任务表单与更完整的事件时间线。
