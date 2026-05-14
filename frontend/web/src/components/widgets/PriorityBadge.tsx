const MAP = {
  low:      { label: 'Faible',   cls: 'chip-quiet'   },
  medium:   { label: 'Moyenne',  cls: 'chip-info'    },
  high:     { label: 'Élevée',   cls: 'chip-warning' },
  critical: { label: 'Critique', cls: 'chip-danger'  },
} as const

export function PriorityBadge({ priority }: { priority: keyof typeof MAP }) {
  const m = MAP[priority] ?? MAP.medium
  return <span className={m.cls}>{m.label}</span>
}
