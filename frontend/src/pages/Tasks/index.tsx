import React, { useState, useEffect } from 'react';
import {
  CheckSquare,
  Plus,
  Clock,
  AlertCircle,
  CheckCircle2,
  Calendar,
  User,
  Trash2,
} from 'lucide-react';
import { getTasks, createTask, updateTask, deleteTask } from '../../services/activities';
import { Task } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatDateTime } from '../../utils/format';

export const Tasks: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activeTab, setActiveTab] = useState<'upcoming' | 'overdue' | 'completed'>('upcoming');
  const [isLoading, setIsLoading] = useState(true);

  // Add Task modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    task_type: 'follow_up',
    priority: 'medium' as Task['priority'],
    due_date: new Date(Date.now() + 86400000 * 2).toISOString().slice(0, 16),
  });

  const fetchTasks = async () => {
    setIsLoading(true);
    try {
      const res = await getTasks({
        page_size: 100,
        overdue_only: activeTab === 'overdue',
        status: activeTab === 'completed' ? 'completed' : 'pending',
      });
      setTasks(res.items);
    } catch {
      // Demo fallback
      setTasks([
        {
          id: 't_1',
          title: 'Review executive Knowledge Panel case study for Dr. Malhotra',
          description: 'Confirm published article references and verify personal site.',
          task_type: 'verification',
          priority: 'high',
          status: 'pending',
          due_date: new Date(Date.now() + 86400000).toISOString(),
          created_at: new Date().toISOString(),
        },
        {
          id: 't_2',
          title: 'Schedule outreach review for PayFin CTO Ananya Roy',
          description: 'Prepare tailored introduction highlighting authority visibility.',
          task_type: 'follow_up',
          priority: 'medium',
          status: 'pending',
          due_date: new Date(Date.now() + 86400000 * 3).toISOString(),
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [activeTab]);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createTask(newTask);
      setIsModalOpen(false);
      setNewTask({
        title: '',
        description: '',
        task_type: 'follow_up',
        priority: 'medium',
        due_date: new Date(Date.now() + 86400000 * 2).toISOString().slice(0, 16),
      });
      fetchTasks();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create task');
    }
  };

  const handleMarkComplete = async (id: string) => {
    try {
      await updateTask(id, { status: 'completed' });
      fetchTasks();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update task');
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Delete this task?')) {
      await deleteTask(id);
      fetchTasks();
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Tasks & Follow-Ups</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage research tasks, verification checkpoints, and prospect follow-up actions.
          </p>
        </div>
        <Button
          variant="primary"
          size="md"
          onClick={() => setIsModalOpen(true)}
          leftIcon={<Plus className="w-4 h-4" />}
        >
          Add Follow-Up
        </Button>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-6">
          <button
            onClick={() => setActiveTab('upcoming')}
            className={`py-3 px-1 border-b-2 font-medium text-xs transition-colors flex items-center gap-1.5 ${
              activeTab === 'upcoming'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <Clock className="w-3.5 h-3.5" /> Upcoming Tasks
          </button>
          <button
            onClick={() => setActiveTab('overdue')}
            className={`py-3 px-1 border-b-2 font-medium text-xs transition-colors flex items-center gap-1.5 ${
              activeTab === 'overdue'
                ? 'border-rose-600 text-rose-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5" /> Overdue
          </button>
          <button
            onClick={() => setActiveTab('completed')}
            className={`py-3 px-1 border-b-2 font-medium text-xs transition-colors flex items-center gap-1.5 ${
              activeTab === 'completed'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" /> Completed
          </button>
        </nav>
      </div>

      {isLoading ? (
        <LoadingSpinner message="Fetching task queue..." />
      ) : tasks.length === 0 ? (
        <EmptyState
          icon={CheckSquare}
          title={`No ${activeTab} tasks`}
          description="Create a task or follow-up note to keep track of prospect verifications."
          actionText="Add New Task"
          onAction={() => setIsModalOpen(true)}
        />
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => (
            <Card key={task.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900 text-xs">{task.title}</span>
                  <Badge
                    variant={
                      task.priority === 'urgent' || task.priority === 'high'
                        ? 'danger'
                        : task.priority === 'medium'
                        ? 'warning'
                        : 'default'
                    }
                  >
                    {task.priority}
                  </Badge>
                  <Badge variant="default">{task.task_type.replace(/_/g, ' ')}</Badge>
                </div>
                {task.description && <p className="text-xs text-slate-600">{task.description}</p>}
                <div className="flex items-center gap-3 text-[11px] text-slate-400 pt-1">
                  {task.due_date && (
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-slate-400" /> Due: {formatDateTime(task.due_date)}
                    </span>
                  )}
                  {task.assigned_to && (
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3 text-slate-400" /> {task.assigned_to}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {task.status !== 'completed' && (
                  <Button
                    variant="success"
                    size="sm"
                    onClick={() => handleMarkComplete(task.id)}
                    leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                  >
                    Mark Done
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(task.id)}
                  className="text-slate-400 hover:text-rose-600"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Add Task Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create Follow-Up / Task"
        description="Schedule a follow-up or research milestone for a prospect lead."
      >
        <form onSubmit={handleCreateTask} className="space-y-4">
          <Input
            label="Task Title *"
            required
            placeholder="e.g. Verify LinkedIn reference"
            value={newTask.title}
            onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
          />

          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Task Type"
              value={newTask.task_type}
              onChange={(e) => setNewTask({ ...newTask, task_type: e.target.value })}
              options={[
                { label: 'Follow-Up', value: 'follow_up' },
                { label: 'Evidence Verification', value: 'verification' },
                { label: 'Outreach Review', value: 'outreach' },
                { label: 'Call Log', value: 'call' },
              ]}
            />

            <Select
              label="Priority"
              value={newTask.priority}
              onChange={(e) => setNewTask({ ...newTask, priority: e.target.value as any })}
              options={[
                { label: 'Low', value: 'low' },
                { label: 'Medium', value: 'medium' },
                { label: 'High', value: 'high' },
                { label: 'Urgent', value: 'urgent' },
              ]}
            />
          </div>

          <Input
            label="Due Date & Time"
            type="datetime-local"
            value={newTask.due_date}
            onChange={(e) => setNewTask({ ...newTask, due_date: e.target.value })}
          />

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
              Task Description
            </label>
            <textarea
              className="w-full rounded-lg border border-slate-300 p-3 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              rows={3}
              placeholder="Provide instructions or background notes..."
              value={newTask.description}
              onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
            />
          </div>

          <div className="pt-3 flex justify-end gap-2 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              Create Task
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
