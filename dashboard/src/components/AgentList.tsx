interface Agent {
  id: string
  type: string
  status: string
  current_task?: string
  tasks_completed: number
}

interface AgentListProps {
  agents: Agent[]
}

const typeColors: Record<string, string> = {
  architect: 'text-purple-400',
  frontend: 'text-cyan-400',
  backend: 'text-orange-400',
  fullstack: 'text-green-400',
  tester: 'text-yellow-400',
  debugger: 'text-red-400',
  devops: 'text-blue-400',
}

export function AgentList({ agents }: AgentListProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-white mb-4">
        Agents ({agents.length})
      </h2>

      <div className="space-y-2">
        {agents.length === 0 ? (
          <p className="text-gray-400 text-sm">No agents active</p>
        ) : (
          agents.map(agent => (
            <div
              key={agent.id}
              className="p-3 rounded bg-gray-700/50 border border-gray-600"
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className={`font-medium ${typeColors[agent.type] || 'text-white'}`}>
                    {agent.type}
                  </span>
                  <span className="text-xs text-gray-500 ml-2">{agent.id.slice(0, 8)}</span>
                </div>
                <div className={`text-xs px-2 py-1 rounded ${
                  agent.status === 'working'
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'bg-gray-600 text-gray-400'
                }`}>
                  {agent.status}
                </div>
              </div>
              {agent.current_task && (
                <div className="text-xs text-gray-400 mt-1 truncate">
                  Working on: {agent.current_task}
                </div>
              )}
              <div className="text-xs text-gray-500 mt-1">
                Completed: {agent.tasks_completed}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
