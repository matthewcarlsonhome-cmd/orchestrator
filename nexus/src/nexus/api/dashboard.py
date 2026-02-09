"""
Premium Dashboard HTML - Beautiful, Fast, Feature-Rich
Inspired by Reflect, Mem.ai, and modern note-taking apps.
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus - Personal AI Assistant</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🧠</text></svg>">
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-tertiary: #1a1a24;
            --bg-hover: #22222e;
            --border: #2a2a3a;
            --text-primary: #f0f0f5;
            --text-secondary: #8888a0;
            --text-muted: #555566;
            --accent: #6366f1;
            --accent-hover: #818cf8;
            --accent-glow: rgba(99, 102, 241, 0.3);
            --success: #22c55e;
            --warning: #f59e0b;
            --error: #ef4444;
        }

        * { box-sizing: border-box; }

        body {
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            overflow: hidden;
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

        /* Layout */
        .app-container {
            display: flex;
            height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            width: 240px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }

        .sidebar-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 20px;
            font-weight: 600;
            background: linear-gradient(135deg, var(--accent), #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .nav-section {
            padding: 12px;
        }

        .nav-label {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-muted);
            padding: 8px 12px;
            letter-spacing: 0.5px;
        }

        .nav-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.15s;
            color: var(--text-secondary);
            font-size: 14px;
        }

        .nav-item:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }

        .nav-item.active {
            background: var(--accent);
            color: white;
        }

        .nav-item-icon {
            width: 18px;
            text-align: center;
        }

        .nav-shortcut {
            margin-left: auto;
            font-size: 11px;
            color: var(--text-muted);
            background: var(--bg-tertiary);
            padding: 2px 6px;
            border-radius: 4px;
        }

        .nav-item.active .nav-shortcut {
            background: rgba(255,255,255,0.2);
            color: rgba(255,255,255,0.8);
        }

        /* Stats in sidebar */
        .sidebar-stats {
            margin-top: auto;
            padding: 16px;
            border-top: 1px solid var(--border);
            font-size: 12px;
            color: var(--text-muted);
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
        }

        .stat-value {
            color: var(--text-secondary);
            font-weight: 500;
        }

        /* Main Content */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* Header */
        .header {
            padding: 16px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 16px;
            background: var(--bg-secondary);
        }

        .search-box {
            flex: 1;
            max-width: 500px;
            position: relative;
        }

        .search-input {
            width: 100%;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px 16px 10px 40px;
            color: var(--text-primary);
            font-size: 14px;
            outline: none;
            transition: all 0.2s;
        }

        .search-input:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }

        .search-input::placeholder {
            color: var(--text-muted);
        }

        .search-icon {
            position: absolute;
            left: 14px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
        }

        .header-actions {
            display: flex;
            gap: 8px;
        }

        .btn {
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
            border: none;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn-primary {
            background: var(--accent);
            color: white;
        }

        .btn-primary:hover {
            background: var(--accent-hover);
            transform: translateY(-1px);
        }

        .btn-secondary {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }

        /* Content Area */
        .content-area {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
        }

        /* View Containers */
        .view { display: none; }
        .view.active { display: block; }

        /* Daily Notes View */
        .daily-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
        }

        .daily-date {
            font-size: 28px;
            font-weight: 600;
        }

        .daily-nav {
            display: flex;
            gap: 8px;
        }

        .daily-nav-btn {
            padding: 8px 12px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s;
        }

        .daily-nav-btn:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }

        .daily-editor {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            min-height: 400px;
        }

        .daily-editor-content {
            padding: 20px;
            min-height: 350px;
            outline: none;
            font-size: 15px;
            line-height: 1.7;
        }

        .daily-editor-content:empty:before {
            content: "What's on your mind today?";
            color: var(--text-muted);
        }

        .daily-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 20px;
            border-top: 1px solid var(--border);
            font-size: 12px;
            color: var(--text-muted);
        }

        /* Entries View */
        .entries-grid {
            display: grid;
            gap: 16px;
        }

        .entry-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .entry-card:hover {
            border-color: var(--accent);
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }

        .entry-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }

        .entry-type {
            font-size: 11px;
            padding: 3px 8px;
            background: var(--accent);
            color: white;
            border-radius: 4px;
            text-transform: uppercase;
            font-weight: 600;
        }

        .entry-date {
            font-size: 12px;
            color: var(--text-muted);
            margin-left: auto;
        }

        .entry-content {
            color: var(--text-secondary);
            font-size: 14px;
            line-height: 1.6;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .entry-tags {
            display: flex;
            gap: 6px;
            margin-top: 12px;
            flex-wrap: wrap;
        }

        .tag {
            font-size: 11px;
            padding: 3px 8px;
            background: var(--bg-tertiary);
            color: var(--text-muted);
            border-radius: 4px;
        }

        /* Graph View */
        .graph-container {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            height: calc(100vh - 200px);
            position: relative;
        }

        .graph-controls {
            position: absolute;
            top: 16px;
            right: 16px;
            display: flex;
            gap: 8px;
            z-index: 10;
        }

        #graph-svg {
            width: 100%;
            height: 100%;
        }

        .node {
            cursor: pointer;
        }

        .node circle {
            stroke: var(--border);
            stroke-width: 2px;
            transition: all 0.2s;
        }

        .node:hover circle {
            stroke: var(--accent);
            stroke-width: 3px;
        }

        .node text {
            font-size: 10px;
            fill: var(--text-secondary);
        }

        .link {
            stroke: var(--border);
            stroke-opacity: 0.4;
        }

        /* Ask View */
        .ask-container {
            max-width: 800px;
            margin: 0 auto;
        }

        .ask-input-area {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        }

        .ask-textarea {
            width: 100%;
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-size: 16px;
            line-height: 1.6;
            resize: none;
            outline: none;
            min-height: 100px;
        }

        .ask-textarea::placeholder {
            color: var(--text-muted);
        }

        .ask-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid var(--border);
        }

        .ask-response {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
        }

        .ask-response-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }

        .ask-response-icon {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, var(--accent), #a855f7);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
        }

        .ask-response-content {
            font-size: 15px;
            line-height: 1.8;
            color: var(--text-secondary);
        }

        .ask-sources {
            margin-top: 20px;
            padding-top: 16px;
            border-top: 1px solid var(--border);
        }

        .ask-sources-title {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 12px;
        }

        .source-item {
            padding: 12px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            margin-bottom: 8px;
            font-size: 13px;
            color: var(--text-secondary);
        }

        /* Command Palette */
        .command-palette-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.7);
            display: none;
            align-items: flex-start;
            justify-content: center;
            padding-top: 100px;
            z-index: 1000;
        }

        .command-palette-overlay.active {
            display: flex;
        }

        .command-palette {
            width: 600px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }

        .command-input {
            width: 100%;
            padding: 16px 20px;
            background: transparent;
            border: none;
            border-bottom: 1px solid var(--border);
            color: var(--text-primary);
            font-size: 16px;
            outline: none;
        }

        .command-results {
            max-height: 400px;
            overflow-y: auto;
        }

        .command-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 20px;
            cursor: pointer;
            transition: background 0.1s;
        }

        .command-item:hover,
        .command-item.selected {
            background: var(--bg-hover);
        }

        .command-item-icon {
            width: 24px;
            text-align: center;
            color: var(--text-muted);
        }

        .command-item-text {
            flex: 1;
        }

        .command-item-title {
            font-size: 14px;
        }

        .command-item-desc {
            font-size: 12px;
            color: var(--text-muted);
        }

        /* Toast Notifications */
        .toast-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 2000;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .toast {
            padding: 12px 20px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: slideIn 0.3s ease;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }

        .toast.success { border-left: 3px solid var(--success); }
        .toast.error { border-left: 3px solid var(--error); }
        .toast.info { border-left: 3px solid var(--accent); }

        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        /* Modal */
        .modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.7);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }

        .modal-overlay.active { display: flex; }

        .modal {
            width: 600px;
            max-height: 80vh;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
        }

        .modal-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-title {
            font-size: 18px;
            font-weight: 600;
        }

        .modal-close {
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 24px;
            cursor: pointer;
        }

        .modal-body {
            padding: 20px;
            overflow-y: auto;
            max-height: 60vh;
        }

        /* Calendar Mini */
        .calendar-mini {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 4px;
            padding: 16px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            margin-bottom: 24px;
        }

        .calendar-day {
            aspect-ratio: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s;
            color: var(--text-secondary);
        }

        .calendar-day:hover {
            background: var(--bg-hover);
        }

        .calendar-day.today {
            background: var(--accent);
            color: white;
            font-weight: 600;
        }

        .calendar-day.has-entry {
            position: relative;
        }

        .calendar-day.has-entry::after {
            content: '';
            position: absolute;
            bottom: 4px;
            width: 4px;
            height: 4px;
            background: var(--accent);
            border-radius: 50%;
        }

        .calendar-day.today.has-entry::after {
            background: white;
        }

        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }

        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 16px;
        }

        .empty-state-title {
            font-size: 18px;
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }

        /* Loading */
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 40px;
        }

        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Quick Add Floating Button */
        .fab {
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            padding: 16px 32px;
            background: linear-gradient(135deg, var(--accent), #a855f7);
            color: white;
            border: none;
            border-radius: 100px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 20px var(--accent-glow);
            transition: all 0.2s;
            z-index: 100;
        }

        .fab:hover {
            transform: translateX(-50%) translateY(-2px);
            box-shadow: 0 8px 30px var(--accent-glow);
        }

        /* Streak indicator */
        .streak-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            background: linear-gradient(135deg, #f59e0b, #ef4444);
            color: white;
            border-radius: 100px;
            font-size: 12px;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="sidebar-header">
                <div class="logo">
                    <span>🧠</span>
                    <span>Nexus</span>
                </div>
            </div>

            <nav class="nav-section">
                <div class="nav-label">Main</div>
                <div class="nav-item active" data-view="daily" onclick="switchView('daily')">
                    <span class="nav-item-icon">📅</span>
                    <span>Daily Notes</span>
                    <span class="nav-shortcut">⌘1</span>
                </div>
                <div class="nav-item" data-view="entries" onclick="switchView('entries')">
                    <span class="nav-item-icon">📝</span>
                    <span>All Entries</span>
                    <span class="nav-shortcut">⌘2</span>
                </div>
                <div class="nav-item" data-view="graph" onclick="switchView('graph')">
                    <span class="nav-item-icon">🔗</span>
                    <span>Knowledge Graph</span>
                    <span class="nav-shortcut">⌘3</span>
                </div>
                <div class="nav-item" data-view="ask" onclick="switchView('ask')">
                    <span class="nav-item-icon">💬</span>
                    <span>Ask Nexus</span>
                    <span class="nav-shortcut">⌘4</span>
                </div>
            </nav>

            <nav class="nav-section">
                <div class="nav-label">Insights</div>
                <div class="nav-item" onclick="showBriefing('daily')">
                    <span class="nav-item-icon">☀️</span>
                    <span>Daily Briefing</span>
                </div>
                <div class="nav-item" onclick="showBriefing('weekly')">
                    <span class="nav-item-icon">📊</span>
                    <span>Weekly Review</span>
                </div>
            </nav>

            <div class="sidebar-stats" id="sidebar-stats">
                <div class="stat-row">
                    <span>Total Entries</span>
                    <span class="stat-value" id="stat-entries">-</span>
                </div>
                <div class="stat-row">
                    <span>This Week</span>
                    <span class="stat-value" id="stat-week">-</span>
                </div>
                <div class="stat-row">
                    <span>Streak</span>
                    <span class="stat-value">🔥 <span id="stat-streak">0</span> days</span>
                </div>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="main-content">
            <!-- Header -->
            <header class="header">
                <div class="search-box">
                    <span class="search-icon">🔍</span>
                    <input type="text" class="search-input" id="global-search"
                           placeholder="Search or press ⌘K for commands..."
                           onclick="openCommandPalette()">
                </div>
                <div class="header-actions">
                    <button class="btn btn-secondary" onclick="openQuickAdd()">
                        <span>+</span> Quick Add
                    </button>
                    <button class="btn btn-primary" onclick="switchView('ask')">
                        <span>✨</span> Ask AI
                    </button>
                </div>
            </header>

            <!-- Content Area -->
            <div class="content-area">
                <!-- Daily Notes View -->
                <div class="view active" id="view-daily">
                    <div class="daily-header">
                        <div>
                            <div class="daily-date" id="daily-date">Today</div>
                            <div style="color: var(--text-muted); margin-top: 4px;" id="daily-date-full"></div>
                        </div>
                        <div class="daily-nav">
                            <button class="daily-nav-btn" onclick="navigateDaily(-1)">← Yesterday</button>
                            <button class="daily-nav-btn" onclick="navigateDaily(0)">Today</button>
                            <button class="daily-nav-btn" onclick="navigateDaily(1)">Tomorrow →</button>
                        </div>
                    </div>

                    <div class="calendar-mini" id="calendar-mini"></div>

                    <div class="daily-editor">
                        <div class="daily-editor-content" contenteditable="true" id="daily-content"
                             onblur="saveDailyNote()"></div>
                        <div class="daily-footer">
                            <span id="daily-word-count">0 words</span>
                            <span id="daily-save-status">Auto-saved</span>
                        </div>
                    </div>
                </div>

                <!-- Entries View -->
                <div class="view" id="view-entries">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                        <h2 style="font-size: 24px; font-weight: 600;">All Entries</h2>
                        <div style="display: flex; gap: 8px;">
                            <select id="filter-type" class="search-input" style="width: auto;" onchange="loadEntries()">
                                <option value="">All Types</option>
                                <option value="thought">Thoughts</option>
                                <option value="note">Notes</option>
                                <option value="meeting">Meetings</option>
                                <option value="idea">Ideas</option>
                            </select>
                        </div>
                    </div>
                    <div class="entries-grid" id="entries-list"></div>
                </div>

                <!-- Graph View -->
                <div class="view" id="view-graph">
                    <div style="margin-bottom: 24px;">
                        <h2 style="font-size: 24px; font-weight: 600;">Knowledge Graph</h2>
                        <p style="color: var(--text-muted);">Visualize connections between your entries</p>
                    </div>
                    <div class="graph-container">
                        <div class="graph-controls">
                            <button class="btn btn-secondary" onclick="resetGraph()">Reset Zoom</button>
                        </div>
                        <svg id="graph-svg"></svg>
                    </div>
                </div>

                <!-- Ask View -->
                <div class="view" id="view-ask">
                    <div class="ask-container">
                        <h2 style="font-size: 24px; font-weight: 600; margin-bottom: 8px;">Ask Nexus</h2>
                        <p style="color: var(--text-muted); margin-bottom: 24px;">
                            Ask questions about your knowledge base and get intelligent answers with sources.
                        </p>

                        <div class="ask-input-area">
                            <textarea class="ask-textarea" id="ask-input"
                                      placeholder="What would you like to know? e.g., 'What were my key decisions last week?'"
                                      rows="3"></textarea>
                            <div class="ask-actions">
                                <div style="font-size: 12px; color: var(--text-muted);">
                                    Press <kbd style="background: var(--bg-tertiary); padding: 2px 6px; border-radius: 4px;">⌘ Enter</kbd> to ask
                                </div>
                                <button class="btn btn-primary" onclick="askQuestion()">
                                    <span>✨</span> Ask
                                </button>
                            </div>
                        </div>

                        <div id="ask-response-area" style="display: none;">
                            <div class="ask-response">
                                <div class="ask-response-header">
                                    <div class="ask-response-icon">✨</div>
                                    <div>
                                        <div style="font-weight: 500;">Nexus</div>
                                        <div style="font-size: 12px; color: var(--text-muted);" id="ask-meta"></div>
                                    </div>
                                </div>
                                <div class="ask-response-content" id="ask-answer"></div>
                                <div class="ask-sources" id="ask-sources-area" style="display: none;">
                                    <div class="ask-sources-title">Sources from your knowledge base</div>
                                    <div id="ask-sources"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Quick Add FAB -->
    <button class="fab" onclick="openQuickAdd()">
        <span>+</span> Quick Add
    </button>

    <!-- Command Palette -->
    <div class="command-palette-overlay" id="command-palette" onclick="closeCommandPalette(event)">
        <div class="command-palette" onclick="event.stopPropagation()">
            <input type="text" class="command-input" id="command-input"
                   placeholder="Type a command or search..."
                   oninput="filterCommands(this.value)">
            <div class="command-results" id="command-results"></div>
        </div>
    </div>

    <!-- Quick Add Modal -->
    <div class="modal-overlay" id="quick-add-modal" onclick="closeQuickAdd(event)">
        <div class="modal" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div class="modal-title">Quick Add</div>
                <button class="modal-close" onclick="closeQuickAddModal()">&times;</button>
            </div>
            <div class="modal-body">
                <textarea id="quick-add-content" class="ask-textarea"
                          placeholder="What's on your mind?" rows="5"></textarea>
                <div style="margin-top: 16px;">
                    <input type="text" id="quick-add-tags" class="search-input"
                           placeholder="Tags (comma separated)" style="width: 100%;">
                </div>
                <div style="display: flex; gap: 8px; margin-top: 16px;">
                    <select id="quick-add-type" class="search-input" style="flex: 1;">
                        <option value="thought">💭 Thought</option>
                        <option value="note">📝 Note</option>
                        <option value="idea">💡 Idea</option>
                        <option value="meeting">📅 Meeting</option>
                        <option value="task">✅ Task</option>
                    </select>
                    <button class="btn btn-primary" onclick="submitQuickAdd()" style="flex: 1;">
                        Save Entry
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- Entry Detail Modal -->
    <div class="modal-overlay" id="entry-modal" onclick="closeEntryModal(event)">
        <div class="modal" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div class="modal-title" id="entry-modal-title">Entry</div>
                <button class="modal-close" onclick="closeEntryModalBtn()">&times;</button>
            </div>
            <div class="modal-body" id="entry-modal-body"></div>
        </div>
    </div>

    <!-- Toast Container -->
    <div class="toast-container" id="toast-container"></div>

    <script>
        // State
        let currentView = 'daily';
        let currentDailyDate = new Date();
        let entries = [];
        let stats = { entries: 0, week: 0, streak: 0 };
        let commandIndex = 0;

        // Commands for palette
        const commands = [
            { icon: '➕', title: 'Quick Add', desc: 'Add a new entry', action: () => openQuickAdd() },
            { icon: '📅', title: 'Daily Notes', desc: 'Open daily notes', action: () => switchView('daily') },
            { icon: '📝', title: 'All Entries', desc: 'Browse all entries', action: () => switchView('entries') },
            { icon: '🔗', title: 'Knowledge Graph', desc: 'View connections', action: () => switchView('graph') },
            { icon: '💬', title: 'Ask Nexus', desc: 'Ask a question', action: () => switchView('ask') },
            { icon: '☀️', title: 'Daily Briefing', desc: 'Get your daily briefing', action: () => showBriefing('daily') },
            { icon: '📊', title: 'Weekly Review', desc: 'Get your weekly review', action: () => showBriefing('weekly') },
            { icon: '🔍', title: 'Search', desc: 'Search your knowledge', action: () => document.getElementById('global-search').focus() },
        ];

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadStats();
            loadEntries();
            updateDailyView();
            renderCalendar();
            setupKeyboardShortcuts();
        });

        // View switching
        function switchView(view) {
            currentView = view;
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById('view-' + view).classList.add('active');
            document.querySelector(`.nav-item[data-view="${view}"]`)?.classList.add('active');

            if (view === 'entries') loadEntries();
            if (view === 'graph') renderGraph();
        }

        // Daily Notes
        function updateDailyView() {
            const options = { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' };
            const isToday = currentDailyDate.toDateString() === new Date().toDateString();

            document.getElementById('daily-date').textContent = isToday ? 'Today' :
                currentDailyDate.toLocaleDateString('en-US', { weekday: 'long' });
            document.getElementById('daily-date-full').textContent =
                currentDailyDate.toLocaleDateString('en-US', options);

            loadDailyNote();
        }

        function navigateDaily(offset) {
            if (offset === 0) {
                currentDailyDate = new Date();
            } else {
                currentDailyDate.setDate(currentDailyDate.getDate() + offset);
            }
            updateDailyView();
        }

        async function loadDailyNote() {
            const dateStr = currentDailyDate.toISOString().split('T')[0];
            try {
                const res = await fetch(`/daily/${dateStr}`);
                if (res.ok) {
                    const data = await res.json();
                    document.getElementById('daily-content').textContent = data.content || '';
                } else {
                    document.getElementById('daily-content').textContent = '';
                }
            } catch (e) {
                document.getElementById('daily-content').textContent = '';
            }
            updateWordCount();
        }

        async function saveDailyNote() {
            const content = document.getElementById('daily-content').textContent;
            const dateStr = currentDailyDate.toISOString().split('T')[0];

            document.getElementById('daily-save-status').textContent = 'Saving...';

            try {
                await fetch(`/daily/${dateStr}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content })
                });
                document.getElementById('daily-save-status').textContent = 'Saved';
                setTimeout(() => {
                    document.getElementById('daily-save-status').textContent = 'Auto-saved';
                }, 2000);
            } catch (e) {
                document.getElementById('daily-save-status').textContent = 'Error saving';
            }
        }

        function updateWordCount() {
            const content = document.getElementById('daily-content').textContent;
            const words = content.trim().split(/\\s+/).filter(w => w).length;
            document.getElementById('daily-word-count').textContent = words + ' words';
        }

        // Calendar
        function renderCalendar() {
            const cal = document.getElementById('calendar-mini');
            const today = new Date();
            const year = today.getFullYear();
            const month = today.getMonth();
            const firstDay = new Date(year, month, 1);
            const lastDay = new Date(year, month + 1, 0);

            let html = '';
            ['S', 'M', 'T', 'W', 'T', 'F', 'S'].forEach(d => {
                html += `<div class="calendar-day" style="color: var(--text-muted); font-weight: 600;">${d}</div>`;
            });

            // Empty cells before first day
            for (let i = 0; i < firstDay.getDay(); i++) {
                html += '<div class="calendar-day"></div>';
            }

            // Days
            for (let d = 1; d <= lastDay.getDate(); d++) {
                const isToday = d === today.getDate();
                const dateObj = new Date(year, month, d);
                html += `<div class="calendar-day ${isToday ? 'today' : ''}"
                             onclick="goToDate('${dateObj.toISOString().split('T')[0]}')">${d}</div>`;
            }

            cal.innerHTML = html;
        }

        function goToDate(dateStr) {
            currentDailyDate = new Date(dateStr + 'T12:00:00');
            updateDailyView();
        }

        // Entries
        async function loadEntries() {
            const typeFilter = document.getElementById('filter-type')?.value || '';
            const container = document.getElementById('entries-list');
            container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

            try {
                let url = '/entries?limit=50';
                if (typeFilter) url += `&type=${typeFilter}`;
                const res = await fetch(url);
                const data = await res.json();
                entries = data.entries;

                if (entries.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">📝</div>
                            <div class="empty-state-title">No entries yet</div>
                            <div>Start by adding your first thought or note</div>
                        </div>`;
                    return;
                }

                container.innerHTML = entries.map(entry => `
                    <div class="entry-card" onclick="showEntry('${entry.id}')">
                        <div class="entry-header">
                            <span class="entry-type">${entry.type}</span>
                            <span class="entry-date">${formatDate(entry.created_at)}</span>
                        </div>
                        <div class="entry-content">${escapeHtml(entry.content)}</div>
                        ${entry.tags.length ? `<div class="entry-tags">${entry.tags.map(t => `<span class="tag">#${t}</span>`).join('')}</div>` : ''}
                    </div>
                `).join('');
            } catch (e) {
                container.innerHTML = '<div class="empty-state"><div>Failed to load entries</div></div>';
            }
        }

        async function showEntry(id) {
            try {
                const res = await fetch(`/entries/${id}`);
                const entry = await res.json();

                document.getElementById('entry-modal-title').textContent = entry.title || 'Entry';
                document.getElementById('entry-modal-body').innerHTML = `
                    <div style="margin-bottom: 16px;">
                        <span class="entry-type">${entry.type}</span>
                        <span style="color: var(--text-muted); margin-left: 8px;">${formatDate(entry.created_at)}</span>
                    </div>
                    <div style="line-height: 1.8; color: var(--text-secondary);">${escapeHtml(entry.content)}</div>
                    ${entry.tags.length ? `<div class="entry-tags" style="margin-top: 20px;">${entry.tags.map(t => `<span class="tag">#${t}</span>`).join('')}</div>` : ''}
                    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border);">
                        <button class="btn btn-secondary" onclick="deleteEntry('${id}')" style="color: var(--error);">
                            Delete Entry
                        </button>
                    </div>
                `;
                document.getElementById('entry-modal').classList.add('active');
            } catch (e) {
                showToast('Failed to load entry', 'error');
            }
        }

        async function deleteEntry(id) {
            if (!confirm('Are you sure you want to delete this entry?')) return;
            try {
                await fetch(`/entries/${id}`, { method: 'DELETE' });
                showToast('Entry deleted', 'success');
                closeEntryModalBtn();
                loadEntries();
                loadStats();
            } catch (e) {
                showToast('Failed to delete', 'error');
            }
        }

        function closeEntryModal(e) {
            if (e.target === document.getElementById('entry-modal')) {
                document.getElementById('entry-modal').classList.remove('active');
            }
        }

        function closeEntryModalBtn() {
            document.getElementById('entry-modal').classList.remove('active');
        }

        // Graph
        async function renderGraph() {
            const container = document.getElementById('graph-svg');
            const width = container.clientWidth;
            const height = container.clientHeight;

            // Clear previous
            container.innerHTML = '';

            try {
                const res = await fetch('/entries?limit=100');
                const data = await res.json();

                if (data.entries.length === 0) {
                    return;
                }

                // Create nodes and links
                const nodes = data.entries.map((e, i) => ({
                    id: e.id,
                    title: e.title || e.content.substring(0, 30) + '...',
                    type: e.type,
                    tags: e.tags
                }));

                // Create links based on shared tags
                const links = [];
                for (let i = 0; i < nodes.length; i++) {
                    for (let j = i + 1; j < nodes.length; j++) {
                        const sharedTags = nodes[i].tags.filter(t => nodes[j].tags.includes(t));
                        if (sharedTags.length > 0) {
                            links.push({ source: nodes[i].id, target: nodes[j].id, strength: sharedTags.length });
                        }
                    }
                }

                const svg = d3.select('#graph-svg')
                    .attr('width', width)
                    .attr('height', height);

                const g = svg.append('g');

                // Zoom
                const zoom = d3.zoom()
                    .scaleExtent([0.1, 4])
                    .on('zoom', (event) => g.attr('transform', event.transform));

                svg.call(zoom);

                // Force simulation
                const simulation = d3.forceSimulation(nodes)
                    .force('link', d3.forceLink(links).id(d => d.id).distance(100))
                    .force('charge', d3.forceManyBody().strength(-200))
                    .force('center', d3.forceCenter(width / 2, height / 2));

                // Links
                const link = g.append('g')
                    .selectAll('line')
                    .data(links)
                    .join('line')
                    .attr('class', 'link')
                    .attr('stroke-width', d => d.strength);

                // Nodes
                const node = g.append('g')
                    .selectAll('g')
                    .data(nodes)
                    .join('g')
                    .attr('class', 'node')
                    .call(d3.drag()
                        .on('start', dragstarted)
                        .on('drag', dragged)
                        .on('end', dragended));

                const colors = {
                    thought: '#6366f1',
                    note: '#22c55e',
                    idea: '#f59e0b',
                    meeting: '#ec4899',
                    task: '#06b6d4'
                };

                node.append('circle')
                    .attr('r', 8)
                    .attr('fill', d => colors[d.type] || '#6366f1');

                node.append('text')
                    .attr('dx', 12)
                    .attr('dy', 4)
                    .text(d => d.title);

                node.on('click', (event, d) => showEntry(d.id));

                simulation.on('tick', () => {
                    link
                        .attr('x1', d => d.source.x)
                        .attr('y1', d => d.source.y)
                        .attr('x2', d => d.target.x)
                        .attr('y2', d => d.target.y);

                    node.attr('transform', d => `translate(${d.x},${d.y})`);
                });

                function dragstarted(event) {
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    event.subject.fx = event.subject.x;
                    event.subject.fy = event.subject.y;
                }

                function dragged(event) {
                    event.subject.fx = event.x;
                    event.subject.fy = event.y;
                }

                function dragended(event) {
                    if (!event.active) simulation.alphaTarget(0);
                    event.subject.fx = null;
                    event.subject.fy = null;
                }

            } catch (e) {
                console.error('Graph error:', e);
            }
        }

        function resetGraph() {
            renderGraph();
        }

        // Ask
        async function askQuestion() {
            const question = document.getElementById('ask-input').value.trim();
            if (!question) {
                showToast('Please enter a question', 'error');
                return;
            }

            document.getElementById('ask-response-area').style.display = 'block';
            document.getElementById('ask-answer').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            document.getElementById('ask-meta').textContent = 'Thinking...';
            document.getElementById('ask-sources-area').style.display = 'none';

            try {
                const res = await fetch('/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question })
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Failed to get answer');
                }

                const data = await res.json();

                document.getElementById('ask-answer').innerHTML = formatResponse(data.answer);
                document.getElementById('ask-meta').textContent =
                    `${data.context_used} sources · ${data.tokens_used} tokens · ${Math.round(data.response_time_ms)}ms`;

                if (data.sources && data.sources.length > 0) {
                    document.getElementById('ask-sources-area').style.display = 'block';
                    document.getElementById('ask-sources').innerHTML = data.sources.map(s => `
                        <div class="source-item">
                            <span class="entry-type" style="font-size: 10px;">${s.type}</span>
                            <span style="margin-left: 8px;">${escapeHtml(s.snippet)}</span>
                        </div>
                    `).join('');
                }
            } catch (e) {
                document.getElementById('ask-answer').innerHTML =
                    `<div style="color: var(--error);">Error: ${e.message}</div>`;
                document.getElementById('ask-meta').textContent = '';
            }
        }

        // Briefing
        async function showBriefing(type) {
            switchView('ask');
            document.getElementById('ask-response-area').style.display = 'block';
            document.getElementById('ask-answer').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            document.getElementById('ask-meta').textContent = `Generating ${type} briefing...`;
            document.getElementById('ask-sources-area').style.display = 'none';

            try {
                const res = await fetch(`/briefing/${type}`);
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Failed to generate briefing');
                }
                const data = await res.json();

                document.getElementById('ask-answer').innerHTML = formatResponse(data.briefing);
                document.getElementById('ask-meta').textContent = type === 'daily' ? 'Daily Briefing' : 'Weekly Review';
            } catch (e) {
                document.getElementById('ask-answer').innerHTML =
                    `<div style="color: var(--error);">Error: ${e.message}</div>`;
            }
        }

        // Stats
        async function loadStats() {
            try {
                const res = await fetch('/stats');
                const data = await res.json();
                document.getElementById('stat-entries').textContent = data.entries || 0;
                document.getElementById('stat-week').textContent = data.week || 0;
                document.getElementById('stat-streak').textContent = data.streak || 0;
            } catch (e) {
                console.error('Failed to load stats');
            }
        }

        // Quick Add
        function openQuickAdd() {
            document.getElementById('quick-add-modal').classList.add('active');
            document.getElementById('quick-add-content').focus();
        }

        function closeQuickAdd(e) {
            if (e.target === document.getElementById('quick-add-modal')) {
                closeQuickAddModal();
            }
        }

        function closeQuickAddModal() {
            document.getElementById('quick-add-modal').classList.remove('active');
            document.getElementById('quick-add-content').value = '';
            document.getElementById('quick-add-tags').value = '';
        }

        async function submitQuickAdd() {
            const content = document.getElementById('quick-add-content').value.trim();
            const tagsInput = document.getElementById('quick-add-tags').value.trim();
            const type = document.getElementById('quick-add-type').value;

            if (!content) {
                showToast('Please enter some content', 'error');
                return;
            }

            const tags = tagsInput ? tagsInput.split(',').map(t => t.trim()).filter(t => t) : [];

            try {
                const res = await fetch('/ingest/text', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content, tags, type })
                });

                if (!res.ok) throw new Error('Failed to save');

                showToast('Entry saved!', 'success');
                closeQuickAddModal();
                loadEntries();
                loadStats();
            } catch (e) {
                showToast('Failed to save entry', 'error');
            }
        }

        // Command Palette
        function openCommandPalette() {
            document.getElementById('command-palette').classList.add('active');
            document.getElementById('command-input').value = '';
            document.getElementById('command-input').focus();
            filterCommands('');
        }

        function closeCommandPalette(e) {
            if (e.target === document.getElementById('command-palette')) {
                document.getElementById('command-palette').classList.remove('active');
            }
        }

        function filterCommands(query) {
            const filtered = commands.filter(c =>
                c.title.toLowerCase().includes(query.toLowerCase()) ||
                c.desc.toLowerCase().includes(query.toLowerCase())
            );

            commandIndex = 0;

            document.getElementById('command-results').innerHTML = filtered.map((c, i) => `
                <div class="command-item ${i === 0 ? 'selected' : ''}" onclick="executeCommand(${commands.indexOf(c)})">
                    <span class="command-item-icon">${c.icon}</span>
                    <div class="command-item-text">
                        <div class="command-item-title">${c.title}</div>
                        <div class="command-item-desc">${c.desc}</div>
                    </div>
                </div>
            `).join('');
        }

        function executeCommand(index) {
            commands[index].action();
            document.getElementById('command-palette').classList.remove('active');
        }

        // Toast
        function showToast(message, type = 'info') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.innerHTML = `<span>${message}</span>`;
            container.appendChild(toast);

            setTimeout(() => toast.remove(), 3000);
        }

        // Keyboard Shortcuts
        function setupKeyboardShortcuts() {
            document.addEventListener('keydown', (e) => {
                // Command palette
                if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                    e.preventDefault();
                    openCommandPalette();
                }

                // View shortcuts
                if ((e.metaKey || e.ctrlKey) && !e.shiftKey) {
                    if (e.key === '1') { e.preventDefault(); switchView('daily'); }
                    if (e.key === '2') { e.preventDefault(); switchView('entries'); }
                    if (e.key === '3') { e.preventDefault(); switchView('graph'); }
                    if (e.key === '4') { e.preventDefault(); switchView('ask'); }
                }

                // Quick add
                if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
                    e.preventDefault();
                    openQuickAdd();
                }

                // Close modals on Escape
                if (e.key === 'Escape') {
                    document.getElementById('command-palette').classList.remove('active');
                    document.getElementById('quick-add-modal').classList.remove('active');
                    document.getElementById('entry-modal').classList.remove('active');
                }

                // Submit ask on Cmd+Enter
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                    if (document.activeElement === document.getElementById('ask-input')) {
                        e.preventDefault();
                        askQuestion();
                    }
                }
            });
        }

        // Utilities
        function formatDate(dateStr) {
            const date = new Date(dateStr);
            const now = new Date();
            const diff = now - date;

            if (diff < 60000) return 'Just now';
            if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
            if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
            if (diff < 604800000) return Math.floor(diff / 86400000) + 'd ago';

            return date.toLocaleDateString();
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function formatResponse(text) {
            return text
                .replace(/\\n/g, '<br>')
                .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
                .replace(/\\*(.+?)\\*/g, '<em>$1</em>')
                .replace(/`(.+?)`/g, '<code style="background: var(--bg-tertiary); padding: 2px 6px; border-radius: 4px;">$1</code>');
        }

        // Listen for daily content changes
        document.getElementById('daily-content').addEventListener('input', () => {
            updateWordCount();
        });
    </script>
</body>
</html>
"""
