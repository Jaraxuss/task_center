import { Task, TaskStatus } from './types';

export const statusMeta: Record<TaskStatus, { label: string; tone: string }> = {
  todo: { label: '待办', tone: 'slate' },
  doing: { label: '进行中', tone: 'blue' },
  done: { label: '已完成', tone: 'green' },
  deferred: { label: '已延期', tone: 'amber' },
  canceled: { label: '已取消', tone: 'red' },
};

export type TimeFormatMode = 'cn-short' | 'ymd-24' | 'slash-24';

const timeFormatOptions: Record<TimeFormatMode, Intl.DateTimeFormatOptions> = {
  'cn-short': { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' },
  'ymd-24': { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false },
  'slash-24': { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false },
};

export function getTimeFormatMode(): TimeFormatMode {
  if (typeof document === 'undefined') return 'cn-short';
  const value = document.documentElement.dataset.timeFormat as TimeFormatMode | undefined;
  return value && value in timeFormatOptions ? value : 'cn-short';
}

export function formatDateTime(value?: string | null) {
  if (!value) return '未设置';
  const date = new Date(value);
  const mode = getTimeFormatMode();

  if (mode === 'slash-24') {
    const parts = new Intl.DateTimeFormat('en-CA', timeFormatOptions[mode]).formatToParts(date);
    const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value || '';
    return `${get('year')}/${get('month')}/${get('day')} ${get('hour')}:${get('minute')}`;
  }

  return new Intl.DateTimeFormat('zh-CN', timeFormatOptions[mode]).format(date);
}

export function formatDateTimeInput(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  const localDate = new Date(date.getTime() - offset * 60000);
  return localDate.toISOString().slice(0, 16);
}

export function toIsoStringFromInput(value: string) {
  return value ? new Date(value).toISOString() : null;
}

export function getTaskSubtitle(task: Task) {
  const parts = [task.project, task.due_at ? `截止 ${formatDateTime(task.due_at)}` : undefined];
  return parts.filter(Boolean).join(' · ') || '无项目 / 无截止时间';
}

export function getTaskStateSummary(task: Task) {
  if (task.status === 'done' && task.completed_at) return `完成于 ${formatDateTime(task.completed_at)}`;
  if (task.status === 'deferred' && task.deferred_to) return `延期到 ${formatDateTime(task.deferred_to)}`;
  if (task.status === 'canceled' && task.canceled_at) return `取消于 ${formatDateTime(task.canceled_at)}`;
  if (task.due_at) return `截止 ${formatDateTime(task.due_at)}`;
  return '待安排';
}

export function summarizeEvents(task: Task) {
  return task.events?.slice(0, 5) ?? [];
}

export function sortTasksByRecency(tasks: Task[]) {
  return [...tasks].sort((a, b) => {
    const aTime = new Date(a.updated_at || a.created_at).getTime();
    const bTime = new Date(b.updated_at || b.created_at).getTime();
    return bTime - aTime;
  });
}

export function groupTasksByProject(tasks: Task[]) {
  const map = new Map<string, Task[]>();
  tasks.forEach((task) => {
    const key = task.project?.trim() || '未分组项目';
    map.set(key, [...(map.get(key) || []), task]);
  });

  return Array.from(map.entries())
    .map(([title, items]) => ({
      key: `project:${title}`,
      title,
      tone: 'project' as const,
      meta: `${items.length} 项`,
      tasks: sortTasksByRecency(items),
    }))
    .sort((a, b) => b.tasks.length - a.tasks.length || a.title.localeCompare(b.title, 'zh-CN'));
}
