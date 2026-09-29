/**
 * Presentation-only. Colour is a function of the value the server sent; the
 * component has no opinion about what a priority means or when one applies.
 */
import type { Category, Priority, Status } from '../api/types'

const STATUS_LABEL: Record<Status, string> = {
  open: 'Open',
  in_progress: 'In progress',
  resolved: 'Resolved',
  rejected: 'Rejected',
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <span className={`badge badge-priority badge-${priority}`} data-testid="priority-badge">
      {priority}
    </span>
  )
}

export function CategoryBadge({ category }: { category: Category }) {
  return (
    <span className="badge badge-category" data-testid="category-badge">
      {category}
    </span>
  )
}

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`badge badge-status badge-${status}`} data-testid="status-badge">
      {STATUS_LABEL[status] ?? status}
    </span>
  )
}

export function CacheBadge({ cache }: { cache: 'HIT' | 'MISS' | 'UNKNOWN' }) {
  return (
    <span className={`badge badge-cache badge-cache-${cache.toLowerCase()}`} data-testid="cache-badge">
      X-Cache: {cache}
    </span>
  )
}
