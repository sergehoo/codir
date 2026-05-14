import { cn } from '@/utils/cn'

const MAP: Record<string, { label: string; cls: string }> = {
  // Meeting
  draft:        { label: 'Brouillon',  cls: 'chip-quiet' },
  scheduled:    { label: 'Planifiée',  cls: 'chip-info' },
  in_progress:  { label: 'En cours',   cls: 'chip-warning' },
  completed:    { label: 'Terminée',   cls: 'chip-success' },
  cancelled:    { label: 'Annulée',    cls: 'chip-danger' },
  // Agenda items
  pending:      { label: 'À traiter',  cls: 'chip-quiet' },
  discussed:    { label: 'Traité',     cls: 'chip-success' },
  postponed:    { label: 'Reporté',    cls: 'chip-warning' },
  // Decision
  proposed:     { label: 'Proposée',   cls: 'chip-quiet' },
  approved:     { label: 'Validée',    cls: 'chip-info' },
  // ActionTask
  todo:         { label: 'À faire',    cls: 'chip-quiet' },
  done:         { label: 'Fait',       cls: 'chip-success' },
  blocked:      { label: 'Bloqué',     cls: 'chip-danger' },
  overdue:      { label: 'En retard',  cls: 'chip-danger' },
  // ActionPlan
  open:         { label: 'Ouvert',     cls: 'chip-quiet' },
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const m = MAP[status] ?? { label: status, cls: 'chip-quiet' }
  return <span className={cn(m.cls, className)}>{m.label}</span>
}
