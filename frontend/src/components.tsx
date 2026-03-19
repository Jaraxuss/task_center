import { FormEvent, ReactNode, useMemo, useState } from 'react';
import { Task, TaskEvent } from './types';
import { formatDateTime, formatDateTimeInput, getTaskSubtitle, statusMeta, summarizeEvents, toIsoStringFromInput } from './utils';

interface LayoutProps {
  activeView: string;
  onChangeView: (view: 'today' | 'board' | 'history') => void;
  apiBaseUrl: string;
  children: ReactNode;
}

export function Layout({ activeView, onChangeView, apiBaseUrl, children }: LayoutProps) {
  const tabs = [
    { key: 'today', label: '今日视图' },
    { key: 'board', label: '看板视图' },
    { key: 'history', label: '历史视图' },
  ] as const;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <div className="eyebrow">Task Center</div>
          <h1>本地轻量任务中心</h1>
          <p className="muted">今天的事别散，历史的坑别忘。</p>
        </div>
        <nav className="nav-list">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              className={`nav-item ${activeView === tab.key ? 'active' : ''}`}
              onClick={() => onChangeView(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="muted">API</span>
          <code>{apiBaseUrl}</code>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}

export function SectionHeader({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) {
  return (
    <div className="section-header">
      <div>
        <h2>{title}</h2>
        <p className="muted">{description}</p>
      </div>
      {actions ? <div className="section-actions">{actions}</div> : null}
    </div>
  );
}

export function SummaryCards({ items }: { items: Array<{ label: string; value: number }> }) {
  return (
    <div className="summary-grid">
      {items.map((item) => (
        <div className="card summary-card" key={item.label}>
          <span className="muted">{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

export function TaskList({ tasks, selectedTaskId, onSelect }: { tasks: Task[]; selectedTaskId?: number; onSelect: (task: Task) => void }) {
  if (!tasks.length) return <EmptyState title="没有任务" description="这里暂时干净得像被 PM 洗过一样。" />;

  return (
    <div className="task-list">
      {tasks.map((task) => (
        <button
          key={task.id}
          className={`card task-row ${selectedTaskId === task.id ? 'selected' : ''}`}
          onClick={() => onSelect(task)}
        >
          <div className="task-row-main">
            <div className="task-row-title-line">
              <strong>{task.title}</strong>
              <StatusBadge status={task.status} />
            </div>
            <span className="muted">{getTaskSubtitle(task)}</span>
          </div>
          <span className="task-row-arrow">›</span>
        </button>
      ))}
    </div>
  );
}

export function BoardColumns({ groups, onSelect, selectedTaskId }: { groups: Array<{ status: string; title: string; tasks: Task[] }>; onSelect: (task: Task) => void; selectedTaskId?: number }) {
  return (
    <div className="board-grid">
      {groups.map((group) => (
        <section className="card board-column" key={group.status}>
          <div className="board-column-header">
            <h3>{group.title}</h3>
            <span className="pill">{group.tasks.length}</span>
          </div>
          <div className="board-column-body">
            {group.tasks.length ? (
              group.tasks.map((task) => (
                <button
                  key={task.id}
                  className={`board-task ${selectedTaskId === task.id ? 'selected' : ''}`}
                  onClick={() => onSelect(task)}
                >
                  <strong>{task.title}</strong>
                  <span className="muted">{task.due_at ? formatDateTime(task.due_at) : '未设置时间'}</span>
                </button>
              ))
            ) : (
              <EmptyState title="空列" description="先留着，任务迟早会来。" compact />
            )}
          </div>
        </section>
      ))}
    </div>
  );
}

export function HistoryFilters({ value, onChange, onSearch }: { value: { q: string; status: string; date: string }; onChange: (next: { q: string; status: string; date: string }) => void; onSearch: () => void }) {
  return (
    <div className="card filters">
      <input placeholder="搜索标题 / 描述" value={value.q} onChange={(e) => onChange({ ...value, q: e.target.value })} />
      <select value={value.status} onChange={(e) => onChange({ ...value, status: e.target.value })}>
        <option value="">全部状态</option>
        <option value="todo">待办</option>
        <option value="doing">进行中</option>
        <option value="done">已完成</option>
        <option value="deferred">已延期</option>
        <option value="canceled">已取消</option>
      </select>
      <input type="date" value={value.date} onChange={(e) => onChange({ ...value, date: e.target.value })} />
      <button className="primary" onClick={onSearch}>筛选</button>
    </div>
  );
}

export function TaskDetail({ task, busyAction, onComplete, onSaveSchedule, onDefer, onCancel, onAddReminder }: {
  task: Task | null;
  busyAction?: string | null;
  onComplete: (task: Task) => void;
  onSaveSchedule: (task: Task, payload: { due_at: string | null }) => void;
  onDefer: (task: Task, payload: { deferred_to: string; note?: string }) => void;
  onCancel: (task: Task, note?: string) => void;
  onAddReminder: (task: Task, payload: { remind_at: string; channel: string; note?: string }) => void;
}) {
  const [scheduleValue, setScheduleValue] = useState('');
  const [deferValue, setDeferValue] = useState('');
  const [deferNote, setDeferNote] = useState('');
  const [remindAt, setRemindAt] = useState('');
  const [channel, setChannel] = useState('web');
  const [reminderNote, setReminderNote] = useState('');
  const [cancelNote, setCancelNote] = useState('');

  const recentEvents = useMemo(() => (task ? summarizeEvents(task) : []), [task]);

  if (!task) {
    return <EmptyState title="选择一个任务" description="左边点一下，右边就能动手处理。" />;
  }

  const submitSchedule = (e: FormEvent) => {
    e.preventDefault();
    onSaveSchedule(task, { due_at: toIsoStringFromInput(scheduleValue) });
  };

  const submitDefer = (e: FormEvent) => {
    e.preventDefault();
    if (!deferValue) return;
    onDefer(task, { deferred_to: new Date(deferValue).toISOString(), note: deferNote || undefined });
  };

  const submitReminder = (e: FormEvent) => {
    e.preventDefault();
    if (!remindAt) return;
    onAddReminder(task, {
      remind_at: new Date(remindAt).toISOString(),
      channel,
      note: reminderNote || undefined,
    });
  };

  return (
    <div className="detail-panel card">
      <div className="detail-header">
        <div>
          <div className="task-row-title-line">
            <h3>{task.title}</h3>
            <StatusBadge status={task.status} />
          </div>
          <p className="muted">{task.description || '暂无描述'}</p>
        </div>
        <button className="primary" disabled={busyAction === 'complete'} onClick={() => onComplete(task)}>
          标记完成
        </button>
      </div>

      <div className="detail-meta">
        <MetaItem label="项目" value={task.project || '未设置'} />
        <MetaItem label="当前时间" value={task.due_at ? formatDateTime(task.due_at) : '未设置'} />
        <MetaItem label="来源" value={task.source || 'web'} />
        <MetaItem label="更新时间" value={formatDateTime(task.updated_at)} />
      </div>

      <div className="detail-actions-grid">
        <form className="subcard" onSubmit={submitSchedule}>
          <h4>改时间</h4>
          <input type="datetime-local" defaultValue={formatDateTimeInput(task.due_at)} onChange={(e) => setScheduleValue(e.target.value)} />
          <button type="submit">保存时间</button>
        </form>

        <form className="subcard" onSubmit={submitDefer}>
          <h4>延期</h4>
          <input type="datetime-local" value={deferValue} onChange={(e) => setDeferValue(e.target.value)} />
          <textarea rows={3} placeholder="延期说明（可选）" value={deferNote} onChange={(e) => setDeferNote(e.target.value)} />
          <button type="submit">确认延期</button>
        </form>

        <form className="subcard" onSubmit={submitReminder}>
          <h4>添加提醒</h4>
          <input type="datetime-local" value={remindAt} onChange={(e) => setRemindAt(e.target.value)} />
          <select value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="web">web</option>
            <option value="chat">chat</option>
            <option value="system">system</option>
          </select>
          <textarea rows={3} placeholder="提醒备注（可选）" value={reminderNote} onChange={(e) => setReminderNote(e.target.value)} />
          <button type="submit">添加提醒</button>
        </form>

        <form className="subcard danger-zone" onSubmit={(e) => {
          e.preventDefault();
          onCancel(task, cancelNote || undefined);
        }}>
          <h4>取消任务</h4>
          <textarea rows={4} placeholder="取消原因（可选）" value={cancelNote} onChange={(e) => setCancelNote(e.target.value)} />
          <button type="submit" className="danger">取消任务</button>
        </form>
      </div>

      <div className="detail-section">
        <h4>提醒</h4>
        <div className="stack-list">
          {task.reminders?.length ? task.reminders.map((reminder) => (
            <div className="subcard inline" key={reminder.id}>
              <strong>{formatDateTime(reminder.remind_at)}</strong>
              <span className="muted">{reminder.channel} · {reminder.status}</span>
              <span>{reminder.note || '无备注'}</span>
            </div>
          )) : <EmptyState title="暂无提醒" description="加一个，免得未来的你又骂现在的你。" compact />}
        </div>
      </div>

      <div className="detail-section">
        <h4>最近变更</h4>
        <div className="stack-list">
          {recentEvents.length ? recentEvents.map((event) => <EventRow key={event.id} event={event} />) : <EmptyState title="暂无事件" description="后端接上后，这里会展示操作日志。" compact />}
        </div>
      </div>
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-item">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EventRow({ event }: { event: TaskEvent }) {
  return (
    <div className="subcard inline">
      <strong>{event.event_type}</strong>
      <span className="muted">{formatDateTime(event.created_at)}</span>
      <code>{event.payload ? JSON.stringify(event.payload) : '{}'}</code>
    </div>
  );
}

function StatusBadge({ status }: { status: Task['status'] }) {
  const meta = statusMeta[status];
  return <span className={`status-badge ${meta.tone}`}>{meta.label}</span>;
}

export function EmptyState({ title, description, compact = false }: { title: string; description: string; compact?: boolean }) {
  return (
    <div className={`empty-state ${compact ? 'compact' : ''}`}>
      <strong>{title}</strong>
      <p className="muted">{description}</p>
    </div>
  );
}

export function LoadingState() {
  return <div className="card empty-state"><strong>加载中…</strong><p className="muted">接口要是慢，就先怪网络，别急着怪人生。</p></div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="card empty-state">
      <strong>加载失败</strong>
      <p className="muted">{message}</p>
      <button onClick={onRetry}>重试</button>
    </div>
  );
}
