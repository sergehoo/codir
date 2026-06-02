// Liste des décisions extraites par l'IA — checkboxes + bouton "Créer les décisions sélectionnées".
import { Calendar, CheckCircle2, FileCheck, Loader2, User } from 'lucide-react'
import { useMemo, useState } from 'react'

import { cn } from '@/utils/cn'

import type { RecordingAIExtraction } from '../types/recording.types'

interface Props {
  extractions: RecordingAIExtraction[]
  onCreate: (extractionIds: string[]) => Promise<void> | void
  isCreating?: boolean
}

const PRIORITY_LABEL: Record<string, string> = {
  low: 'Faible', medium: 'Moyenne', high: 'Élevée', critical: 'Critique',
}
const PRIORITY_COLOR: Record<string, string> = {
  low: 'bg-fg/10 text-fg-muted',
  medium: 'bg-blue-500/15 text-blue-400',
  high: 'bg-amber-500/15 text-amber-400',
  critical: 'bg-red-500/15 text-red-400',
}

export function ExtractedDecisionsPanel({ extractions, onCreate, isCreating }: Props) {
  const drafts = useMemo(
    () => extractions.filter((e) => e.extraction_type === 'decision' && e.status === 'draft'),
    [extractions],
  )
  const created = useMemo(
    () => extractions.filter((e) => e.extraction_type === 'decision' && e.status === 'pushed'),
    [extractions],
  )

  const [selected, setSelected] = useState<Set<string>>(new Set())
  const toggle = (id: string) => {
    setSelected((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id); else n.add(id)
      return n
    })
  }
  const allSelected = drafts.length > 0 && selected.size === drafts.length
  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(drafts.map((d) => d.id)))
  }

  const handleCreate = async () => {
    if (selected.size === 0) return
    await onCreate(Array.from(selected))
    setSelected(new Set())
  }

  if (drafts.length === 0 && created.length === 0) {
    return (
      <div className="p-5 rounded-xl border border-border bg-bg-elevated text-sm text-fg-muted text-center">
        Aucune décision détectée dans cet enregistrement.
      </div>
    )
  }

  return (
    <div className="p-5 rounded-xl border border-border bg-bg-elevated space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <FileCheck size={16} className="text-copper-500" />
          Décisions proposées par l'IA
          <span className="text-2xs uppercase tracking-wider text-fg-subtle ml-1">
            {drafts.length} brouillon{drafts.length > 1 ? 's' : ''}
          </span>
        </h3>
        {drafts.length > 0 && (
          <button
            type="button"
            onClick={toggleAll}
            className="text-xs text-copper-400 hover:underline"
          >
            {allSelected ? 'Tout désélectionner' : 'Tout sélectionner'}
          </button>
        )}
      </div>

      <div className="space-y-3">
        {drafts.map((ext) => {
          const p = ext.raw_payload || {}
          const isSel = selected.has(ext.id)
          return (
            <label
              key={ext.id}
              className={cn(
                'block p-3 rounded-lg border cursor-pointer transition',
                isSel
                  ? 'border-copper-500/50 bg-copper-500/10'
                  : 'border-border bg-bg-base hover:bg-fg/5',
              )}
            >
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 rounded border-border accent-copper-500"
                  checked={isSel}
                  onChange={() => toggle(ext.id)}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold">{p.title || 'Décision sans titre'}</span>
                    {p.priority && (
                      <span className={cn(
                        'text-2xs uppercase tracking-wider px-1.5 py-0.5 rounded',
                        PRIORITY_COLOR[p.priority] || 'bg-fg/10 text-fg-muted',
                      )}>
                        {PRIORITY_LABEL[p.priority] || p.priority}
                      </span>
                    )}
                  </div>
                  {p.description && (
                    <p className="text-xs text-fg-muted mt-1">{p.description}</p>
                  )}
                  <div className="flex items-center gap-4 mt-2 text-2xs text-fg-subtle">
                    {p.responsible_suggested && (
                      <span className="inline-flex items-center gap-1">
                        <User size={10} /> {p.responsible_suggested}
                      </span>
                    )}
                    {p.deadline_suggested && (
                      <span className="inline-flex items-center gap-1">
                        <Calendar size={10} /> {p.deadline_suggested}
                      </span>
                    )}
                  </div>
                  {p.quote && (
                    <blockquote className="mt-2 pl-2 border-l-2 border-fg/20 text-2xs italic text-fg-muted">
                      « {p.quote} »
                    </blockquote>
                  )}
                </div>
              </div>
            </label>
          )
        })}
      </div>

      {drafts.length > 0 && (
        <button
          type="button"
          onClick={handleCreate}
          disabled={selected.size === 0 || isCreating}
          className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-copper-500 hover:bg-copper-600 disabled:bg-fg/10 disabled:text-fg-muted disabled:cursor-not-allowed text-white text-sm font-semibold transition"
        >
          {isCreating
            ? <><Loader2 size={14} className="animate-spin" /> Création…</>
            : <><CheckCircle2 size={14} /> Créer {selected.size} décision{selected.size > 1 ? 's' : ''}</>}
        </button>
      )}

      {created.length > 0 && (
        <div className="pt-3 border-t border-border space-y-1.5">
          <div className="text-2xs uppercase tracking-wider text-fg-subtle">
            Décisions déjà créées
          </div>
          {created.map((ext) => (
            <div key={ext.id} className="text-xs text-fg-muted flex items-center gap-1.5">
              <CheckCircle2 size={12} className="text-emerald-400" />
              {ext.raw_payload?.title || 'Décision'} →&nbsp;
              <a
                href={`/decisions/${ext.created_decision}`}
                className="text-copper-400 hover:underline"
              >
                voir
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
