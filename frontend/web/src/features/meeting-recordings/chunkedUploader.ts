/**
 * ChunkedUploader — découpe + upload parallèle + retry + reprise.
 *
 * Conçu pour uploader des fichiers audio CODIR > 50 Mo de façon robuste :
 *   - Découpe le Blob en chunks de N Mo (50 Mo par défaut).
 *   - Worker pool : MAX_PARALLEL chunks envoyés en parallèle.
 *   - Retry exponentiel par chunk (3 tentatives, backoff 1s/2s/4s).
 *   - Progress global = somme bytes envoyés / total.
 *   - Reprise : si un chunk a déjà été reçu par le serveur, on le skip.
 *
 * Utilisation :
 *   const uploader = new ChunkedUploader({
 *     blob, meetingId, filename, contentType,
 *     onProgress: (pct) => setProgress(pct),
 *   });
 *   const recording = await uploader.run();
 */
import { apiClient } from '@/api/client'

import type { MeetingRecording } from './types/recording.types'

export interface ChunkedUploaderOptions {
  blob: Blob
  meetingId: string
  filename: string
  contentType?: string
  title?: string
  durationSeconds?: number
  consentAcknowledged?: boolean

  /** Taille d'un chunk en octets (défaut : 50 Mo). */
  chunkSizeBytes?: number
  /** Nb de chunks envoyés en parallèle (défaut : 4). */
  maxParallel?: number
  /** Tentatives par chunk (défaut : 3). */
  maxRetriesPerChunk?: number
  /** Callback de progression (0..100). */
  onProgress?: (percent: number) => void
  /** Callback debug par chunk (utile pour UI détaillée). */
  onChunkComplete?: (chunkIndex: number, totalChunks: number) => void
  /** Signal d'annulation. */
  abortSignal?: AbortSignal
}

interface InitResponse {
  recording_id: string
  chunk_size_bytes: number
  total_chunks: number
  expected_total_bytes: number
}

interface ChunkAckResponse {
  recording_id: string
  chunk_index: number
  size: number
  checksum: string
  uploaded_chunks: number[]
  uploaded_count: number
}

interface StatusResponse {
  recording_id: string
  status: string
  expected_total_bytes: number
  uploaded_bytes: number
  uploaded_chunks: number[]
  uploaded_count: number
}

const DEFAULT_CHUNK_SIZE = 50 * 1024 * 1024  // 50 Mo
const DEFAULT_MAX_PARALLEL = 4
const DEFAULT_MAX_RETRIES = 3

/** Sleep avec support AbortSignal. */
function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new Error('Aborted'))
    const t = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => {
      clearTimeout(t)
      reject(new Error('Aborted'))
    }, { once: true })
  })
}

/** Retry un async avec backoff exponentiel (1s → 2s → 4s). */
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number,
  signal?: AbortSignal,
  label = 'chunk',
): Promise<T> {
  let lastErr: unknown
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    if (signal?.aborted) throw new Error('Aborted')
    try {
      return await fn()
    } catch (e) {
      lastErr = e
      // N'attend pas après la dernière tentative
      if (attempt === maxRetries) break
      const wait = 1000 * Math.pow(2, attempt)  // 1s, 2s, 4s
      console.warn(`[ChunkedUploader] ${label} attempt ${attempt + 1}/${maxRetries + 1} failed, retry in ${wait}ms`, e)
      await sleep(wait, signal)
    }
  }
  throw lastErr
}

export class ChunkedUploader {
  private opts: Required<Omit<ChunkedUploaderOptions, 'contentType' | 'title' | 'durationSeconds' | 'consentAcknowledged' | 'onProgress' | 'onChunkComplete' | 'abortSignal'>> & {
    contentType?: string
    title?: string
    durationSeconds?: number
    consentAcknowledged?: boolean
    onProgress?: (percent: number) => void
    onChunkComplete?: (chunkIndex: number, totalChunks: number) => void
    abortSignal?: AbortSignal
  }
  private uploadedBytes = 0
  private bytesPerChunk: Map<number, number> = new Map()

  constructor(opts: ChunkedUploaderOptions) {
    this.opts = {
      blob: opts.blob,
      meetingId: opts.meetingId,
      filename: opts.filename,
      chunkSizeBytes: opts.chunkSizeBytes ?? DEFAULT_CHUNK_SIZE,
      maxParallel: opts.maxParallel ?? DEFAULT_MAX_PARALLEL,
      maxRetriesPerChunk: opts.maxRetriesPerChunk ?? DEFAULT_MAX_RETRIES,
      contentType: opts.contentType,
      title: opts.title,
      durationSeconds: opts.durationSeconds,
      consentAcknowledged: opts.consentAcknowledged,
      onProgress: opts.onProgress,
      onChunkComplete: opts.onChunkComplete,
      abortSignal: opts.abortSignal,
    }
  }

  /** Lance l'upload complet et retourne le MeetingRecording finalisé. */
  async run(): Promise<MeetingRecording> {
    const { blob, meetingId, filename } = this.opts

    // ─── 1. Init côté serveur ────────────────────────────────
    const initResp = await withRetry(
      () => apiClient.post<InitResponse>(
        `/meetings/${meetingId}/recordings/upload/init/`,
        {
          filename,
          total_size_bytes: blob.size,
          content_type: this.opts.contentType ?? blob.type ?? '',
          chunk_size_bytes: this.opts.chunkSizeBytes,
          title: this.opts.title ?? '',
          duration_seconds: this.opts.durationSeconds,
          consent_acknowledged: this.opts.consentAcknowledged ?? false,
        },
        { timeout: 30_000 },
      ).then(r => r.data),
      2,
      this.opts.abortSignal,
      'init',
    )

    const recordingId = initResp.recording_id
    const totalChunks = initResp.total_chunks
    const serverChunkSize = initResp.chunk_size_bytes

    console.info(
      `[ChunkedUploader] init OK : rec=${recordingId} ${totalChunks} chunks de ${(serverChunkSize / 1024 / 1024).toFixed(0)} Mo`,
    )

    // ─── 2. Si on resume, on récupère la liste des chunks déjà reçus ──
    let alreadyUploaded: Set<number> = new Set()
    try {
      const statusResp = await apiClient.get<StatusResponse>(
        `/recordings/upload/${recordingId}/status/`,
      ).then(r => r.data)
      alreadyUploaded = new Set(statusResp.uploaded_chunks ?? [])
      if (alreadyUploaded.size > 0) {
        console.info(`[ChunkedUploader] reprise : ${alreadyUploaded.size}/${totalChunks} chunks déjà présents`)
        // Compte ces octets dans la progress
        for (const idx of alreadyUploaded) {
          const size = idx === totalChunks - 1
            ? blob.size - idx * serverChunkSize
            : serverChunkSize
          this.bytesPerChunk.set(idx, size)
          this.uploadedBytes += size
        }
        this._emitProgress()
      }
    } catch {
      // Pas grave si le status échoue — on uploadera tous les chunks.
    }

    // ─── 3. Build liste des chunks à uploader ────────────────
    const chunkIndexes: number[] = []
    for (let i = 0; i < totalChunks; i++) {
      if (!alreadyUploaded.has(i)) chunkIndexes.push(i)
    }

    // ─── 4. Worker pool ──────────────────────────────────────
    await this._runWorkerPool(
      chunkIndexes,
      this.opts.maxParallel,
      async (idx) => {
        const start = idx * serverChunkSize
        const end = Math.min(blob.size, start + serverChunkSize)
        const chunkBlob = blob.slice(start, end)
        const chunkSize = end - start

        await withRetry(
          () => this._uploadOneChunk(recordingId, idx, chunkBlob, chunkSize),
          this.opts.maxRetriesPerChunk,
          this.opts.abortSignal,
          `chunk[${idx}]`,
        )

        // Comptabilise les octets
        if (!this.bytesPerChunk.has(idx)) {
          this.bytesPerChunk.set(idx, chunkSize)
          this.uploadedBytes += chunkSize
          this._emitProgress()
        }
        this.opts.onChunkComplete?.(idx, totalChunks)
      },
    )

    // ─── 5. Finalise → assemble + déclenche Celery ──────────
    const finalResp = await withRetry(
      () => apiClient.post<MeetingRecording>(
        `/recordings/upload/${recordingId}/complete/`,
        { total_chunks: totalChunks },
        { timeout: 5 * 60 * 1000 },  // 5 min : assemblage peut être long sur S3
      ).then(r => r.data),
      2,
      this.opts.abortSignal,
      'complete',
    )

    this.opts.onProgress?.(100)
    return finalResp
  }

  /** Upload un chunk via multipart PUT, sans retry (retry géré par caller). */
  private async _uploadOneChunk(
    recordingId: string,
    chunkIndex: number,
    chunkBlob: Blob,
    expectedSize: number,
  ): Promise<ChunkAckResponse> {
    const form = new FormData()
    form.append('chunk', chunkBlob, `chunk_${chunkIndex.toString().padStart(4, '0')}.bin`)
    form.append('expected_size', String(expectedSize))

    const res = await apiClient.put<ChunkAckResponse>(
      `/recordings/upload/${recordingId}/chunks/${chunkIndex}/`,
      form,
      {
        // ⚠ Le client axios a Content-Type=application/json par défaut.
        // Sans `undefined` ici, axios sérialiserait FormData en JSON et le
        // chunk binaire deviendrait `{}` → 400 backend. Avec undefined,
        // axios détecte FormData et génère multipart/form-data avec boundary.
        headers: { 'Content-Type': undefined as unknown as string },
        timeout: 5 * 60 * 1000,  // 5 min par chunk
        signal: this.opts.abortSignal as any,
      },
    )
    return res.data
  }

  /** Exécute un pool de N workers parallèles sur une liste d'items. */
  private async _runWorkerPool<T>(
    items: T[],
    concurrency: number,
    worker: (item: T, index: number) => Promise<void>,
  ): Promise<void> {
    if (items.length === 0) return

    let cursor = 0
    const errors: unknown[] = []

    const runWorker = async (): Promise<void> => {
      while (cursor < items.length) {
        if (this.opts.abortSignal?.aborted) {
          throw new Error('Aborted')
        }
        const myIndex = cursor++
        try {
          await worker(items[myIndex], myIndex)
        } catch (e) {
          errors.push(e)
          // On stoppe le worker dès la 1re erreur définitive
          throw e
        }
      }
    }

    const workers = Array.from(
      { length: Math.min(concurrency, items.length) },
      () => runWorker(),
    )

    try {
      await Promise.all(workers)
    } catch (e) {
      // Si un worker plante, on remonte la première erreur.
      throw errors[0] ?? e
    }
  }

  private _emitProgress() {
    const pct = Math.min(99, Math.round((this.uploadedBytes / this.opts.blob.size) * 100))
    this.opts.onProgress?.(pct)
  }
}
