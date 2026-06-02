// Éditeur léger du transcript final (édition locale → save vers backend).
// V1 = édition par segment. Pour V2 on pourra introduire Tiptap.
import { Check, Edit3, X } from 'lucide-react'
import { useState } from 'react'

import type { TranscriptSegmentFinal } from '../types/recording.types'

interface Props {
  segments: TranscriptSegmentFinal[]
  onSave: (segments: TranscriptSegmentFinal[]) => Promise<void> | void
  isSaving?: boolean
}

export function FinalTranscriptEditor({ segments, onSave, isSaving }: Props) {
  const [draft, setDraft] = useState<TranscriptSegmentFinal[]>(segments)
  const [editingIdx, setEditingIdx] = useState<number | null>(null)

  const handleSave = async () => {
    await onSave(draft)
    setEditingIdx(null)
  }

  return (
    <div className="space-y-2">
      {draft.map((seg, idx) => {
        const isEditing = editingIdx === idx
        return (
          <div key={idx} className="p-3 rounded-lg border border-border bg-bg-elevated">
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <span className="text-xs font-medium text-copper-400">{seg.speaker}</span>
              <div className="flex items-center gap-1">
                {isEditing ? (
                  <>
                    <button
                      type="button"
                      onClick={handleSave}
                      disabled={isSaving}
                      className="p-1 rounded hover:bg-fg/10 text-emerald-400"
                      aria-label="Enregistrer"
                    >
                      <Check size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => { setEditingIdx(null); setDraft(segments) }}
                      className="p-1 rounded hover:bg-fg/10 text-fg-muted"
                      aria-label="Annuler"
                    >
                      <X size={14} />
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => setEditingIdx(idx)}
                    className="p-1 rounded hover:bg-fg/10 text-fg-muted"
                    aria-label="Éditer"
                  >
                    <Edit3 size={12} />
                  </button>
                )}
              </div>
            </div>
            {isEditing ? (
              <textarea
                value={seg.text}
                onChange={(e) => {
                  const v = e.target.value
                  setDraft((prev) => prev.map((s, i) => i === idx ? { ...s, text: v } : s))
                }}
                rows={3}
                className="w-full rounded border border-border bg-bg-base p-2 text-sm focus:outline-none focus:border-copper-500/40"
              />
            ) : (
              <div className="text-sm text-fg whitespace-pre-wrap">{seg.text}</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
