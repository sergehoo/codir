/**
 * Historique des enregistrements d'une réunion (lot HIST).
 *
 * Une réunion peut porter plusieurs enregistrements (reprises après échec
 * d'upload, sessions multiples, corrections). Avant ce composant, seul le
 * plus récent était accessible dans l'UI — les comptes rendus des takes
 * antérieurs devenaient orphelins.
 *
 * Chaque entrée expose : date, durée, statut, aperçu du CR, lecteur audio,
 * et les actions (consulter, exporter, renommer, annoter, archiver,
 * supprimer).
 */
import { Link } from '@tanstack/react-router'
import {
  Archive, ArchiveRestore, Check, ChevronDown, ChevronRight,
  Clock, Download, Eye, FileText, Loader2, Mic, MoreVertical,
  Pencil, Sparkles, Trash2, X,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { cn } from '@/utils/cn'
import { safeFormat } from '@/utils/safeDate'

import { recordingsApi } from '../api'
import { useMeetingRecordingsHistory, useRecordingActions } from '../hooks/useRecordingHistory'
import type { MeetingRecording } from '../types/recording.types'

import { RecordingStatusBadge } from './RecordingStatusBadge'

interface Props {
  meetingId: string
  /** L'utilisateur peut-il modifier/supprimer. Default true. */
  canManage?: boolean
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds < 1) return '—'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h} h ${String(m).padStart(2, '0')}`
  if (m > 0) return `${m} min ${String(s).padStart(2, '0')}`
  return `${s} s`
}

function formatSize(bytes: number): string {
  if (!bytes) return '—'
  const mb = bytes / 1024 / 1024
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} Go`
  return `${mb.toFixed(1)} Mo`
}

export function RecordingsHistoryList({ meetingId, canManage = true }: Props) {
  const [includeArchived, setIncludeArchived] = useState(false)
  const { data: recordings = [], isLoading } =
    useMeetingRecordingsHistory(meetingId, { includeArchived })

  if (isLoading) {
    return (
      <div className="p-6 grid place-items-center">
        <Loader2 size={18} className="animate-spin text-copper-500" />
      </div>
    )
  }

  const archivedCount = recordings.filter((r) => r.is_archived).length

  if (recordings.length === 0) {
    return (
      <div className="p-6 text-center">
        <Mic size={20} className="mx-auto mb-2 text-fg-subtle" />
        <p className="text-sm text-fg-muted">
          Aucun enregistrement pour cette réunion.
        </p>
        {!includeArchived && (
          <button
            type="button"
            onClick={() => setIncludeArchived(true)}
            className="mt-2 text-xs text-copper-500 hover:underline"
          >
            Afficher les enregistrements archivés
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between px-1">
        <span className="text-2xs uppercase tracking-wider text-fg-subtle">
          {recordings.length} enregistrement{recordings.length > 1 ? 's' : ''}
          {includeArchived && archivedCount > 0 && ` · ${archivedCount} archivé${archivedCount > 1 ? 's' : ''}`}
        </span>
        <label className="inline-flex items-center gap-1.5 text-2xs text-fg-muted cursor-pointer">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => setIncludeArchived(e.target.checked)}
            className="rounded border-border accent-copper-500"
          />
          Inclure les archivés
        </label>
      </div>

      {recordings.map((rec) => (
        <RecordingHistoryCard
          key={rec.id}
          recording={rec}
          meetingId={meetingId}
          canManage={canManage}
        />
      ))}
    </div>
  )
}

/* ─── Carte d'un enregistrement ────────────────────────────── */

function RecordingHistoryCard({
  recording, meetingId, canManage,
}: {
  recording: MeetingRecording
  meetingId: string
  canManage: boolean
}) {
  const actions = useRecordingActions(recording.id, meetingId)

  const [expanded, setExpanded] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [editingMeta, setEditingMeta] = useState(false)
  const [titleDraft, setTitleDraft] = useState(recording.title ?? '')
  const [noteDraft, setNoteDraft] = useState(recording.internal_note ?? '')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [exporting, setExporting] = useState<'docx' | 'pdf' | null>(null)

  const displayTitle = recording.title?.trim()
    || `Enregistrement du ${safeFormat(recording.created_at, 'dd/MM/yyyy à HH:mm')}`

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

  const doExport = async (kind: 'docx' | 'pdf') => {
    setExporting(kind)
    try {
      const blob = kind === 'docx'
        ? await recordingsApi.exportDocxBlob(recording.id)
        : await recordingsApi.exportPdfBlob(recording.id)
      const date = safeFormat(recording.created_at, 'yyyy-MM-dd', { fallback: 'sans-date' })
      downloadBlob(blob, `CR_${date}_${recording.id.slice(0, 8)}.${kind}`)
      toast.success(`${kind.toUpperCase()} téléchargé`)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? `Export ${kind.toUpperCase()} impossible`)
    } finally {
      setExporting(null)
    }
  }

  const saveMeta = async () => {
    try {
      await actions.rename({ title: titleDraft, internal_note: noteDraft })
      toast.success('Enregistrement mis à jour')
      setEditingMeta(false)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Modification refusée')
    }
  }

  const toggleArchive = async () => {
    try {
      await actions.setArchived(!recording.is_archived)
      toast.success(recording.is_archived ? 'Désarchivé' : 'Archivé')
      setMenuOpen(false)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Action impossible')
    }
  }

  const doDelete = async () => {
    try {
      await actions.remove()
      toast.success('Enregistrement supprimé')
      setConfirmDelete(false)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Suppression refusée')
    }
  }

  return (
    <div
      className={cn(
        'rounded-xl border transition',
        recording.is_archived
          ? 'border-border/60 bg-bg-base/50 opacity-70'
          : 'border-border bg-bg-elevated',
      )}
    >
      {/* ─── En-tête ─── */}
      <div className="flex items-start gap-3 p-3">
        <button
          type="button"
          onClick={() => setExpanded((s) => !s)}
          className="mt-0.5 text-fg-subtle hover:text-fg transition shrink-0"
          aria-label={expanded ? 'Replier' : 'Déplier'}
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>

        <div className="flex-1 min-w-0">
          {editingMeta ? (
            <div className="space-y-2">
              <input
                type="text"
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                placeholder="Titre de l'enregistrement"
                className="w-full px-2 py-1 rounded-md border border-copper-500/40 bg-bg-base text-sm focus:outline-none focus:border-copper-500"
                aria-label="Titre"
              />
              <textarea
                value={noteDraft}
                onChange={(e) => setNoteDraft(e.target.value)}
                placeholder="Note interne (contexte, qualité audio…)"
                rows={2}
                className="w-full px-2 py-1 rounded-md border border-border bg-bg-base text-xs focus:outline-none focus:border-copper-500"
                aria-label="Note interne"
              />
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => { setEditingMeta(false); setTitleDraft(recording.title ?? ''); setNoteDraft(recording.internal_note ?? '') }}
                  className="px-2 py-1 rounded-md text-2xs text-fg-muted hover:bg-fg/5 transition"
                >
                  <X size={11} className="inline mr-1" />Annuler
                </button>
                <button
                  type="button"
                  onClick={saveMeta}
                  disabled={actions.isRenaming}
                  className="px-2 py-1 rounded-md text-2xs bg-emerald-500 hover:bg-emerald-600 text-white font-medium transition disabled:opacity-50"
                >
                  {actions.isRenaming
                    ? <Loader2 size={11} className="inline animate-spin" />
                    : <Check size={11} className="inline mr-1" />}
                  Enregistrer
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium truncate">{displayTitle}</span>
                {recording.is_archived && (
                  <span className="px-1.5 py-0.5 rounded text-2xs bg-fg/10 text-fg-muted">
                    Archivé
                  </span>
                )}
                <RecordingStatusBadge status={recording.status} />
              </div>

              <div className="flex items-center gap-2.5 mt-1 text-2xs text-fg-subtle flex-wrap">
                <span className="inline-flex items-center gap-1">
                  <Clock size={10} />
                  {safeFormat(recording.created_at, 'dd/MM/yyyy HH:mm')}
                </span>
                <span>{formatDuration(recording.duration_seconds)}</span>
                <span>{formatSize(recording.file_size)}</span>
                {recording.recorded_by && (
                  <span>par {recording.recorded_by.full_name || recording.recorded_by.email}</span>
                )}
                {(recording.versions_count ?? 0) > 0 && (
                  <span className="inline-flex items-center gap-1 text-copper-500">
                    <FileText size={10} />
                    {recording.versions_count} version{(recording.versions_count ?? 0) > 1 ? 's' : ''} de CR
                  </span>
                )}
              </div>

              {recording.internal_note && (
                <p className="mt-1.5 text-2xs italic text-fg-muted">
                  {recording.internal_note}
                </p>
              )}

              {recording.has_summary && recording.summary_preview && (
                <p className="mt-1.5 text-2xs text-fg-muted line-clamp-2 leading-relaxed">
                  <Sparkles size={10} className="inline mr-1 text-copper-500" />
                  {recording.summary_preview}
                </p>
              )}

              {!recording.has_summary && recording.status === 'failed' && (
                <p className="mt-1.5 text-2xs text-rose-500">
                  {recording.error_message || 'Traitement échoué — aucun compte rendu.'}
                </p>
              )}
            </>
          )}
        </div>

        {/* ─── Menu actions ─── */}
        {canManage && !editingMeta && (
          <div className="relative shrink-0">
            <button
              type="button"
              onClick={() => setMenuOpen((s) => !s)}
              className="p-1 rounded-md text-fg-subtle hover:text-fg hover:bg-fg/5 transition"
              aria-label="Actions"
            >
              <MoreVertical size={14} />
            </button>

            {menuOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setMenuOpen(false)}
                />
                <div className="absolute right-0 top-7 z-20 w-48 rounded-lg border border-border bg-bg-elevated shadow-floating py-1">
                  <button
                    type="button"
                    onClick={() => { setEditingMeta(true); setMenuOpen(false) }}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-fg hover:bg-fg/5 transition"
                  >
                    <Pencil size={12} /> Renommer / annoter
                  </button>
                  <button
                    type="button"
                    onClick={toggleArchive}
                    disabled={actions.isArchiving}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-fg hover:bg-fg/5 transition disabled:opacity-50"
                  >
                    {recording.is_archived
                      ? <><ArchiveRestore size={12} /> Désarchiver</>
                      : <><Archive size={12} /> Archiver</>}
                  </button>
                  <div className="h-px bg-border my-1" />
                  <button
                    type="button"
                    onClick={() => { setConfirmDelete(true); setMenuOpen(false) }}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-rose-500 hover:bg-rose-500/10 transition"
                  >
                    <Trash2 size={12} /> Supprimer définitivement
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* ─── Contenu déplié ─── */}
      {expanded && (
        <div className="border-t border-border px-3 py-3 space-y-3">
          {/* Lecteur audio */}
          {recording.has_audio && recording.audio_url ? (
            <div>
              <div className="text-2xs uppercase tracking-wider text-fg-subtle mb-1.5">
                Audio de la réunion
              </div>
              <audio
                controls
                preload="none"
                src={recording.audio_url}
                className="w-full h-9"
              >
                Votre navigateur ne supporte pas la lecture audio.
              </audio>
            </div>
          ) : (
            <p className="text-2xs text-fg-subtle">
              {recording.archived_at
                ? 'Audio purgé (rétention).'
                : 'Aucun fichier audio disponible.'}
            </p>
          )}

          {/* Actions sur le CR */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <Link
              to="/meetings/$meetingId/recordings/$recordingId/summary"
              params={{ meetingId, recordingId: recording.id }}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-bg-base border border-border hover:bg-fg/5 text-fg transition"
            >
              <Eye size={12} /> Consulter le compte rendu
            </Link>

            {recording.has_summary && (
              <>
                <button
                  type="button"
                  onClick={() => doExport('docx')}
                  disabled={exporting !== null}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-bg-base border border-border hover:bg-fg/5 text-fg transition disabled:opacity-50"
                >
                  {exporting === 'docx'
                    ? <Loader2 size={12} className="animate-spin" />
                    : <FileText size={12} />}
                  Word
                </button>
                <button
                  type="button"
                  onClick={() => doExport('pdf')}
                  disabled={exporting !== null}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-copper-500 hover:bg-copper-600 text-white transition disabled:opacity-50"
                >
                  {exporting === 'pdf'
                    ? <Loader2 size={12} className="animate-spin" />
                    : <Download size={12} />}
                  PDF
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* ─── Confirmation suppression ─── */}
      {confirmDelete && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4"
          onClick={() => setConfirmDelete(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-border bg-bg-elevated p-5 shadow-floating"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-3">
              <Trash2 size={16} className="text-rose-500" />
              <h3 className="text-sm font-semibold">Supprimer cet enregistrement ?</h3>
            </div>
            <p className="text-xs text-fg-muted leading-relaxed mb-2">
              <strong className="text-fg">{displayTitle}</strong>
            </p>
            <p className="text-xs text-fg-muted leading-relaxed mb-4">
              L'audio, la transcription, le compte rendu et tout l'historique
              de versions seront définitivement détruits. Cette action est
              irréversible — préférez l'archivage si vous hésitez.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmDelete(false)}
                disabled={actions.isRemoving}
                className="px-3 py-1.5 rounded-lg text-xs text-fg-muted hover:text-fg hover:bg-fg/5 transition"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={doDelete}
                disabled={actions.isRemoving}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-rose-500 hover:bg-rose-600 text-white font-semibold transition disabled:opacity-50"
              >
                {actions.isRemoving
                  ? <><Loader2 size={12} className="animate-spin" /> Suppression…</>
                  : <><Trash2 size={12} /> Supprimer</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
