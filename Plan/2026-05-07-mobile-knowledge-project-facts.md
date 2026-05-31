# 移动端知识事实按客户项目组织 + 概览接口（2026-05-07 Phase 4）

创建时间：2026-05-07  
负责人：task owner / OpenClaw  
父 Plan：`Plan/2026-05-06-mobile-task-fact-and-board-customer-rename.md`

## 目标

1. 「知识」模块进入后即显示事实相关数字，不再等用户点开事实列表才知道数量。
2. 「知识-事实」从"客户 → facts"改为"客户 → 项目 → facts"，符合 `customers → projects → facts` 的业务层级。
3. 客户层支持与「看板-客户」类似的搜索、置顶、上移、下移。
4. 不通过 `GET /api/facts?limit=300/500` 这种全量拉 facts 的方式计算概览数字。
5. 项目和 facts 不做手动排序，统一按时间倒序。
6. `project_id = null` 的事实显示为「未归项目」，作为数据修复兜底。

---

## 0. 与父 Plan 的关系

### 0.1 仍然有效

- Phase 3 中「知识」Tab 的事实 / 材料 segmented 保留。
- Phase 3 中 fact 编辑、删除、任务详情跳 fact 的能力保留。
- Phase 3 中看板"按客户"仍只是文案层改名，不在本 Plan 中切真客户分组。
- 父 Plan 对 `raw_markdown` / `raw_facts_markdown` 的唯一正文原则继续生效。

### 0.2 本 Plan 替换 / 细化的条目

- 替换当前移动端事实页 `api.getFacts({ limit: 300 })` 全量拉取后按客户分组的实现。
- 事实页改为：
  - 先加载轻量 overview。
  - 客户 / 项目数字从 overview 来。
  - 展开项目时再懒加载该项目 facts。
- 新增知识模块独立偏好，不复用 `BoardPreferences`。

---

## 1. 产品决策

### 1.1 搜索范围

本轮只支持搜索客户名。

不支持项目搜索，原因：

- 项目是客户的下一层，项目命中后仍需保留客户作为一级容器，展示规则更复杂。
- 当前用户需求是"像看板客户一样搜索客户"，客户名搜索已满足核心诉求。
- 后续如果项目量上来，再单独设计"搜索项目 / fact 正文"的增强入口。

### 1.2 排序规则

客户层：

- 支持置顶。
- 支持上移 / 下移。
- 搜索只过滤展示，不改变偏好顺序。

项目层：

- 不支持置顶。
- 不支持手动排序。
- 按 `latest_fact_at desc` 排序。
- `latest_fact_at` 相同则按项目名稳定排序。
- 「未归项目」参与同样排序；如果无法比较，放在项目列表末尾。

Facts 层：

- 不支持手动排序。
- 按 `fact_date desc, id desc` 排序。
- 展开项目后懒加载。

### 1.3 未归项目

`project_id = null` 的 facts 不隐藏，统一显示在客户下的「未归项目」分组。

原因：

- 业务上理论不应存在无项目 fact，但 schema 和历史数据允许 nullable。
- 隐藏会造成数据丢失感。
- 显示出来方便后续人工修正归属。

---

## 2. 后端 API

### 2.1 新增 `GET /api/knowledge/facts/overview`

用途：返回知识事实页所需的轻量聚合数据，不包含 fact 正文。

查询参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `status` | optional string | 事实状态筛选：`draft` / `confirmed` / `rejected` |

`q` 参数不在后端处理，前端拿 overview 后本地按客户名过滤。

响应结构：

```json
{
  "total_fact_count": 128,
  "customers": [
    {
      "customer_id": 1,
      "customer_name": "佰世赛",
      "area": "客户_A",
      "fact_count": 42,
      "project_count": 3,
      "latest_fact_at": "2026-05-06T10:00:00Z",
      "projects": [
        {
          "project_id": 10,
          "project_name": "账号增购合同流程",
          "status": "active",
          "fact_count": 18,
          "latest_fact_at": "2026-05-06T10:00:00Z"
        },
        {
          "project_id": null,
          "project_name": "未归项目",
          "status": null,
          "fact_count": 2,
          "latest_fact_at": "2026-05-02T09:00:00Z"
        }
      ]
    }
  ]
}
```

实现方式：

- 基于 `facts` 聚合，不返回 `raw_markdown`。
- join `customers` 获取客户名 / area。
- outer join `projects` 获取项目名 / status。
- 按 `customer_id + project_id` 聚合 count 和 latest_fact_at。
- 顶层 `total_fact_count` 是筛选后的事实总数。
- 客户下 projects 按 `latest_fact_at desc` 排序。
- 客户列表默认按 `latest_fact_at desc` 排序，前端再套用户偏好。

### 2.2 继续复用 `GET /api/facts`

项目展开时使用现有接口：

```http
GET /api/facts?customer_id=1&project_id=10&status=confirmed&limit=100
```

`project_id = null` 的「未归项目」需要一个后端支持点。

当前 `GET /api/facts` 只支持 `project_id=<int>`，无法表达 `project_id IS NULL`。本轮建议新增查询参数：

```http
GET /api/facts?customer_id=1&project_unassigned=true&limit=100
```

规则：

- `project_unassigned=true` 时筛选 `Fact.project_id IS NULL`。
- 如果同时传 `project_id` 和 `project_unassigned=true`，后端返回 400，避免歧义。
- 前端只在「未归项目」展开时传该参数。

### 2.3 新增知识偏好 API

新增：

```http
GET /api/preferences/knowledge
PATCH /api/preferences/knowledge
```

响应：

```json
{
  "pinned_customer_ids": [1, 3],
  "customer_order_ids": [3, 1, 2]
}
```

设计决策：

- 不复用 `BoardPreferences`。
- 不用客户名字符串，使用稳定 `customer_id`。
- 客户改名不影响排序。
- 后续如果知识模块还要支持项目排序，可以扩展新字段，不污染看板偏好。

数据库建议：

新增表 `knowledge_preferences`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer PK | 单行偏好 |
| `pinned_customer_ids_json` | text | JSON array |
| `customer_order_ids_json` | text | JSON array |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

兼容策略：

- `ensure_schema_compatibility` 中创建表，幂等。
- Alembic baseline 同步补表。
- 与 `board_preferences` 的处理方式保持一致。

---

## 3. 移动端类型

### 3.1 新增类型

`types.ts` 增加：

```ts
export interface KnowledgeFactProjectOverview {
  project_id: number | null;
  project_name: string;
  status?: string | null;
  fact_count: number;
  latest_fact_at?: string | null;
}

export interface KnowledgeFactCustomerOverview {
  customer_id: number | null;
  customer_name: string;
  area?: string | null;
  fact_count: number;
  project_count: number;
  latest_fact_at?: string | null;
  projects: KnowledgeFactProjectOverview[];
}

export interface KnowledgeFactsOverview {
  total_fact_count: number;
  customers: KnowledgeFactCustomerOverview[];
}

export interface KnowledgePreferences {
  pinned_customer_ids: number[];
  customer_order_ids: number[];
}
```

### 3.2 扩展 FactFilters

`FactFilters` 增加：

```ts
project_unassigned?: boolean;
```

---

## 4. 移动端 API Wrapper

`api.ts` 新增：

```ts
getKnowledgeFactsOverview(filters?: { status?: FactStatus | '' }): Promise<KnowledgeFactsOverview>
getKnowledgePreferences(): Promise<KnowledgePreferences>
updateKnowledgePreferences(payload: Partial<KnowledgePreferences>): Promise<KnowledgePreferences>
```

修改：

```ts
getFacts(filters?: FactFilters)
```

支持 `project_unassigned=true` 序列化。

---

## 5. 移动端状态与数据流

### 5.1 加载时机

当前：

```ts
const facts = useAsyncData(
  () => api.getFacts({ limit: 300 }),
  [],
  activeTab === 'knowledge' && knowledgeMode === 'facts',
);
```

替换为：

```ts
const knowledgeFactOverview = useAsyncData(
  () => api.getKnowledgeFactsOverview({ status: factStatusFilter }),
  [factStatusFilter],
  activeTab === 'knowledge',
);
```

说明：

- 只要进入知识模块就加载 overview。
- 即使当前停在「材料」tab，也能显示事实总数。
- `KnowledgeHero` 的 `factCount` 使用 `knowledgeFactOverview.data?.total_fact_count ?? 0`。
- 不再依赖全量 facts 数组。

### 5.2 项目 facts 懒加载

新增本地 state：

```ts
const [knowledgeProjectFacts, setKnowledgeProjectFacts] = useState<Record<string, Fact[]>>({});
const [knowledgeProjectFactsLoading, setKnowledgeProjectFactsLoading] = useState<Record<string, boolean>>({});
const [knowledgeCustomerQuery, setKnowledgeCustomerQuery] = useState('');
```

项目 key 规则：

```ts
`${customerId || 'none'}:${projectId || 'unassigned'}`
```

展开项目时：

- 如果缓存已有，不重复请求。
- 如果没有：
  - 普通项目：`api.getFacts({ customer_id, project_id, status, limit: 100 })`
  - 未归项目：`api.getFacts({ customer_id, project_unassigned: true, status, limit: 100 })`

状态筛选变化时：

- 清空 `knowledgeProjectFacts` 缓存。
- 重新加载 overview。
- 已展开项目可按需重新加载，第一版可以等用户再次展开触发。

### 5.3 客户搜索

本轮只按客户名过滤：

```ts
customer.customer_name.toLowerCase().includes(query)
```

### 5.4 客户排序偏好

新增通用函数，语义参考看板：

```ts
sortKnowledgeCustomersWithPreference(customers, pinnedCustomerIds, customerOrderIds)
buildKnowledgeCustomerOrderPayload(customers, currentOrder, movingCustomerId, direction)
```

规则：

- 置顶客户排最前。
- 置顶内部按 pinned 数组顺序。
- 非置顶客户按 customer_order_ids 顺序。
- 未出现在偏好里的客户按 `latest_fact_at desc`。
- 搜索过滤后，上移 / 下移只影响当前可见客户顺序，但保留隐藏客户原顺序。

---

## 6. 移动端 UI

### 6.1 KnowledgeHero

事实数量来源改为 overview。

如果 overview 正在加载：

- 可显示 `事实 …` 或 `事实 0`。
- 建议显示 `事实 …`，避免误导。

### 6.2 事实页结构

替换当前 `FactCustomerGroupSection` 直接接收 `facts` 的模式。

新增组件建议：

```tsx
<KnowledgeFactCustomerSection
  customer={customerOverview}
  pinned={pinned}
  collapsed={collapsed}
  onToggleCollapsed={...}
  onTogglePinned={...}
  onMoveUp={...}
  onMoveDown={...}
/>
```

客户 header 展示：

```text
客户名
3 个项目 · 42 条事实 · 最近 05-06
```

项目 row 展示：

```text
项目名
18 条事实 · 最近 05-06
```

展开项目后展示 facts：

- 复用现有 `FactRow`。
- fact row 点击仍打开 `FactEditorSheet`。
- loading 只在项目内部显示。

### 6.3 操作按钮

客户级复用看板已有 SVG 图标：

- 上移
- 下移
- 置顶 / 取消置顶

不做"全部展开项目"按钮，避免一键触发大量 facts 懒加载。

可保留客户折叠/展开。

### 6.4 空态

情况一：overview 无数据。

```text
当前没有客户事实。由主代理在转发 / 截图 / 会议纪要场景写入。
```

情况二：客户搜索无结果。

```text
没有匹配的客户
```

情况三：项目展开后 facts 为空。

```text
这个项目暂无匹配状态的事实
```

---

## 7. 后端实现范围

新增 / 修改文件：

- `backend/models.py`
  - 增加 `KnowledgePreference`。
- `backend/schemas.py`
  - 增加 overview response schemas。
  - 增加 `KnowledgePreferenceRead / KnowledgePreferenceUpdate`。
- `backend/services/knowledge.py`
  - 新增 overview 聚合逻辑。
- `backend/routers/knowledge.py`
  - `GET /api/knowledge/facts/overview`。
- `backend/routers/preferences.py`
  - `GET /knowledge`
  - `PATCH /knowledge`
- `backend/routers/facts.py`
  - `project_unassigned` 查询参数。
- `backend/services/schema_compat.py`
  - 创建 `knowledge_preferences` 表。
- `backend/alembic/versions/612481f0ad55_baseline_schema.py`
  - baseline 同步表结构。
- `backend/main.py`
  - include knowledge router。

测试：

- `GET /api/knowledge/facts/overview` 聚合客户 / 项目 / 未归项目。
- `status` 筛选影响 count。
- `GET /api/facts?project_unassigned=true` 返回 `project_id IS NULL`。
- `project_id` 与 `project_unassigned=true` 同传返回 400。
- `GET/PATCH /api/preferences/knowledge` 能保存并去重 ID。

---

## 8. 移动端实现范围

修改文件：

- `mobile_frontend/src/types.ts`
  - 新增 overview / preference 类型。
  - `FactFilters` 支持 `project_unassigned`。
- `mobile_frontend/src/api.ts`
  - 新增 overview / knowledge preferences API。
  - facts query 支持 boolean。
- `mobile_frontend/src/App.tsx`
  - 移除知识 facts 全量加载。
  - 新增 overview 加载。
  - 新增客户搜索 / 偏好排序 / 置顶 / 上下移动。
  - 新增客户 → 项目 → facts UI。
  - 项目展开懒加载 facts。
- 如需样式：
  - 复用现有 `.material-group-card` / `.material-list` / `.project-group-action-button`。
  - 只做少量新增 class，避免大规模改样式。

---

## 9. 验证

后端：

```bash
cd backend
pytest
```

移动端：

```bash
cd mobile_frontend
npm run build
```

手测路径：

1. 进入「知识」模块，材料 tab 下也能看到事实总数。
2. 切到「事实」，客户列表直接显示客户事实数 / 项目数。
3. 搜索客户名，只过滤客户。
4. 置顶客户后刷新页面，顺序保留。
5. 上移 / 下移客户后刷新页面，顺序保留。
6. 展开客户后看到项目列表，项目按最近事实时间倒序。
7. 展开项目后才加载 facts。
8. 「未归项目」能展示 `project_id = null` 的 facts。
9. 点击 fact 仍进入事实详情，保存 / 删除后刷新 overview 和当前项目 facts。
