# 本地轻量任务中心 API CONTRACT

## 1. 文档目标
本文件定义 React 前端与 FastAPI 后端在 MVP 阶段的接口契约、字段格式、请求/响应示例、错误码和联调约束。

约定：
- API Base URL：`/api`
- 数据格式：`application/json`
- 时间格式：统一使用 ISO 8601，例如 `2026-03-19T15:00:00Z`
- 列表接口默认按 `updated_at desc` 或业务指定规则排序

---

## 2. 通用约定

## 2.1 响应结构
### 成功响应
```json
{
  "data": {},
  "meta": {}
}
```

### 错误响应
```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task not found",
    "details": {}
  }
}
```

## 2.2 通用错误码
| HTTP | code | 说明 |
|---|---|---|
| 400 | BAD_REQUEST | 请求参数缺失或不合法 |
| 404 | TASK_NOT_FOUND | 任务不存在 |
| 404 | REMINDER_NOT_FOUND | 提醒不存在 |
| 409 | INVALID_STATUS_TRANSITION | 非法状态流转 |
| 409 | TASK_ALREADY_DONE | 任务已完成 |
| 409 | TASK_ALREADY_CANCELED | 任务已取消 |
| 422 | VALIDATION_ERROR | 字段校验失败 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

## 2.3 前端字段模型（推荐）
```ts
export type TaskStatus = 'todo' | 'doing' | 'done' | 'deferred' | 'canceled';
export type ReminderStatus = 'scheduled' | 'fired' | 'canceled';
export type TaskSource = 'chat' | 'web' | 'system';

export interface Reminder {
  id: number;
  task_id: number;
  remind_at: string;
  channel: string;
  status: ReminderStatus;
  note?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskEvent {
  id: number;
  task_id: number;
  event_type: string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface Task {
  id: number;
  title: string;
  description?: string | null;
  due_at?: string | null;
  status: TaskStatus;
  project?: string | null;
  tags: string[];
  source: TaskSource;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  canceled_at?: string | null;
  deferred_to?: string | null;
  reminders?: Reminder[];
  events?: TaskEvent[];
  needs_nightly_review?: boolean;
}
```

---

## 3. 健康检查

## 3.1 GET /api/health
### 用途
服务存活检查。

### 响应示例
```json
{
  "data": {
    "status": "ok",
    "service": "task-center-api"
  },
  "meta": {}
}
```

---

## 4. 任务接口

## 4.1 GET /api/tasks
### 用途
查询任务列表；供 Today、History、Board 等页面使用。

### Query 参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| date | string | 否 | `today` 或 `YYYY-MM-DD` |
| status | string | 否 | 单个状态值 |
| q | string | 否 | 标题/描述关键词 |
| project | string | 否 | 项目过滤 |
| tag | string | 否 | 标签过滤 |
| include_completed | boolean | 否 | 是否包含已完成 |
| include_canceled | boolean | 否 | 是否包含已取消 |
| sort | string | 否 | `due_at_asc` / `updated_at_desc` |

### 典型使用
- Today：`GET /api/tasks?date=today&sort=due_at_asc`
- Board：`GET /api/tasks?include_completed=true&include_canceled=true`
- History：`GET /api/tasks?status=done&q=客户`

### 响应示例
```json
{
  "data": [
    {
      "id": 101,
      "title": "给客户回电话",
      "description": "确认报价与交付时间",
      "due_at": "2026-03-19T15:00:00Z",
      "status": "todo",
      "project": "销售跟进",
      "tags": ["客户", "电话"],
      "source": "chat",
      "created_at": "2026-03-19T08:00:00Z",
      "updated_at": "2026-03-19T08:00:00Z",
      "completed_at": null,
      "canceled_at": null,
      "deferred_to": null,
      "needs_nightly_review": false
    }
  ],
  "meta": {
    "total": 1
  }
}
```

## 4.2 GET /api/tasks/{task_id}
### 用途
查询任务详情，供详情抽屉/页面使用。

### 响应示例
```json
{
  "data": {
    "id": 101,
    "title": "给客户回电话",
    "description": "确认报价与交付时间",
    "due_at": "2026-03-19T15:00:00Z",
    "status": "todo",
    "project": "销售跟进",
    "tags": ["客户", "电话"],
    "source": "chat",
    "created_at": "2026-03-19T08:00:00Z",
    "updated_at": "2026-03-19T08:05:00Z",
    "completed_at": null,
    "canceled_at": null,
    "deferred_to": null,
    "reminders": [
      {
        "id": 201,
        "task_id": 101,
        "remind_at": "2026-03-19T14:30:00Z",
        "channel": "chat",
        "status": "scheduled",
        "note": "提前半小时提醒",
        "created_at": "2026-03-19T08:01:00Z",
        "updated_at": "2026-03-19T08:01:00Z"
      }
    ],
    "events": [
      {
        "id": 301,
        "task_id": 101,
        "event_type": "created",
        "payload": {
          "source": "chat"
        },
        "created_at": "2026-03-19T08:00:00Z"
      }
    ]
  },
  "meta": {}
}
```

### 失败示例
```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task not found",
    "details": {
      "task_id": 999
    }
  }
}
```

## 4.3 POST /api/tasks
### 用途
创建任务。

### 请求体
```json
{
  "title": "给客户回电话",
  "description": "确认报价与交付时间",
  "due_at": "2026-03-19T15:00:00Z",
  "project": "销售跟进",
  "tags": ["客户", "电话"],
  "source": "web"
}
```

### 字段说明
| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| title | string | 是 | 任务标题 |
| description | string | 否 | 描述 |
| due_at | string(datetime) | 否 | 截止/计划时间 |
| project | string | 否 | 项目 |
| tags | string[] | 否 | 标签数组 |
| source | string | 否 | 默认 `web` |

### 响应示例
```json
{
  "data": {
    "id": 101,
    "title": "给客户回电话",
    "description": "确认报价与交付时间",
    "due_at": "2026-03-19T15:00:00Z",
    "status": "todo",
    "project": "销售跟进",
    "tags": ["客户", "电话"],
    "source": "web",
    "created_at": "2026-03-19T08:00:00Z",
    "updated_at": "2026-03-19T08:00:00Z",
    "completed_at": null,
    "canceled_at": null,
    "deferred_to": null
  },
  "meta": {}
}
```

## 4.4 PATCH /api/tasks/{task_id}
### 用途
更新任务基础字段。

### 可更新字段
- title
- description
- due_at
- project
- tags
- status（仅允许 `todo <-> doing` 这类轻量切换；完成/延期/取消建议走专用接口）

### 请求体示例
```json
{
  "title": "给客户回电话并确认报价",
  "due_at": "2026-03-19T16:00:00Z",
  "tags": ["客户", "电话", "报价"]
}
```

### 响应示例
```json
{
  "data": {
    "id": 101,
    "title": "给客户回电话并确认报价",
    "description": "确认报价与交付时间",
    "due_at": "2026-03-19T16:00:00Z",
    "status": "todo",
    "project": "销售跟进",
    "tags": ["客户", "电话", "报价"],
    "source": "web",
    "created_at": "2026-03-19T08:00:00Z",
    "updated_at": "2026-03-19T08:20:00Z",
    "completed_at": null,
    "canceled_at": null,
    "deferred_to": null
  },
  "meta": {}
}
```

## 4.5 POST /api/tasks/{task_id}/complete
### 用途
标记任务完成。

### 请求体
```json
{
  "completed_at": "2026-03-19T10:00:00Z",
  "note": "已完成电话回访"
}
```

### 响应示例
```json
{
  "data": {
    "id": 101,
    "status": "done",
    "completed_at": "2026-03-19T10:00:00Z"
  },
  "meta": {}
}
```

## 4.6 POST /api/tasks/{task_id}/defer
### 用途
延期任务。

### 请求体
```json
{
  "deferred_to": "2026-03-20T03:00:00Z",
  "reason": "客户今天不在办公室"
}
```

### 响应示例
```json
{
  "data": {
    "id": 101,
    "status": "deferred",
    "deferred_to": "2026-03-20T03:00:00Z"
  },
  "meta": {}
}
```

### 失败示例
```json
{
  "error": {
    "code": "INVALID_STATUS_TRANSITION",
    "message": "Completed task cannot be deferred",
    "details": {
      "task_id": 101,
      "current_status": "done"
    }
  }
}
```

## 4.7 POST /api/tasks/{task_id}/cancel
### 用途
取消任务。

### 请求体
```json
{
  "reason": "需求已失效"
}
```

### 响应示例
```json
{
  "data": {
    "id": 101,
    "status": "canceled",
    "canceled_at": "2026-03-19T09:00:00Z"
  },
  "meta": {}
}
```

---

## 5. 提醒接口

## 5.1 POST /api/tasks/{task_id}/reminders
### 用途
给任务新增提醒。

### 请求体
```json
{
  "remind_at": "2026-03-19T14:30:00Z",
  "channel": "chat",
  "note": "提前半小时提醒"
}
```

### 响应示例
```json
{
  "data": {
    "id": 201,
    "task_id": 101,
    "remind_at": "2026-03-19T14:30:00Z",
    "channel": "chat",
    "status": "scheduled",
    "note": "提前半小时提醒",
    "created_at": "2026-03-19T08:01:00Z",
    "updated_at": "2026-03-19T08:01:00Z"
  },
  "meta": {}
}
```

## 5.2 PATCH /api/reminders/{reminder_id}
### 用途
修改提醒状态或时间。

### 请求体示例
```json
{
  "status": "canceled"
}
```

### 响应示例
```json
{
  "data": {
    "id": 201,
    "task_id": 101,
    "remind_at": "2026-03-19T14:30:00Z",
    "channel": "chat",
    "status": "canceled",
    "note": "提前半小时提醒",
    "created_at": "2026-03-19T08:01:00Z",
    "updated_at": "2026-03-19T08:10:00Z"
  },
  "meta": {}
}
```

> 说明：该接口未在 bootstrap 草案中显式列出，但前端若需要取消提醒，建议补充该接口；否则只能通过任务详情只读展示提醒。

---

## 6. 历史与看板聚合接口

## 6.1 GET /api/history
### 用途
历史视图查询任务及变更。

### Query 参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| date | string | 否 | `YYYY-MM-DD` 或日期范围扩展 |
| status | string | 否 | 状态过滤 |
| q | string | 否 | 关键词 |

### 响应示例
```json
{
  "data": [
    {
      "id": 101,
      "title": "给客户回电话",
      "status": "done",
      "updated_at": "2026-03-19T10:00:00Z",
      "latest_event_type": "completed"
    }
  ],
  "meta": {
    "total": 1
  }
}
```

## 6.2 GET /api/dashboard/today
### 用途
Today 页聚合接口，减少前端拼装成本。

### 响应示例
```json
{
  "data": {
    "date": "2026-03-19",
    "summary": {
      "todo": 3,
      "doing": 1,
      "deferred": 1,
      "done": 4
    },
    "tasks": [
      {
        "id": 101,
        "title": "给客户回电话",
        "due_at": "2026-03-19T15:00:00Z",
        "status": "todo",
        "tags": ["客户"]
      }
    ]
  },
  "meta": {}
}
```

## 6.3 GET /api/dashboard/board
### 用途
Board 页聚合接口。

### 响应示例
```json
{
  "data": {
    "todo": [],
    "doing": [],
    "deferred": [],
    "done": [],
    "canceled": []
  },
  "meta": {}
}
```

## 6.4 GET /api/dashboard/history
### 用途
History 页聚合接口。

### 响应示例
```json
{
  "data": {
    "filters": {
      "date": "2026-03-19",
      "status": "done",
      "q": "客户"
    },
    "items": [
      {
        "id": 101,
        "title": "给客户回电话",
        "status": "done",
        "updated_at": "2026-03-19T10:00:00Z"
      }
    ]
  },
  "meta": {}
}
```

---

## 7. 晚间收口接口

## 7.1 GET /api/nightly-review/candidates?date=YYYY-MM-DD
### 用途
获取某日 22:00 收口候选任务。

### 响应示例
```json
{
  "data": {
    "date": "2026-03-19",
    "tasks": [
      {
        "id": 101,
        "title": "给客户回电话",
        "status": "todo",
        "due_at": "2026-03-19T15:00:00Z",
        "deferred_to": null,
        "needs_nightly_review": true
      }
    ]
  },
  "meta": {}
}
```

## 7.2 POST /api/nightly-review/commit
### 用途
提交某次晚间收口结果。该接口由聊天接入层或后台任务调用，前端 MVP 可不直接调用。

### 请求体
```json
{
  "date": "2026-03-19",
  "review_session_id": "nightly-2026-03-19",
  "user_replied": true,
  "actions": [
    {
      "task_id": 101,
      "action": "defer",
      "deferred_to": "2026-03-20T03:00:00Z",
      "reason": "客户今天不在办公室"
    },
    {
      "task_id": 102,
      "action": "auto_done"
    }
  ]
}
```

### 处理规则
- `user_replied=false` 时，不允许 `auto_done`。
- 后端需对每条 action 执行状态变更与事件落库。

### 响应示例
```json
{
  "data": {
    "review_session_id": "nightly-2026-03-19",
    "processed": 2,
    "succeeded": 2,
    "failed": 0
  },
  "meta": {}
}
```

---

## 8. 事件接口（可选但推荐）

## 8.1 GET /api/tasks/{task_id}/events
### 用途
若任务详情不默认内嵌全部 events，可单独分页读取。

### 响应示例
```json
{
  "data": [
    {
      "id": 301,
      "task_id": 101,
      "event_type": "created",
      "payload": {
        "source": "chat"
      },
      "created_at": "2026-03-19T08:00:00Z"
    }
  ],
  "meta": {
    "total": 1
  }
}
```

---

## 9. 前后端联调约束

## 9.1 前端约束
- 不自行推断字段名，严格按 contract 使用。
- 时间统一以 ISO 字符串接收。
- `tags_json` 为后端内部字段，前端只接收 `tags`。
- 完成 / 延期 / 取消必须调用专用接口，不直接 PATCH `status`。

## 9.2 后端约束
- 返回字段命名稳定，不随 ORM 命名泄漏。
- 列表接口返回数组，详情接口返回对象。
- 所有状态变更接口都应写 `task_events`。
- 错误码要稳定，不能只有裸字符串报错。

## 9.3 幂等建议
- `POST /complete`：重复提交可返回当前 done 状态，不报错。
- `POST /cancel`：重复提交可返回当前 canceled 状态，不报错。
- `POST /defer`：若任务已 done/canceled，则返回 409。

---

## 10. 建议的数据校验规则
- `title`: 1~120 字
- `description`: 最长 5000 字
- `project`: 最长 50 字
- `tags`: 每项最长 20 字，最多 20 项
- `due_at`, `deferred_to`, `remind_at`: 必须为合法 datetime
- `remind_at` 不应早于当前时间（允许少量容忍窗口由后端决定）

---

## 11. MVP 最小接口集
若需要压缩开发范围，优先保证以下接口可用：
1. `GET /api/health`
2. `GET /api/tasks`
3. `GET /api/tasks/{id}`
4. `POST /api/tasks`
5. `PATCH /api/tasks/{id}`
6. `POST /api/tasks/{id}/complete`
7. `POST /api/tasks/{id}/defer`
8. `POST /api/tasks/{id}/cancel`
9. `POST /api/tasks/{id}/reminders`
10. `GET /api/dashboard/today`
11. `GET /api/dashboard/board`
12. `GET /api/history`
13. `GET /api/nightly-review/candidates`
14. `POST /api/nightly-review/commit`

结论：前端页面层优先消费聚合接口，详情与动作层优先消费资源接口。这样 Today/Board/History 页面会更稳，Task Detail 的操作也更清晰。