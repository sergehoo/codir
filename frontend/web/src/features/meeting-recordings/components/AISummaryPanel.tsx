// Affichage du résumé Markdown généré par Claude / DeepSeek.
// Pas de lib markdown lourde — rendu Markdown léger en pure CSS via classes.
import { Check, Download, Edit3, FileText, Loader2, RefreshCw, Sparkles, X } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { cn } from '@/utils/cn'

import { recordingsApi } from '../api'

interface Props {
  summary: string
  minutes?: string
  recordingId: string
  onRegenerate?: () => void
  onMinutesUpdated?: (newMinutes: string) => void
  isRegenerating?: boolean
  /** L'utilisateur peut-il éditer (chair/secretary/owner). Default true. */
  editable?: boolean
}

/** Mini-renderer Markdown : titres ##, listes -, gras **bold**. */
function renderMd(md: string): React.ReactNode {
  if (!md) return null
  const lines = md.split('\n')
  const out: React.ReactNode[] = []
  let listBuffer: string[] = []
  const flushList = () => {
    if (listBuffer.length === 0) return
    out.push(
      <ul key={`ul-${out.length}`} className="list-disc pl-5 space-y-1 my-2">
        {listBuffer.map((item, i) => (
          <li key={i} className="text-sm text-fg leading-relaxed">
            <span dangerouslySetInnerHTML={{ __html: bold(item) }} />
          </li>
        ))}
      </ul>,
    )
    listBuffer = []
  }
  for (const raw of lines) {
    const line = raw.trim()
    if (!line) { flushList(); continue }
    if (line.startsWith('## ')) {
      flushList()
      out.push(
        <h3 key={`h-${out.length}`} className="text-sm font-semibold mt-4 mb-2 text-copper-400 uppercase tracking-wider">
          {line.slice(3)}
        </h3>,
      )
    } else if (line.startsWith('### ')) {
      flushList()
      out.push(
        <h4 key={`h4-${out.length}`} className="text-xs font-semibold mt-3 mb-1.5">
          {line.slice(4)}
        </h4>,
      )
    } else if (/^[-*]\s+/.test(line)) {
      listBuffer.push(line.replace(/^[-*]\s+/, ''))
    } else {
      flushList()
      out.push(
        <p key={`p-${out.length}`} className="text-sm text-fg leading-relaxed my-2">
          <span dangerouslySetInnerHTML={{ __html: bold(line) }} />
        </p>,
      )
    }
  }
  flushList()
  return out
}

function bold(s: string): string {
  // Échappe HTML basique puis applique **gras**
  const escaped = s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

export function AISummaryPanel({
  summary, minutes, recordingId,
  onRegenerate, onMinutesUpdated,
  isRegenerating, editable = true,
}: Props) {
  const content = minutes && minutes.length > summary.length ? minutes : summary

  // ─── Mode édition ─────────────────────────────────────────
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState<'docx' | 'pdf' | null>(null)

  const startEditing = () => {
    setDraft(content)
    setEditing(true)
  }
  const cancelEditing = () => {
    setEditing(false)
    setDraft('')
  }
  const saveEdit = async () => {
    setSaving(true)
    try {
      // On édite `ai_minutes` (le format complet). Le `summary` court est dérivé.
      await recordingsApi.updateMinutes(recordingId, { ai_minutes: draft })
      toast.success('Compte rendu mis à jour')
      onMinutesUpdated?.(draft)
      setEditing(false)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Sauvegarde refusée')
    } finally {
      setSaving(false)
    }
  }

  // ─── Téléchargement Word/PDF ──────────────────────────────
  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 500)
  }

  const exportDocx = async () => {
    setExporting('docx')
    try {
      const blob = await recordingsApi.exportDocxBlob(recordingId)
      downloadBlob(blob, `CR_reunion_${recordingId.slice(0, 8)}.docx`)
      toast.success('Word téléchargé')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Export Word KO')
    } finally {
      setExporting(null)
    }
  }
  const exportPdf = async () => {
    setExporting('pdf')
    try {
      const blob = await recordingsApi.exportPdfBlob(recordingId)
      downloadBlob(blob, `CR_reunion_${recordingId.slice(0, 8)}.pdf`)
      toast.success('PDF téléchargé')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Export PDF KO')
    } finally {
      setExporting(null)
    }
  }

  // ─── Rendu ────────────────────────────────────────────────
  return (
    <div className="p-5 rounded-xl border border-border bg-bg-elevated">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-copper-500" />
          <span className="text-sm font-semibold">Compte rendu IA</span>
        </div>
        {!editing && (
          <div className="flex items-center gap-1.5 flex-wrap">
            {editable && (
              <button
                type="button"
                onClick={startEditing}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-fg-muted hover:text-fg hover:bg-fg/5 transition"
                title="Modifier le compte rendu manuellement"
              >
                <Edit3 size={12} /> Modifier
              </button>
            )}
            {onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                disabled={isRegenerating}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-fg-muted hover:text-fg hover:bg-fg/5 transition disabled:opacity-50"
                title="Régénérer le résumé via Claude/DeepSeek"
              >
                <RefreshCw size={12} className={cn(isRegenerating && 'animate-spin')} />
                Régénérer
              </button>
            )}
            <span className="w-px h-4 bg-border" />
            <button
              type="button"
              onClick={exportDocx}
              disabled={!content || exporting !== null}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-bg-base border border-border hover:bg-fg/5 text-fg transition disabled:opacity-50"
              title="Télécharger le compte rendu au format Word"
            >
              {exporting === 'docx'
                ? <Loader2 size={12} className="animate-spin" />
                : <FileText size={12} />}
              Word
            </button>
            <button
              type="button"
              onClick={exportPdf}
              disabled={!content || exporting !== null}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-copper-500 hover:bg-copper-600 text-white transition disabled:opacity-50"
              title="Télécharger le compte rendu au format PDF"
            >
              {exporting === 'pdf'
                ? <Loader2 size={12} className="animate-spin" />
                : <Download size={12} />}
              PDF
            </button>
          </div>
        )}
        {editing && (
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={cancelEditing}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs text-fg-muted hover:text-fg hover:bg-fg/5 transition"
            >
              <X size={12} /> Annuler
            </button>
            <button
              type="button"
              onClick={saveEdit}
              disabled={saving || draft.trim() === content.trim()}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs bg-emerald-500 hover:bg-emerald-600 text-white font-semibold transition disabled:opacity-50"
            >
              {saving
                ? <><Loader2 size={12} className="animate-spin" /> Sauvegarde…</>
                : <><Check size={12} /> Enregistrer</>}
            </button>
          </div>
        )}
      </div>

      {editing ? (
        <div className="space-y-2">
          <div className="text-2xs text-fg-subtle uppercase tracking-wider">
            Édition manuelle (format Markdown — ## titres, * gras *, - listes)
          </div>
          <textarea
            id={`minutes-editor-${recordingId}`}
            name="ai_minutes"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="w-full min-h-[400px] p-3 rounded-lg border border-copper-500/40 bg-bg-base font-mono text-xs leading-relaxed focus:outline-none focus:border-copper-500"
            placeholder="## Résumé exécutif&#10;Trois phrases clés…&#10;&#10;## Décisions actées&#10;- Décision 1&#10;- Décision 2"
            aria-label="Éditer le compte rendu IA en Markdown"
          />
          <p className="text-2xs text-fg-muted">
            Les modifications seront utilisées pour les exports Word/PDF.
            Régénérer écrasera vos changements.
          </p>
        </div>
      ) : content ? (
        <div>{renderMd(content)}</div>
      ) : (
        <p className="text-sm text-fg-muted">Aucun résumé généré pour le moment.</p>
      )}
    </div>
  )
}
