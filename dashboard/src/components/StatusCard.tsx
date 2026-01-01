interface StatusCardProps {
  status: any
  isRunning: boolean
}

export function StatusCard({ status, isRunning }: StatusCardProps) {
  const taskStats = status?.scheduler?.tasks || {}
  const agentStats = status?.agent_pool || {}

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-white mb-4">System Status</h2>

      <div className="grid grid-cols-2 gap-4">
        {/* Status */}
        <div className="bg-gray-700 rounded p-3">
          <div className="text-xs text-gray-400 uppercase">Status</div>
          <div className={`text-lg font-bold ${isRunning ? 'text-green-400' : 'text-gray-400'}`}>
            {isRunning ? 'Running' : 'Idle'}
          </div>
        </div>

        {/* Agents */}
        <div className="bg-gray-700 rounded p-3">
          <div className="text-xs text-gray-400 uppercase">Agents</div>
          <div className="text-lg font-bold text-white">
            {agentStats.size || 0} / {agentStats.max_agents || 3}
          </div>
        </div>

        {/* Tasks Completed */}
        <div className="bg-gray-700 rounded p-3">
          <div className="text-xs text-gray-400 uppercase">Completed</div>
          <div className="text-lg font-bold text-green-400">
            {taskStats.completed || 0}
          </div>
        </div>

        {/* Tasks In Progress */}
        <div className="bg-gray-700 rounded p-3">
          <div className="text-xs text-gray-400 uppercase">In Progress</div>
          <div className="text-lg font-bold text-blue-400">
            {taskStats.in_progress || 0}
          </div>
        </div>

        {/* Tasks Queued */}
        <div className="bg-gray-700 rounded p-3">
          <div className="text-xs text-gray-400 uppercase">Queued</div>
          <div className="text-lg font-bold text-yellow-400">
            {taskStats.queued || 0}
          </div>
        </div>

        {/* Tasks Failed */}
        <div className="bg-gray-700 rounded p-3">
          <div className="text-xs text-gray-400 uppercase">Failed</div>
          <div className="text-lg font-bold text-red-400">
            {taskStats.failed || 0}
          </div>
        </div>
      </div>
    </div>
  )
}
