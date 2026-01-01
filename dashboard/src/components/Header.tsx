interface HeaderProps {
  isConnected: boolean
  isRunning: boolean
  onStop: () => void
}

export function Header({ isConnected, isRunning, onStop }: HeaderProps) {
  return (
    <header className="max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Orchestrator Dashboard</h1>
          <p className="text-gray-400 mt-1">Multi-Agent Development System</p>
        </div>

        <div className="flex items-center gap-4">
          {/* Connection status */}
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-400">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          {/* Running status */}
          {isRunning && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-blue-500 animate-pulse" />
              <span className="text-sm text-blue-400">Running</span>
              <button
                onClick={onStop}
                className="ml-2 px-3 py-1 bg-red-600 hover:bg-red-700 text-white text-sm rounded"
              >
                Stop
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
