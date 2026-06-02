// Hook MediaRecorder : capture micro, pause/resume/stop, niveau audio,
// timer, garde-fou avant fermeture page.
//
// Stratégie format :
// - On préfère audio/webm;codecs=opus (Chrome/Firefox) — meilleur ratio.
// - Fallback audio/mp4 ou audio/webm (Safari).
//
// Le hook expose :
// - state          : 'idle' | 'recording' | 'paused' | 'stopped' | 'error'
// - durationMs     : durée totale enregistrée (hors pauses)
// - audioLevel     : 0..1 (RMS lissé pour visualiseur)
// - permissionError: si l'utilisateur a refusé le micro
// - start / pause / resume / stop / reset
// - lastBlob       : Blob audio final (disponible après stop)
//
// Tous les chunks sont accumulés en mémoire — pour une bêta, c'est OK.
// Pour > 2h d'audio, on basculera sur l'upload par chunks (RecordingChunk).

import { useCallback, useEffect, useRef, useState } from 'react'

export type MediaRecorderState = 'idle' | 'recording' | 'paused' | 'stopped' | 'error'

interface UseMediaRecorderOptions {
  /** Empêche la fermeture de la page tant qu'un enregistrement est en cours. */
  preventUnload?: boolean
  /** Callback à chaque chunk (pour upload streamé future). Optionnel. */
  onChunk?: (chunk: Blob) => void
  /** Durée min en ms avant que stop() ne soit accepté (anti-clic accidentel). */
  minDurationMs?: number
}

interface UseMediaRecorderReturn {
  state: MediaRecorderState
  durationMs: number
  audioLevel: number
  permissionError: string | null
  start: () => Promise<boolean>
  pause: () => void
  resume: () => void
  stop: () => Promise<Blob | null>
  reset: () => void
  lastBlob: Blob | null
  mimeType: string
}

function pickMimeType(): string {
  if (typeof MediaRecorder === 'undefined') return ''
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
  ]
  for (const c of candidates) {
    try {
      if (MediaRecorder.isTypeSupported(c)) return c
    } catch { /* ignore */ }
  }
  return ''
}

export function useMediaRecorder(opts: UseMediaRecorderOptions = {}): UseMediaRecorderReturn {
  const { preventUnload = true, onChunk, minDurationMs = 1500 } = opts

  const [state, setState] = useState<MediaRecorderState>('idle')
  const [durationMs, setDurationMs] = useState(0)
  const [audioLevel, setAudioLevel] = useState(0)
  const [permissionError, setPermissionError] = useState<string | null>(null)
  const [lastBlob, setLastBlob] = useState<Blob | null>(null)
  const [mimeType, setMimeType] = useState<string>('')

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startMsRef = useRef<number>(0)
  const accumulatedMsRef = useRef<number>(0)
  const tickRef = useRef<number | null>(null)

  // AudioContext pour la visualisation niveau
  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const dataRef = useRef<Uint8Array | null>(null)
  const rafRef = useRef<number | null>(null)

  const cleanup = useCallback(() => {
    if (tickRef.current) {
      window.clearInterval(tickRef.current); tickRef.current = null
    }
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current); rafRef.current = null
    }
    try { recorderRef.current?.stream.getTracks().forEach((t) => t.stop()) } catch { /**/ }
    try { streamRef.current?.getTracks().forEach((t) => t.stop()) } catch { /**/ }
    streamRef.current = null
    recorderRef.current = null
    try { audioCtxRef.current?.close() } catch { /**/ }
    audioCtxRef.current = null
    analyserRef.current = null
    dataRef.current = null
  }, [])

  // Reset complet (à appeler entre 2 enregistrements ou pour annuler).
  const reset = useCallback(() => {
    cleanup()
    chunksRef.current = []
    startMsRef.current = 0
    accumulatedMsRef.current = 0
    setDurationMs(0)
    setAudioLevel(0)
    setLastBlob(null)
    setPermissionError(null)
    setState('idle')
  }, [cleanup])

  // Démarre la capture micro + MediaRecorder.
  const start = useCallback(async (): Promise<boolean> => {
    setPermissionError(null)
    if (!navigator.mediaDevices?.getUserMedia) {
      setPermissionError("Votre navigateur ne supporte pas l'accès au micro.")
      setState('error')
      return false
    }
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
    } catch (err: any) {
      const name = err?.name ?? ''
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setPermissionError(
          "Permission micro refusée. Activez-la dans les paramètres du navigateur.",
        )
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        setPermissionError("Aucun micro détecté sur cet appareil.")
      } else {
        setPermissionError(`Impossible d'accéder au micro : ${err?.message ?? err}`)
      }
      setState('error')
      return false
    }

    streamRef.current = stream
    const picked = pickMimeType()
    setMimeType(picked)

    let recorder: MediaRecorder
    try {
      recorder = new MediaRecorder(stream, picked ? { mimeType: picked } : undefined)
    } catch (err: any) {
      setPermissionError("Format audio non supporté par ce navigateur.")
      setState('error')
      return false
    }
    recorderRef.current = recorder
    chunksRef.current = []

    recorder.ondataavailable = (ev) => {
      if (ev.data && ev.data.size > 0) {
        chunksRef.current.push(ev.data)
        onChunk?.(ev.data)
      }
    }
    recorder.onerror = () => {
      setState('error')
      setPermissionError("Erreur du MediaRecorder.")
    }

    // Demande des chunks toutes les 5 sec pour permettre un upload progressif si besoin.
    recorder.start(5000)

    startMsRef.current = Date.now()
    accumulatedMsRef.current = 0
    setDurationMs(0)
    setState('recording')

    // Timer 200ms
    tickRef.current = window.setInterval(() => {
      const cur = Date.now() - startMsRef.current + accumulatedMsRef.current
      setDurationMs(cur)
    }, 200)

    // Audio level (RMS)
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const src = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      src.connect(analyser)
      audioCtxRef.current = ctx
      analyserRef.current = analyser
      dataRef.current = new Uint8Array(analyser.fftSize)
      const loop = () => {
        const data = dataRef.current
        if (!analyserRef.current || !data) return
        // Cast nécessaire : le DOM exige Uint8Array<ArrayBuffer> strict
        // depuis TS 5.7, alors que `new Uint8Array(n)` produit
        // `Uint8Array<ArrayBufferLike>`. C'est sûr puisque c'est le même
        // buffer concret en runtime.
        ;(analyserRef.current as any).getByteTimeDomainData(data)
        let sum = 0
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128
          sum += v * v
        }
        const rms = Math.sqrt(sum / data.length)
        // Lissage léger (passe-bas)
        setAudioLevel((prev) => prev * 0.7 + rms * 0.3)
        rafRef.current = requestAnimationFrame(loop)
      }
      rafRef.current = requestAnimationFrame(loop)
    } catch { /* analyseur facultatif */ }

    return true
  }, [onChunk])

  const pause = useCallback(() => {
    const rec = recorderRef.current
    if (rec && rec.state === 'recording') {
      try { rec.pause() } catch { /**/ }
      accumulatedMsRef.current += Date.now() - startMsRef.current
      if (tickRef.current) {
        window.clearInterval(tickRef.current); tickRef.current = null
      }
      setState('paused')
    }
  }, [])

  const resume = useCallback(() => {
    const rec = recorderRef.current
    if (rec && rec.state === 'paused') {
      try { rec.resume() } catch { /**/ }
      startMsRef.current = Date.now()
      tickRef.current = window.setInterval(() => {
        const cur = Date.now() - startMsRef.current + accumulatedMsRef.current
        setDurationMs(cur)
      }, 200)
      setState('recording')
    }
  }, [])

  // Stop : on finalise le Blob et on retourne la version assemblée.
  const stop = useCallback(async (): Promise<Blob | null> => {
    const rec = recorderRef.current
    if (!rec) return null
    if (state === 'recording' || state === 'paused') {
      // Anti-clic accidentel
      const total = (state === 'paused'
        ? accumulatedMsRef.current
        : accumulatedMsRef.current + (Date.now() - startMsRef.current))
      if (total < minDurationMs) {
        // On stoppe quand même pour libérer le micro, mais on retourne null
        try { rec.stop() } catch { /**/ }
        cleanup()
        setState('idle')
        setPermissionError(`L'enregistrement doit durer au moins ${Math.ceil(minDurationMs / 1000)} sec.`)
        return null
      }
    }
    return new Promise<Blob | null>((resolve) => {
      const finalize = () => {
        try {
          const type = mimeType || rec.mimeType || 'audio/webm'
          const blob = new Blob(chunksRef.current, { type })
          setLastBlob(blob)
          setState('stopped')
          cleanup()
          resolve(blob)
        } catch (err) {
          cleanup()
          setState('error')
          resolve(null)
        }
      }
      rec.onstop = finalize
      try {
        if (rec.state !== 'inactive') {
          rec.stop()
        } else {
          finalize()
        }
      } catch {
        finalize()
      }
    })
  }, [state, mimeType, cleanup, minDurationMs])

  // Garde-fou onbeforeunload — empêche fermeture si recording en cours
  useEffect(() => {
    if (!preventUnload) return
    const onBefore = (e: BeforeUnloadEvent) => {
      if (state === 'recording' || state === 'paused') {
        e.preventDefault()
        e.returnValue = ''
        return ''
      }
    }
    window.addEventListener('beforeunload', onBefore)
    return () => window.removeEventListener('beforeunload', onBefore)
  }, [preventUnload, state])

  // Cleanup à l'unmount
  useEffect(() => () => cleanup(), [cleanup])

  return {
    state, durationMs, audioLevel, permissionError,
    start, pause, resume, stop, reset, lastBlob, mimeType,
  }
}
