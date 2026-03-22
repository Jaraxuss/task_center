import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react';
import { Task, TaskEvent } from './types';
import {
  formatDateTime,
  formatDateTimeInput,
  getTaskSubtitle,
  getTaskStateSummary,
  statusMeta,
  summarizeEvents,
  toIsoStringFromInput,
} from './utils';

interface LayoutProps {
  activeView: string;
  onChangeView: (view: 'today' | 'board' | 'history') => void;
  apiBaseUrl: string;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  children: ReactNode;
}

const tabs = [
  { key: 'today', label: '今日', description: '聚焦今天必须推进的任务', icon: '01' },
  { key: 'board', label: '看板', description: '从状态流转扫全局进度', icon: '02' },
  { key: 'history', label: '历史', description: '检索记录，复盘变化链路', icon: '03' },
] as const;

export function Layout({ activeView, onChangeView, apiBaseUrl, theme, onToggleTheme, children }: LayoutProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-card card card-elevated">
          <div className="brand-mark">TC</div>
          <div className="brand-copy">
            <div className="eyebrow">Task Center</div>
            <h1>任务中心</h1>
            <p className="muted">把提醒、进度和复盘放进同一块操作台，别再靠记性硬撑。</p>
          </div>
        </div>

        <nav className="nav-list" aria-label="主视图切换">
          {tabs.map((tab) => (
            <button key={tab.key} className={`nav-item ${activeView === tab.key ? 'active' : ''}`} onClick={() => onChangeView(tab.key)}>
              <span className="nav-icon">{tab.icon}</span>
              <span className="nav-copy">
                <span className="nav-label">{tab.label}</span>
                <span className="nav-description">{tab.description}</span>
              </span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer card subtle-card">
          <div className="sidebar-settings">
            <div>
              <span className="label-caption">界面主题</span>
              <strong>{theme === 'dark' ? '深色模式' : '浅色模式'}</strong>
            </div>
            <button className="ghost-toggle" onClick={onToggleTheme}>
              <span aria-hidden="true">{theme === 'dark' ? '☀️' : '🌙'}</span>
              <span>{theme === 'dark' ? '切到浅色' : '切到深色'}</span>
            </button>
          </div>
          <div className="sidebar-divider" />
          <span className="label-caption">API Endpoint</span>
          <code>{apiBaseUrl}</code>
          <span className="muted">本地服务在线时，所有操作都会直接落到账本，不再靠口头同步。</span>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}

export function ViewHero({
  eyebrow,
  title,
  description,
  highlight,
  metrics,
}: {
  eyebrow: string;
  title: string;
  description: string;
  highlight: string;
  metrics?: Array<{ label: string; value: string; tone?: 'default' | 'brand' | 'success' | 'danger' }>;
}) {
  return (
    <section className="view-hero card card-elevated">
      <div className="view-hero-main">
        <div className="eyebrow">{eyebrow}</div>
        <h2>{title}</h2>
        <p className="hero-description">{description}</p>
      </div>
      <div className="hero-callout">
        <div className="hero-callout-card hero-callout-highlight">
          <span className="label-caption">当前提示</span>
          <strong>{highlight}</strong>
        </div>
        {metrics?.length ? (
          <div className="hero-mini-metrics hero-mini-metrics-dense">
            {metrics.map((metric) => (
              <div key={metric.label} className={`hero-mini-metric tone-${metric.tone || 'default'}`}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}

export function SectionHeader({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) {
  return (
    <div className="section-header">
      <div>
        <h3>{title}</h3>
        <p className="muted">{description}</p>
      </div>
      {actions ? <div className="section-actions">{actions}</div> : null}
    </div>
  );
}

export function Panel({ title, description, actions, children }: { title: string; description: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="panel card">
      <SectionHeader title={title} description={description} actions={actions} />
      {children}
    </section>
  );
}

export function TaskList({
  tasks,
  selectedTaskId,
  onSelect,
  variant = 'today',
  page = 1,
  pageSize = 10,
  onPageChange,
}: {
  tasks: Task[];
  selectedTaskId?: number;
  onSelect: (task: Task) => void;
  variant?: 'today' | 'history';
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
}) {
  if (!tasks.length) return <EmptyState title="没有任务" description="这里暂时干净得有点反常，但先享受几秒宁静。" />;

  const totalPages = Math.max(1, Math.ceil(tasks.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const startIndex = (safePage - 1) * pageSize;
  const visibleTasks = tasks.slice(startIndex, startIndex + pageSize);

  return (
    <div className="task-list-shell">
      <div className="task-list-meta muted">
        <span>共 {tasks.length} 项</span>
        <span>当前显示 {startIndex + 1}-{Math.min(startIndex + visibleTasks.length, tasks.length)} 项</span>
      </div>
      <div className="task-list">
        {visibleTasks.map((task) => {
          const stateSummary = getTaskStateSummary(task);
          return (
            <button key={task.id} className={`card task-row ${selectedTaskId === task.id ? 'selected' : ''}`} onClick={() => onSelect(task)}>
              <div className="task-row-main">
                <div className="task-row-topline">
                  <StatusBadge status={task.status} />
                  <span className="task-row-meta">#{task.id}</span>
                </div>
                <div className="task-row-title-line">
                  <strong>{task.title}</strong>
                </div>
                <span className="muted">{getTaskSubtitle(task)}</span>
                <div className="task-row-footer">
                  <MetaChip label="状态" value={stateSummary} />
                  <MetaChip label="来源" value={task.source || 'web'} />
                  {task.project ? <MetaChip label="项目" value={task.project} /> : null}
                  {variant === 'history' ? <MetaChip label="更新" value={formatDateTime(task.updated_at)} /> : null}
                </div>
              </div>
              <span className="task-row-arrow">›</span>
            </button>
          );
        })}
      </div>
      {totalPages > 1 ? <Pagination page={safePage} totalPages={totalPages} onPageChange={onPageChange} /> : null}
    </div>
  );
}

export function BoardColumns({
  groups,
  onSelect,
  selectedTaskId,
}: {
  groups: Array<{ status: string; title: string; tasks: Task[] }>;
  onSelect: (task: Task) => void;
  selectedTaskId?: number;
}) {
  return (
    <div className="board-grid">
      {groups.map((group) => (
        <section className="card board-column" key={group.status}>
          <div className="board-column-header">
            <div>
              <StatusBadge status={group.status as Task['status']} />
              <h4>{group.title}</h4>
            </div>
            <span className="pill">{group.tasks.length}</span>
          </div>
          <div className="board-column-body">
            {group.tasks.length ? (
              group.tasks.map((task) => (
                <button key={task.id} className={`board-task ${selectedTaskId === task.id ? 'selected' : ''}`} onClick={() => onSelect(task)}>
                  <div className="board-task-topline">
                    <strong>{task.title}</strong>
                    <span className="task-row-meta">#{task.id}</span>
                  </div>
                  <span className="muted">{task.description || '暂无描述'}</span>
                  <div className="board-task-footer">
                    <MetaChip label="时间" value={task.due_at ? formatDateTime(task.due_at) : '未设置'} />
                    <MetaChip label="项目" value={task.project || '未分组'} />
                  </div>
                </button>
              ))
            ) : (
              <EmptyState title="空列" description="这里暂时没有任务，说明这一档还没堵住。" compact />
            )}
          </div>
        </section>
      ))}
    </div>
  );
}

export function HistoryFilters({
  value,
  onChange,
  onSearch,
  resultCount,
}: {
  value: { q: string; status: string; date: string };
  onChange: (next: { q: string; status: string; date: string }) => void;
  onSearch: () => void;
  resultCount?: number;
}) {
  return (
    <div className="filters-toolbar card">
      <div className="filters-grid">
        <label className="field">
          <span className="label-caption">关键词</span>
          <input placeholder="搜索标题 / 描述" value={value.q} onChange={(e) => onChange({ ...value, q: e.target.value })} />
        </label>
        <label className="field">
          <span className="label-caption">状态</span>
          <select value={value.status} onChange={(e) => onChange({ ...value, status: e.target.value })}>
            <option value="">全部状态</option>
            <option value="todo">待办</option>
            <option value="doing">进行中</option>
            <option value="done">已完成</option>
            <option value="deferred">已延期</option>
            <option value="canceled">已取消</option>
          </select>
        </label>
        <label className="field">
          <span className="label-caption">日期</span>
          <input type="date" value={value.date} onChange={(e) => onChange({ ...value, date: e.target.value })} />
        </label>
      </div>
      <div className="filters-actions">
        <div className="filter-result-meta">
          <span className="label-caption">命中记录</span>
          <strong>{resultCount ?? 0}</strong>
        </div>
        <button className="primary" onClick={onSearch}>应用筛选</button>
      </div>
    </div>
  );
}

export function TaskDetailModal({
  task,
  open,
  onClose,
  busyAction,
  onComplete,
  onSaveSchedule,
  onDefer,
  onCancel,
  onAddReminder,
}: {
  task: Task | null;
  open: boolean;
  onClose: () => void;
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

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  useEffect(() => {
    setScheduleValue(formatDateTimeInput(task?.due_at));
    setDeferValue('');
    setDeferNote('');
    setRemindAt('');
    setChannel('web');
    setReminderNote('');
    setCancelNote('');
  }, [task?.id]);

  if (!open || !task) return null;

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
    <div className="modal-backdrop" onClick={onClose}>
      <aside className="detail-modal card card-elevated" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={`任务 ${task.title}`}>
        <div className="detail-modal-header">
          <div className="detail-header-main">
            <div className="detail-header-topline">
              <StatusBadge status={task.status} />
              <span className="task-row-meta">任务 #{task.id}</span>
            </div>
            <h3>{task.title}</h3>
            <p className="muted">{task.description || '暂无描述，至少你现在知道这事还没被写明白。'}</p>
          </div>
          <div className="detail-modal-actions">
            <button className="primary" disabled={busyAction === 'complete'} onClick={() => onComplete(task)}>
              {busyAction === 'complete' ? '处理中…' : '标记完成'}
            </button>
            <button className="icon-button" onClick={onClose} aria-label="关闭详情">✕</button>
          </div>
        </div>

        <div className="detail-overview-strip compact-overview">
          <MetaItem label="项目" value={task.project || '未设置'} />
          <MetaItem label="当前时间" value={task.due_at ? formatDateTime(task.due_at) : '未设置'} />
          <MetaItem label="来源" value={task.source || 'web'} />
          <MetaItem label="更新时间" value={formatDateTime(task.updated_at)} />
        </div>

        {task.tags?.length ? (
          <div className="tag-row">
            {task.tags.map((tag) => (
              <span className="tag" key={tag}>{tag}</span>
            ))}
          </div>
        ) : null}

        <div className="detail-modal-body">
          <div className="detail-section-grid detail-section-grid-modal">
            <div className="detail-section card section-card">
              <div className="detail-section-title">
                <h4>任务信息</h4>
                <span className="label-caption">Overview</span>
              </div>
              <div className="detail-meta">
                <MetaItem label="创建时间" value={formatDateTime(task.created_at)} />
                <MetaItem label="标签数" value={String(task.tags?.length || 0)} />
                <MetaItem label="提醒数" value={String(task.reminders?.length || 0)} />
                <MetaItem label="事件数" value={String(task.events?.length || 0)} />
              </div>
            </div>

            <div className="detail-section card section-card">
              <div className="detail-section-title">
                <h4>必要操作</h4>
                <span className="label-caption">Actions</span>
              </div>
              <div className="detail-actions-stack">
                <form className="subcard action-card" onSubmit={submitSchedule}>
                  <h5>改时间</h5>
                  <p className="muted">直接重设截止时间，适合轻量调整。</p>
                  <input type="datetime-local" value={scheduleValue} onChange={(e) => setScheduleValue(e.target.value)} />
                  <button type="submit" disabled={busyAction === 'schedule'}>{busyAction === 'schedule' ? '保存中…' : '保存时间'}</button>
                </form>

                <form className="subcard action-card" onSubmit={submitDefer}>
                  <h5>延期</h5>
                  <p className="muted">需要留下说明，避免未来只看到结果看不到原因。</p>
                  <input type="datetime-local" value={deferValue} onChange={(e) => setDeferValue(e.target.value)} />
                  <textarea rows={3} placeholder="延期说明（可选）" value={deferNote} onChange={(e) => setDeferNote(e.target.value)} />
                  <button type="submit" disabled={busyAction === 'defer'}>{busyAction === 'defer' ? '处理中…' : '确认延期'}</button>
                </form>

                <form className="subcard action-card" onSubmit={submitReminder}>
                  <h5>添加提醒</h5>
                  <p className="muted">把提醒挂上，省得未来的你回来骂现在的你。</p>
                  <input type="datetime-local" value={remindAt} onChange={(e) => setRemindAt(e.target.value)} />
                  <select value={channel} onChange={(e) => setChannel(e.target.value)}>
                    <option value="web">web</option>
                    <option value="chat">chat</option>
                    <option value="system">system</option>
                  </select>
                  <textarea rows={3} placeholder="提醒备注（可选）" value={reminderNote} onChange={(e) => setReminderNote(e.target.value)} />
                  <button type="submit" disabled={busyAction === 'remind'}>{busyAction === 'remind' ? '添加中…' : '添加提醒'}</button>
                </form>

                <form
                  className="subcard action-card danger-zone"
                  onSubmit={(e) => {
                    e.preventDefault();
                    onCancel(task, cancelNote || undefined);
                  }}
                >
                  <h5>取消任务</h5>
                  <p className="muted">仅在任务确认不再执行时使用，建议留下原因。</p>
                  <textarea rows={4} placeholder="取消原因（可选）" value={cancelNote} onChange={(e) => setCancelNote(e.target.value)} />
                  <button type="submit" className="danger" disabled={busyAction === 'cancel'}>{busyAction === 'cancel' ? '处理中…' : '取消任务'}</button>
                </form>
              </div>
            </div>
          </div>

          <div className="detail-section-grid detail-section-grid-secondary detail-section-grid-modal">
            <div className="detail-section card section-card">
              <div className="detail-section-title">
                <h4>提醒记录</h4>
                <span className="label-caption">Reminders</span>
              </div>
              <div className="stack-list">
                {task.reminders?.length ? task.reminders.map((reminder) => (
                  <div className="subcard inline" key={reminder.id}>
                    <strong>{formatDateTime(reminder.remind_at)}</strong>
                    <span className="muted">{reminder.channel} · {reminder.status}</span>
                    <span>{reminder.note || '无备注'}</span>
                  </div>
                )) : <EmptyState title="暂无提醒" description="现在没设，不代表未来不会忘。" compact />}
              </div>
            </div>

            <div className="detail-section card section-card">
              <div className="detail-section-title">
                <h4>最近变更</h4>
                <span className="label-caption">Timeline</span>
              </div>
              <div className="stack-list">
                {recentEvents.length ? recentEvents.map((event) => <EventRow key={event.id} event={event} />) : <EmptyState title="暂无事件" description="后端接更完整后，这里就是任务时间线。" compact />}
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}

function Pagination({ page, totalPages, onPageChange }: { page: number; totalPages: number; onPageChange?: (page: number) => void }) {
  if (!onPageChange) return null;

  return (
    <div className="pagination-bar">
      <button onClick={() => onPageChange(Math.max(1, page - 1))} disabled={page <= 1}>上一页</button>
      <span className="pagination-label">第 {page} / {totalPages} 页</span>
      <button onClick={() => onPageChange(Math.min(totalPages, page + 1))} disabled={page >= totalPages}>下一页</button>
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-item">
      <span className="label-caption">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MetaChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="meta-chip">
      <span>{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

function EventRow({ event }: { event: TaskEvent }) {
  return (
    <div className="subcard inline event-row">
      <div className="event-row-head">
        <strong>{event.event_type}</strong>
        <span className="muted">{formatDateTime(event.created_at)}</span>
      </div>
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
  return <div className="card empty-state"><strong>加载中…</strong><p className="muted">数据在路上，先别急着骂系统。</p></div>;
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
