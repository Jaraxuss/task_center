import { Task, TaskStatus } from './types';

export const statusMeta: Record<TaskStatus, { label: string; tone: string }> = {
  todo: { label: '待办', tone: 'slate' },
  doing: { label: '进行中', tone: 'blue' },
  done: { label: '已完成', tone: 'green' },
  deferred: { label: '已延期', tone: 'amber' },
  canceled: { label: '已取消', tone: 'red' },
};

export function formatDateTime(value?: string | null) {
  if (!value) return '未设置';
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
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

export function summarizeEvents(task: Task) {
  return task.events?.slice(0, 5) ?? [];
}
