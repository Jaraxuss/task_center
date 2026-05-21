# 移动端任务时间与提醒同步方案（2026-05-21）

创建时间：2026-05-21
负责人：南哥 / OpenCode

## 目标

解决移动端 Task 详情页中「改时间」和「提醒设置」重复配置时间的问题。

第一版产品语义定为：

```text
任务时间是主时间。
默认提醒跟随任务时间。
通知方式只负责投递方式、接收人、备注和 AI Prompt。
```

本 Plan 先记录方案；后续实现单独提交。

---

## 1. 当前问题

移动端 Task 详情页现在有两个入口都能影响用户心智里的“提醒时间”：

| 入口 | 当前行为 | 用户感受 |
|---|---|---|
| 改时间 | 修改 `task.due_at` / `deferred_to` | 认为任务提醒时间也应该变 |
| 提醒设置 | 修改 `reminder.remind_at` | 又要改一次时间 |

对普通任务来说，绝大多数时候：

```text
task.due_at = reminder.remind_at
```

所以用户不应该被迫维护两套时间。

---

## 2. 产品决策

### 2.1 主路径

移动端的「改时间」是唯一主时间入口。

保存「改时间」时同步做两件事：

1. 更新 task 的 `due_at`。
2. 更新 primary reminder 的 `remind_at`；如果没有 primary reminder，则创建默认 V2 reminder。

### 2.2 提醒设置改名

详情页中的「提醒设置」入口改为：

```text
通知方式
```

原因：这个入口不再强调“什么时候提醒”，而是配置：

- 飞书卡片 V2 / V1 / AI 提醒。
- 接收 ID。
- 发送备注。
- AI Prompt。

### 2.3 提醒时间在通知方式中弱化

第一版不新增后端字段 `sync_with_task_time`。

通知方式 sheet 中可以继续展示提醒时间，但文案上表达为：

```text
提醒时间跟随任务时间
```

如果后续需要独立提醒时间，再增加“自定义提醒时间”开关和 `sync_with_task_time` 字段。

---

## 3. Task 详情页动作区

详情页动作区改成简洁方案：

```text
完成
改时间
编辑
更多
```

第一版「更多」可以先不做复杂菜单，保留必要动作即可。推荐落地为：

| 按钮 | 行为 |
|---|---|
| 完成 | 打开完成 sheet |
| 改时间 | 打开改时间 sheet，保存后同步 primary reminder |
| 编辑 | 打开任务编辑 sheet |
| 通知方式 | 打开 reminder settings sheet |
| 取消 | 保留为危险动作，可放第二行或更多中 |

如果实现成本要更低，可以先落成五个按钮：

```text
完成
改时间
编辑
通知方式
取消
```

关键是移除与「改时间」重复的提醒时间主入口。

---

## 4. Primary Reminder 规则

沿用移动端当前 `getPrimaryReminder(task)`：

1. 排除 `canceled` / `disabled`。
2. 优先选择未来的 `scheduled` reminder 中最近的一条。
3. 如果没有未来 scheduled reminder，则选择最新的一条非取消 reminder。

这个 primary reminder 是「改时间」同步的对象。

---

## 5. 保存逻辑

### 5.1 改时间保存

用户在 Task 详情页点击「改时间」并保存后：

```text
PATCH /api/tasks/{task_id}
{
  due_at: newTime
}
```

成功后，移动端继续同步 primary reminder：

```text
如果已有 primary reminder:
  PATCH /api/tasks/{task_id}/reminders/{reminder_id}
  {
    remind_at: newTime
  }

如果没有 primary reminder:
  POST /api/tasks/{task_id}/reminders
  {
    remind_at: newTime,
    channel: "feishu",
    delivery_mode: "feishu_card_v2"
  }
```

### 5.2 AI 提醒

如果 primary reminder 是 AI 模式，`PATCH reminder` 会走后端已有逻辑：

```text
openclaw cron rm old_job
openclaw cron add new_job
```

因此移动端不需要特殊处理，只要更新 `remind_at`。

### 5.3 错误处理

如果 task 时间更新成功，但 reminder 同步失败：

- 不回滚 task 时间。
- Toast 提示：`任务时间已更新，但通知时间同步失败`。
- 详情页保留后端返回的最新 task 状态。

原因：任务主时间比通知配置更重要，不能因为通知链路失败阻塞用户改时间。

---

## 6. 通知方式 Sheet 调整

第一版保留现有 sheet，但调整文案：

- 标题：`通知方式`
- 时间字段文案：`跟随任务时间`
- 说明：`改时间请回到任务详情页使用「改时间」。这里主要配置通知方式。`

可以把 `datetime-local` 字段设为只读或直接隐藏。

第一版推荐隐藏时间输入，避免重复心智。

---

## 7. 实现范围

### 7.1 移动端

| 文件 | 改动 |
|---|---|
| `src/lib/forms.ts` | 继续使用 `getPrimaryReminder` / `makeReminderFormState` |
| `src/useAppHandlers.ts` | `runTaskAction('reschedule')` 成功后同步 primary reminder |
| `src/sheets/TaskDetailSheet.tsx` | 动作区改为简洁方案，入口名改为「通知方式」 |
| `src/sheets/ReminderSettingsSheet.tsx` | 标题与文案改成通知方式，隐藏或弱化时间输入 |
| `src/styles.css` | 如有必要调整动作区和通知方式样式 |

### 7.2 后端

第一版不改后端。

原因：后端已有 reminder 创建/更新端点，移动端可以串联调用。

后续可选增强：新增原子接口 `PATCH /api/tasks/{id}/schedule`。

---

## 8. 验证

### 8.1 手测

1. 打开一个没有 reminder 的 task。
2. 点击「改时间」，保存新时间。
3. 确认 task 安排时间更新。
4. 确认自动创建 V2 reminder，并且详情页通知摘要显示同一时间。
5. 打开已有 V2 reminder 的 task，点击「改时间」。
6. 确认 primary reminder 的 `remind_at` 同步更新。
7. 打开 AI reminder 的 task，点击「改时间」。
8. 确认后端没有 500；OpenClaw cron 由后端重建。

### 8.2 构建

```bash
cd mobile_frontend
npm run build
```

---

## 9. 后续不在本轮

- `sync_with_task_time` 后端字段。
- 多提醒管理。
- 自定义提前提醒（例如提前 10 分钟）。
- 后端原子 schedule 接口。
- 通知方式中的高级诊断页。

---

## 10. 最终结论

本轮移动端应把用户心智收敛为：

```text
改时间 = 改任务主时间，并同步默认提醒时间。
通知方式 = 改 V2 / V1 / AI、接收人、备注和 Prompt。
```

这样用户不需要为了同一件事改两次时间，同时保留 AI/V1/V2 的高级投递能力。
