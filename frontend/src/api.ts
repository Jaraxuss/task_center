import {
  DashboardBoard,
  DashboardToday,
  DeferTaskPayload,
  HistoryResponse,
  ReminderPayload,
  Task,
  TaskEvent,
  TaskFilters,
  TaskStatus,
  UpdateTaskPayload,
} from './types';
import { API_BASE_URL } from './config';

const boardTitles: Record<TaskStatus, string> = {
  todo: '待办',
  doing: '进行中',
  deferred: '已延期',
  done: '已完成',
  canceled: '已取消',
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `请求失败: ${response.status}`);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function toSearchParams(filters?: TaskFilters) {
  const params = new URLSearchParams();
  if (!filters) return '';

  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });

  const query = params.toString();
  return query ? `?${query}` : '';
}

function normalizeEvent(event: Partial<TaskEvent> & { payload?: Record<string, unknown> }) : TaskEvent {
  return {
    id: Number(event.id),
    task_id: Number(event.task_id),
    event_type: event.event_type || 'updated',
    payload: event.payload || {},
    created_at: event.created_at || new Date().toISOString(),
  };
}

function normalizeTask(task: any): Task {
  return {
    id: Number(task.id),
    title: task.title,
    description: task.description ?? null,
    due_at: task.due_at ?? null,
    status: task.status,
    project: task.project ?? null,
    tags: Array.isArray(task.tags) ? task.tags : [],
    source: task.source,
    created_at: task.created_at,
    updated_at: task.updated_at,
    completed_at: task.completed_at ?? null,
    canceled_at: task.canceled_at ?? null,
    deferred_to: task.deferred_to ?? null,
    reminders: Array.isArray(task.reminders)
      ? task.reminders.map((reminder: any) => ({ ...reminder, id: Number(reminder.id), task_id: Number(reminder.task_id) }))
      : [],
    events: Array.isArray(task.events) ? task.events.map(normalizeEvent) : [],
  };
}

export const api = {
  baseUrl: API_BASE_URL,
  getHealth: () => request<{ status: string }>('/api/health'),
  getTasks: async (filters?: TaskFilters) => (await request<any[]>(`/api/tasks${toSearchParams(filters)}`)).map(normalizeTask),
  getTask: async (id: number) => normalizeTask(await request<any>(`/api/tasks/${id}`)),
  updateTask: async (id: number, payload: UpdateTaskPayload) =>
    normalizeTask(
      await request<any>(`/api/tasks/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }),
    ),
  completeTask: async (id: number) =>
    normalizeTask(
      await request<any>(`/api/tasks/${id}/complete`, {
        method: 'POST',
        body: JSON.stringify({}),
      }),
    ),
  deferTask: async (id: number, payload: DeferTaskPayload) =>
    normalizeTask(
      await request<any>(`/api/tasks/${id}/defer`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    ),
  cancelTask: async (id: number, reason?: string) =>
    normalizeTask(
      await request<any>(`/api/tasks/${id}/cancel`, {
        method: 'POST',
        body: JSON.stringify(reason ? { reason } : {}),
      }),
    ),
  addReminder: async (id: number, payload: ReminderPayload) =>
    normalizeTask(
      await request<any>(`/api/tasks/${id}/reminders`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    ),
  getHistory: async (filters?: TaskFilters) => {
    const response = await request<any>(`/api/history${toSearchParams(filters)}`);
    return {
      items: Array.isArray(response.tasks) ? response.tasks.map(normalizeTask) : [],
      total: Number(response.total || 0),
    } satisfies HistoryResponse;
  },
  getTodayDashboard: async () => {
    const response = await request<any>('/api/dashboard/today');
    const tasks = Array.isArray(response.tasks) ? response.tasks.map(normalizeTask) : [];
    const now = Date.now();
    const completed = tasks.filter((task: Task) => task.status === 'done').length;
    const overdue = tasks.filter((task: Task) => task.status !== 'done' && task.status !== 'canceled' && task.due_at && new Date(task.due_at).getTime() < now).length;
    return {
      date: response.date,
      summary: {
        total: Number(response.total || tasks.length),
        dueToday: tasks.length,
        overdue,
        completed,
        open: Number(response.open_count || 0),
      },
      tasks,
    } satisfies DashboardToday;
  },
  getBoardDashboard: async () => {
    const response = await request<any>('/api/dashboard/board');
    return {
      groups: Array.isArray(response.groups)
        ? response.groups.map((group: any) => ({
            status: group.status,
            title: boardTitles[group.status as TaskStatus] || group.status,
            tasks: Array.isArray(group.tasks) ? group.tasks.map(normalizeTask) : [],
          }))
        : [],
    } satisfies DashboardBoard;
  },
  getHistoryDashboard: async (filters?: TaskFilters) => {
    const response = await request<any>(`/api/dashboard/history${toSearchParams(filters)}`);
    return {
      items: Array.isArray(response.tasks) ? response.tasks.map(normalizeTask) : [],
      total: Number(response.total || 0),
    } satisfies HistoryResponse;
  },
};
