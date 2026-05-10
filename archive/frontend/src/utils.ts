import { Task, TaskRecurrence, TaskStatus } from './types';

export const APP_TIME_ZONE = 'Asia/Shanghai';

export const statusMeta: Record<TaskStatus, { label: string; tone: string }> = {
  todo: { label: '待办', tone: 'slate' },
  doing: { label: '进行中', tone: 'blue' },
  done: { label: '已完成', tone: 'green' },
  deferred: { label: '已延期', tone: 'amber' },
  canceled: { label: '已取消', tone: 'red' },
};

export type TimeFormatMode = 'cn-short' | 'ymd-24' | 'slash-24';

const timeFormatOptions: Record<TimeFormatMode, Intl.DateTimeFormatOptions> = {
  'cn-short': { timeZone: APP_TIME_ZONE, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false },
  'ymd-24': { timeZone: APP_TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false },
  'slash-24': { timeZone: APP_TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false },
};

export function getTimeFormatMode(): TimeFormatMode {
  if (typeof document === 'undefined') return 'cn-short';
  const value = document.documentElement.dataset.timeFormat as TimeFormatMode | undefined;
  return value && value in timeFormatOptions ? value : 'cn-short';
}

export function getLocalTimeZone() {
  return APP_TIME_ZONE;
}

function getDateFormatterParts(value: Date) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: APP_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(value);
}

function getNaiveDateTimeParts(value?: string | null) {
  if (!value) return null;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?)?$/);
  if (!match) return null;
  return {
    year: match[1],
    month: match[2],
    day: match[3],
    hour: match[4] || '00',
    minute: match[5] || '00',
    dateKey: `${match[1]}-${match[2]}-${match[3]}`,
  };
}

export function getDateKey(value?: string | null) {
  if (!value) return null;
  const naive = getNaiveDateTimeParts(value);
  if (naive) return naive.dateKey;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const parts = getDateFormatterParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value || '';
  return `${get('year')}-${get('month')}-${get('day')}`;
}

export function currentDateKey(date = new Date()) {
  return getDateKey(date.toISOString()) || date.toISOString().slice(0, 10);
}

export function toDateMillis(value?: string | null) {
  if (!value) return Number.NaN;
  const naive = getNaiveDateTimeParts(value);
  if (naive) return new Date(`${naive.dateKey}T${naive.hour}:${naive.minute}:00+08:00`).getTime();
  return new Date(value).getTime();
}

export function formatDateTime(value?: string | null) {
  if (!value) return '未设置';
  const naive = getNaiveDateTimeParts(value);
  if (naive) return `${naive.month}/${naive.day} ${naive.hour}:${naive.minute}`;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
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
  const naive = getNaiveDateTimeParts(value);
  if (naive) return `${naive.dateKey}T${naive.hour}:${naive.minute}`;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const parts = getDateFormatterParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value || '';
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`;
}

export function toIsoStringFromInput(value: string) {
  return value ? new Date(`${value}:00+08:00`).toISOString() : null;
}

function normalizeTimeOfDay(value?: string | null) {
  if (!value) return null;
  const matched = value.match(/^(\d{1,2}):(\d{2})/);
  if (!matched) return value;
  return `${matched[1].padStart(2, '0')}:${matched[2]}`;
}

export function normalizeTaskRecurrence(value: any): TaskRecurrence | null {
  if (!value) return null;
  const rawType = String(value.type || value.kind || value.frequency || '').toLowerCase();
  if (!rawType || rawType === 'none' || rawType === 'once' || rawType === 'single') return null;

  if (rawType === 'monthly' || rawType === 'monthly_fixed_day' || rawType === 'monthly_fixed') {
    const dayOfMonth = Number(value.day_of_month ?? value.dayOfMonth ?? value.month_day ?? value.day);
    return {
      type: 'monthly',
      day_of_month: Number.isFinite(dayOfMonth) && dayOfMonth > 0 ? dayOfMonth : null,
      time_of_day: normalizeTimeOfDay(value.time_of_day ?? value.timeOfDay ?? value.time ?? value.at),
      timezone: value.timezone || value.tz || null,
    };
  }

  return {
    type: 'monthly',
    day_of_month: Number(value.day_of_month ?? value.dayOfMonth) || null,
    time_of_day: normalizeTimeOfDay(value.time_of_day ?? value.timeOfDay ?? value.time ?? value.at),
    timezone: value.timezone || value.tz || null,
  };
}

export function formatTaskRecurrence(recurrence?: TaskRecurrence | null) {
  if (!recurrence) return '不重复';
  if (recurrence.type === 'monthly') {
    const day = recurrence.day_of_month ? `${recurrence.day_of_month} 日` : '固定日';
    const time = recurrence.time_of_day || '--:--';
    return `每月 ${day} ${time}`;
  }
  return '不重复';
}

export function getTaskSubtitle(task: Task) {
  const parts = [task.project, task.due_at ? `截止 ${formatDateTime(task.due_at)}` : undefined, task.recurrence ? formatTaskRecurrence(task.recurrence) : undefined];
  return parts.filter(Boolean).join(' · ') || '无项目 / 无截止时间';
}

export function getTaskStateSummary(task: Task) {
  if (task.status === 'done' && task.completed_at) return `完成于 ${formatDateTime(task.completed_at)}`;
  if (task.status === 'deferred' && task.deferred_to) return `延期到 ${formatDateTime(task.deferred_to)}`;
  if (task.status === 'canceled' && task.canceled_at) return `取消于 ${formatDateTime(task.canceled_at)}`;
  if (task.due_at) return `截止 ${formatDateTime(task.due_at)}`;
  if (task.recurrence) return formatTaskRecurrence(task.recurrence);
  return '待安排';
}

export function summarizeEvents(task: Task) {
  return task.events?.slice(0, 5) ?? [];
}

export function sortTasksByRecency(tasks: Task[]) {
  return [...tasks].sort((a, b) => {
    const aTime = toDateMillis(a.updated_at || a.created_at);
    const bTime = toDateMillis(b.updated_at || b.created_at);
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
      meta: title === '未分组项目' ? '未填写项目的任务' : `${items.length} 项`,
      renamable: title !== '未分组项目',
      tasks: sortTasksByRecency(items),
    }))
    .sort((a, b) => b.tasks.length - a.tasks.length || a.title.localeCompare(b.title, 'zh-CN'));
}
