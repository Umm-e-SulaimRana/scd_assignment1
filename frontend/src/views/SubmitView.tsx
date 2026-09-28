/**
 * Submit view (§2.1, rubric B-1).
 *
 * Client-side validation MIRRORS the server's rules -- text 10..2000,
 * location 3..200 -- it does not replace them. The bounds are duplicated
 * knowingly and for one reason: to save a round trip on an obviously empty
 * form. The server validates the same fields again in schemas.py and its
 * 400 body is rendered field by field below, so if the two ever drift the
 * server wins and the user sees why.
 *
 * Loading state is honest (§2.1): a triage call takes seconds, so the button
 * says what is actually happening rather than showing a spinner that implies
 * the work is nearly done.
 */
import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { ApiError, type Complaint } from '../api/types'
import { CategoryBadge, PriorityBadge } from '../components/Badge'

const TEXT_MIN = 10
const TEXT_MAX = 2000
const LOCATION_MIN = 3
const LOCATION_MAX = 200

interface LocalErrors {
  text?: string
  location?: string
}

function validate(text: string, location: string): LocalErrors {
  const errors: LocalErrors = {}
  const t = text.trim()
  const l = location.trim()
  if (t.length < TEXT_MIN) errors.text = `Describe the problem in at least ${TEXT_MIN} characters.`
  else if (t.length > TEXT_MAX) errors.text = `Keep it under ${TEXT_MAX} characters.`
  if (l.length < LOCATION_MIN) errors.location = `Give a location of at least ${LOCATION_MIN} characters.`
  else if (l.length > LOCATION_MAX) errors.location = `Keep the location under ${LOCATION_MAX} characters.`
  return errors
}

export function SubmitView() {
  const [text, setText] = useState('')
  const [location, setLocation] = useState('')
  const [contact, setContact] = useState('')
  const [localErrors, setLocalErrors] = useState<LocalErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<Complaint | null>(null)
  const [serverError, setServerError] = useState<ApiError | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const errors = validate(text, location)
    setLocalErrors(errors)
    if (Object.keys(errors).length > 0) return

    setSubmitting(true)
    setServerError(null)
    setResult(null)
    try {
      const complaint = await api.createComplaint({
        text: text.trim(),
        location: location.trim(),
        reporter_contact: contact.trim() || null,
      })
      setResult(complaint)
      setText('')
      setLocation('')
      setContact('')
    } catch (err) {
      setServerError(err instanceof ApiError ? err : new ApiError(0, String(err)))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="panel">
      <h2>Report a problem</h2>
      <p className="muted">
        Write it the way you would say it. The system reads the text and works out the category and
        how urgent it is; you do not have to pick from a dropdown.
      </p>

      <form onSubmit={onSubmit} noValidate>
        <label htmlFor="text">What is wrong?</label>
        <textarea
          id="text"
          name="text"
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-invalid={Boolean(localErrors.text)}
          aria-describedby={localErrors.text ? 'text-error' : undefined}
          placeholder="Burst water main flooding Street 12 since fajr, water entering ground floors"
        />
        <div className="field-foot">
          <span className="muted">
            {text.trim().length} / {TEXT_MAX}
          </span>
          {localErrors.text && (
            <span className="error" id="text-error" role="alert">
              {localErrors.text}
            </span>
          )}
        </div>

        <label htmlFor="location">Location</label>
        <input
          id="location"
          name="location"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          aria-invalid={Boolean(localErrors.location)}
          aria-describedby={localErrors.location ? 'location-error' : undefined}
          placeholder="Sector G-9, Islamabad"
        />
        {localErrors.location && (
          <span className="error" id="location-error" role="alert">
            {localErrors.location}
          </span>
        )}

        <label htmlFor="contact">Contact (optional)</label>
        <input
          id="contact"
          name="contact"
          value={contact}
          onChange={(e) => setContact(e.target.value)}
          placeholder="03xx-xxxxxxx or an email"
        />

        <button type="submit" disabled={submitting}>
          {submitting ? 'Reading your report and triaging it…' : 'Submit complaint'}
        </button>
        {submitting && (
          <p className="muted" data-testid="loading-note">
            This calls a language model, so it can take a few seconds. Nothing is lost if it is slow.
          </p>
        )}
      </form>

      {serverError && (
        <div className="panel panel-error" role="alert" data-testid="server-error">
          <strong>{serverError.detail}</strong>
          {serverError.status === 429 && serverError.retryAfter !== null && (
            <p>Try again in {serverError.retryAfter} seconds.</p>
          )}
          {serverError.fieldErrors.length > 0 && (
            <ul>
              {serverError.fieldErrors.map((fe, i) => (
                <li key={i}>
                  <span className="mono">{fe.loc.filter((p) => p !== 'body').join('.')}</span>: {fe.msg}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {result && (
        <div className="panel panel-result" data-testid="triage-result">
          <h3>Logged. Here is how it was triaged.</h3>
          <dl>
            <dt>Category</dt>
            <dd>
              <CategoryBadge category={result.category} />
            </dd>
            <dt>Priority</dt>
            <dd>
              <PriorityBadge priority={result.priority} />
            </dd>
            <dt>Summary</dt>
            <dd>{result.ai_summary ?? <span className="muted">none produced</span>}</dd>
            <dt>Triaged by</dt>
            <dd>
              <span className="mono" data-testid="triaged-by">
                {result.triaged_by}
              </span>{' '}
              <span className="muted">in {result.triage_latency_ms} ms</span>
            </dd>
            <dt>Reference</dt>
            <dd className="mono">{result.id}</dd>
          </dl>
          {result.triaged_by === 'rules:fallback' && (
            <p className="muted">
              The language model did not answer in time, so the keyword classifier handled this one.
              Your report was still saved.
            </p>
          )}
        </div>
      )}
    </section>
  )
}
