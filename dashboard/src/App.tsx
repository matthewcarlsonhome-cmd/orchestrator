import { useState, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { Header } from './components/Header'
import { StatusCard } from './components/StatusCard'
import { TaskList } from './components/TaskList'
import { AgentList } from './components/AgentList'
import { LogViewer } from './components/LogViewer'
import { RunForm } from './components/RunForm'

interface Task {
  id: string
  title: string
  status: string
  agent_type: string
  assigned_agent?: string
}

interface Agent {
  id: string
  type: string
  status: string
  current_task?: string
  tasks_completed: number
}

interface LogEntry {
  type: string
  timestamp: string
  [key: string]: any
}

function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [status, setStatus] = useState<any>(null)
  const [isRunning, setIsRunning] = useState(false)

  const { lastMessage, sendMessage, isConnected } = useWebSocket('ws://localhost:8420/ws')

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      const event = lastMessage as LogEntry
      setLogs(prev => [...prev.slice(-100), event])

      // Update state based on event type
      if (event.type === 'run_start') {
        setIsRunning(true)
        setTasks([])
        setLogs([event])
      } else if (event.type === 'run_complete') {
        setIsRunning(false)
      } else if (event.type === 'tasks_created') {
        setTasks(event.tasks?.map((t: any) => ({
          id: t.id,
          title: t.title,
          status: 'queued',
          agent_type: 'pending',
        })) || [])
      } else if (event.type === 'task_started') {
        setTasks(prev => prev.map(t =>
          t.id === event.task_id
            ? { ...t, status: 'in_progress', assigned_agent: event.agent_id }
            : t
        ))
      } else if (event.type === 'task_completed') {
        setTasks(prev => prev.map(t =>
          t.id === event.task_id
            ? { ...t, status: 'completed' }
            : t
        ))
      } else if (event.type === 'task_failed') {
        setTasks(prev => prev.map(t =>
          t.id === event.task_id
            ? { ...t, status: 'failed' }
            : t
        ))
      } else if (event.type === 'agent_created') {
        setAgents(prev => [...prev, {
          id: event.agent_id,
          type: event.agent_type,
          status: 'idle',
          tasks_completed: 0,
        }])
      }
    }
  }, [lastMessage])

  // Fetch initial status
  useEffect(() => {
    fetch('/api/status')
      .then(res => res.json())
      .then(data => {
        setStatus(data)
        setIsRunning(data.running)
      })
      .catch(() => {})

    fetch('/api/tasks')
      .then(res => res.json())
      .then(data => setTasks(data.tasks || []))
      .catch(() => {})

    fetch('/api/agents')
      .then(res => res.json())
      .then(data => setAgents(data.agents || []))
      .catch(() => {})
  }, [])

  const handleRun = async (project: string, instructions: string) => {
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project, instructions }),
      })
      if (res.ok) {
        setIsRunning(true)
      }
    } catch (err) {
      console.error('Failed to start run:', err)
    }
  }

  const handleStop = async () => {
    try {
      await fetch('/api/stop', { method: 'POST' })
    } catch (err) {
      console.error('Failed to stop:', err)
    }
  }

  return (
    <div className="min-h-screen p-6">
      <Header isConnected={isConnected} isRunning={isRunning} onStop={handleStop} />

      <div className="max-w-7xl mx-auto mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Status and Run Form */}
        <div className="space-y-6">
          <StatusCard status={status} isRunning={isRunning} />
          <RunForm onRun={handleRun} disabled={isRunning} />
        </div>

        {/* Middle column - Tasks */}
        <div className="lg:col-span-1">
          <TaskList tasks={tasks} />
        </div>

        {/* Right column - Agents and Logs */}
        <div className="space-y-6">
          <AgentList agents={agents} />
          <LogViewer logs={logs} />
        </div>
      </div>
    </div>
  )
}

export default App
