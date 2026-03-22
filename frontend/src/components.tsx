import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react';
import { Task, TaskEvent, TaskGroup, TaskStatus } from './types';
import {
  formatDateTime,
  formatDateTimeInput,
  getTaskSubtitle,
  getTaskStateSummary,
  statusMeta,
  summarizeEvents,
  TimeFormatMode,
  toIsoStringFromInput,
} from './utils';

interface LayoutProps {
  activeView: string;
  onChangeView: (view: 'today' | 'board' | 'history') => void;
  apiBaseUrl: string;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  timeFormat: TimeFormatMode;
  onTimeFormatChange: (value: TimeFormatMode) => void;
  children: ReactNode;
}

export type BoardFilterField = 'title' | 'description' | 'due_at' | 'project' | 'status';
export type BoardFilterOperator = 'contains' | 'not_contains' | 'is' | 'is_not' | 'is_empty' | 'is_not_empty' | 'on' | 'before' | 'after';
export type BoardVisibleField = 'title' | 'description' | 'due_at' | 'project' | 'status';

export interface BoardFilterCondition {
  id: string;
  field: BoardFilterField;
  operator: BoardFilterOperator;
  value?: string;
}

const tabs = [
  { key: 'today', label: '今日', icon: '01' },
  { key: 'board', label: '看板', icon: '02' },
  { key: 'history', label: '历史', icon: '03' },
] as const;

const timeFormatOptions: Array<{ value: TimeFormatMode; label: string; sample: string }> = [
  { value: 'cn-short', label: '月日 + 时间', sample: '03-22 20:30' },
  { value: 'ymd-24', label: '完整日期', sample: '2026-03-22 20:30' },
  { value: 'slash-24', label: '斜杠格式', sample: '2026/03/22 20:30' },
];

const boardFieldMeta: Record<BoardFilterField, { label: string; type: 'text' | 'enum' | 'date' }> = {
  title: { label: '标题', type: 'text' },
  description: { label: '内容', type: 'text' },
  due_at: { label: '日期', type: 'date' },
  project: { label: '项目', type: 'enum' },
  status: { label: '状态', type: 'enum' },
};

const fieldOperatorOptions: Record<'text' | 'enum' | 'date', Array<{ value: BoardFilterOperator; label: string }>> = {
  text: [
    { value: 'contains', label: '包含' },
    { value: 'not_contains', label: '不包含' },
    { value: 'is', label: '等于' },
    { value: 'is_not', label: '不等于' },
    { value: 'is_empty', label: '为空' },
    { value: 'is_not_empty', label: '不为空' },
  ],
  enum: [
    { value: 'is', label: '是' },
    { value: 'is_not', label: '不是' },
    { value: 'is_empty', label: '为空' },
    { value: 'is_not_empty', label: '不为空' },
  ],
  date: [
    { value: 'on', label: '当天' },
    { value: 'before', label: '早于' },
    { value: 'after', label: '晚于' },
    { value: 'is_empty', label: '未设置' },
    { value: 'is_not_empty', label: '已设置' },
  ],
};

const visibleFieldOptions: Array<{ key: BoardVisibleField; label: string }> = [
  { key: 'title', label: '标题' },
  { key: 'description', label: '内容' },
  { key: 'due_at', label: '日期' },
  { key: 'project', label: '项目' },
  { key: 'status', label: '状态' },
];

const statusOptions: Array<{ value: TaskStatus; label: string }> = [
  { value: 'todo', label: '待办' },
  { value: 'doing', label: '进行中' },
  { value: 'done', label: '已完成' },
  { value: 'deferred', label: '已延期' },
  { value: 'canceled', label: '已取消' },
];

export function Layout({ activeView, onChangeView, apiBaseUrl, theme, onToggleTheme, timeFormat, onTimeFormatChange, children }: LayoutProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-card brand-block">
          <div className="brand-copy brand-copy-block">
            <span className="brand-kicker">Task Center</span>
            <h1>任务中心</h1>
          </div>
        </div>

        <nav className="nav-list" aria-label="主视图切换">
          {tabs.map((tab) => (
            <button key={tab.key} className={`nav-item ${activeView === tab.key ? 'active' : ''}`} onClick={() => onChangeView(tab.key)}>
              <span className="nav-icon">{tab.icon}</span>
              <span className="nav-copy">
                <span className="nav-label">{tab.label}</span>
              </span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer card subtle-card">
          <button className="settings-trigger" onClick={() => setSettingsOpen(true)}>
            <span aria-hidden="true">⚙</span>
            <span>设置</span>
          </button>
          <div className="sidebar-divider" />
          <span className="label-caption">API Endpoint</span>
          <code>{apiBaseUrl}</code>
        </div>
      </aside>
      <main className="main-content">{children}</main>
      {settingsOpen ? (
        <ModalFrame title="设置" onClose={() => setSettingsOpen(false)} width="520px">
          <div className="settings-panel-grid">
            <div className="settings-panel-card">
              <div>
                <span className="label-caption">主题</span>
                <strong>外观模式</strong>
              </div>
              <button className="ghost-toggle" onClick={onToggleTheme}>
                <span aria-hidden="true">{theme === 'dark' ? '☀️' : '🌙'}</span>
                <span>{theme === 'dark' ? '切到浅色' : '切到深色'}</span>
              </button>
            </div>

            <label className="field">
              <span className="label-caption">时间显示</span>
              <select value={timeFormat} onChange={(e) => onTimeFormatChange(e.target.value as TimeFormatMode)}>
                {timeFormatOptions.map((option) => (
                  <option value={option.value} key={option.value}>
                    {option.label} · {option.sample}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </ModalFrame>
      ) : null}
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
  eyebrow?: string;
  title: string;
  description?: string;
  highlight?: string;
  metrics?: Array<{ label: string; value: string; tone?: 'default' | 'brand' | 'success' | 'danger' }>;
}) {
  return (
    <section className="view-hero card card-elevated compact-hero">
      <div className="view-hero-main compact-hero-main">
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <h2>{title}</h2>
        {description ? <p className="hero-description">{description}</p> : null}
      </div>
      {(highlight || metrics?.length) ? (
        <div className="hero-callout compact-hero-side">
          {highlight ? (
            <div className="hero-callout-card hero-callout-highlight compact-callout">
              <strong>{highlight}</strong>
            </div>
          ) : null}
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
      ) : null}
    </section>
  );
}

export function SectionHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="section-header compact-section-header">
      <div>
        <h3>{title}</h3>
        {description ? <p className="muted">{description}</p> : null}
      </div>
      {actions ? <div className="section-actions">{actions}</div> : null}
    </div>
  );
}

export function Panel({ title, description, actions, children }: { title: string; description?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="panel card compact-panel">
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
  if (!tasks.length) return <EmptyState title="没有任务" description="这里目前没有内容。" />;

  const totalPages = Math.max(1, Math.ceil(tasks.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const startIndex = (safePage - 1) * pageSize;
  const visibleTasks = tasks.slice(startIndex, startIndex + pageSize);

  return (
    <div className="task-list-shell">
      <div className="task-list-meta muted">
        <span>共 {tasks.length} 项</span>
        <span>
          当前显示 {startIndex + 1}-{Math.min(startIndex + visibleTasks.length, tasks.length)} 项
        </span>
      </div>
      <div className="task-list fade-in">
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
  groupMode,
  onGroupModeChange,
  filters,
  onFiltersChange,
  visibleFields,
  onVisibleFieldsChange,
  projectOptions,
  onRenameProject,
  renamingProject,
  renameProjectSupported,
}: {
  groups: TaskGroup[];
  onSelect: (task: Task) => void;
  selectedTaskId?: number;
  groupMode: 'status' | 'project';
  onGroupModeChange: (mode: 'status' | 'project') => void;
  filters: BoardFilterCondition[];
  onFiltersChange: (filters: BoardFilterCondition[]) => void;
  visibleFields: BoardVisibleField[];
  onVisibleFieldsChange: (fields: BoardVisibleField[]) => void;
  projectOptions: string[];
  onRenameProject: (currentName: string, nextName: string) => Promise<void>;
  renamingProject?: string | null;
  renameProjectSupported?: boolean;
}) {
  const [builderOpen, setBuilderOpen] = useState(false);

  const addCondition = () => {
    const nextId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    onFiltersChange([...filters, { id: nextId, field: 'title', operator: 'contains', value: '' }]);
  };

  const updateCondition = (id: string, patch: Partial<BoardFilterCondition>) => {
    onFiltersChange(
      filters.map((condition) => {
        if (condition.id !== id) return condition;
        const nextField = patch.field ?? condition.field;
        const fieldType = boardFieldMeta[nextField].type;
        const defaultOperator = fieldOperatorOptions[fieldType][0].value;
        return {
          ...condition,
          ...patch,
          operator: patch.field && !patch.operator ? defaultOperator : patch.operator ?? condition.operator,
          value: patch.field ? '' : patch.value ?? condition.value,
        };
      }),
    );
  };

  const removeCondition = (id: string) => onFiltersChange(filters.filter((condition) => condition.id !== id));

  const toggleField = (field: BoardVisibleField) => {
    const exists = visibleFields.includes(field);
    if (exists && visibleFields.length === 1) return;
    onVisibleFieldsChange(exists ? visibleFields.filter((item) => item !== field) : [...visibleFields, field]);
  };

  return (
    <div className="board-shell">
      <div className="board-toolbar board-toolbar-compact">
        <div className="toolbar-inline toolbar-wrap">
          <div className="segmented-control" role="tablist" aria-label="看板分组方式">
            <button className={groupMode === 'status' ? 'active' : ''} onClick={() => onGroupModeChange('status')}>
              按状态
            </button>
            <button className={groupMode === 'project' ? 'active' : ''} onClick={() => onGroupModeChange('project')}>
              按项目
            </button>
          </div>
          <button onClick={() => setBuilderOpen((current) => !current)}>{builderOpen ? '收起筛选' : '筛选'}</button>
        </div>
        <div className="toolbar-inline toolbar-wrap field-toggle-wrap">
          <span className="label-caption">显示字段</span>
          {visibleFieldOptions.map((option) => (
            <label className="checkbox-chip" key={option.key}>
              <input type="checkbox" checked={visibleFields.includes(option.key)} onChange={() => toggleField(option.key)} />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </div>

      {builderOpen ? (
        <div className="board-filter-builder card fade-in">
          <div className="board-filter-builder-header">
            <div>
              <h4>筛选条件</h4>
              <p className="muted">支持多条条件组合，字段类型自动切换可用运算符。</p>
            </div>
            <div className="toolbar-inline toolbar-wrap">
              <button onClick={addCondition}>添加条件</button>
              {filters.length ? <button onClick={() => onFiltersChange([])}>清空</button> : null}
            </div>
          </div>
          {filters.length ? (
            <div className="board-filter-list">
              {filters.map((condition) => {
                const fieldType = boardFieldMeta[condition.field].type;
                const operators = fieldOperatorOptions[fieldType];
                const needsValue = !['is_empty', 'is_not_empty'].includes(condition.operator);
                return (
                  <div className="board-filter-row" key={condition.id}>
                    <select value={condition.field} onChange={(e) => updateCondition(condition.id, { field: e.target.value as BoardFilterField })}>
                      {Object.entries(boardFieldMeta).map(([value, meta]) => (
                        <option value={value} key={value}>{meta.label}</option>
                      ))}
                    </select>
                    <select value={condition.operator} onChange={(e) => updateCondition(condition.id, { operator: e.target.value as BoardFilterOperator })}>
                      {operators.map((operator) => (
                        <option value={operator.value} key={operator.value}>{operator.label}</option>
                      ))}
                    </select>
                    {needsValue ? (
                      <FilterValueInput
                        field={condition.field}
                        value={condition.value || ''}
                        onChange={(value) => updateCondition(condition.id, { value })}
                      />
                    ) : (
                      <div className="filter-value-placeholder muted">无需值</div>
                    )}
                    <button className="icon-button" onClick={() => removeCondition(condition.id)} aria-label="删除条件">✕</button>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="empty-state compact">
              <strong>暂无筛选条件</strong>
              <p className="muted">点“添加条件”开始组合筛选。</p>
            </div>
          )}
        </div>
      ) : null}

      <div className="board-scroll-shell">
        <div className="board-grid board-grid-scrollable fade-in">
          {groups.map((group) => (
            <BoardColumn
              key={group.key}
              group={group}
              onSelect={onSelect}
              selectedTaskId={selectedTaskId}
              visibleFields={visibleFields}
              allowRename={groupMode === 'project' && group.renamable !== false}
              onRenameProject={onRenameProject}
              renamingProject={renamingProject}
              renameProjectSupported={renameProjectSupported}
            />
          ))}
        </div>
      </div>
      <datalist id="board-project-options">
        {projectOptions.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </div>
  );
}

function FilterValueInput({
  field,
  value,
  onChange,
}: {
  field: BoardFilterField;
  value: string;
  onChange: (value: string) => void;
}) {
  if (field === 'status') {
    return (
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">选择状态</option>
        {statusOptions.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    );
  }

  if (field === 'project') {
    return (
      <input list="board-project-options" value={value} onChange={(e) => onChange(e.target.value)} placeholder="输入或选择项目" />
    );
  }

  if (field === 'due_at') {
    return <input type="date" value={value} onChange={(e) => onChange(e.target.value)} />;
  }

  return <input value={value} onChange={(e) => onChange(e.target.value)} placeholder="输入筛选值" />;
}

function BoardColumn({
  group,
  onSelect,
  selectedTaskId,
  visibleFields,
  allowRename,
  onRenameProject,
  renamingProject,
  renameProjectSupported,
}: {
  group: TaskGroup;
  onSelect: (task: Task) => void;
  selectedTaskId?: number;
  visibleFields: BoardVisibleField[];
  allowRename?: boolean;
  onRenameProject: (currentName: string, nextName: string) => Promise<void>;
  renamingProject?: string | null;
  renameProjectSupported?: boolean;
}) {
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState(group.title);
  const [renameError, setRenameError] = useState<string | null>(null);

  useEffect(() => {
    setTitleDraft(group.title);
    setIsEditingTitle(false);
    setRenameError(null);
  }, [group.title]);

  const submitRename = async (e: FormEvent) => {
    e.preventDefault();
    const nextName = titleDraft.trim();
    if (!nextName || nextName === group.title) {
      setIsEditingTitle(false);
      setTitleDraft(group.title);
      setRenameError(null);
      return;
    }
    setRenameError(null);
    try {
      await onRenameProject(group.title, nextName);
      setIsEditingTitle(false);
    } catch (error) {
      setRenameError(error instanceof Error ? error.message : '项目重命名失败');
    }
  };

  return (
    <section className="card board-column">
      <div className="board-column-header">
        <div className="board-column-header-main">
          {group.tone === 'project' ? <span className="group-badge">项目</span> : <StatusBadge status={group.tone || 'todo'} />}
          {allowRename ? (
            <div className="board-column-title-row">
              {isEditingTitle ? (
                <form className="inline-rename-form" onSubmit={submitRename}>
                  <input value={titleDraft} onChange={(e) => { setTitleDraft(e.target.value); if (renameError) setRenameError(null); }} aria-label="项目名称" />
                  <button type="submit" disabled={renamingProject === group.title}>保存</button>
                  <button type="button" onClick={() => { setIsEditingTitle(false); setTitleDraft(group.title); setRenameError(null); }}>取消</button>
                </form>
              ) : (
                <>
                  <h4>{group.title}</h4>
                  <button className="ghost-link" onClick={() => setIsEditingTitle(true)}>
                    重命名
                  </button>
                </>
              )}
            </div>
          ) : (
            <h4>{group.title}</h4>
          )}
          {group.meta ? <p className="muted board-column-meta">{group.meta}</p> : null}
          {allowRename && !renameProjectSupported ? <p className="muted board-column-meta">当前项目改名接口不可用。</p> : null}
          {renameError ? <p className="board-inline-feedback danger">{renameError}</p> : null}
        </div>
        <span className="pill">{group.tasks.length}</span>
      </div>
      <div className="board-column-body">
        {group.tasks.length ? (
          group.tasks.map((task) => (
            <button key={task.id} className={`board-task ${selectedTaskId === task.id ? 'selected' : ''}`} onClick={() => onSelect(task)}>
              {visibleFields.includes('status') ? (
                <div className="board-task-status-row">
                  <StatusBadge status={task.status} />
                  <span className="task-row-meta">#{task.id}</span>
                </div>
              ) : null}
              {visibleFields.includes('title') ? (
                <div className="board-task-topline">
                  <strong>{task.title}</strong>
                  {!visibleFields.includes('status') ? <span className="task-row-meta">#{task.id}</span> : null}
                </div>
              ) : null}
              {visibleFields.includes('description') ? <span className="muted board-task-description">{truncateText(task.description || '暂无描述', 30)}</span> : null}
              <div className="board-task-footer">
                {visibleFields.includes('due_at') ? <MetaChip label="日期" value={task.due_at ? formatDateTime(task.due_at) : '未设置'} /> : null}
                {visibleFields.includes('project') ? <MetaChip label="项目" value={task.project || '未分组'} /> : null}
              </div>
            </button>
          ))
        ) : (
          <EmptyState title="空列" description="这里暂时没有任务。" compact />
        )}
      </div>
    </section>
  );
}

function truncateText(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

function ModalFrame({ title, onClose, children, width = '860px' }: { title: string; onClose: () => void; children: ReactNode; width?: string }) {
  useEffect(() => {
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
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <aside className="detail-modal card card-elevated" style={{ width }} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={title}>
        <div className="detail-modal-header">
          <div className="detail-header-main">
            <h3>{title}</h3>
          </div>
          <div className="detail-modal-actions">
            <button className="icon-button" onClick={onClose} aria-label="关闭">✕</button>
          </div>
        </div>
        {children}
      </aside>
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
    <div className="filters-toolbar card fade-in">
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
  isLoadingDetails,
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
  isLoadingDetails?: boolean;
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
    <ModalFrame title={`任务 ${task.title}`} onClose={onClose}>
      <div className="detail-header-main">
        <div className="detail-header-topline">
          <StatusBadge status={task.status} />
          <span className="task-row-meta">任务 #{task.id}</span>
          {isLoadingDetails ? <span className="loading-dot">详情更新中…</span> : null}
        </div>
        <p className="muted">{task.description || '暂无描述'}</p>
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
                <input type="datetime-local" value={scheduleValue} onChange={(e) => setScheduleValue(e.target.value)} />
                <button type="submit" disabled={busyAction === 'schedule'}>{busyAction === 'schedule' ? '保存中…' : '保存时间'}</button>
              </form>

              <form className="subcard action-card" onSubmit={submitDefer}>
                <h5>延期</h5>
                <input type="datetime-local" value={deferValue} onChange={(e) => setDeferValue(e.target.value)} />
                <textarea rows={3} placeholder="延期说明（可选）" value={deferNote} onChange={(e) => setDeferNote(e.target.value)} />
                <button type="submit" disabled={busyAction === 'defer'}>{busyAction === 'defer' ? '处理中…' : '确认延期'}</button>
              </form>

              <form className="subcard action-card" onSubmit={submitReminder}>
                <h5>添加提醒</h5>
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
              )) : <EmptyState title="暂无提醒" description="现在没有提醒。" compact />}
            </div>
          </div>

          <div className="detail-section card section-card">
            <div className="detail-section-title">
              <h4>最近变更</h4>
              <span className="label-caption">Timeline</span>
            </div>
            <div className="stack-list">
              {recentEvents.length ? recentEvents.map((event) => <EventRow key={event.id} event={event} />) : <EmptyState title="暂无事件" description="后端补全后会显示更多时间线。" compact />}
            </div>
          </div>
        </div>

        <div className="detail-modal-actions footer-actions">
          <button className="primary" disabled={busyAction === 'complete'} onClick={() => onComplete(task)}>
            {busyAction === 'complete' ? '处理中…' : '标记完成'}
          </button>
        </div>
      </div>
    </ModalFrame>
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

export function LoadingState({ mode = 'default' }: { mode?: 'default' | 'list' | 'board' }) {
  if (mode === 'list') {
    return (
      <div className="skeleton-stack">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className="card skeleton-card" key={index}>
            <div className="skeleton-line short shimmer" />
            <div className="skeleton-line shimmer" />
            <div className="skeleton-line medium shimmer" />
          </div>
        ))}
      </div>
    );
  }

  if (mode === 'board') {
    return (
      <div className="board-grid board-grid-scrollable">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className="card board-column" key={index}>
            <div className="skeleton-line short shimmer" />
            <div className="skeleton-stack">
              {Array.from({ length: 3 }).map((__, taskIndex) => (
                <div className="board-task skeleton-card" key={taskIndex}>
                  <div className="skeleton-line shimmer" />
                  <div className="skeleton-line medium shimmer" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return <div className="card empty-state"><strong>加载中…</strong><p className="muted">数据加载中。</p></div>;
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
