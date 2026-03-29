export type TaskStatus = 'todo' | 'doing' | 'done' | 'deferred' | 'canceled';
export type TaskSource = 'chat' | 'web' | 'system' | 'seed' | string;
export type TaskRecurrenceKind = 'none' | 'monthly';

export interface TaskRecurrence {
  type: Exclude<TaskRecurrenceKind, 'none'>;
  day_of_month?: number | null;
  time_of_day?: string | null;
  timezone?: string | null;
}

export interface Reminder {
  id: number;
  task_id: number;
  remind_at: string;
  channel: string;
  status: 'scheduled' | 'fired' | 'canceled';
  note?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskEvent {
  id: number;
  task_id: number;
  event_type:
    | 'created'
    | 'updated'
    | 'status_changed'
    | 'reminder_added'
    | 'reminder_fired'
    | 'deferred'
    | 'completed'
    | 'canceled'
    | 'nightly_reviewed'
    | string;
  payload?: Record<string, unknown>;
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
  source?: TaskSource;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  canceled_at?: string | null;
  deferred_to?: string | null;
  recurrence?: TaskRecurrence | null;
  reminders?: Reminder[];
  events?: TaskEvent[];
}

export interface PlanGroup {
  key: string;
  title: string;
  group_date?: string | null;
  tasks: Task[];
}

export interface DashboardToday {
  date: string;
  summary: {
    total: number;
    dueToday: number;
    overdue: number;
    completed: number;
    open: number;
  };
  tasks: Task[];
  planGroups: PlanGroup[];
}

export interface TaskGroup {
  key: string;
  title: string;
  tasks: Task[];
  tone?: TaskStatus | 'project';
  meta?: string;
  renamable?: boolean;
}

export interface DashboardBoard {
  groups: TaskGroup[];
}

export interface ProjectSummary {
  name: string;
  task_count: number;
  open_task_count: number;
  done_task_count: number;
}

export interface ProjectRenameResponse {
  old_name: string;
  new_name: string;
  updated_task_count: number;
  project: ProjectSummary;
}

export interface HistoryResponse {
  items: Task[];
  total: number;
}

export interface TaskFilters {
  date?: string;
  status?: string;
  q?: string;
}

export interface TaskRecurrencePayload {
  type: TaskRecurrenceKind;
  day_of_month?: number | null;
  time_of_day?: string | null;
  timezone?: string | null;
}

export interface CreateTaskPayload {
  title: string;
  description?: string | null;
  due_at?: string | null;
  project?: string | null;
  tags?: string[];
  source?: TaskSource;
  reminders?: ReminderPayload[];
  recurrence?: TaskRecurrencePayload | null;
}

export interface UpdateTaskPayload {
  title?: string;
  description?: string | null;
  due_at?: string | null;
  status?: TaskStatus;
  project?: string | null;
  tags?: string[];
  recurrence?: TaskRecurrencePayload | null;
}

export interface DeferTaskPayload {
  deferred_to: string;
  due_at?: string;
  reason?: string;
}

export interface ReminderPayload {
  remind_at: string;
  channel: string;
  note?: string;
}
