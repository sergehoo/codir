/**
 * Historique des versions du compte rendu (lot HIST).
 *
 * Affiche une timeline des snapshots successifs du CR, avec pour chacun :
 * son origine (génération IA, édition manuelle, restauration), son auteur,
 * un aperçu, et la possibilité de consulter le contenu intégral ou de
 * restaurer cette version comme CR courant.
 *
 * La restauration n'est jamais destructive : le serveur archive l'état
 * courant avant d'écraser, donc on peut toujours revenir en arrière.
 */
import {
  ChevronDown, ChevronRight, Clock, Loader2, RotateCcw,
  Sparkles, User as UserIcon, X,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { cn } from '@/utils/cn'
import { safeFormat } from '@/utils/safeDate'

import { recordingsApi } from '../api'
import {
  useMinutesVersions, useRecordingActions,
} from '../hooks/useRecordingHistory'
import type { MinutesVersion, MinutesVersionOrigin } from '../types/recording.types'

interface Props {
  recordingId: string
  meetingId?: string | null
  /** L'utilisateur peut-il restaurer (chair/secretary/owner). Default true. */
  canRestore?: boolean
  onRestored?: () => void
}

const ORIGIN_STYLE: Record<MinutesVersionOrigin, { dot: string; label: string }> = {
  ai_generated:   { dot: 'bg-copper-500',  label: 'Génération IA' },
  ai_regenerated: { dot: 'bg-copper-400',  label: 'Régénération IA' },
  manual_edit:    { dot: 'bg-sky-500',     label: 'Édition manuelle' },
  restored:       { dot: 'bg-emerald-500', label: 'Restauration' },
}

export function MinutesVersionHistory({
  recordingId, meetingId, canRestore = true, onRestored,
}: Props) {
  const { data, isLoading } = useMinutesVersions(recordingId)
  const actions = useRecordingActions(recordingId, meetingId)

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [fullContent, setFullContent] = useState<Record<string, string>>({})
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [confirmRestore, setConfirmRestore] = useState<MinutesVersion | null>(null)

  const versions = data?.versions ?? []

  const toggleExpand = async (v: MinutesVersion) => {
    if (expandedId === v.id) {
      setExpandedId(null)
      return
    }
    setExpandedId(v.id)
    // Charge le contenu complet à la demande (la liste ne renvoie qu'un aperçu).
    if (!fullContent[v.id]) {
      setLoadingId(v.id)
      try {
        const detail = await recordingsApi.minutesVersionDetail(recordingId, v.id)
        setFullContent((prev) => ({
          ...prev,
          [v.id]: detail.ai_minutes || detail.summary || '(vide)',
        }))
      } catch {
        toast.error('Impossible de charger cette version')
        setExpandedId(null)
      } finally {
        setLoadingId(null)
      }
    }
  }

  const doRestore = async (v: MinutesVersion) => {
    try {
      await actions.restoreVersion(v.id)
      toast.success(`Compte rendu restauré à la version ${v.version_number}`)
      setConfirmRestore(null)
      onRestored?.()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Restauration impossible')
    }
  }

  if (isLoading) {
    return (
      <div className="p-4 grid place-items-center">
        <Loader2 size={16} className="animate-spin text-copper-500" />
      </div>
    )
  }

  if (versions.length === 0) {
    return (
      <div className="p-4 text-center text-xs text-fg-subtle">
        Aucune version archivée pour l'instant. L'historique se remplit à chaque
        génération ou modification du compte rendu.
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 px-1 pb-2">
        <Clock size={13} className="text-fg-subtle" />
        <span className="text-2xs uppercase tracking-wider text-fg-subtle">
          {versions.length} version{versions.length > 1 ? 's' : ''} archivée
          {versions.length > 1 ? 's' : ''}
        </span>
      </div>

      <ol className="relative border-l border-border ml-2 space-y-1">
        {versions.map((v, idx) => {
          const style = ORIGIN_STYLE[v.origin] ?? ORIGIN_STYLE.ai_generated
          const isCurrent = idx === 0
          const isOpen = expandedId === v.id

          return (
            <li key={v.id} className="relative pl-5 py-1.5">
              {/* Point de la timeline */}
              <span
                className={cn(
                  'absolute -left-[5px] top-3.5 w-2.5 h-2.5 rounded-full ring-2 ring-bg-elevated',
                  style.dot,
                )}
              />

              <div
                className={cn(
                  'rounded-lg border transition',
                  isCurrent
                    ? 'border-copper-500/40 bg-copper-500/5'
                    : 'border-border bg-bg-base hover:bg-fg/[0.02]',
                )}
              >
                <div className="flex items-start justify-between gap-2 p-2.5">
                  <button
                    type="button"
                    onClick={() => toggleExpand(v)}
                    className="flex-1 text-left min-w-0"
                  >
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {isOpen
                        ? <ChevronDown size={12} className="text-fg-subtle shrink-0" />
                        : <ChevronRight size={12} className="text-fg-subtle shrink-0" />}
                      <span className="text-xs font-semibold">
                        v{v.version_number}
                      </span>
                      {isCurrent && (
                        <span className="px-1.5 py-0.5 rounded text-2xs bg-copper-500 text-white font-medium">
                          Actuelle
                        </span>
                      )}
                      <span className="text-2xs text-fg-subtle">
                        {v.origin_display || style.label}
                      </span>
                      {v.restored_from_version != null && (
                        <span className="text-2xs text-emerald-500">
                          ← v{v.restored_from_version}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 mt-1 text-2xs text-fg-subtle flex-wrap">
                      <span className="inline-flex items-center gap-1">
                        <Clock size={10} />
                        {safeFormat(v.created_at, 'dd/MM/yyyy HH:mm')}
                      </span>
                      {v.created_by ? (
                        <span className="inline-flex items-center gap-1">
                          <UserIcon size={10} />
                          {v.created_by.full_name || v.created_by.email}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1">
                          <Sparkles size={10} /> Automatique
                        </span>
                      )}
                      <span>{v.char_count.toLocaleString('fr-FR')} car.</span>
                    </div>

                    {v.label && (
                      <div className="mt-1 text-2xs italic text-fg-muted">
                        {v.label}
                      </div>
                    )}

                    {!isOpen && v.preview && (
                      <p className="mt-1.5 text-2xs text-fg-muted line-clamp-2 leading-relaxed">
                        {v.preview}
                      </p>
                    )}
                  </button>

                  {canRestore && !isCurrent && (
                    <button
                      type="button"
                      onClick={() => setConfirmRestore(v)}
                      disabled={actions.isRestoring}
                      className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded-md text-2xs text-fg-muted hover:text-fg hover:bg-fg/5 transition disabled:opacity-50"
                      title={`Restaurer la version ${v.version_number}`}
                    >
                      <RotateCcw size={11} /> Restaurer
                    </button>
                  )}
                </div>

                {/* Contenu intégral déplié */}
                {isOpen && (
                  <div className="border-t border-border px-3 py-2.5">
                    {loadingId === v.id ? (
                      <div className="grid place-items-center py-3">
                        <Loader2 size={14} className="animate-spin text-copper-500" />
                      </div>
                    ) : (
                      <pre className="whitespace-pre-wrap font-mono text-2xs leading-relaxed text-fg-muted max-h-64 overflow-y-auto">
                        {fullContent[v.id] ?? '—'}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            </li>
          )
        })}
      </ol>

      {/* ─── Confirmation de restauration ─── */}
      {confirmRestore && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4"
          onClick={() => setConfirmRestore(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-border bg-bg-elevated p-5 shadow-floating"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <RotateCcw size={16} className="text-copper-500" />
                <h3 className="text-sm font-semibold">
                  Restaurer la version {confirmRestore.version_number} ?
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setConfirmRestore(null)}
                className="text-fg-subtle hover:text-fg transition"
              >
                <X size={16} />
              </button>
            </div>

            <p className="text-xs text-fg-muted leading-relaxed mb-4">
              Le compte rendu actuel sera remplacé par cette version.
              Rien n'est perdu : l'état actuel est automatiquement archivé
              comme nouvelle version avant le remplacement.
            </p>

            <div className="rounded-lg border border-border bg-bg-base p-2.5 mb-4">
              <div className="text-2xs text-fg-subtle mb-1">
                {safeFormat(confirmRestore.created_at, 'dd/MM/yyyy HH:mm')}
                {' · '}
                {confirmRestore.origin_display}
              </div>
              <p className="text-2xs text-fg-muted line-clamp-3 leading-relaxed">
                {confirmRestore.preview || '(aperçu indisponible)'}
              </p>
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmRestore(null)}
                disabled={actions.isRestoring}
                className="px-3 py-1.5 rounded-lg text-xs text-fg-muted hover:text-fg hover:bg-fg/5 transition"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={() => doRestore(confirmRestore)}
                disabled={actions.isRestoring}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-copper-500 hover:bg-copper-600 text-white font-semibold transition disabled:opacity-50"
              >
                {actions.isRestoring
                  ? <><Loader2 size={12} className="animate-spin" /> Restauration…</>
                  : <><RotateCcw size={12} /> Restaurer</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
