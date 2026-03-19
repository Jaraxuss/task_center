import { useEffect, useMemo, useState } from 'react';
import { api } from './api';
import { useAsyncData } from './hooks';
import { BoardColumns, ErrorState, HistoryFilters, Layout, LoadingState, SectionHeader, SummaryCards, TaskDetail, TaskList } from './components';
import { Task } from './types';

function App() {
  const [activeView, setActiveView] = useState<'today' | 'board' | 'history'>('today');
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [historyFilters, setHistoryFilters] = useState({ q: '', status: '', date: '' });
  const [historyQuery, setHistoryQuery] = useState(historyFilters);

  const today = useAsyncData(() => api.getTodayDashboard(), []);
  const board = useAsyncData(() => api.getBoardDashboard(), []);
  const history = useAsyncData(
    () => api.getHistoryDashboard({ q: historyQuery.q || undefined, status: historyQuery.status || undefined, date: historyQuery.date || undefined }),
    [historyQuery],
  );

  useEffect(() => {
    const pool = [today.data?.tasks, ...(board.data?.groups.map((group: { tasks: Task[] }) => group.tasks) || []), history.data?.items].flat().filter(Boolean) as Task[];
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
    if (!selectedTask?.id) return;
    let cancelled = false;

    api.getTask(selectedTask.id)
      .then((task) => {
        if (!cancelled) setSelectedTask(task);
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [selectedTask?.id]);

  const refreshAll = async () => {
    await Promise.all([today.reload(), board.reload(), history.reload()]);
  };

  const runTaskAction = async (label: string, action: () => Promise<Task>) => {
    if (!selectedTask) return;
    setBusyAction(label);
    try {
      const updated = await action();
      setSelectedTask(updated);
      await refreshAll();
    } finally {
      setBusyAction(null);
    }
  };

  const detailProps = {
    task: selectedTask,
    busyAction,
    onComplete: (task: Task) => runTaskAction('complete', () => api.completeTask(task.id)),
    onSaveSchedule: (task: Task, payload: { due_at: string | null }) => runTaskAction('schedule', () => api.updateTask(task.id, payload)),
    onDefer: (task: Task, payload: { deferred_to: string; note?: string }) => runTaskAction('defer', () => api.deferTask(task.id, { deferred_to: payload.deferred_to, reason: payload.note })),
    onCancel: (task: Task, note?: string) => runTaskAction('cancel', () => api.cancelTask(task.id, note)),
    onAddReminder: (task: Task, payload: { remind_at: string; channel: string; note?: string }) => runTaskAction('remind', () => api.addReminder(task.id, payload)),
  };

  const currentContent = useMemo(() => {
    if (activeView === 'today') {
      if (today.loading) return <LoadingState />;
      if (today.error || !today.data) return <ErrorState message={today.error || '今日数据为空'} onRetry={today.reload} />;
      return (
        <div className="content-grid">
          <section>
            <SectionHeader title="今日视图" description="按时间顺序处理今天要盯住的任务。" />
            <SummaryCards items={[
              { label: '任务总数', value: today.data.summary.total },
              { label: '今日到期', value: today.data.summary.dueToday },
              { label: '已逾期', value: today.data.summary.overdue },
              { label: '已完成', value: today.data.summary.completed },
            ]} />
            <TaskList tasks={today.data.tasks} selectedTaskId={selectedTask?.id} onSelect={setSelectedTask} />
          </section>
          <TaskDetail {...detailProps} />
        </div>
      );
    }

    if (activeView === 'board') {
      if (board.loading) return <LoadingState />;
      if (board.error || !board.data) return <ErrorState message={board.error || '看板数据为空'} onRetry={board.reload} />;
      return (
        <div className="content-grid">
          <section>
            <SectionHeader title="看板视图" description="按状态分组，适合扫一眼整体进度。" />
            <BoardColumns groups={board.data.groups} selectedTaskId={selectedTask?.id} onSelect={setSelectedTask} />
          </section>
          <TaskDetail {...detailProps} />
        </div>
      );
    }

    if (history.loading) return <LoadingState />;
    if (history.error || !history.data) return <ErrorState message={history.error || '历史数据为空'} onRetry={history.reload} />;
    return (
      <div className="content-grid">
        <section>
          <SectionHeader
            title="历史视图"
            description="查看过往任务与变更，方便复盘，也方便抓背锅证据。"
            actions={<button onClick={() => setHistoryQuery(historyFilters)}>刷新筛选</button>}
          />
          <HistoryFilters value={historyFilters} onChange={setHistoryFilters} onSearch={() => setHistoryQuery(historyFilters)} />
          <TaskList tasks={history.data.items} selectedTaskId={selectedTask?.id} onSelect={setSelectedTask} />
        </section>
        <TaskDetail {...detailProps} />
      </div>
    );
  }, [activeView, today, board, history, selectedTask, busyAction, historyFilters]);

  return (
    <Layout activeView={activeView} onChangeView={setActiveView} apiBaseUrl={api.baseUrl}>
      {currentContent}
    </Layout>
  );
}

export default App;
