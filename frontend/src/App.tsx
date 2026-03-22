import { useEffect, useMemo, useState } from 'react';
import { api } from './api';
import { useAsyncData, useLocalStorage } from './hooks';
import {
  BoardColumns,
  ErrorState,
  HistoryFilters,
  Layout,
  LoadingState,
  Panel,
  TaskDetailModal,
  TaskList,
  ViewHero,
} from './components';
import { DashboardBoard, DashboardToday, HistoryResponse, Task, TaskGroup, TaskStatus } from './types';
import { groupTasksByProject, sortTasksByRecency, TimeFormatMode } from './utils';

type ViewMode = 'today' | 'board' | 'history';
type ThemeMode = 'light' | 'dark';
type BoardGroupMode = 'status' | 'project';

const viewMeta: Record<ViewMode, { eyebrow: string; title: string; description: string }> = {
  today: {
    eyebrow: 'Focus mode',
    title: '今日先把该盯的事盯住',
    description: '把今天必须推进的任务、提醒和异常项先捞出来，少切视图，少丢重点。',
  },
  board: {
    eyebrow: 'Flow overview',
    title: '看板视角扫全局进度',
    description: '按状态看流转是否顺畅，快速定位堵点、延期和未推进项。',
  },
  history: {
    eyebrow: 'Audit trail',
    title: '历史记录用于复盘，不是考古',
    description: '带着条件查记录，定位上下文、责任和时间线，不再盲翻。',
  },
};

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

  const today = useAsyncData(() => api.getTodayDashboard(), [], activeView === 'today');
  const board = useAsyncData(() => api.getBoardDashboard(), [], activeView === 'board');
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
  const boardProjectGroups = useMemo<TaskGroup[]>(() => groupTasksByProject(boardStatusGroups.flatMap((group: TaskGroup) => group.tasks)), [boardStatusGroups]);
  const boardGroups = boardGroupMode === 'project' ? boardProjectGroups : boardStatusGroups;

  const boardMetrics = useMemo(() => {
    if (!board.data) return { total: 0, active: 0, blocked: 0 };
    const total = board.data.groups.reduce((sum: number, group: TaskGroup) => sum + group.tasks.length, 0);
    const active = board.data.groups.find((group: TaskGroup) => group.key === ('doing' satisfies TaskStatus))?.tasks.length || 0;
    const blocked = board.data.groups.find((group: TaskGroup) => group.key === ('deferred' satisfies TaskStatus))?.tasks.length || 0;
    return { total, active, blocked };
  }, [board.data]);

  const todaySummaryHighlight = useMemo(() => {
    if (!today.data) return '';
    const { total, open, overdue, completed, dueToday } = today.data.summary;
    return `今天共 ${total} 项任务，未完成 ${open} 项，今日到期 ${dueToday} 项${overdue ? `，其中逾期 ${overdue} 项要先灭火` : '，当前没有逾期项'}；已完成 ${completed} 项。`;
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
            description={viewMeta.today.description}
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
              title="今日任务池"
              description="列表优先按今天视角呈现，先处理到期、逾期和正在推进的事项。"
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
            description={viewMeta.board.description}
            highlight={`当前共 ${boardMetrics.total} 项任务分布在各状态列。优先关注进行中和延期列是否堆积。`}
            metrics={[
              { label: '总任务', value: String(boardMetrics.total), tone: 'brand' },
              { label: '进行中', value: String(boardMetrics.active), tone: 'default' },
              { label: '延期', value: String(boardMetrics.blocked), tone: boardMetrics.blocked ? 'danger' : 'success' },
            ]}
          />
          <section className="view-column">
            <Panel title="状态看板" description="看整体流转，找堆积点，别靠直觉管理进度。">
              <BoardColumns
                groups={boardGroups}
                selectedTaskId={selectedTask?.id}
                onSelect={openTaskDetail}
                groupMode={boardGroupMode}
                onGroupModeChange={setBoardGroupMode}
              />
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
          description={viewMeta.history.description}
          highlight={`当前命中 ${history.data.total} 条历史任务记录。先用关键词和状态缩窄范围，再看详情时间线。`}
          metrics={[
            { label: '命中记录', value: String(history.data.total), tone: 'brand' },
            { label: '筛选状态', value: historyFilters.status || '全部', tone: 'default' },
            { label: '日期', value: historyFilters.date || '不限', tone: 'default' },
          ]}
        />
        <section className="view-column">
          <Panel
            title="历史检索"
            description="带着条件查，少翻无效记录，复盘效率会高很多。"
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
