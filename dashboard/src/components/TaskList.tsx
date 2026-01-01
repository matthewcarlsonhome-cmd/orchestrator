interface Task {
  id: string
  title: string
  status: string
  agent_type: string
  assigned_agent?: string
}

interface TaskListProps {
  tasks: Task[]
}

const statusColors: Record<string, string> = {
  queued: 'bg-yellow-500',
  in_progress: 'bg-blue-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  pending: 'bg-gray-500',
}

const statusBg: Record<string, string> = {
  queued: 'bg-yellow-500/10 border-yellow-500/30',
  in_progress: 'bg-blue-500/10 border-blue-500/30',
  completed: 'bg-green-500/10 border-green-500/30',
  failed: 'bg-red-500/10 border-red-500/30',
  pending: 'bg-gray-500/10 border-gray-500/30',
}

export function TaskList({ tasks }: TaskListProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-white mb-4">
        Tasks ({tasks.length})
      </h2>

      <div className="space-y-2 max-h-[500px] overflow-y-auto">
        {tasks.length === 0 ? (
          <p className="text-gray-400 text-sm">No tasks yet</p>
        ) : (
          tasks.map(task => (
            <div
              key={task.id}
              className={`p-3 rounded border ${statusBg[task.status] || statusBg.pending}`}
            >
              <div className="flex items-start gap-2">
                <div className={`w-2 h-2 rounded-full mt-2 ${statusColors[task.status] || statusColors.pending}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white truncate">{task.title}</div>
                  <div className="text-xs text-gray-400 mt-1">
                    {task.status}
                    {task.assigned_agent && ` • ${task.assigned_agent}`}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
