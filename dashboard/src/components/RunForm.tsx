import { useState, useEffect } from 'react'

interface RunFormProps {
  onRun: (project: string, instructions: string) => void
  disabled: boolean
}

interface Project {
  name: string
  repo: string
  tech_stack: string[]
}

export function RunForm({ onRun, disabled }: RunFormProps) {
  const [project, setProject] = useState('')
  const [instructions, setInstructions] = useState('')
  const [projects, setProjects] = useState<Project[]>([])

  useEffect(() => {
    fetch('/api/projects')
      .then(res => res.json())
      .then(data => {
        setProjects(data.projects || [])
        if (data.projects?.length > 0) {
          setProject(data.projects[0].name)
        }
      })
      .catch(() => {})
  }, [])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (project && instructions) {
      onRun(project, instructions)
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Start New Run</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Project</label>
          <select
            value={project}
            onChange={e => setProject(e.target.value)}
            disabled={disabled}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
          >
            {projects.map(p => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">Instructions</label>
          <textarea
            value={instructions}
            onChange={e => setInstructions(e.target.value)}
            disabled={disabled}
            placeholder="What should the agents build?"
            rows={4}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 resize-none"
          />
        </div>

        <button
          type="submit"
          disabled={disabled || !project || !instructions}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-medium py-2 rounded transition-colors"
        >
          {disabled ? 'Running...' : 'Start Orchestration'}
        </button>
      </form>
    </div>
  )
}
