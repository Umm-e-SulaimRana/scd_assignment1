import { useState } from 'react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { SubmitView } from './views/SubmitView'
import { DashboardView } from './views/DashboardView'
import { StatsView } from './views/StatsView'
import { config } from './config'

type Tab = 'submit' | 'dashboard' | 'stats'

const TABS: { id: Tab; label: string }[] = [
  { id: 'submit', label: 'Report' },
  { id: 'dashboard', label: 'Operations' },
  { id: 'stats', label: 'Statistics' },
]

export function App() {
  const [tab, setTab] = useState<Tab>('submit')

  return (
    <div className="shell">
      <header>
        <h1>CivicPulse</h1>
        <nav>
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={tab === t.id ? 'tab tab-active' : 'tab'}
              aria-current={tab === t.id ? 'page' : undefined}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {/* One boundary per view: a crash in Operations must not take Report down with it. */}
        {tab === 'submit' && (
          <ErrorBoundary label="the report form">
            <SubmitView />
          </ErrorBoundary>
        )}
        {tab === 'dashboard' && (
          <ErrorBoundary label="the operations dashboard">
            <DashboardView />
          </ErrorBoundary>
        )}
        {tab === 'stats' && (
          <ErrorBoundary label="the statistics view">
            <StatsView />
          </ErrorBoundary>
        )}
      </main>

      <footer className="muted">
        API base <span className="mono">{config.apiBase}</span> · resolved at runtime, never baked
        into the build
      </footer>
    </div>
  )
}
