// FileUploadCard — alternative à l'enregistrement micro : importer un fichier
// audio (mp3, m4a, wav, webm, mp4, ogg, opus, flac…) déjà existant.
//
// Cas d'usage :
//   - Réunion enregistrée avec un autre outil (Zoom export, dictaphone, etc.)
//   - Reprise d'un fichier sauvé localement
//   - Import d'audio brut envoyé par un collaborateur
//
// Le fichier est uploadé via le MÊME pipeline que la captation directe :
//   - < 50 Mo : POST multipart single-shot
//   - ≥ 50 Mo : chunked upload (4 chunks parallèle + retry)
import { File as FileIcon, FileAudio, Upload, X } from 'lucide-react'
import { useRef, useState } from 'react'

import { cn } from '@/utils/cn'

interface Props {
  consentAck: boolean
  isUploading: boolean
  /** Lance l'upload via le hook parent (qui réutilise doUpload). */
  onUpload: (file: File, durationSeconds?: number) => void | Promise<void>
  /** Limite en Mo, lue depuis le settings backend. */
  maxMb?: number
}

const ACCEPT = 'audio/*,video/webm,video/mp4,application/ogg'

export function FileUploadCard({
  consentAck, isUploading, onUpload, maxMb = 600,
}: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [duration, setDuration] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const maxBytes = maxMb * 1024 * 1024

  function validate(f: File): string | null {
    if (f.size > maxBytes) {
      return `Fichier trop volumineux (${(f.size / 1024 / 1024).toFixed(1)} Mo). Limite : ${maxMb} Mo.`
    }
    if (f.size === 0) {
      return "Fichier vide."
    }
    // MIME tolérant : on accepte audio/*, video/webm, video/mp4, ou vide
    // (Firefox/Safari mettent souvent application/octet-stream).
    const t = (f.type || '').toLowerCase()
    if (t && !(
      t.startsWith('audio/')
      || t.startsWith('video/webm')
      || t.startsWith('video/mp4')
      || t.startsWith('video/mpeg')
      || t === 'application/octet-stream'
      || t === 'application/ogg'
    )) {
      return `Format non supporté (${t}). Attendu : mp3, m4a, wav, aac, ogg, opus, flac, webm, mp4.`
    }
    return null
  }

  function handleFiles(files: FileList | File[] | null) {
    if (!files || files.length === 0) return
    const f = files[0]
    const err = validate(f)
    if (err) {
      setError(err)
      setFile(null)
      setDuration(null)
      return
    }
    setError(null)
    setFile(f)
    setDuration(null)
    // Tente d'extraire la durée via un Audio element (gratuit, pas de décodage complet)
    try {
      const url = URL.createObjectURL(f)
      const audio = document.createElement('audio')
      audio.preload = 'metadata'
      audio.onloadedmetadata = () => {
        if (Number.isFinite(audio.duration)) setDuration(audio.duration)
        URL.revokeObjectURL(url)
      }
      audio.onerror = () => URL.revokeObjectURL(url)
      audio.src = url
    } catch {
      /* ignore : la durée sera détectée côté serveur via ffmpeg */
    }
  }

  function clearFile() {
    setFile(null)
    setDuration(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  async function handleSubmit() {
    if (!file || !consentAck || isUploading) return
    await onUpload(file, duration ?? undefined)
  }

  // ─── Drag & drop ────────────────────────────────────────
  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragging(false)
    handleFiles(e.dataTransfer.files)
  }
  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    setIsDragging(true)
  }
  function handleDragLeave() {
    setIsDragging(false)
  }

  // ─── Render ─────────────────────────────────────────────

  return (
    <div className="space-y-3">
      {/* Zone drop / sélecteur */}
      <div
        onClick={() => !file && inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={cn(
          'relative border-2 border-dashed rounded-xl px-5 py-8 transition-colors text-center',
          file
            ? 'border-copper-500/40 bg-copper-500/5 cursor-default'
            : isDragging
              ? 'border-copper-500 bg-copper-500/10 cursor-pointer'
              : 'border-border bg-bg-elevated hover:border-copper-500/40 hover:bg-bg-base cursor-pointer',
        )}
      >
        <input
          ref={inputRef}
          id="recording-file-input"
          name="recording-file-input"
          type="file"
          accept={ACCEPT}
          onChange={(e) => handleFiles(e.target.files)}
          className="hidden"
        />

        {!file ? (
          <>
            <FileAudio size={28} className="mx-auto text-copper-500 mb-2" strokeWidth={1.5} />
            <div className="text-sm font-semibold">
              Cliquez ou déposez un fichier audio
            </div>
            <p className="text-xs text-fg-muted mt-1.5">
              Formats : mp3, m4a, wav, aac, ogg, opus, flac, webm, mp4
            </p>
            <p className="text-2xs text-fg-subtle mt-1">
              Taille max : {maxMb} Mo
            </p>
          </>
        ) : (
          <div className="flex items-start gap-3 text-left">
            <div className="w-10 h-10 rounded-lg bg-copper-500/15 grid place-items-center shrink-0">
              <FileIcon size={18} className="text-copper-500" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold truncate" title={file.name}>
                {file.name}
              </div>
              <div className="text-xs text-fg-muted mt-0.5">
                {(file.size / 1024 / 1024).toFixed(1)} Mo
                {file.type ? ` · ${file.type}` : ''}
                {duration !== null ? ` · ${formatDuration(duration)}` : ''}
              </div>
              {file.size > 50 * 1024 * 1024 && (
                <div className="text-2xs text-copper-400 mt-1">
                  ⚡ Upload chunked (4 chunks en parallèle, reprise auto)
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); clearFile() }}
              className="p-1 rounded hover:bg-fg/10 text-fg-muted hover:text-fg shrink-0"
              title="Retirer ce fichier"
            >
              <X size={14} />
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <button
        type="button"
        disabled={!file || !consentAck || isUploading}
        onClick={handleSubmit}
        className={cn(
          'w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl',
          'text-sm font-semibold transition shadow-sm',
          file && consentAck && !isUploading
            ? 'bg-copper-500 hover:bg-copper-600 text-white'
            : 'bg-fg/10 text-fg-muted cursor-not-allowed',
        )}
      >
        <Upload size={16} />
        {isUploading ? 'Envoi en cours…' : 'Téléverser et lancer le traitement'}
      </button>
    </div>
  )
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m.toString().padStart(2, '0')}m`
  if (m > 0) return `${m}m ${s.toString().padStart(2, '0')}s`
  return `${s}s`
}
