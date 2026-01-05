"""FastAPI application for the orchestrator dashboard."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from orchestrator.config import config
from orchestrator.core.orchestrator import Orchestrator
from orchestrator.core.checkpoint import CheckpointManager
from orchestrator.core.health import HealthMonitor


# Embedded dashboard HTML (no separate React server needed)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orchestrator Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #111827; color: #f3f4f6; }
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .task-clickable { cursor: pointer; transition: all 0.2s; }
        .task-clickable:hover { transform: translateX(4px); }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 50; }
        .modal.active { display: flex; align-items: center; justify-content: center; }
    </style>
</head>
<body class="min-h-screen p-6">
    <div id="app" class="max-w-7xl mx-auto">
        <!-- Header -->
        <header class="flex items-center justify-between mb-8">
            <div>
                <h1 class="text-3xl font-bold text-white">Orchestrator Dashboard</h1>
                <p class="text-gray-400 mt-1">Multi-Agent Development System</p>
            </div>
            <div class="flex items-center gap-4">
                <div class="flex items-center gap-2">
                    <div id="ws-status" class="w-3 h-3 rounded-full bg-red-500"></div>
                    <span id="ws-text" class="text-sm text-gray-400">Connecting...</span>
                    <button onclick="connectWebSocket()" class="ml-2 text-xs text-blue-400 hover:text-blue-300">Reconnect</button>
                </div>
                <div id="running-indicator" class="hidden flex items-center gap-2">
                    <div class="w-3 h-3 rounded-full bg-blue-500 pulse"></div>
                    <span class="text-sm text-blue-400">Running</span>
                    <button onclick="stopRun()" class="ml-2 px-3 py-1 bg-red-600 hover:bg-red-700 text-white text-sm rounded">Stop</button>
                </div>
            </div>
        </header>

        <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <!-- Left Column - Status & Controls -->
            <div class="space-y-6">
                <!-- Status Card -->
                <div class="bg-gray-800 rounded-lg p-6">
                    <h2 class="text-lg font-semibold text-white mb-4">System Status</h2>
                    <div class="grid grid-cols-2 gap-4">
                        <div class="bg-gray-700 rounded p-3">
                            <div class="text-xs text-gray-400 uppercase">Status</div>
                            <div id="status-text" class="text-lg font-bold text-gray-400">Idle</div>
                        </div>
                        <div class="bg-gray-700 rounded p-3">
                            <div class="text-xs text-gray-400 uppercase">Agents</div>
                            <div id="agents-count" class="text-lg font-bold text-white">0 / 3</div>
                        </div>
                        <div class="bg-gray-700 rounded p-3">
                            <div class="text-xs text-gray-400 uppercase">Completed</div>
                            <div id="completed-count" class="text-lg font-bold text-green-400">0</div>
                        </div>
                        <div class="bg-gray-700 rounded p-3">
                            <div class="text-xs text-gray-400 uppercase">In Progress</div>
                            <div id="progress-count" class="text-lg font-bold text-blue-400">0</div>
                        </div>
                    </div>
                </div>

                <!-- Run Form -->
                <div class="bg-gray-800 rounded-lg p-6">
                    <h2 class="text-lg font-semibold text-white mb-4">Start New Run</h2>
                    <form id="run-form" onsubmit="startRun(event)">
                        <div class="mb-4">
                            <label class="block text-sm text-gray-400 mb-1">Project</label>
                            <select id="project-select" class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                                <option value="">Loading projects...</option>
                            </select>
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm text-gray-400 mb-1">Instructions</label>
                            <textarea id="instructions" rows="4" placeholder="What should the agents build?"
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white placeholder-gray-500 resize-none"></textarea>
                        </div>
                        <button type="submit" id="run-btn"
                            class="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-medium py-2 rounded">
                            Start Orchestration
                        </button>
                    </form>
                    <button onclick="pushToGithub()" id="push-btn"
                        class="w-full mt-3 bg-green-600 hover:bg-green-700 text-white font-medium py-2 rounded flex items-center justify-center gap-2">
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.605-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12"/></svg>
                        Push to GitHub
                    </button>
                    <div id="push-status" class="mt-2 text-sm text-center hidden"></div>
                </div>

                <!-- Agents -->
                <div class="bg-gray-800 rounded-lg p-6">
                    <h2 class="text-lg font-semibold text-white mb-4">Agents <span id="agent-list-count" class="text-gray-400">(0)</span></h2>
                    <div id="agent-list" class="space-y-2">
                        <p class="text-gray-400 text-sm">No agents active</p>
                    </div>
                </div>
            </div>

            <!-- Middle Column - Tasks -->
            <div class="bg-gray-800 rounded-lg p-6">
                <h2 class="text-lg font-semibold text-white mb-4">Tasks <span id="task-count" class="text-gray-400">(0)</span></h2>
                <p class="text-xs text-gray-500 mb-3">Click a task to view output</p>
                <div id="task-list" class="space-y-2 max-h-[600px] overflow-y-auto">
                    <p class="text-gray-400 text-sm">No tasks yet</p>
                </div>
            </div>

            <!-- Task Output Column -->
            <div class="bg-gray-800 rounded-lg p-6">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-lg font-semibold text-white">Task Output</h2>
                    <button onclick="copyOutput()" class="text-xs text-blue-400 hover:text-blue-300">Copy</button>
                </div>
                <div id="selected-task-title" class="text-sm text-gray-400 mb-2">Select a task to view output</div>
                <div id="task-output" class="bg-gray-900 rounded p-4 h-[550px] overflow-y-auto font-mono text-sm whitespace-pre-wrap">
                    <span class="text-gray-500">Task output will appear here...</span>
                </div>
            </div>

            <!-- Right Column - Activity Log -->
            <div class="bg-gray-800 rounded-lg p-6">
                <h2 class="text-lg font-semibold text-white mb-4">Activity Log</h2>
                <div id="log-list" class="h-[600px] overflow-y-auto font-mono text-xs space-y-1">
                    <p class="text-gray-400">Waiting for activity...</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Task Detail Modal -->
    <div id="task-modal" class="modal" onclick="closeModal(event)">
        <div class="bg-gray-800 rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto" onclick="event.stopPropagation()">
            <div class="flex justify-between items-start mb-4">
                <h2 id="modal-title" class="text-xl font-bold text-white">Task Details</h2>
                <button onclick="closeModal()" class="text-gray-400 hover:text-white text-2xl">&times;</button>
            </div>
            <div id="modal-content" class="space-y-4"></div>
        </div>
    </div>

    <script>
        let ws = null;
        let isRunning = false;
        let tasks = [];
        let agents = [];
        let logs = [];
        let taskOutputs = {};  // Store task outputs/summaries
        let selectedTaskId = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 10;

        // WebSocket connection with auto-reconnect
        function connectWebSocket() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.close();
            }

            const wsUrl = `ws://${window.location.host}/ws`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                reconnectAttempts = 0;
                document.getElementById('ws-status').className = 'w-3 h-3 rounded-full bg-green-500';
                document.getElementById('ws-text').textContent = 'Connected';
                addLog('system', 'Connected to server');
            };

            ws.onclose = () => {
                document.getElementById('ws-status').className = 'w-3 h-3 rounded-full bg-red-500';
                document.getElementById('ws-text').textContent = 'Disconnected';
                // Auto-reconnect with exponential backoff
                if (reconnectAttempts < maxReconnectAttempts) {
                    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                    reconnectAttempts++;
                    document.getElementById('ws-text').textContent = `Reconnecting in ${delay/1000}s...`;
                    setTimeout(connectWebSocket, delay);
                } else {
                    document.getElementById('ws-text').textContent = 'Connection failed - click Reconnect';
                }
            };

            ws.onerror = () => {
                console.error('WebSocket error');
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleEvent(data);
            };
        }

        function handleEvent(event) {
            addLog(event.type, formatEvent(event));

            switch(event.type) {
                case 'run_start':
                    isRunning = true;
                    tasks = [];
                    taskOutputs = {};
                    updateUI();
                    break;
                case 'run_complete':
                    isRunning = false;
                    updateUI();
                    break;
                case 'tasks_created':
                    tasks = event.tasks.map(t => ({...t, status: 'queued'}));
                    updateUI();
                    break;
                case 'task_started':
                    const startTask = tasks.find(t => t.id === event.task_id);
                    if (startTask) {
                        startTask.status = 'in_progress';
                        startTask.agent = event.agent_id;
                    }
                    updateUI();
                    break;
                case 'task_completed':
                    const doneTask = tasks.find(t => t.id === event.task_id);
                    if (doneTask) {
                        doneTask.status = 'completed';
                        doneTask.summary = event.summary;
                        doneTask.files_modified = event.files_modified || [];
                    }
                    // Store output for viewing
                    taskOutputs[event.task_id] = {
                        summary: event.summary || 'Task completed',
                        files_modified: event.files_modified || [],
                        timestamp: new Date().toISOString()
                    };
                    updateUI();
                    // Auto-select completed task to show output
                    selectTask(event.task_id);
                    break;
                case 'task_failed':
                    const failTask = tasks.find(t => t.id === event.task_id);
                    if (failTask) {
                        failTask.status = 'failed';
                        failTask.error = event.error;
                    }
                    taskOutputs[event.task_id] = {
                        error: event.error || 'Task failed',
                        timestamp: new Date().toISOString()
                    };
                    updateUI();
                    break;
                case 'agent_created':
                    agents.push({id: event.agent_id, type: event.agent_type, status: 'idle', details: ''});
                    updateUI();
                    break;
                case 'agent_status':
                    // Update agent status with detailed activity info including tokens
                    const statusAgent = agents.find(a => a.id === event.agent_id);
                    if (statusAgent) {
                        statusAgent.status = event.status;
                        statusAgent.details = event.details || '';
                        statusAgent.api_calls = event.api_calls || 0;
                        statusAgent.total_input_tokens = event.total_input_tokens || 0;
                        statusAgent.total_output_tokens = event.total_output_tokens || 0;
                        statusAgent.conversation_turns = event.conversation_turns || 0;
                    }
                    updateUI();
                    break;
            }
        }

        function selectTask(taskId) {
            selectedTaskId = taskId;
            const task = tasks.find(t => t.id === taskId);
            const output = taskOutputs[taskId];

            document.getElementById('selected-task-title').textContent = task ? task.title : 'Unknown task';

            const outputEl = document.getElementById('task-output');
            if (output) {
                let html = '';
                if (output.summary) {
                    html += `<div class="text-green-400 mb-4"><strong>Summary:</strong>\\n${output.summary}</div>`;
                }
                if (output.error) {
                    html += `<div class="text-red-400 mb-4"><strong>Error:</strong>\\n${output.error}</div>`;
                }
                if (output.files_modified && output.files_modified.length > 0) {
                    html += `<div class="text-blue-400"><strong>Files Modified:</strong>\\n${output.files_modified.join('\\n')}</div>`;
                }
                outputEl.innerHTML = html || '<span class="text-gray-500">No output data</span>';
            } else if (task && task.status === 'in_progress') {
                outputEl.innerHTML = '<span class="text-yellow-400 pulse">Task in progress...</span>';
            } else if (task && task.status === 'queued') {
                outputEl.innerHTML = '<span class="text-gray-500">Task waiting in queue...</span>';
            } else {
                outputEl.innerHTML = '<span class="text-gray-500">No output available</span>';
            }
            updateUI();
        }

        function copyOutput() {
            const outputEl = document.getElementById('task-output');
            navigator.clipboard.writeText(outputEl.innerText).then(() => {
                addLog('system', 'Output copied to clipboard');
            });
        }

        function openTaskModal(taskId) {
            const task = tasks.find(t => t.id === taskId);
            const output = taskOutputs[taskId];
            if (!task) return;

            document.getElementById('modal-title').textContent = task.title;
            let content = `
                <div class="bg-gray-700 rounded p-4">
                    <div class="text-sm text-gray-400 mb-2">Status: <span class="${task.status === 'completed' ? 'text-green-400' : task.status === 'failed' ? 'text-red-400' : 'text-blue-400'}">${task.status}</span></div>
                    ${task.agent ? `<div class="text-sm text-gray-400">Agent: ${task.agent}</div>` : ''}
                </div>
            `;
            if (output) {
                if (output.summary) {
                    content += `<div class="bg-gray-900 rounded p-4"><h3 class="text-green-400 font-bold mb-2">Summary</h3><pre class="whitespace-pre-wrap text-gray-300">${output.summary}</pre></div>`;
                }
                if (output.error) {
                    content += `<div class="bg-gray-900 rounded p-4"><h3 class="text-red-400 font-bold mb-2">Error</h3><pre class="whitespace-pre-wrap text-gray-300">${output.error}</pre></div>`;
                }
                if (output.files_modified && output.files_modified.length > 0) {
                    content += `<div class="bg-gray-900 rounded p-4"><h3 class="text-blue-400 font-bold mb-2">Files Modified</h3><ul class="list-disc list-inside text-gray-300">${output.files_modified.map(f => `<li>${f}</li>`).join('')}</ul></div>`;
                }
            }
            document.getElementById('modal-content').innerHTML = content;
            document.getElementById('task-modal').classList.add('active');
        }

        function closeModal(event) {
            if (!event || event.target.id === 'task-modal') {
                document.getElementById('task-modal').classList.remove('active');
            }
        }

        function formatEvent(event) {
            switch(event.type) {
                case 'run_start': return `Started: ${event.project}`;
                case 'run_complete': return `Completed in ${event.summary?.duration_seconds?.toFixed(1)}s`;
                case 'tasks_created': return `Created ${event.count} tasks`;
                case 'task_started': return `Started: ${event.task_title}`;
                case 'task_completed': return `Completed: ${event.task_title}`;
                case 'task_failed': return `Failed: ${event.error}`;
                case 'agent_created': return `Agent created: ${event.agent_type}`;
                default: return JSON.stringify(event);
            }
        }

        function addLog(type, message) {
            const time = new Date().toLocaleTimeString();
            logs.push({time, type, message});
            if (logs.length > 100) logs.shift();
            updateLogs();
        }

        function updateLogs() {
            const container = document.getElementById('log-list');
            const colors = {
                run_start: 'text-green-400',
                run_complete: 'text-green-400',
                task_started: 'text-cyan-400',
                task_completed: 'text-green-400',
                task_failed: 'text-red-400',
                agent_created: 'text-purple-400',
                system: 'text-gray-400'
            };
            container.innerHTML = logs.map(l =>
                `<div><span class="text-gray-500">${l.time}</span> <span class="${colors[l.type] || 'text-gray-300'}">${l.message}</span></div>`
            ).join('');
            container.scrollTop = container.scrollHeight;
        }

        function updateUI() {
            // Running indicator
            document.getElementById('running-indicator').className = isRunning ? 'flex items-center gap-2' : 'hidden';
            document.getElementById('status-text').textContent = isRunning ? 'Running' : 'Idle';
            document.getElementById('status-text').className = isRunning ? 'text-lg font-bold text-green-400' : 'text-lg font-bold text-gray-400';
            document.getElementById('run-btn').disabled = isRunning;

            // Counts
            const completed = tasks.filter(t => t.status === 'completed').length;
            const inProgress = tasks.filter(t => t.status === 'in_progress').length;
            document.getElementById('completed-count').textContent = completed;
            document.getElementById('progress-count').textContent = inProgress;
            document.getElementById('agents-count').textContent = `${agents.length} / 3`;
            document.getElementById('task-count').textContent = `(${tasks.length})`;
            document.getElementById('agent-list-count').textContent = `(${agents.length})`;

            // Task list - clickable to show output
            const taskContainer = document.getElementById('task-list');
            if (tasks.length === 0) {
                taskContainer.innerHTML = '<p class="text-gray-400 text-sm">No tasks yet</p>';
            } else {
                const statusColors = {
                    queued: 'bg-yellow-500',
                    in_progress: 'bg-blue-500',
                    completed: 'bg-green-500',
                    failed: 'bg-red-500'
                };
                const statusBg = {
                    queued: 'bg-yellow-500/10 border-yellow-500/30',
                    in_progress: 'bg-blue-500/10 border-blue-500/30',
                    completed: 'bg-green-500/10 border-green-500/30',
                    failed: 'bg-red-500/10 border-red-500/30'
                };
                taskContainer.innerHTML = tasks.map(t => `
                    <div class="p-3 rounded border task-clickable ${statusBg[t.status] || 'bg-gray-700'} ${selectedTaskId === t.id ? 'ring-2 ring-blue-500' : ''}"
                         onclick="selectTask('${t.id}')" ondblclick="openTaskModal('${t.id}')">
                        <div class="flex items-start gap-2">
                            <div class="w-2 h-2 rounded-full mt-2 ${statusColors[t.status] || 'bg-gray-500'}"></div>
                            <div class="flex-1 min-w-0">
                                <div class="text-sm text-white truncate">${t.title}</div>
                                <div class="text-xs text-gray-400 mt-1">${t.status}${t.agent ? ' • ' + t.agent : ''}</div>
                            </div>
                        </div>
                    </div>
                `).join('');
            }

            // Agent list - with detailed status
            const agentContainer = document.getElementById('agent-list');
            if (agents.length === 0) {
                agentContainer.innerHTML = '<p class="text-gray-400 text-sm">No agents active</p>';
            } else {
                const typeColors = {
                    architect: 'text-purple-400',
                    frontend: 'text-cyan-400',
                    backend: 'text-orange-400',
                    fullstack: 'text-green-400'
                };
                const statusColors = {
                    idle: 'bg-gray-600 text-gray-400',
                    calling_api: 'bg-yellow-500/20 text-yellow-400',
                    processing: 'bg-blue-500/20 text-blue-400',
                    error: 'bg-red-500/20 text-red-400'
                };
                const statusIcons = {
                    calling_api: '⏳',
                    processing: '⚙️',
                    idle: '💤',
                    error: '❌'
                };
                // Helper to format large numbers
                const formatTokens = (n) => n >= 1000 ? (n/1000).toFixed(1) + 'k' : n;

                agentContainer.innerHTML = agents.map(a => `
                    <div class="p-3 rounded bg-gray-700/50 border border-gray-600 ${a.status === 'calling_api' ? 'pulse' : ''}">
                        <div class="flex items-center justify-between mb-1">
                            <span class="${typeColors[a.type] || 'text-white'} font-medium">${a.type}</span>
                            <span class="text-xs px-2 py-1 rounded ${statusColors[a.status] || 'bg-gray-600 text-gray-400'}">
                                ${statusIcons[a.status] || ''} ${a.status}
                            </span>
                        </div>
                        ${a.details ? `<div class="text-xs text-gray-400 truncate" title="${a.details}">${a.details}</div>` : ''}
                        <div class="text-xs text-gray-500 mt-1 grid grid-cols-2 gap-1">
                            <span>API calls: ${a.api_calls || 0}</span>
                            <span>Turns: ${a.conversation_turns || 0}</span>
                            ${a.total_input_tokens ? `<span>In: ${formatTokens(a.total_input_tokens)}</span>` : ''}
                            ${a.total_output_tokens ? `<span>Out: ${formatTokens(a.total_output_tokens)}</span>` : ''}
                        </div>
                    </div>
                `).join('');
            }
        }

        async function loadProjects() {
            try {
                const res = await fetch('/projects');
                const data = await res.json();
                const select = document.getElementById('project-select');
                if (data.projects && data.projects.length > 0) {
                    select.innerHTML = data.projects.map(p =>
                        `<option value="${p.name}">${p.name} (${p.tech_stack?.slice(0,2).join(', ') || 'no stack'})</option>`
                    ).join('');
                } else {
                    select.innerHTML = '<option value="">No projects configured</option>';
                }
            } catch (e) {
                console.error('Failed to load projects:', e);
            }
        }

        async function startRun(event) {
            event.preventDefault();
            const project = document.getElementById('project-select').value;
            const instructions = document.getElementById('instructions').value;

            if (!project || !instructions) {
                alert('Please select a project and enter instructions');
                return;
            }

            try {
                const res = await fetch('/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({project, instructions})
                });
                if (res.ok) {
                    isRunning = true;
                    logs = [];
                    updateUI();
                } else {
                    const err = await res.json();
                    alert('Error: ' + err.detail);
                }
            } catch (e) {
                alert('Failed to start: ' + e.message);
            }
        }

        async function stopRun() {
            try {
                await fetch('/stop', {method: 'POST'});
            } catch (e) {
                console.error('Failed to stop:', e);
            }
        }

        async function pushToGithub() {
            const btn = document.getElementById('push-btn');
            const status = document.getElementById('push-status');

            btn.disabled = true;
            btn.innerHTML = '<svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Pushing...';
            status.className = 'mt-2 text-sm text-center text-yellow-400';
            status.textContent = 'Pushing to GitHub...';
            status.classList.remove('hidden');

            try {
                const res = await fetch('/push', {method: 'POST'});
                const data = await res.json();

                if (data.status === 'success') {
                    status.className = 'mt-2 text-sm text-center text-green-400';
                    status.textContent = data.message;
                    addLog('git', 'Pushed to GitHub: ' + data.branch);
                } else {
                    status.className = 'mt-2 text-sm text-center text-red-400';
                    status.textContent = data.message || 'Push failed';
                    addLog('error', 'Git push failed: ' + data.message);
                }
            } catch (e) {
                status.className = 'mt-2 text-sm text-center text-red-400';
                status.textContent = 'Error: ' + e.message;
            }

            btn.disabled = false;
            btn.innerHTML = '<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.605-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12"/></svg> Push to GitHub';

            // Hide status after 5 seconds
            setTimeout(() => { status.classList.add('hidden'); }, 5000);
        }

        // Initialize
        connectWebSocket();
        loadProjects();
        updateUI();
    </script>
</body>
</html>
"""


# Global orchestrator instance
_orchestrator: Optional[Orchestrator] = None
_checkpoint_manager: Optional[CheckpointManager] = None
_health_monitor: Optional[HealthMonitor] = None
_connected_websockets: list[WebSocket] = []


class RunRequest(BaseModel):
    """Request to start an orchestration run."""
    project: str
    instructions: str
    use_llm_decomposition: bool = True
    timeout_minutes: int = 240


class ProjectConfig(BaseModel):
    """Project configuration."""
    name: str
    repo: str
    tech_stack: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _orchestrator, _checkpoint_manager, _health_monitor

    # Initialize components
    _orchestrator = Orchestrator(
        on_progress=broadcast_progress,
    )
    _checkpoint_manager = CheckpointManager()
    _health_monitor = HealthMonitor(
        agent_pool=_orchestrator.agent_pool,
        on_system_degraded=on_system_degraded,
    )

    # Start health monitor
    await _health_monitor.start()

    yield

    # Cleanup
    if _health_monitor:
        await _health_monitor.stop()
    if _orchestrator and _orchestrator.running:
        await _orchestrator.shutdown()


async def broadcast_progress(event: dict) -> None:
    """Broadcast progress events to all connected WebSocket clients."""
    disconnected = []
    for ws in _connected_websockets:
        try:
            await ws.send_json(event)
        except Exception:
            disconnected.append(ws)

    # Remove disconnected clients
    for ws in disconnected:
        _connected_websockets.remove(ws)


async def on_system_degraded(health) -> None:
    """Handle system degradation."""
    await broadcast_progress({
        "type": "system_health",
        "status": health.status.value,
        "issues": health.issues,
        "timestamp": datetime.utcnow().isoformat(),
    })


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Orchestrator API",
        description="Multi-agent orchestration system API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware for dashboard
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict this
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the dashboard."""
        return DASHBOARD_HTML

    @app.get("/api")
    async def api_root():
        """API root."""
        return {
            "name": "Orchestrator API",
            "version": "0.1.0",
            "status": "running" if _orchestrator and _orchestrator.running else "idle",
        }

    @app.get("/health")
    async def health():
        """Get system health."""
        if not _health_monitor:
            return {"status": "unknown"}
        return _health_monitor.get_health_summary()

    @app.get("/status")
    async def status():
        """Get orchestrator status."""
        if not _orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")
        return _orchestrator.get_status()

    @app.get("/projects")
    async def list_projects():
        """List configured projects."""
        from pathlib import Path
        from orchestrator.models.project import ProjectConfig as PC

        projects = []
        config_dir = Path("projects")

        if config_dir.exists():
            for path in config_dir.glob("*.yaml"):
                try:
                    proj = PC.from_yaml(path)
                    projects.append({
                        "name": proj.name,
                        "repo": proj.github.repo,
                        "tech_stack": proj.tech_stack,
                    })
                except Exception as e:
                    projects.append({
                        "name": path.stem,
                        "error": str(e),
                    })

        return {"projects": projects}

    @app.post("/run")
    async def run(request: RunRequest, background_tasks: BackgroundTasks):
        """Start an orchestration run."""
        if not _orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")

        if _orchestrator.running:
            raise HTTPException(status_code=409, detail="Orchestrator already running")

        # Run in background
        background_tasks.add_task(
            _orchestrator.run,
            project_name=request.project,
            instructions=request.instructions,
            use_llm_decomposition=request.use_llm_decomposition,
            timeout_minutes=request.timeout_minutes,
        )

        return {
            "status": "started",
            "project": request.project,
            "instructions": request.instructions,
        }

    @app.post("/stop")
    async def stop():
        """Stop the current run."""
        if not _orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")

        if not _orchestrator.running:
            raise HTTPException(status_code=409, detail="Orchestrator not running")

        _orchestrator.stop()
        return {"status": "stopping"}

    @app.post("/push")
    async def push_to_github():
        """Push changes to GitHub."""
        if not _orchestrator or not _orchestrator.project:
            raise HTTPException(status_code=503, detail="No project loaded")

        try:
            import subprocess
            from pathlib import Path

            project_path = Path(_orchestrator.project.local_path)
            if not project_path.exists():
                raise HTTPException(status_code=404, detail="Project path not found")

            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=project_path,
                capture_output=True,
                text=True
            )
            branch = result.stdout.strip() or "main"

            # Check for changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_path,
                capture_output=True,
                text=True
            )

            has_changes = bool(result.stdout.strip())

            if has_changes:
                # Add all changes
                subprocess.run(["git", "add", "-A"], cwd=project_path)

                # Commit
                subprocess.run(
                    ["git", "commit", "-m", "Orchestrator: automated changes"],
                    cwd=project_path,
                    capture_output=True
                )

            # Push to remote
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch],
                cwd=project_path,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "status": "error",
                    "message": result.stderr or "Push failed",
                    "branch": branch
                }

            return {
                "status": "success",
                "message": f"Pushed to origin/{branch}",
                "branch": branch,
                "had_changes": has_changes
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/tasks")
    async def get_tasks():
        """Get all tasks."""
        if not _orchestrator:
            return {"tasks": []}

        tasks = []
        for task_id, task in _orchestrator.scheduler.tasks.items():
            tasks.append({
                "id": task.id,
                "title": task.title,
                "status": task.status.value,
                "agent_type": task.agent_type_hint.value,
                "assigned_agent": task.assigned_agent_id,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            })

        return {"tasks": tasks}

    @app.get("/agents")
    async def get_agents():
        """Get all agents."""
        if not _orchestrator:
            return {"agents": []}

        agents = []
        for agent_id, agent in _orchestrator.agent_pool.agents.items():
            agents.append({
                "id": agent.id,
                "type": agent.agent_type.value,
                "status": agent.status.value,
                "current_task": agent.current_task_id,
                "tasks_completed": agent.tasks_completed,
                "errors_count": agent.errors_count,
                "last_heartbeat": agent.last_heartbeat.isoformat(),
            })

        return {"agents": agents}

    @app.get("/checkpoints")
    async def get_checkpoints():
        """Get available checkpoints."""
        if not _checkpoint_manager:
            return {"checkpoints": []}

        checkpoints = _checkpoint_manager.list_checkpoints()
        return {
            "checkpoints": [
                {
                    "id": c.id,
                    "timestamp": c.timestamp.isoformat(),
                    "project": c.project,
                    "tasks_total": c.tasks_total,
                    "tasks_completed": c.tasks_completed,
                    "size_mb": round(c.size_bytes / (1024 * 1024), 2),
                }
                for c in checkpoints
            ],
            "stats": _checkpoint_manager.get_stats(),
        }

    @app.post("/checkpoints/{checkpoint_id}/restore")
    async def restore_checkpoint(checkpoint_id: str):
        """Restore from a checkpoint."""
        if not _checkpoint_manager:
            raise HTTPException(status_code=503, detail="Checkpoint manager not initialized")

        if _orchestrator and _orchestrator.running:
            raise HTTPException(status_code=409, detail="Cannot restore while running")

        state = await _checkpoint_manager.load(checkpoint_id)
        if not state:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        # TODO: Implement state restoration
        return {"status": "restored", "checkpoint_id": checkpoint_id}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time updates."""
        await websocket.accept()
        _connected_websockets.append(websocket)

        try:
            while True:
                # Keep connection alive and receive any commands
                data = await websocket.receive_json()

                # Handle commands
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data.get("type") == "get_status":
                    if _orchestrator:
                        await websocket.send_json({
                            "type": "status",
                            "data": _orchestrator.get_status(),
                        })

        except WebSocketDisconnect:
            pass
        finally:
            if websocket in _connected_websockets:
                _connected_websockets.remove(websocket)

    return app


# Create default app instance
app = create_app()


def run_server(host: str = "127.0.0.1", port: int = 8420):
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
