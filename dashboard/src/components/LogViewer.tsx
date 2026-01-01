import { useRef, useEffect } from 'react'

interface LogEntry {
  type: string
  timestamp: string
  [key: string]: any
}

interface LogViewerProps {
  logs: LogEntry[]
}

const typeColors: Record<string, string> = {
  run_start: 'text-green-400',
  run_complete: 'text-green-400',
  decomposing: 'text-blue-400',
  tasks_created: 'text-blue-400',
  task_started: 'text-cyan-400',
  task_completed: 'text-green-400',
  task_failed: 'text-red-400',
  agent_created: 'text-purple-400',
  agent_message: 'text-yellow-400',
  error: 'text-red-400',
  checkpoint_saved: 'text-gray-400',
}

function formatLog(log: LogEntry): string {
  switch (log.type) {
    case 'run_start':
      return `Started: ${log.project} - "${log.instructions}"`
    case 'run_complete':
      return `Completed in ${log.summary?.duration_seconds?.toFixed(1)}s`
    case 'decomposing':
      return 'Decomposing instructions into tasks...'
    case 'tasks_created':
      return `Created ${log.count} tasks`
    case 'task_started':
      return `Started: ${log.task_title} (${log.agent_type})`
    case 'task_completed':
      return `Completed: ${log.summary || log.task_title}`
    case 'task_failed':
      return `Failed: ${log.error}`
    case 'agent_created':
      return `Agent created: ${log.agent_type}`
    case 'agent_message':
      return `${log.from} -> ${log.to}: ${log.message}`
    case 'error':
      return `Error: ${log.error}`
    case 'checkpoint_saved':
      return `Checkpoint saved`
    default:
      return JSON.stringify(log)
  }
}

export function LogViewer({ logs }: LogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs])

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Activity Log</h2>

      <div
        ref={containerRef}
        className="h-64 overflow-y-auto font-mono text-xs space-y-1"
      >
        {logs.length === 0 ? (
          <p className="text-gray-400">No activity yet</p>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-gray-500 shrink-0">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className={typeColors[log.type] || 'text-gray-300'}>
                {formatLog(log)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
