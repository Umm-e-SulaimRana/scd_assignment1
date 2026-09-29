/**
 * Required by §2.1. A render-time exception anywhere below this boundary
 * produces this panel instead of a white screen, and the operator keeps the
 * ability to reload one view rather than the whole app.
 *
 * Class component on purpose: componentDidCatch has no hook equivalent.
 */
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Named so the panel can say which view died. */
  label?: string
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Goes to the browser console, which is where a frontend's logs live.
    // The backend's structured JSON logging (middleware.py) covers the
    // server side; this is the client half of the same idea.
    console.error('[civicpulse] render error', { error, componentStack: info.componentStack })
  }

  private reset = () => this.setState({ error: null })

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="panel panel-error" role="alert">
        <h2>Something broke while rendering {this.props.label ?? 'this view'}</h2>
        <p className="mono">{error.message}</p>
        <button type="button" onClick={this.reset}>
          Try again
        </button>
      </div>
    )
  }
}
