import { useEffect, useMemo, useState } from 'react';
import { api } from './api';
import { useAsyncData, useLocalStorage } from './hooks';
import {
  BoardColumns,
  BoardFilterCondition,
  BoardVisibleField,
  ErrorState,
  HistoryFilters,
  Layout,
  LoadingState,
  Panel,
  TaskDetailModal,
  TaskList,
  ViewHero,
} from './components';
import { DashboardBoard, DashboardToday, HistoryResponse, ProjectSummary, Task, TaskGroup, TaskStatus } from './types';
import { groupTasksByProject, sortTasksByRecency, TimeFormatMode } from './utils';

type ViewMode = 'today' | 'board' | 'history';
type ThemeMode = 'light' | 'dark';
type BoardGroupMode = 'status' | 'project';

const viewMeta: Record<ViewMode, { eyebrow: string; title: string }> = {
  today: {
    eyebrow: 'Today',
    title: '今日',
  },
  board: {
    eyebrow: 'Board',
    title: '看板',
  },
  history: {
    eyebrow: 'History',
    title: '历史',
  },
};

const defaultBoardVisibleFields: BoardVisibleField[] = ['title', 'description', 'due_at', 'project', 'status'];

function computeTodaySummary(tasks: Task[], date = new Date().toISOString().slice(0, 10)): DashboardToday['summary'] {
  const now = Date.now();
  const completed = tasks.filter((task) => task.status === 'done').length;
  const overdue = tasks.filter((task) => task.status !== 'done' && task.status !== 'canceled' && task.due_at && new Date(task.due_at).getTime() < now).length;
  const open = tasks.filter((task) => task.status !== 'done' && task.status !== 'canceled').length;
  const dueToday = tasks.filter((task) => task.due_at?.slice(0, 10) === date).length;

  return {
    total: tasks.length,
    dueToday,
    overdue,
    completed,
    open,
  };
}

function upsertTask(list: Task[], updatedTask: Task) {
  const exists = list.some((task) => task.id === updatedTask.id);
  const next = exists ? list.map((task) => (task.id === updatedTask.id ? updatedTask : task)) : [updatedTask, ...list];
  return sortTasksByRecency(next);
}

function matchesBoardCondition(task: Task, condition: BoardFilterCondition) {
  const value = (condition.value || '').trim();

  if (condition.field === 'title' || condition.field === 'description') {
    const target = String(condition.field === 'title' ? task.title : task.description || '').toLowerCase();
    const input = value.toLowerCase();
    switch (condition.operator) {
      case 'contains':
        return target.includes(input);
      case 'not_contains':
        return !target.includes(input);
      case 'is':
        return target === input;
      case 'is_not':
        return target !== input;
      case 'is_empty':
        return !target;
      case 'is_not_empty':
        return Boolean(target);
      default:
        return true;
    }
  }

  if (condition.field === 'project' || condition.field === 'status') {
    const target = String(condition.field === 'project' ? task.project || '' : task.status || '');
    switch (condition.operator) {
      case 'is':
        return target === value;
      case 'is_not':
        return target !== value;
      case 'is_empty':
        return !target;
      case 'is_not_empty':
        return Boolean(target);
      default:
        return true;
    }
  }

  if (condition.field === 'due_at') {
    const target = task.due_at?.slice(0, 10) || '';
    switch (condition.operator) {
      case 'on':
        return target === value;
      case 'before':
        return Boolean(target) && target < value;
      case 'after':
        return Boolean(target) && target > value;
      case 'is_empty':
        return !target;
      case 'is_not_empty':
        return Boolean(target);
      default:
        return true;
    }
  }

  return true;
}

function App() {
  const [activeView, setActiveView] = useState<ViewMode>('today');
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [theme, setTheme] = useLocalStorage<ThemeMode>('task-center-theme', 'light');
  const [timeFormat, setTimeFormat] = useLocalStorage<TimeFormatMode>('task-center-time-format', 'cn-short');
  const [todayPageSize, setTodayPageSize] = useLocalStorage<number>('task-center-today-page-size', 10);
  const [todayPage, setTodayPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useLocalStorage<number>('task-center-history-page-size', 20);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyFilters, setHistoryFilters] = useState({ q: '', status: '', date: '' });
  const [historyQuery, setHistoryQuery] = useState(historyFilters);
  const [boardGroupMode, setBoardGroupMode] = useState<BoardGroupMode>('status');
  const [boardFilters, setBoardFilters] = useLocalStorage<BoardFilterCondition[]>('task-center-board-filters', []);
  const [boardVisibleFields, setBoardVisibleFields] = useLocalStorage<BoardVisibleField[]>('task-center-board-visible-fields', defaultBoardVisibleFields);
  const [renamingProject, setRenamingProject] = useState<string | null>(null);
  const [boardFeedback, setBoardFeedback] = useState<{ tone: 'success' | 'danger'; message: string } | null>(null);

  const today = useAsyncData(() => api.getTodayDashboard(), [], activeView === 'today');
  const board = useAsyncData(() => api.getBoardDashboard(), [], activeView === 'board');
  const projects = useAsyncData(() => api.getProjects(), [], activeView === 'board');
  const history = useAsyncData(
    () => api.getHistoryDashboard({ q: historyQuery.q || undefined, status: historyQuery.status || undefined, date: historyQuery.date || undefined }),
    [historyQuery],
    activeView === 'history',
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    document.documentElement.dataset.timeFormat = timeFormat;
  }, [timeFormat]);

  useEffect(() => {
    const pool = [today.data?.tasks, ...(board.data?.groups.map((group: TaskGroup) => group.tasks) || []), history.data?.items]
      .flat()
      .filter(Boolean) as Task[];
    if (!pool.length) return;
    if (!selectedTask) {
      setSelectedTask(pool[0]);
      return;
    }
    const refreshed = pool.find((task) => task.id === selectedTask.id);
    if (refreshed) {
      setSelectedTask((current) => ({ ...refreshed, reminders: current?.reminders, events: current?.events }));
    }
  }, [today.data, board.data, history.data, selectedTask]);

  useEffect(() => {
    if (!selectedTask?.id || !isDetailOpen) return;
    let cancelled = false;
    setIsDetailLoading(true);

    api
      .getTask(selectedTask.id)
      .then((task) => {
        if (!cancelled) setSelectedTask(task);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setIsDetailLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedTask?.id, isDetailOpen]);

  useEffect(() => {
    setTodayPage(1);
  }, [todayPageSize, today.data?.tasks.length]);

  useEffect(() => {
    setHistoryPage(1);
  }, [historyPageSize, history.data?.items.length, historyQuery]);

  useEffect(() => {
    if (activeView !== 'board') setBoardFeedback(null);
  }, [activeView]);

  const refreshLoadedViews = async () => {
    await Promise.all([
      today.loaded ? today.reload() : Promise.resolve(null),
      board.loaded ? board.reload() : Promise.resolve(null),
      history.loaded ? history.reload() : Promise.resolve(null),
    ]);
  };

  const patchLoadedData = (updatedTask: Task) => {
    today.setData((current) => {
      if (!current) return current;
      const tasks = upsertTask(current.tasks, updatedTask);
      return {
        ...current,
        tasks,
        summary: computeTodaySummary(tasks, current.date),
      } satisfies DashboardToday;
    });

    board.setData((current) => {
      if (!current) return current;
      return {
        ...current,
        groups: current.groups.map((group: TaskGroup) => {
          const withoutTask = group.tasks.filter((task: Task) => task.id !== updatedTask.id);
          if (group.key === updatedTask.status) {
            return {
              ...group,
              tasks: sortTasksByRecency([...withoutTask, updatedTask]),
            };
          }
          return {
            ...group,
            tasks: withoutTask,
          };
        }),
      } satisfies DashboardBoard;
    });

    history.setData((current) => {
      if (!current) return current;
      const items = upsertTask(current.items, updatedTask);
      return {
        ...current,
        items,
        total: Math.max(current.total, items.length),
      } satisfies HistoryResponse;
    });
  };

  const openTaskDetail = (task: Task) => {
    setSelectedTask(task);
    setIsDetailOpen(true);
  };

  const runTaskAction = async (label: string, action: () => Promise<Task>) => {
    if (!selectedTask) return;
    setBusyAction(label);
    try {
      const updated = await action();
      setSelectedTask(updated);
      patchLoadedData(updated);
      await refreshLoadedViews();
    } finally {
      setBusyAction(null);
    }
  };

  const renameProject = async (currentName: string, nextName: string) => {
    setRenamingProject(currentName);
    setBoardFeedback(null);
    try {
      const result = await api.renameProject(currentName, nextName);
      await Promise.all([
        refreshLoadedViews(),
        projects.loaded ? projects.reload() : Promise.resolve(projects.data),
      ]);
      setBoardFeedback({
        tone: 'success',
        message: `项目“${result.old_name}”已重命名为“${result.new_name}”，同步更新 ${result.updated_task_count} 条任务。`,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : '项目重命名失败';
      setBoardFeedback({ tone: 'danger', message: `项目重命名失败：${message}` });
      throw error;
    } finally {
      setRenamingProject(null);
    }
  };

  const detailProps = {
    task: selectedTask,
    open: isDetailOpen,
    onClose: () => setIsDetailOpen(false),
    busyAction,
    isLoadingDetails: isDetailLoading,
    onComplete: (task: Task) => runTaskAction('complete', () => api.completeTask(task.id)),
    onSaveSchedule: (task: Task, payload: { due_at: string | null }) => runTaskAction('schedule', () => api.updateTask(task.id, payload)),
    onDefer: (task: Task, payload: { deferred_to: string; note?: string }) => runTaskAction('defer', () => api.deferTask(task.id, { deferred_to: payload.deferred_to, reason: payload.note })),
    onCancel: (task: Task, note?: string) => runTaskAction('cancel', () => api.cancelTask(task.id, note)),
    onAddReminder: (task: Task, payload: { remind_at: string; channel: string; note?: string }) => runTaskAction('remind', () => api.addReminder(task.id, payload)),
  };

  const boardStatusGroups: TaskGroup[] = board.data?.groups || [];
  const projectSummaryMap = useMemo(
    () => new Map((projects.data || []).map((project: ProjectSummary) => [project.name, project])),
    [projects.data],
  );
  const filteredBoardTasks = useMemo(
    () => boardStatusGroups.flatMap((group: TaskGroup) => group.tasks).filter((task) => boardFilters.every((condition) => matchesBoardCondition(task, condition))),
    [boardStatusGroups, boardFilters],
  );
  const boardProjectGroups = useMemo<TaskGroup[]>(() => {
    return groupTasksByProject(filteredBoardTasks).map((group) => {
      const summary = projectSummaryMap.get(group.title);
      if (!summary) return group;
      return {
        ...group,
        meta: `共 ${summary.task_count} · 未完成 ${summary.open_task_count} · 已完成 ${summary.done_task_count}`,
      } satisfies TaskGroup;
    });
  }, [filteredBoardTasks, projectSummaryMap]);
  const filteredStatusGroups = useMemo<TaskGroup[]>(() => {
    const map = new Map<string, Task[]>();
    boardStatusGroups.forEach((group) => map.set(group.key, []));
    filteredBoardTasks.forEach((task) => {
      const list = map.get(task.status) || [];
      map.set(task.status, [...list, task]);
    });
    return boardStatusGroups.map((group) => ({ ...group, tasks: sortTasksByRecency(map.get(group.key) || []) }));
  }, [boardStatusGroups, filteredBoardTasks]);
  const boardGroups = boardGroupMode === 'project' ? boardProjectGroups : filteredStatusGroups;
  const projectOptions = useMemo(
    () =>
      Array.from(
        new Set([
          ...(projects.data || []).map((project: ProjectSummary) => project.name).filter(Boolean),
          ...boardStatusGroups.flatMap((group: TaskGroup) =>
            group.tasks.map((task: Task) => task.project?.trim()).filter(Boolean) as string[],
          ),
        ]),
      ).sort((a, b) => a.localeCompare(b, 'zh-CN')),
    [boardStatusGroups, projects.data],
  );

  const boardMetrics = useMemo(() => {
    if (!board.data) return { total: 0, active: 0, blocked: 0 };
    const total = filteredBoardTasks.length;
    const active = filteredBoardTasks.filter((task) => task.status === ('doing' satisfies TaskStatus)).length;
    const blocked = filteredBoardTasks.filter((task) => task.status === ('deferred' satisfies TaskStatus)).length;
    return { total, active, blocked };
  }, [board.data, filteredBoardTasks]);

  const todaySummaryHighlight = useMemo(() => {
    if (!today.data) return '';
    const { total, open, overdue, completed, dueToday } = today.data.summary;
    return `共 ${total} 项，未完成 ${open}，今日到期 ${dueToday}，逾期 ${overdue}，已完成 ${completed}`;
  }, [today.data]);

  const currentContent = useMemo(() => {
    if (activeView === 'today') {
      if (today.loading && !today.data) return <LoadingState mode="list" />;
      if (today.error || !today.data) return <ErrorState message={today.error || '今日数据为空'} onRetry={today.reload} />;
      return (
        <div className="content-stack">
          <ViewHero
            eyebrow={viewMeta.today.eyebrow}
            title={viewMeta.today.title}
            highlight={todaySummaryHighlight}
            metrics={[
              { label: '未完成', value: String(today.data.summary.open), tone: 'brand' },
              { label: '今日到期', value: String(today.data.summary.dueToday), tone: 'default' },
              { label: '逾期', value: String(today.data.summary.overdue), tone: today.data.summary.overdue ? 'danger' : 'success' },
              { label: '已完成', value: String(today.data.summary.completed), tone: 'success' },
            ]}
          />

          <section className="view-column">
            <Panel
              title="任务"
              actions={
                <div className="toolbar-inline">
                  <span className="label-caption">每页</span>
                  <select value={todayPageSize} onChange={(e) => setTodayPageSize(Number(e.target.value))}>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                  </select>
                </div>
              }
            >
              <TaskList
                tasks={today.data.tasks}
                selectedTaskId={selectedTask?.id}
                onSelect={openTaskDetail}
                variant="today"
                page={todayPage}
                pageSize={todayPageSize}
                onPageChange={setTodayPage}
              />
            </Panel>
          </section>
        </div>
      );
    }

    if (activeView === 'board') {
      if (board.loading && !board.data) return <LoadingState mode="board" />;
      if (board.error || !board.data) return <ErrorState message={board.error || '看板数据为空'} onRetry={board.reload} />;
      return (
        <div className="content-stack">
          <ViewHero
            eyebrow={viewMeta.board.eyebrow}
            title={viewMeta.board.title}
            highlight={`当前筛选后 ${boardMetrics.total} 项任务`}
            metrics={[
              { label: '总任务', value: String(boardMetrics.total), tone: 'brand' },
              { label: '进行中', value: String(boardMetrics.active), tone: 'default' },
              { label: '延期', value: String(boardMetrics.blocked), tone: boardMetrics.blocked ? 'danger' : 'success' },
            ]}
          />
          <section className="view-column">
            <Panel title="看板">
              <div className="board-panel-stack">
                {projects.error ? <div className="inline-banner danger">项目列表加载失败：{projects.error}</div> : null}
                {boardFeedback ? <div className={`inline-banner ${boardFeedback.tone}`}>{boardFeedback.message}</div> : null}
                <BoardColumns
                  groups={boardGroups}
                  selectedTaskId={selectedTask?.id}
                  onSelect={openTaskDetail}
                  groupMode={boardGroupMode}
                  onGroupModeChange={(mode) => {
                    setBoardGroupMode(mode);
                    setBoardFeedback(null);
                  }}
                  filters={boardFilters}
                  onFiltersChange={setBoardFilters}
                  visibleFields={boardVisibleFields.length ? boardVisibleFields : defaultBoardVisibleFields}
                  onVisibleFieldsChange={setBoardVisibleFields}
                  projectOptions={projectOptions}
                  onRenameProject={renameProject}
                  renamingProject={renamingProject}
                  renameProjectSupported={!projects.error}
                />
              </div>
            </Panel>
          </section>
        </div>
      );
    }

    if (history.loading && !history.data) return <LoadingState mode="list" />;
    if (history.error || !history.data) return <ErrorState message={history.error || '历史数据为空'} onRetry={history.reload} />;
    return (
      <div className="content-stack">
        <ViewHero
          eyebrow={viewMeta.history.eyebrow}
          title={viewMeta.history.title}
          highlight={`当前命中 ${history.data.total} 条记录`}
          metrics={[
            { label: '命中记录', value: String(history.data.total), tone: 'brand' },
            { label: '筛选状态', value: historyFilters.status || '全部', tone: 'default' },
            { label: '日期', value: historyFilters.date || '不限', tone: 'default' },
          ]}
        />
        <section className="view-column">
          <Panel
            title="历史检索"
            actions={
              <div className="toolbar-inline toolbar-inline-split">
                <div className="toolbar-inline">
                  <span className="label-caption">每页</span>
                  <select value={historyPageSize} onChange={(e) => setHistoryPageSize(Number(e.target.value))}>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                  </select>
                </div>
                <button onClick={() => setHistoryQuery(historyFilters)}>刷新筛选</button>
              </div>
            }
          >
            <HistoryFilters value={historyFilters} onChange={setHistoryFilters} onSearch={() => setHistoryQuery(historyFilters)} resultCount={history.data.total} />
            <TaskList
              tasks={history.data.items}
              selectedTaskId={selectedTask?.id}
              onSelect={openTaskDetail}
              variant="history"
              page={historyPage}
              pageSize={historyPageSize}
              onPageChange={setHistoryPage}
            />
          </Panel>
        </section>
      </div>
    );
  }, [
    activeView,
    today,
    board,
    history,
    selectedTask,
    historyFilters,
    historyPage,
    historyPageSize,
    boardMetrics,
    todayPage,
    todayPageSize,
    todaySummaryHighlight,
    boardGroups,
    boardGroupMode,
    boardFilters,
    boardVisibleFields,
    projectOptions,
    renamingProject,
  ]);

  return (
    <>
      <Layout
        activeView={activeView}
        onChangeView={setActiveView}
        apiBaseUrl={api.baseUrl}
        theme={theme}
        onToggleTheme={() => setTheme(theme === 'light' ? 'dark' : 'light')}
        timeFormat={timeFormat}
        onTimeFormatChange={setTimeFormat}
      >
        {currentContent}
      </Layout>
      <TaskDetailModal {...detailProps} />
    </>
  );
}

export default App;
